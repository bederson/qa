#!/usr/bin/env python
#
# Copyright 2013 Ben Bederson - http://www.cs.umd.edu/~bederson
# Anne Rose - http://www.cs.umd.edu/hcil/members/arose
# University of Maryland
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import constants
import helpers
import random
from google.appengine.api import rdbms
from google.appengine.api import users

class DatabaseConnection():
    conn = None
    cursor = None
    def connect(self):
        # check if already connected
        if self.conn:
            self.disconnect()
            
        # check if running locally
        # if so, connect to local MySQL database
        # only import MySQLdb when running locally since it is not available on GAE
        if constants.USE_LOCAL_DATABASE_WHEN_RUNNING_LOCALLY and helpers.isRunningLocally():
            import MySQLdb
            self.conn = MySQLdb.connect("localhost", constants.LOCAL_DB_USER, constants.LOCAL_DB_PWD, constants.DATABASE_NAME)
            self.cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
        
        # otherwise, connect to Google Cloud SQL
        # BEHAVIOR: connects as MySQL root
        # TODO: create database user to use instead of root
        else:
            self.conn = rdbms.connect(constants.CLOUDSQL_INSTANCE, constants.DATABASE_NAME)
            self.cursor = self.conn.cursor(use_dict_cursor=True)
            
    def disconnect(self):
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        
        if self.conn:
            self.conn.close()
            self.conn = None

class DBObject(object):
    table = None
    fields = {}

    @classmethod
    def tableField(cls, field):
        return cls.table + "." + field if cls.table else None
        
    # TODO: is it possible to make class property instead so it can be called like this: Question.fieldsSql?
    @classmethod
    def fieldsSql(cls):
        tableFields = []
        for field in cls.fields:
            tableField = cls.tableField(field)
            # CHECK: may not need to explicitly name field with "as"
            tableFields.append(tableField + " as '" + tableField + "'" if tableField else field)
        return ",".join(tableFields) if len(tableFields)>0 else ""
        
    @staticmethod
    def extractField(tableField=""):    
        tokens = tableField.split(".")            
        table = tokens[0] if len(tokens) == 2 else None
        field = tokens[1] if len(tokens) == 2 else (tokens[0] if len(tokens)==1 else None) 
        return table, field
    
    @classmethod
    def createFromData(cls, data=None):
    # creates an object from the given data
        obj = None
        if data:
            obj = globals()[cls.__name__]()
            for property in data:
                table, field = cls.extractField(property)
                if (not table or not cls.table or table==cls.table) and hasattr(obj, field):
                    setattr(obj, field, data[property])
        return obj
    
    def update(self, dbConnection=None, properties={}, keys=["id"], commit=True):
    # update the values of the specified properties in both memory and the database
    # assumes that property names and database field names are the same
        updateProperties = []
        updateValues = ()
        keyProperties = []
        keyValues = ()
        
        for property in properties:
            value = properties[property]
            setattr(self, property, value)
            
            if property in keys:
                # collect key properties
                keyProperties.append(property+"=%s")
                keyValues += (value,)
            else:
                # collect properties to be updated
                updateProperties.append(property+"=%s")
                updateValues += (value,)

        if len(keyProperties) != len(keys):
            helpers.log("WARNING: key values not included in properties: {0}".format(keys))
            return
        
        if dbConnection and self.table and len(updateProperties) > 0 and id:
            sql = "update {0} set {1} where {2}".format(self.table, ",".join(updateProperties), " and ".join(keyProperties))
            dbConnection.cursor.execute(sql, updateValues + keyValues)
            if commit:
                dbConnection.conn.commit()
  
    def toDict(self):
        objDict = {}
        for field in self.fields:
            objDict[field] = getattr(self, field)
        return objDict
           
class Question(DBObject):
    id = None
    title = None
    question = None
    nickname_authentication = False
    user_id = None
    authenticated_user_id = None # stored in users table
    phase = 0
    cascade_step = 0
    cascade_k = 5
    cascade_m = 32
    cascade_t = 8
    table = "questions"
    fields = { "id", "title", "question", "nickname_authentication", "user_id", "phase", "cascade_step", "cascade_k", "cascade_m", "cascade_t" }    
        
    @staticmethod
    def create(dbConnection, author, title, questionText, nicknameAuthentication=False):
        # create unique 5 digit id
        # TODO: need better way to generate unique question ids
        idCreated = False
        while not idCreated:
            questionId = str(random.randint(10000, 99999))
            question = Question.getById(dbConnection, questionId)
            if not question:
                idCreated = True
                        
        question = Question()
        question.id = questionId
        question.title = title
        question.question = questionText
        question.nickname_authentication = nicknameAuthentication
        question.user_id = author.id
            
        if dbConnection:
            sql = "insert into questions (id, title, question, nickname_authentication, user_id) values (%s, %s, %s, %s, %s)"
            dbConnection.cursor.execute(sql, (question.id, question.title, question.question, question.nickname_authentication, question.user_id))
            dbConnection.conn.commit()
            
        return question

    @classmethod
    def createFromData(cls, data=None):
        question = super(Question, cls).createFromData(data)
        if question:
            authenticatedUserIdField = "authenticated_user_id" if "authenticated_user_id" in data else Person.tableField("authenticated_user_id") if Person.tableField("authenticated_user_id") in data else None
            if authenticatedUserIdField:
                question.authenticated_user_id = data[authenticatedUserIdField]
            else:
                helpers.log("WARNING: authenticated_user_id not included in question data")
        return question

    def setPhase(self, dbConnection, phase):
        if self.phase != phase:
            self.update(dbConnection, { "phase" : phase, "id" : self.id })
            # BEHAVIOR: Any existing cascade data is deleted when cascade disabled and then re-enabled         
            if phase == constants.PHASE_CASCADE:
                self.deleteCascade(dbConnection)
                self.initCascadeNextStep(dbConnection)

    def initCascadeNextStep(self, dbConnection):
        self.update(dbConnection, { "cascade_step" : self.cascade_step+1, "id" : self.id })            
        if CASCADE_CLASSES[self.cascade_step-1]:
            CASCADE_CLASSES[self.cascade_step-1].initStep(dbConnection, self)
        else:
            helpers.log("INITSTEP FOR STEP {0} NOT IMPLEMENTED YET".format(self.cascade_step))

    def getCascadeJob(self, dbConnection, person):
        job = None
        if CASCADE_CLASSES[self.cascade_step-1]:
            job = CASCADE_CLASSES[self.cascade_step-1].getJob(dbConnection, self, person) 
        else:
            helpers.log("GETJOB FOR STEP {0} NOT IMPLEMENTED YET".format(self.cascade_step))
        return job, self.cascade_step
        
    def saveCascadeJob(self, dbConnection, step, job=[]):
        stepComplete = False
        if CASCADE_CLASSES[self.cascade_step-1]:
            stepComplete = CASCADE_CLASSES[self.cascade_step-1].saveJob(dbConnection, self, job)
        else:
            helpers.log("SAVEJOB FOR STEP {0} NOT IMPLEMENTED YET".format(self.cascade_step))
        return stepComplete
        
    def delete(self, dbConnection):
        dbConnection.cursor.execute("delete from questions where id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_ideas where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete user_clients from users,user_clients where users.id=user_clients.user_id and question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from users where question_id={0}".format(self.id))
        self.deleteCascade(dbConnection, False)
        dbConnection.conn.commit()
        self = Question()
        return self
    
    def deleteCascade(self, dbConnection, commit=True):
        self.update(dbConnection, { "cascade_step" : 0, "id" : self.id })
        dbConnection.cursor.execute("delete from cascade_suggested_categories where question_id={0}".format(self.id))
        helpers.log("REMEMBER TO DELETE OTHER CASCADE DATA")
        if commit:
            dbConnection.conn.commit()
        
    def isAuthor(self):
        # BEHAVIOR: check if currently authenticated user is the question author
        # currently only authenticated users can create questions
        user = users.get_current_user()
        return user and self.authenticated_user_id and user.user_id()==self.authenticated_user_id
                
    @staticmethod
    def getById(dbConnection, questionId):
        sql = "select {0}, users.authenticated_user_id from questions,users where questions.user_id=users.id and questions.id=%s".format(Question.fieldsSql())
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return Question.createFromData(row)

    @staticmethod                
    def getByUser(dbConnection, asDict=False):
        questions = []
        user = users.get_current_user()
        if user:
            sql = "select {0}, users.authenticated_user_id from questions,users where questions.user_id=users.id and authenticated_user_id=%s".format(Question.fieldsSql())
            dbConnection.cursor.execute(sql, (user.user_id()))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                question = Question.createFromData(row)
                if asDict:
                    question = question.toDict()
                questions.append(question)
        return questions
         
    @staticmethod
    def getStats(dbConnection, questionId):
        stats = {
            "question_id" : questionId,
            "num_ideas" : Idea.getCountForQuestion(dbConnection, questionId),
            "num_users" : Person.getCountForQuestion(dbConnection, questionId)
        }
        return stats

class Person(DBObject):               
    id = None
    authenticated_user_id = None
    authenticated_nickname = None
    nickname = None
    question_id = None
    latest_login_timestamp = None
    latest_logout_timestamp = None
    is_logged_in = False # not stored in db
    table = "users"
    fields = { "id", "authenticated_user_id", "authenticated_nickname", "nickname", "question_id", "latest_login_timestamp", "latest_logout_timestamp" }    

    @staticmethod
    def create(dbConnection, question=None, nickname=None):
        user = users.get_current_user()
        authenticatedUserId = user.user_id() if user else None
        authenticatedNickname = user.nickname() if user else None

        # Person must be either an authenticated Google user
        # or login with a nickname (if the question allows)
        if not authenticatedUserId and not nickname:
            return None
        
        person = Person()
        person.authenticated_user_id = authenticatedUserId
        person.authenticated_nickname = authenticatedNickname
        person.nickname = nickname if nickname else (Person.cleanNickname(user.nickname()) if user else None)
        person.question_id = question.id if question else None
          
        if dbConnection:
            sql = "insert into users (authenticated_user_id, authenticated_nickname, nickname, question_id, latest_login_timestamp, latest_logout_timestamp) values (%s, %s, %s, %s, now(), null)"
            dbConnection.cursor.execute(sql, (person.authenticated_user_id, person.authenticated_nickname, person.nickname, person.question_id))
            person.id = dbConnection.cursor.lastrowid
            dbConnection.conn.commit()
            person.is_logged_in=True          
    
        return person
    
    @classmethod
    def createFromData(cls, data):
        person = super(Person, cls).createFromData(data)
        if person:
            person.is_logged_in = person.latest_login_timestamp is not None and person.latest_logout_timestamp is None
        return person
              
    def login(self, dbConnection, commit=True):
        if not self.is_logged_in:
            sql = "update users set latest_login_timestamp=now(), latest_logout_timestamp=null where id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            dbConnection.conn.commit()
            self.is_logged_in = True 
            
    def logout(self, dbConnection, commit=True):
        if self.is_logged_in:
            # if a Google authenticated user is logging out, modify all records associated with this user
            if self.authenticated_user_id:
                sql = "update users set latest_logout_timestamp=now() where authenticated_user_id=%s"
                dbConnection.cursor.execute(sql, (self.authenticated_user_id))
                sql = "delete from user_clients using user_clients, users where user_clients.user_id=users.id and authenticated_user_id=%s"
                dbConnection.cursor.execute(sql, (self.authenticated_user_id))
            # otherwise, logout this specific user instance
            else:
                sql = "update users set latest_logout_timestamp=now() where id=%s"
                dbConnection.cursor.execute(sql, (self.id))
                sql = "delete from user_clients where user_id=%s"
                dbConnection.cursor.execute(sql, (self.id))
            if commit:
                dbConnection.conn.commit()
            self.is_logged_in = False
        
    def addClient(self, dbConnection, clientId, commit=True):   
        sql = "insert into user_clients (user_id, client_id) values(%s, %s)"
        dbConnection.cursor.execute(sql, (self.id, clientId))
        if commit:
            dbConnection.conn.commit()
     
    def removeClient(self, dbConnection, clientId, returnNumClients=False, commit=True):
        sql = "delete from user_clients where client_id=%s"
        dbConnection.cursor.execute(sql, (clientId))
        
        numClients = 0
        if returnNumClients:
            sql = "select count(*) as ct from user_clients where user_id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            numClients = row["ct"] if row else 0
        
        if commit:
            dbConnection.conn.commit()
            
        return numClients
            
    @staticmethod
    def getPerson(dbConnection, question=None, nickname=None):
        person = None
        user = users.get_current_user()

        # if question allows nickname authentication and nickname given, check for user
        # question author does not have to login with nickname if already authenticated
        if question and question.nickname_authentication and nickname and not question.isAuthor():
            sql = "select {0} from users where question_id=%s and nickname=%s".format(Person.fieldsSql())
            dbConnection.cursor.execute(sql, (question.id, nickname))
            row = dbConnection.cursor.fetchone()
            person = Person.createFromData(row)
                    
        # if authenticated user logged in, check for user     
        if user:
            sql = "select {0} from users where authenticated_user_id=%s".format(Person.fieldsSql())
            sqlValues = (user.user_id())
            if question:
                sql += " and question_id=%s"
                # TODO: compile error when trying to add item to sqlValues; must have syntax wrong
                sqlValues = (user.user_id(), question.id)

            dbConnection.cursor.execute(sql, sqlValues)
            row = dbConnection.cursor.fetchone()
            person = Person.createFromData(row)

            # if user not found, check if question author is logging into the 
            # question for the first time (i.e., entering ideas, helping categorize, etc.)
            # and if so, create user            
            if not person and question and question.isAuthor:
                person = Person.create(dbConnection, question=question)
                
        return person
                                                                          
    @staticmethod
    def doesNicknameExist(dbConnection, questionId, nickname):
        sql = "select {0} from users where question_id=%s and nickname=%s".format(Person.fieldsSql())
        dbConnection.cursor.execute(sql, (questionId, nickname))
        row = dbConnection.cursor.fetchone()
        return row is not None
    
    @staticmethod
    def cleanNickname(nickname=None):
        cleanedNickname = nickname
        if nickname:
            cleanedNickname = nickname[:nickname.index("@")] if nickname.count("@") > 0 else nickname
        return cleanedNickname
        
    @staticmethod
    def isAdmin():
        return users.is_current_user_admin()
    
    @staticmethod
    def getById(dbConnection, userId):
        person = None
        if userId:
            sql = "select {0} from users where id=%s".format(Person.fieldsSql())
            dbConnection.cursor.execute(sql, (userId))
            row = dbConnection.cursor.fetchone()
            person = Person.createFromData(row)
        return person
        
    @staticmethod
    def getCountForQuestion(dbConnection, questionId):
        sql = "select count(*) as ct from users where question_id=%s"
        #sql = "select count(*) as ct from users where question_id=%s and latest_login_timestamp is not null and latest_logout_timestamp is null"
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return row["ct"] if row else 0
        
    def toDict(self):
        return {
            "id": self.id,
            "nickname": self.nickname
        } 
     
    def equals(self, person):        
        return self.id == person.id    
 
class Idea(DBObject):
    id = None
    question_id = None
    user_id = None
    idea = None
    table = "question_ideas"
    fields = { "id", "question_id", "user_id", "idea" }
        
    @staticmethod
    def create(dbConnection, questionId, userId, ideaText):
        idea = Idea()
        idea.question_id = questionId
        idea.user_id = userId
        idea.idea = ideaText
        
        if dbConnection:
            sql = "insert into question_ideas (question_id, user_id, idea) values (%s, %s, %s)"
            dbConnection.cursor.execute(sql, (idea.question_id, idea.user_id, idea.idea))
            idea.id = dbConnection.cursor.lastrowid
            dbConnection.conn.commit()

        return idea
       
    @staticmethod
    def getById(dbConnection, ideaId):
        sql = "select {0} from question_ideas where id=%s".format(Idea.fieldsSql())
        dbConnection.cursor.execute(sql, (ideaId))
        row = dbConnection.cursor.fetchone()
        return Idea.createFromData(row)
        
    @staticmethod
    def getByQuestion(dbConnection, question, asDict=False):
        ideas = []
        if question:
            sql = "select {0},{1} from question_ideas,users where question_ideas.user_id=users.id and question_ideas.question_id=%s order by created_on desc".format(Idea.fieldsSql(), Person.fieldsSql())
            dbConnection.cursor.execute(sql, (question.id))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                idea = Idea.createFromData(row)
                if asDict:
                    # include author info with idea
                    author = {
                        "authenticated_nickname" : row[Person.tableField("authenticated_nickname")] if not question.nickname_authentication else None,
                        "nickname" : row[Person.tableField("nickname")]
                    }
                    idea = idea.toDict(author=author, admin=Person.isAdmin() or question.isAuthor())
                ideas.append(idea)
        return ideas
    
    @staticmethod
    def getCountForQuestion(dbConnection, questionId):
        sql = "select count(*) as ct from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return row["ct"] if row else 0
          
    def toDict(self, author=None, admin=False):
        objDict = super(Idea, self).toDict()                 
        if author:
            nickname = author["nickname"] if "nickname" in author else None
            authenticatedNickname = author["authenticated_nickname"] if "authenticated_nickname" in author else None
            objDict["author"] = nickname if nickname else "Anonymous"
            # only pass authenticated nickname to admin users
            if admin and authenticatedNickname:
                hiddenIdentity = nickname and Person.cleanNickname(authenticatedNickname) != nickname
                if hiddenIdentity:
                    objDict["author_identity"] = authenticatedNickname
                            
        return objDict
                 
# ###################
# ##### CASCADE #####
# ###################
# 
# # BEHAVIOR: cascade jobs created when phase enabled
# # BEHAVIOR: when cascade params are changed, cascade jobs are re-created
# # BEHAVIOR: user currently allowed to do as many jobs per step as they can
# # BEHAVIOR: step 1 - displays up to t ideas at a time
# # BEHAVIOR: step 1 - does not remove ideas authored by person
# # BEHAVIOR: step 1 - k jobs performed to create a category for an idea; should k categories be required for each idea? or ok to skip?
# # BEHAVIOR: step 2 - user can choose best category or select none of the above
# 
# # TODO/BUG: how to ensure updates available to all users in time; model blocking? transactions?
# # TODO: warn admin that any previous cascade data will be lost when jobs re-created
# # TODO: need to add timestamps to record how long each step takes
# # TODO: when step changes, need to notify waiting users
# # TODO: ask users to suggest category during idea creation
# # TODO: would it be better to create task and then keep track of k responses (instead of repeating task)
# # TODO: limit # of channels; do not reload page for new steps
# # TODO: step 1 - remove any ideas user has authored, skipped, or already created categories for
# # TODO: step 1 - need to release assignments after some period of inactivity
# # TODO: step 1 - need to better randomize ideas presented in jobs 
# # TODO: step 1 - should users be asked once more to create categories for any ideas with no categories
# # TODO: step 2 - what if only one category suggested - still vote?
# # TODO: step 2 - categories that only differ by case should be shown together
# # TODO: step 2 - user should only vote once per idea
# # TODO: step 2 - how should voting threshold be determined (based on k?)
# 

class CascadeSuggestedCategory(DBObject):
    id = None
    question_id = None
    idea_id = None
    idea = None # stored in question_ideas table
    suggested_category = None
    skipped = 0
    user_id = None
    table = "cascade_suggested_categories"
    fields = { "id", "question_id", "idea_id", "idea", "suggested_category", "skipped", "user_id" }
        
    @staticmethod
    def create(dbConnection, questionId, ideaId, commit=True):        
        task = CascadeSuggestedCategory()
        task.question_id = questionId
        task.idea_id = ideaId
          
        if dbConnection:
            sql = "insert into cascade_suggested_categories (question_id, idea_id) values (%s, %s)"
            dbConnection.cursor.execute(sql, (task.question_id, task.idea_id))
            if commit:
                dbConnection.conn.commit()
    
        return task
    
    @classmethod
    def createFromData(cls, data):
        task = super(CascadeSuggestedCategory, cls).createFromData(data)
        if task:
            ideaField = "idea" if "idea" in data else Idea.tableField("idea") if Idea.tableField("idea") in data else None
            if ideaField:
                task.idea = data[ideaField]
            else:
                helpers.log("WARNING: idea not included in task data")
        return task
    
    @staticmethod
    def initStep(dbConnection, question):
        sql = "select id from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            ideaId = row["id"]
            for i in range(question.cascade_k):
                CascadeSuggestedCategory.create(dbConnection, question.id, ideaId, False)
        dbConnection.conn.commit()

    @staticmethod
    def getJob(dbConnection, question, person):      
        job = []
        # check if job already assigned
        sql = "select cascade_suggested_categories.*,idea from cascade_suggested_categories,question_ideas where "
        sql += "cascade_suggested_categories.idea_id=question_ideas.id and "
        sql += "cascade_suggested_categories.question_id=%s and "
        sql += "cascade_suggested_categories.user_id=%s and "
        sql += "suggested_category is null and "
        sql += "skipped=0"
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeSuggestedCategory.createFromData(row)
            job.append(task)
             
        # if not, assign new tasks
        if len(job) == 0:
            sql = "select cascade_suggested_categories.*,idea from cascade_suggested_categories,question_ideas where "
            sql += "cascade_suggested_categories.idea_id=question_ideas.id "
            sql += "and cascade_suggested_categories.question_id=%s " 
            sql += "and cascade_suggested_categories.user_id is null "
            # TODO/TESTING: remove comment when done testing
            #sql += "and idea_id not in (select idea_id from cascade_suggested_categories where user_id=%s) "
            sql += "group by idea_id order by rand() limit {0}".format(question.cascade_k)
            # TODO/TESTING: remove comment when done testing
            #dbConnection.cursor.execute(sql, (question.id, person.id))
            dbConnection.cursor.execute(sql, (question.id,))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                task = CascadeSuggestedCategory.createFromData(row)
                task.assignTo(dbConnection, person, commit=False)
                job.append(task)
                
            if len(job) > 0:
                dbConnection.conn.commit()
        
        return job if len(job) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):
        sql = "update cascade_suggested_categories set user_id=%s where id=%s"
        dbConnection.cursor.execute(sql, (person.id, self.id))
        if commit:
            dbConnection.conn.commit()

    @staticmethod
    def saveJob(dbConnection, question, job):
        for task in job:
            taskId = task["id"]
            suggestedCategory = task["suggested_category"]
            # save suggested category
            if suggestedCategory != "":
                sql = "update cascade_suggested_categories set suggested_category=%s where id=%s"
                dbConnection.cursor.execute(sql, (suggestedCategory, taskId))
            # if skipped, mark it so not assigned in future
            else:
                sql = "update cascade_suggested_categories set skipped=1 where id=%s"
                dbConnection.cursor.execute(sql, (taskId))
        dbConnection.conn.commit()
        
        stepComplete = CascadeSuggestedCategory.isStepComplete(dbConnection, question)
        if stepComplete:
            question.initCascadeNextStep(dbConnection)
            
        return stepComplete
        
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_suggested_categories where question_id=%s and suggested_category is null and skipped=0"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0
              
class CascadeBestCategory(DBObject):
    id = None
    question_id = None
    idea_id = None
    idea = None # stored in question_ideas table
    suggested_categories = [] # stored in cascade_suggested_categories table
    best_category = None
    none_of_the_above = 0
    user_id = None
    table = "cascade_best_categories"
    fields = { "id", "question_id", "idea_id", "idea", "suggested_categories", "best_category", "none_of_the_above", "user_id" }
        
    @staticmethod
    def create(dbConnection, questionId, ideaId, commit=True):        
        task = CascadeBestCategory()
        task.question_id = questionId
        task.idea_id = ideaId
          
        if dbConnection:
            sql = "insert into cascade_best_categories (question_id, idea_id) values (%s, %s)"
            dbConnection.cursor.execute(sql, (task.question_id, task.idea_id))
            if commit:
                dbConnection.conn.commit()
    
        return task
    
    @classmethod
    def createFromData(cls, data):
        task = super(CascadeBestCategory, cls).createFromData(data)
        if task:
            ideaField = "idea" if "idea" in data else Idea.tableField("idea") if Idea.tableField("idea") in data else None
            if ideaField:
                task.idea = data[ideaField]
            else:
                helpers.log("WARNING: idea not included in task data")
            # TODO: set suggested_categories
        return task
    
    @staticmethod
    def initStep(dbConnection, question):
        # TODO: same as for step 1 except class name
        sql = "select id from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            ideaId = row["id"]
            for i in range(question.cascade_k):
                CascadeBestCategory.create(dbConnection, question.id, ideaId, False)
        dbConnection.conn.commit()

    @staticmethod
    def getJob(dbConnection, question, person):      
        job = []
        # check if job already assigned
        sql = "select cascade_best_categories.*,idea from cascade_best_categories,question_ideas where "
        sql += "cascade_best_categories.idea_id=question_ideas.id and "
        sql += "cascade_best_categories.question_id=%s and "
        sql += "cascade_best_categories.user_id=%s and "
        sql += "best_category is null and "
        sql += "none_of_the_above=0"
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeSuggestedCategory.createFromData(row)
            job.append(task)
             
        # if not, assign new tasks
        if len(job) == 0:
            sql = "select cascade_best_categories.*,idea from cascade_best_categories,question_ideas where "
            sql += "cascade_best_categories.idea_id=question_ideas.id "
            sql += "and cascade_best_categories.question_id=%s " 
            sql += "and cascade_best_categories.user_id is null "
            # TODO/TESTING: remove comment when done testing
            #sql += "and idea_id not in (select idea_id from cascade_best_categories where user_id=%s) "
            sql += "group by idea_id order by rand() limit 1"
            # TODO/TESTING: remove comment when done testing
            #dbConnection.cursor.execute(sql, (question.id, person.id))
            dbConnection.cursor.execute(sql, (question.id,))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                task = CascadeBestCategory.createFromData(row)
                task.assignTo(dbConnection, person, commit=False)
                job.append(task)
                
            if len(job) > 0:
                dbConnection.conn.commit()
        
        return job if len(job) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):
        # TODO: same as step 1 except for table name
        sql = "update cascade_best_categories set user_id=%s where id=%s"
        dbConnection.cursor.execute(sql, (person.id, self.id))
        if commit:
            dbConnection.conn.commit()

    @staticmethod
    def saveJob(dbConnection, question, job):
        for task in job:
            taskId = task["id"]
            bestCategory = task["best_category"]
            # save best category
            if bestCategory != "":
                sql = "update cascade_best_categories set best_category=%s where id=%s"
                dbConnection.cursor.execute(sql, (bestCategory, taskId))
            # if skipped, mark it so not assigned in future
            else:
                sql = "update cascade_best_categories set none_of_the_above=1 where id=%s"
                dbConnection.cursor.execute(sql, (taskId))
        dbConnection.conn.commit()
        
        stepComplete = CascadeBestCategory.isStepComplete(dbConnection, question)
        if stepComplete:
            question.initCascadeNextStep(dbConnection)
            
        return stepComplete
        
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_best_categories where question_id=%s and best_category is null"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0
    
CASCADE_CLASSES = [ CascadeSuggestedCategory, CascadeBestCategory, None, None, None ]
                                                     
#     def createJobsForStep2(self):
#         suggestedCategories = {}
#         step1 = CascadeJob.all().filter("question =", self.question).filter("step =", 1)
#         for job in step1:
#             i = 0
#             for idea in job.task.ideas:
#                 ideaId = idea.key().id()
#                 category = job.task.categories[i].strip()
#                 if category != "":
#                     if ideaId not in suggestedCategories:
#                         suggestedCategories[ideaId] = { "idea": idea, "categories": [] }
#                          
#                     if category not in suggestedCategories[ideaId]["categories"]:
#                         suggestedCategories[ideaId]["categories"].append(category)
#                 i += 1
#                  
#         # TODO: improve by saving only 1 version of task in datastore, but save result in job?
#         for i in range(self.k):
#             for ideaId in suggestedCategories:
#                 task = CascadeSelectBestTask()
#                 task.question = self.question
#                 task.idea = suggestedCategories[ideaId]["idea"]
#                 task.categories = suggestedCategories[ideaId]["categories"]
#                 if i==0: task.categories.append(NONE_OF_THE_ABOVE)
#                 task.put()
#                      
#                 job = CascadeJob()
#                 job.question = self.question
#                 job.cascade = self
#                 job.step = 2
#                 job.task = task
#                 job.worker = None
#                 job.put()
#        
#     def createJobsForStep3(self):
#         helpers.log("createJobsForStep3")
#         groupedVotes = {}
#         step2 = CascadeJob.all().filter("question =", self.question).filter("step =", 2)
#         for job in step2:
#             idea = job.task.idea
#             ideaId = idea.key().id()
#             category = job.task.categories[job.task.bestCategoryIndex] if job.task.bestCategoryIndex is not None else None
#             if category:
#                 if ideaId not in groupedVotes:                    
#                     groupedVotes[ideaId] = { "idea": idea, "votes": {} }
#                       
#                 if category not in groupedVotes[ideaId]["votes"]:
#                     groupedVotes[ideaId]["votes"][category] = 0
#                 groupedVotes[ideaId]["votes"][category] += 1
#           
#         # TODO: how should the voting threshold be calculated; k=5 and voting threshold=2 by default
#         votingThreshold = DEFAULT_VOTING_THRESHOLD if self.k > 3 else 1
#  
#         bestCategories = []
#         for ideaId in groupedVotes:
#             for category in groupedVotes[ideaId]["votes"]:
#                 numVotesForCategory = groupedVotes[ideaId]["votes"][category]
#                 if numVotesForCategory >= votingThreshold:
#                     if category not in bestCategories:
#                         bestCategories.append(category)
#  
#         # TODO: currently using t for group size; should be separate variable?
#         task_group = { "idea_keys": [], "categories": [] }
#         idea_keys = Idea.all(keys_only=True).filter("question = ", self.question).order("rand")
#         for i in range(self.k):
#             for idea_key in idea_keys:
#                 for category in bestCategories:
#                     if len(task_group["idea_keys"]) == self.t:
#                         task = CascadeCategoryFitTask()
#                         task.question = self.question
#                         task.idea_keys = task_group["idea_keys"]
#                         task.categories = task_group["categories"]
#                         task.put()
#                          
#                         job = CascadeJob()
#                         job.question = self.question
#                         job.cascade = self
#                         job.step = 3
#                         job.task = task
#                         job.worker = None
#                         job.put()
#                          
#                         task_group = { "idea_keys": [], "categories": [] }
#  
#                     task_group["idea_keys"].append(idea_key)
#                     task_group["categories"].append(category)
#      
#         # TODO: move to function?
#         if len(task_group["idea_keys"]) > 0:
#             task = CascadeSuggestCategoryTask()
#             task.question = self.question
#             task.idea_keys = task_group["idea_keys"]
#             task.categories = task_group["categories"]
#             task.put()
#                      
#             job = CascadeJob()
#             job.question = self.question
#             job.cascade = self
#             job.step = 3
#             job.task = task
#             job.worker = None
#             job.put()
#     
#     def deleteJobs(self, dbConnection):
#         xx anything else to delete out of memory?
#         dbConnection.cursor.execute("delete from cascade_jobs where question_id={0}".format(self.question.id))
#         dbConnection.cursor.execute("delete from cascade_xx where question_id={0}".format(self.question.id))
#         dbConnection.conn.commit()
#         helpers.log("WARNING: Remember to delete cascade jobs for steps 3b-5")
#                   
# class CascadeTask(db.Model): 
#     question = db.ReferenceProperty(Question)
#     
#     def toDict(self):
#         return {
#             "question_id" : self.question.id
#         }
#      
# class CascadeSuggestCategoryTask(CascadeTask):
#     idea_keys = db.ListProperty(db.Key)
#     categories = db.StringListProperty(default=[])
#      
#     @property
#     def ideas(self):
#         return db.get(self.idea_keys)
#      
#     def completed(self, data):
#         self.categories = data["categories"]
#         self.put()
#          
#     def toDict(self): 
#         dict = CascadeTask.toDict(self)
#         dict["ideas"] = [ idea.toDict(xx) for idea in self.ideas ]
#         dict["categories"] = self.categories
#         return dict
#          
# class CascadeSelectBestTask(CascadeTask):
#     idea = db.ReferenceProperty(Idea)
#     categories = db.StringListProperty(default=[])
#     bestCategoryIndex = db.IntegerProperty(default=None)
#      
#     def completed(self, data):
#         bestCategoryIndex = int(data["best_category_index"])
#         if bestCategoryIndex != -1 and self.categories[bestCategoryIndex] != NONE_OF_THE_ABOVE:
#             self.bestCategoryIndex = bestCategoryIndex
#             self.put()
#          
#     def toDict(self): 
#         dict = CascadeTask.toDict(self)
#         dict["idea"] = self.idea.toDict(xx)
#         dict["categories"] = self.categories
#         dict["best_category_index"] = self.bestCategoryIndex
#         return dict
#  
# # TODO: improve by separating out class that just contains single idea, category, and fit vote; same for CascadeSuggestCategoryTask
# class CascadeCategoryFitTask(CascadeTask):
#     idea_keys = db.ListProperty(db.Key)
#     categories = db.StringListProperty(default=[])
#     categoryFits = db.ListProperty(bool)
#      
#     @property
#     def ideas(self):
#         return db.get(self.idea_keys)
#      
#     def completed(self, data):
#         self.categoryFits = data["category_fits"]
#         self.put()
#          
#     def toDict(self): 
#         dict = CascadeTask.toDict(self)
#         dict["ideas"] = [ idea.toDict(xx) for idea in self.ideas ]
#         dict["categories"] = self.categories
#         dict["category_fits"] = self.categoryFits
#         return dict
#              
# class CascadeJob(db.Model):
#     question = db.ReferenceProperty(Question)
#     cascade = db.ReferenceProperty(Cascade)
#     step = db.IntegerProperty() # step for this job, current step in progress stored in Cascade class
#     task = db.ReferenceProperty(CascadeTask)
#     worker = db.ReferenceProperty(Person)
#     status = db.IntegerProperty(default=0)
#  
#     @staticmethod
#     def getJob(question, jobStep, worker):
#  
#         # TODO/FIX: Decide what needs to be stored in datastore vs. memcache only      
#         workerKey = str(worker.key().id())  
#                          
#         # check if jobStep stored in memcache
#         client = memcache.Client()
#         step = client.gets(question.id + "_step")
#         assert step is not None, "Step not initialized"
#         if step != jobStep:
#             helpers.log("WARNING: Jobs for step {0} not stored in memcache".format(jobStep))
#             return { "job": None, "newStep": False }
#  
#         # check if worker is already assigned a job
#         # TODO: ok to get all assigned jobs? or better to check only for this worker?
#         assignedJobsKey = question.id + "_assigned_jobs"
#         assignedJobs = client.gets(assignedJobsKey)
#         assert assignedJobs is not None, "Assigned jobs not initialized"
#         jobId = assignedJobs[workerKey] if workerKey in assignedJobs else None
#  
#         # if not, get new assignment
#         newStep = False
#         if not jobId:  
#             # TODO: need to limit to MAX_TRIES
#             availableJobsKey = question.id + "_available_jobs"
#             helpers.log("availableJobsKey={0}".format(availableJobsKey))
#             while True:
#                 availableJobs = client.gets(availableJobsKey)
#                 assert availableJobs is not None, "Available jobs not initialized"
#                 newJobId = availableJobs.pop()
#                 if client.cas(availableJobsKey, availableJobs):
#                     jobId = newJobId
#                     while True:
#                         # TODO: can retrieved value above be reused?
#                         # TODO: need to limit to MAX_TRIES
#                         assignedJobs = client.gets(assignedJobsKey)
#                         assignedJobs[workerKey] = jobId
#                         if client.cas(assignedJobsKey, assignedJobs):
#                             # TODO: get job and pass to below?
#                             helpers.log("assigned job {0} to worker {1}".format(jobId, workerKey))
#                             job = CascadeJob.get_by_id(jobId)
#                             job.worker = worker
#                             job.put()
#                             break
#                     break
#                          
#             # check if all jobs completed for this step, and if so, advance to next step
#             # TODO/FIX: need to store job status in memcache
#             # QUESTION: is count() strong consistency?
#             if not jobId and jobStep < 5:
#                 numJobsRemaining = CascadeJob.all().filter("question =", question).filter("step =", step).filter("status =", 0).count()
#                 isStepComplete = numJobsRemaining == 0
#                 if isStepComplete:
#                     cascade = Cascade.getCascadeForQuestion(question)
#                     # TODO: combine with memcache update
#                     cascade.step += 1
#                     cascade.put()
#                      
#                     # TODO: remember to advance step in memcache in init?                                            
#                     # create jobs for this step
#                     cascade.init(question, jobStep+1)
#  
#                     # TODO: need to notify waiting users that new jobs available
#                                          
#                     newStep = True
#          
#         return { "job": CascadeJob.get_by_id(jobId) if jobId else None, "new_step": newStep }
#  
# #         newStep = False
# #                         
# #         # check if job already assigned
# #         job = CascadeJob.all().filter("question =", question).filter("step =", step).filter("worker =", worker).filter("status =", 0).get()
# # 
# #         # if not, get new assignment
# #         if not job:  
# #             job = CascadeJob.all().filter("question =", question).filter("step =", step).filter("worker =", None).get()
# #             if job:
# #                 job.worker = worker
# #                 jobKey = job.put()
# #                 
# #                 # TODO/HACK - need to guarantee datastore updated and searchable before next job requested
# #                 job = CascadeJob.get_by_id(jobKey.id()) 
# #             
# #             # check if all jobs completed for this step, and if so, advance to next step
# #             if not job and step < 5:
# #                 numJobsRemaining = CascadeJob.all().filter("question =", question).filter("step =", step).filter("status =", 0).count()
# #                 isStepComplete = numJobsRemaining == 0
# #                 if isStepComplete:
# #                     cascade = Cascade.getCascadeForQuestion(question)
# #                     cascade.step += 1
# #                     cascade.put()
# #                                             
# #                     # TODO: check if jobs created and searchable before getJob called
# #                     # TODO: need to notify waiting users that new jobs available
# #                     # create jobs for this step
# #                     cascade.init(question, step+1)
# #                     
# #                     job = CascadeJob.getJob(question, step+1, worker)
# #                     newStep = True
# #         
# #         return { "job": job, "new_step": newStep }
#  
#     def completed(self, data):
#         self.task.completed(data)
#         self.status = 1
#         key = self.put()
#                      
#         # TODO/HACK - seems to increase odds of updated values being in datastore before CascadeJob.getJob called
#         # otherwise, job only changing every other time submit pressed (at least on localhost)
#         job = CascadeJob.get_by_id(key.id())
#          
#     def toDict(self):
#         helpers.log("CascadeJob:toDict worker={0}".format(self.worker))
#         return {
#             "id" : self.key().id(),
#             "question_id": self.question.id,
#             "step": self.step,
#             "task": self.task.toDict(),    
#             "worker": Person.toDict(self.worker),
#             "status": self.status
#         }


