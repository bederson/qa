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
import math
import random
from google.appengine.api import rdbms
from google.appengine.api import users

class DatabaseConnection():
    def __init__(self):
        self.conn = None
        self.cursor = None
        
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
    def createFromData(cls, data):
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
    table = "questions"
    fields = { "id", "title", "question", "nickname_authentication", "user_id", "phase", "cascade_step", "cascade_iteration", "cascade_complete", "cascade_k", "cascade_k2", "cascade_m", "cascade_t" }    
        
    def __init__(self):
        self.id = None
        self.title = None
        self.question = None
        self.nickname_authentication = False
        self.user_id = None
        self.authenticated_user_id = None # stored in users table
        self.phase = 0
        self.cascade_step = 0
        self.cascade_iteration = 0
        self.cascade_complete = 0
        self.cascade_k = 5
        self.cascade_k2 = 2
        self.cascade_m = 32
        self.cascade_t = 8
        
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
            
        sql = "insert into questions (id, title, question, nickname_authentication, user_id) values (%s, %s, %s, %s, %s)"
        dbConnection.cursor.execute(sql, (question.id, question.title, question.question, question.nickname_authentication, question.user_id))
        dbConnection.conn.commit()
            
        return question

    @classmethod
    def createFromData(cls, data):
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
        if not self.cascade_complete:
            if self.cascade_step < len(CASCADE_CLASSES):
                nextStep = self.cascade_step + 1
                data = { "cascade_step" : nextStep, "id" : self.id }
                if self.cascade_step == 0:
                    data["cascade_iteration"] = 1
                self.update(dbConnection, data)            
                CASCADE_CLASSES[nextStep-1].initStep(dbConnection, self)
    
            # if on last step, check if cascade is complete, if not move to next iteration
            else:
                complete = self.checkIfCascadeComplete(dbConnection)
                if not complete:
                    nextStep = 1
                    nextIteration = self.cascade_iteration + 1
                    self.update(dbConnection, { "cascade_step" : nextStep, "cascade_iteration" : nextIteration, "id" : self.id })
                    CASCADE_CLASSES[nextStep-1].initStep(dbConnection, self)
        
    def getCascadeJob(self, dbConnection, person):
        job = None
        if CASCADE_CLASSES[self.cascade_step-1]:
            job = CASCADE_CLASSES[self.cascade_step-1].getJob(dbConnection, self, person) 
        return job
        
    def saveCascadeJob(self, dbConnection, job=[]):
        stepComplete = False
        if CASCADE_CLASSES[self.cascade_step-1]:
            stepComplete = CASCADE_CLASSES[self.cascade_step-1].saveJob(dbConnection, self, job)
        return stepComplete

    def checkIfCascadeComplete(self, dbConnection):
        if not self.cascade_complete:
            lastStepComplete = self.cascade_step == len(CASCADE_CLASSES) and CASCADE_CLASSES[self.cascade_step-1].isStepComplete(dbConnection, self)
            complete = lastStepComplete and self.cascade_iteration == constants.CASCADE_MAX_ITERATIONS
            if lastStepComplete and self.cascade_iteration < constants.CASCADE_MAX_ITERATIONS:
                sql = "select count(*) as ct from question_ideas left join question_categories on question_ideas.id=question_categories.idea_id where question_ideas.question_id=%s and category_id is null"
                dbConnection.cursor.execute(sql, (self.id))
                row = dbConnection.cursor.fetchone()
                complete = True if row["ct"] <= constants.CASCADE_MAX_UNCATEGORIZED else False 
            
            if complete:
                self.update(dbConnection, { "cascade_complete" : 1, "id" : self.id })
                                
        return self.cascade_complete
    
    def delete(self, dbConnection):
        dbConnection.cursor.execute("delete from questions where id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_ideas where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete user_clients from users,user_clients where users.id=user_clients.user_id and question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from users where question_id={0}".format(self.id))
        self.deleteCascade(dbConnection, commit=False)
        dbConnection.conn.commit()
        self = Question()
        return self
    
    def deleteCascade(self, dbConnection, commit=True):
        self.update(dbConnection, { "cascade_step" : 0, "cascade_iteration" : 0, "cascade_complete" : 0, "id" : self.id }, commit=False)
        dbConnection.cursor.execute("delete from cascade_suggested_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_best_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_fit_categories_phase1 where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_fit_categories_phase2 where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from categories where question_id={0}".format(self.id))
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
    table = "users"
    fields = { "id", "authenticated_user_id", "authenticated_nickname", "nickname", "question_id", "latest_login_timestamp", "latest_logout_timestamp" }    

    def __init__(self):
        self.id = None
        self.authenticated_user_id = None
        self.authenticated_nickname = None
        self.nickname = None
        self.question_id = None
        self.latest_login_timestamp = None
        self.latest_logout_timestamp = None
        self.is_logged_in = False # not stored in db
    
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
    table = "question_ideas"
    fields = { "id", "question_id", "user_id", "idea" }
        
    def __init__(self):
        self.id = None
        self.question_id = None
        self.user_id = None
        self.idea = None
    
    @staticmethod
    def create(dbConnection, question, userId, ideaText):
        idea = Idea()
        idea.question_id = question.id
        idea.user_id = userId
        idea.idea = ideaText
        
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
        
    # TODO: store in memcache and only retrieve from database if needed
    @staticmethod
    def getByCategories(dbConnection, question, asDict=False):
        ideaIds = []
        categorizedIdeas = []
        category = None
        categoryIdeas = []
        uncategorizedIdeas = []
        if question:
            # sorts categories alphabetically unless sortByFrequency is true
            # if sortByFrequency is true, return categories in order of largest to smallest
            # TODO: add option to GUI to specify sort type
            sortByFrequency = False
            sql = "select {0},{1},category,same_as from question_ideas ".format(Idea.fieldsSql(), Person.fieldsSql())
            sql += "left join question_categories on question_ideas.id=question_categories.idea_id "
            if sortByFrequency:
                sql += "left join (select id,category,same_as,count(*) as ct from categories,question_categories where categories.id=question_categories.category_id group by id) cat1 on question_categories.category_id=cat1.id "
            else:
                sql += "left join categories on question_categories.category_id=categories.id "
            sql += "left join users on question_ideas.user_id=users.id where "
            sql += "question_ideas.question_id=%s "
            sql += "order by ct desc,category,idea" if sortByFrequency else "order by category,idea"
            dbConnection.cursor.execute(sql, (question.id))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                ideaCategory = row["category"]
                ideaSameAs = row["same_as"]
                idea = Idea.createFromData(row)
                ideaId = idea.id
                if asDict:
                    # include author info with idea
                    author = {
                        "authenticated_nickname" : row[Person.tableField("authenticated_nickname")] if not question.nickname_authentication else None,
                        "nickname" : row[Person.tableField("nickname")]
                    }
                    idea = idea.toDict(author=author, admin=Person.isAdmin() or question.isAuthor())
                    
                if ideaCategory: 
                    if not category:
                        category = ideaCategory
                        sameAs = ideaSameAs
                                        
                    if category != ideaCategory:
                        if len(categoryIdeas) > 0:
                            categorizedIdeas.append({ "category" : category , "same_as" : sameAs, "ideas" : categoryIdeas })
                        category = ideaCategory
                        sameAs = ideaSameAs
                        categoryIdeas = []
                        
                    categoryIdeas.append(idea)
                    
                else:
                    uncategorizedIdeas.append(idea)
        
                ideaIds.append(ideaId)
                           
            if len(categoryIdeas) > 0:
                categorizedIdeas.append({ "category" : category, "same_as" : sameAs, "ideas" : categoryIdeas })
                
        return categorizedIdeas, uncategorizedIdeas, len(set(ideaIds))
    
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
                 
###################
##### CASCADE #####
###################
 
# BEHAVIOR: cascade jobs for step 1 are created when cascade is enabled, and for subsequent jobs whenever the previous job is completed
# BEHAVIOR: currently any existing cascade data is deleted if cascade is disabled and then re-enabled
# BEHAVIOR: users are restricted to unique tasks when running on GAE; >= k users required to complete cascade 
# BEHAVIOR: users can can do as many jobs as they can when running locally, but are restricted to unique tasks on GAE
# BEHAVIOR: introduced cascade_k2 to use for steps 3-6 (category fit tasks) since step 3/5 can be very expensive in terms of # of tasks
# BEHAVIOR: cascade recurses if # uncategorized items > CASCADE_MAX_UNCATEGORIZED but not for loose categories 
# BEHAVIOR: # iterations limited by CASCADE_MAX_ITERATIONS, regardless of how many items still uncategorized
# BEHAVIOR: categories with fewer than CASCADE_Q items removed
# BEHAVIOR: duplicate categories merged (the % of overlapping categories used to detect duplicates is defined by CASCADE_P)
# BEHAVIOR: nested categories not generated

class CascadeSuggestedCategory(DBObject):
    table = "cascade_suggested_categories"
    fields = { "id", "question_id", "idea_id", "idea", "suggested_category", "skipped", "cascade_iteration", "user_id" }
        
    def __init__(self):
        self.id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas table
        self.suggested_category = None
        self.skipped = 0
        self.cascade_iteration = 0
        self.user_id = None
        
    @staticmethod
    def create(dbConnection, question, ideaId, commit=True):        
        task = CascadeSuggestedCategory()
        task.question_id = question.id
        task.idea_id = ideaId
          
        sql = "insert into cascade_suggested_categories (question_id, idea_id, cascade_iteration) values (%s, %s, %s)"
        dbConnection.cursor.execute(sql, (task.question_id, task.idea_id, question.cascade_iteration))
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
        if question.cascade_iteration == 1:
            sql = "select id from question_ideas where question_id=%s order by rand() limit {0}".format(question.cascade_m)
        else:
            sql = "select id from question_ideas left join question_categories on question_ideas.id=question_categories.idea_id where question_ideas.question_id=%s and category_id is null order by rand()"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            ideaId = row["id"]
            for i in range(question.cascade_k):
                CascadeSuggestedCategory.create(dbConnection, question, ideaId, False)
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
        # do not check if user already performed task on idea when running locally
        if len(job) == 0:
            try:
                sql = "select cascade_suggested_categories.*,idea from cascade_suggested_categories,question_ideas where "
                sql += "cascade_suggested_categories.idea_id=question_ideas.id "
                sql += "and cascade_suggested_categories.question_id=%s " 
                sql += "and cascade_suggested_categories.user_id is null "
                sql += "and idea_id not in (select distinct idea_id from cascade_suggested_categories where question_id=%s and user_id=%s) " if not helpers.isRunningLocally() else ""
                sql += "group by idea_id order by rand() limit {0} ".format(question.cascade_t)
                sql += "for update"
    
                if helpers.isRunningLocally():
                    dbConnection.cursor.execute(sql, (question.id,))
                else:
                    dbConnection.cursor.execute(sql, (question.id, question.id, person.id))
    
                rows = dbConnection.cursor.fetchall()
                for row in rows:
                    task = CascadeSuggestedCategory.createFromData(row)
                    task.assignTo(dbConnection, person, commit=False)
                    job.append(task)
                    
                dbConnection.conn.commit()
            except:
                job = []
                dbConnection.rollback()
        
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
        
        stepComplete = CascadeSuggestedCategory.continueToNextStepIfComplete(dbConnection, question)
        return stepComplete
        
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_suggested_categories where question_id=%s and suggested_category is null and skipped=0"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0
   
    @staticmethod
    def continueToNextStepIfComplete(dbConnection, question):
        stepComplete = CascadeSuggestedCategory.isStepComplete(dbConnection, question)
        if stepComplete:
            question.initCascadeNextStep(dbConnection)
        return stepComplete
                       
class CascadeBestCategory(DBObject):
    table = "cascade_best_categories"
    fields = { "id", "question_id", "idea_id", "idea", "suggested_categories", "best_category", "none_of_the_above", "cascade_iteration", "user_id" }
    
    def __init__(self):
        self.id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas
        self.suggested_categories = [] # stored in cascade_suggested_categories
        self.best_category = None
        self.none_of_the_above = 0
        self.cascade_iteration = 0
        self.user_id = None
        
    @staticmethod
    def create(dbConnection, question, ideaId, commit=True):        
        task = CascadeBestCategory()
        task.question_id = question.id
        task.idea_id = ideaId
          
        sql = "insert into cascade_best_categories (question_id, idea_id, cascade_iteration) values (%s, %s, %s)"
        dbConnection.cursor.execute(sql, (task.question_id, task.idea_id, question.cascade_iteration))
        if commit:
            dbConnection.conn.commit()
    
        return task
        
    @classmethod
    def createFromData(cls, data, dbConnection=None):
        task = super(CascadeBestCategory, cls).createFromData(data)
        if task and dbConnection:
            sql = "select idea,suggested_category from cascade_suggested_categories,question_ideas where cascade_suggested_categories.idea_id=question_ideas.id and cascade_suggested_categories.idea_id=%s and suggested_category is not null"
            dbConnection.cursor.execute(sql, (task.idea_id))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                task.idea = row["idea"]
                if row["suggested_category"] not in task.suggested_categories:
                    task.suggested_categories.append(row["suggested_category"])
        return task
           
    @staticmethod
    def initStep(dbConnection, question):
        iterationCondition = "and cascade_suggested_categories.cascade_iteration=questions.cascade_iteration" if question.cascade_iteration > 1 else ""
        sql = "select distinct idea_id from cascade_suggested_categories,questions where cascade_suggested_categories.question_id=questions.id and question_id=%s {0} and suggested_category is not null".format(iterationCondition)
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            ideaId = row["idea_id"]
            for i in range(question.cascade_k):
                CascadeBestCategory.create(dbConnection, question, ideaId, False)
        dbConnection.conn.commit()

    @staticmethod
    def getJob(dbConnection, question, person):     
        job = []
        # check if job already assigned
        sql = "select * from cascade_best_categories where "
        sql += "question_id=%s and "
        sql += "user_id=%s and "
        sql += "best_category is null and "
        sql += "none_of_the_above=0"
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeBestCategory.createFromData(row, dbConnection)
            job.append(task)
             
        # if not, assign new tasks
        # do not check if user already performed task on idea when running locally
        if len(job) == 0:
            try:
                sql = "select * from cascade_best_categories where "
                sql += "question_id=%s " 
                sql += "and user_id is null "
                sql += "and idea_id not in (select distinct idea_id from cascade_best_categories where question_id=%s and user_id=%s) " if not helpers.isRunningLocally() else ""
                sql += "group by idea_id order by rand() limit 1 "
                sql += "for update"
    
                if helpers.isRunningLocally():
                    dbConnection.cursor.execute(sql, (question.id,))
                else:
                    dbConnection.cursor.execute(sql, (question.id, question.id, person.id))
                
                rows = dbConnection.cursor.fetchall()
                for row in rows:
                    task = CascadeBestCategory.createFromData(row, dbConnection)
                    task.assignTo(dbConnection, person, commit=False)
                    job.append(task)
            
                dbConnection.conn.commit()
            except:
                job = []
                dbConnection.rollback()
                    
        return job if len(job) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):
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
            # vote for none of the above
            else:
                sql = "update cascade_best_categories set none_of_the_above=1 where id=%s"
                dbConnection.cursor.execute(sql, (taskId)) 

        dbConnection.conn.commit()
        
        stepComplete = CascadeBestCategory.continueToNextStepIfComplete(dbConnection, question)
        return stepComplete
        
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_best_categories where question_id=%s and best_category is null and none_of_the_above=0"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0
    
    @staticmethod
    def continueToNextStepIfComplete(dbConnection, question):
        stepComplete = CascadeBestCategory.isStepComplete(dbConnection, question)
        if stepComplete:
            question.initCascadeNextStep(dbConnection)
        return stepComplete
            
    def toDict(self, dbConnection=None, includeIdeaText=True):
        objDict = super(CascadeBestCategory, self).toDict()                 
        if dbConnection and includeIdeaText:
            idea = None
            suggestedCategories = []
            sql = "select cascade_suggested_categories.*,idea from cascade_suggested_categories,question_ideas where cascade_suggested_categories.idea_id=question_ideas.id and cascade_suggested_categories.idea_id=%s and suggested_category is not null"
            dbConnection.cursor.execute(sql, (self.id))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                idea = row["idea"]
                suggestedCategories.append(row["suggested_catgegory"])
            objDict["idea"] = idea
            objDict["suggested_categories"] = suggestedCategories
            
        return objDict

class CascadeFitCategoryPhase1(DBObject):
    table = "cascade_fit_categories_phase1"
    fields = { "id", "question_id", "idea_id", "idea", "category", "fit", "cascade_iteration", "subsequent", "user_id" }
        
    def __init__(self):
        self.id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas table
        self.category = None
        self.fit = 0
        self.cascade_iteration = 0
        self.subsequent = 0
        self.user_id = None
        
    @staticmethod
    def create(dbConnection, question, ideaId, category, subsequent=0, commit=True):        
        task = CascadeFitCategoryPhase1()
        task.question_id = question.id
        task.idea_id = ideaId
        task.category = category
                  
        sql = "insert into cascade_fit_categories_phase1 (question_id, idea_id, category, cascade_iteration, subsequent) values (%s, %s, %s, %s, %s)"
        dbConnection.cursor.execute(sql, (task.question_id, task.idea_id, task.category, question.cascade_iteration, subsequent))
        if commit:
            dbConnection.conn.commit()
    
        return task
    
    @classmethod
    def createFromData(cls, data):
        task = super(CascadeFitCategoryPhase1, cls).createFromData(data)
        if task:
            ideaField = "idea" if "idea" in data else Idea.tableField("idea") if Idea.tableField("idea") in data else None
            if ideaField:
                task.idea = data[ideaField]
            else:
                helpers.log("WARNING: idea not included in task data")
        return task
    
    @staticmethod
    def initStep(dbConnection, question):
        sql = "select distinct idea_id from cascade_suggested_categories where question_id=%s and cascade_iteration=%s"
        dbConnection.cursor.execute(sql, (question.id, question.cascade_iteration))
        rows = dbConnection.cursor.fetchall()

        # TODO: how should voting threshold be determined
        votingThreshold = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k>3 else 1
        sql = "select distinct best_category from cascade_best_categories where question_id=%s and cascade_iteration=%s and none_of_the_above=0 group by question_id,idea_id,best_category having count(*)>=%s"
        dbConnection.cursor.execute(sql, (question.id, question.cascade_iteration, votingThreshold))
        rows2 = dbConnection.cursor.fetchall()

        for row in rows:
            ideaId = row["idea_id"]
            for row2 in rows2:
                category = row2["best_category"]
                for i in range(question.cascade_k2):
                    CascadeFitCategoryPhase1.create(dbConnection, question, ideaId, category)

    @staticmethod
    def getJob(dbConnection, question, person): 
        job = []
        # check if job already assigned
        sql = "select cascade_fit_categories_phase1.*,idea from cascade_fit_categories_phase1,question_ideas where "
        sql += "cascade_fit_categories_phase1.idea_id=question_ideas.id and "
        sql += "cascade_fit_categories_phase1.question_id=%s and "
        sql += "cascade_fit_categories_phase1.user_id=%s and "
        sql += "fit=-1"
            
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeFitCategoryPhase1.createFromData(row)
            job.append(task)
             
        # if not, assign new tasks
        # do not check if user already performed task on idea when running locally
        # ask user to check whether all categories fit or not for an idea (regardless of how many)
        if len(job) == 0:
            try:
                # find an idea that still needs categories checked
                sql = "select idea_id from cascade_fit_categories_phase1 where "
                sql += "question_id=%s "
                sql += "and user_id is null "
                sql += "and (idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase1 where question_id=%s and user_id=%s) " if not helpers.isRunningLocally() else ""
                sql += "order by rand() limit 1 "
                sql += "for update"
                if helpers.isRunningLocally():
                    dbConnection.cursor.execute(sql, (question.id,))
                else:
                    dbConnection.cursor.execute(sql, (question.id, question.id, person.id))
                row = dbConnection.cursor.fetchone()
                ideaId = row["idea_id"] if row else None
        
                # now find categories that still need to be checked for this idea
                if ideaId:
                    sql = "select cascade_fit_categories_phase1.*,idea from cascade_fit_categories_phase1,question_ideas where "
                    sql += "cascade_fit_categories_phase1.question_id=%s "
                    sql += "and cascade_fit_categories_phase1.idea_id=question_ideas.id "
                    sql += "and cascade_fit_categories_phase1.idea_id=%s "
                    sql += "and cascade_fit_categories_phase1.user_id is null "
                    sql += "and (cascade_fit_categories_phase1.idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase1 where question_id=%s and user_id=%s) " if not helpers.isRunningLocally() else ""
                    sql += "group by category order by rand() limit {0} ".format(question.cascade_t)
                    sql += "for update"
                    if helpers.isRunningLocally():
                        dbConnection.cursor.execute(sql, (question.id, ideaId))
                    else:
                        dbConnection.cursor.execute(sql, (question.id, ideaId, question.id, person.id))
                    
                    rows = dbConnection.cursor.fetchall()
                    for row in rows:
                        task = CascadeFitCategoryPhase1.createFromData(row)
                        task.assignTo(dbConnection, person, commit=False)
                        job.append(task)
                    
                    dbConnection.conn.commit()
            except:
                job = []
                dbConnection.rollback()
                
        return job if len(job) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):
        sql = "update cascade_fit_categories_phase1 set user_id=%s where id=%s"
        dbConnection.cursor.execute(sql, (person.id, self.id))
        if commit:
            dbConnection.conn.commit()

    @staticmethod
    def saveJob(dbConnection, question, job):
        for task in job:
            taskId = task["id"]
            fit = task["fit"]
            sql = "update cascade_fit_categories_phase1 set fit=%s where id=%s"
            dbConnection.cursor.execute(sql, (fit, taskId))
        dbConnection.conn.commit()
        
        stepComplete = CascadeFitCategoryPhase1.continueToNextStepIfComplete(dbConnection, question)
        return stepComplete
        
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_fit_categories_phase1 where question_id=%s and fit=-1"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0

    @staticmethod
    def continueToNextStepIfComplete(dbConnection, question):
        stepComplete = CascadeFitCategoryPhase1.isStepComplete(dbConnection, question)
        if stepComplete:
            question.initCascadeNextStep(dbConnection)
        return stepComplete
            
class CascadeFitCategoryPhase2(DBObject):
    table = "cascade_fit_categories_phase2"
    fields = { "id", "question_id", "idea_id", "idea", "category", "fit", "user_id" }
        
    def __init__(self):
        self.id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas table
        self.category = None
        self.fit = 0
        self.user_id = None
        
    @staticmethod
    def create(dbConnection, question, ideaId, category, commit=True):        
        task = CascadeFitCategoryPhase2()
        task.question_id = question.id
        task.idea_id = ideaId
        task.category = category
                  
        sql = "insert into cascade_fit_categories_phase2 (question_id, idea_id, category, cascade_iteration) values (%s, %s, %s, %s)"
        dbConnection.cursor.execute(sql, (task.question_id, task.idea_id, task.category, question.cascade_iteration))
        if commit:
            dbConnection.conn.commit()
    
        return task
    
    @classmethod
    def createFromData(cls, data):
        task = super(CascadeFitCategoryPhase2, cls).createFromData(data)
        if task:
            ideaField = "idea" if "idea" in data else Idea.tableField("idea") if Idea.tableField("idea") in data else None
            if ideaField:
                task.idea = data[ideaField]
            else:
                helpers.log("WARNING: idea not included in task data")
        return task
    
    @staticmethod
    def initStep(dbConnection, question):
        # TODO: how should voting threshold be determined
        votingThreshold = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k>3 else 1
        sql = "select *,count(*) as ct from cascade_fit_categories_phase1 where question_id=%s and cascade_iteration=%s and fit=1 group by question_id,idea_id,category having ct>=%s";
        dbConnection.cursor.execute(sql, (question.id, question.cascade_iteration, votingThreshold))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            ideaId = row["idea_id"]
            category = row["category"]
            for i in range(question.cascade_k2):
                CascadeFitCategoryPhase2.create(dbConnection, question, ideaId, category)

    @staticmethod
    def getJob(dbConnection, question, person):  
        job = []
        # check if job already assigned
        sql = "select cascade_fit_categories_phase2.*,idea from cascade_fit_categories_phase2,question_ideas where "
        sql += "cascade_fit_categories_phase2.idea_id=question_ideas.id and "
        sql += "cascade_fit_categories_phase2.question_id=%s and "
        sql += "cascade_fit_categories_phase2.user_id=%s and "
        sql += "fit=-1"
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeFitCategoryPhase2.createFromData(row)
            job.append(task)
             
        # if not, assign new tasks
        # ask user to check whether all categories fit or not for an idea (regardless of how many)
        # do not check if user already performed task on idea when running locally

        if len(job) == 0:
            try:
                # find an idea that still needs categories checked
                sql = "select idea_id from cascade_fit_categories_phase2 where "
                sql += "question_id=%s "
                sql += "and user_id is null "
                sql += "and (idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase2 where question_id=%s and user_id=%s) " if not helpers.isRunningLocally() else ""
                sql += "order by rand() limit 1 "
                sql += "for update"
                if helpers.isRunningLocally():
                    dbConnection.cursor.execute(sql, (question.id,))
                else:
                    dbConnection.cursor.execute(sql, (question.id, question.id, person.id))
                row = dbConnection.cursor.fetchone()
                ideaId = row["idea_id"] if row else None
        
                # now find categories that still need to be checked for this idea
                if ideaId:
                    sql = "select cascade_fit_categories_phase2.*,idea from cascade_fit_categories_phase2,question_ideas where "
                    sql += "cascade_fit_categories_phase2.question_id=%s "
                    sql += "and cascade_fit_categories_phase2.idea_id=question_ideas.id "
                    sql += "and cascade_fit_categories_phase2.idea_id=%s "
                    sql += "and cascade_fit_categories_phase2.user_id is null "
                    sql += "and (cascade_fit_categories_phase2.idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase2 where question_id=%s and user_id=%s) " if not helpers.isRunningLocally() else ""
                    sql += "group by category order by rand() limit {0} ".format(question.cascade_t)
                    sql += "for update"
                    if helpers.isRunningLocally():
                        dbConnection.cursor.execute(sql, (question.id, ideaId))
                    else:
                        dbConnection.cursor.execute(sql, (question.id, ideaId, question.id, person.id))
                    rows = dbConnection.cursor.fetchall()
                    for row in rows:
                        task = CascadeFitCategoryPhase2.createFromData(row)
                        task.assignTo(dbConnection, person, commit=False)
                        job.append(task)
                    
                    dbConnection.conn.commit()
            except:
                job = []
                dbConnection.rollback()
                
        return job if len(job) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):
        sql = "update cascade_fit_categories_phase2 set user_id=%s where id=%s"
        dbConnection.cursor.execute(sql, (person.id, self.id))
        if commit:
            dbConnection.conn.commit()

    @staticmethod
    def saveJob(dbConnection, question, job):
        for task in job:
            taskId = task["id"]
            fit = task["fit"]
            sql = "update cascade_fit_categories_phase2 set fit=%s where id=%s"
            dbConnection.cursor.execute(sql, (fit, taskId))
        dbConnection.conn.commit()
        
        stepComplete = CascadeFitCategoryPhase2.continueToNextStepIfComplete(dbConnection, question)
        return stepComplete
        
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_fit_categories_phase2 where question_id=%s and fit=-1"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0

    @staticmethod
    def continueToNextStepIfComplete(dbConnection, question):
        stepComplete = CascadeFitCategoryPhase2.isStepComplete(dbConnection, question)
        if stepComplete:
            GenerateCascadeHierarchy(dbConnection, question)
            question.initCascadeNextStep(dbConnection)

        return stepComplete
    
class CascadeFitCategorySubsequentPhase1(CascadeFitCategoryPhase1):        
    def __init__(self):
        super().__init__()
    
    @staticmethod
    def initStep(dbConnection, question):
        if question.cascade_iteration == 1:
            sql = "select id from question_ideas where question_id=%s and id not in (select distinct idea_id from cascade_suggested_categories where question_id=%s)"
            dbConnection.cursor.execute(sql, (question.id, question.id))
        else:
            sql = "select id from question_ideas where question_id=%s and id in (select distinct idea_id from cascade_suggested_categories where question_id=%s and cascade_iteration<%s)"            
            dbConnection.cursor.execute(sql, (question.id, question.id, question.cascade_iteration))
        rows = dbConnection.cursor.fetchall()
                    
        if len(rows) == 0:
            # BEHAVIOR: no subsequent items so skip to next step
            question.initCascadeNextStep(dbConnection)
            return

        # TODO: how should voting threshold be determined
        votingThreshold = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k>3 else 1        
        sql = "select distinct best_category from cascade_best_categories where question_id=%s and cascade_iteration=%s and none_of_the_above=0 group by question_id,idea_id,best_category having count(*)>=%s"

        dbConnection.cursor.execute(sql, (question.id, question.cascade_iteration, votingThreshold))
        rows2= dbConnection.cursor.fetchall()

        for row in rows:
            ideaId = row["id"]
            for row2 in rows2:
                category = row2["best_category"]
                for i in range(question.cascade_k2):
                    CascadeFitCategoryPhase1.create(dbConnection, question, ideaId, category, subsequent=1)
        
class CascadeFitCategorySubsequentPhase2(CascadeFitCategoryPhase2):        
    def __init__(self):
        super().__init__()
    
    @staticmethod
    def initStep(dbConnection, question):
        # TODO: how should voting threshold be determined
        votingThreshold = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k>3 else 1
        sql = "select *,count(*) as ct from cascade_fit_categories_phase1 where question_id=%s and cascade_iteration=%s and subsequent=1 and fit=1 group by question_id,idea_id,category having ct>=%s";
        dbConnection.cursor.execute(sql, (question.id, question.cascade_iteration, votingThreshold))
        rows = dbConnection.cursor.fetchall()
        
        if len(rows) == 0:
            question.initCascadeNextStep(dbConnection)
            return
            
        for row in rows:
            ideaId = row["idea_id"]
            category = row["category"]
            for i in range(question.cascade_k2):
                CascadeFitCategoryPhase2.create(dbConnection, question, ideaId, category)
                        
def GenerateCascadeHierarchy(dbConnection, question):
    categories = {}
    ideas = {}
    sql = "select idea_id,idea,category,count(*) as ct from cascade_fit_categories_phase2,question_ideas where "
    sql += "cascade_fit_categories_phase2.idea_id=question_ideas.id "
    sql += "and cascade_fit_categories_phase2.question_id=%s "
    sql += "and fit=1 "
    sql += "group by idea_id,category "
    sql += "having ct>=%s"
    # TODO: how should voting threshold be determined
    minCount = math.ceil(question.cascade_k2 * 0.8)
    dbConnection.cursor.execute(sql, (question.id, minCount))
    rows = dbConnection.cursor.fetchall()
    for row in rows:
        category = row["category"]
        ideaId = row["idea_id"]
        idea = row["idea"]
        if category not in categories:
            categories[category] = []
        categories[category].append(ideaId)
        ideas[ideaId] = idea
    
    # remove any categories with less than q items
    categoriesToRemove = []
    for category in categories:
        if len(categories[category]) < constants.CASCADE_Q:
            categoriesToRemove.append(category)
        
    for category in categoriesToRemove:
        del categories[category]
    
    # remove any duplicate categories (more than p overlapping items)
    # TODO: consider whether not duplicate categories should only be removed last time it is called in case subsequent categories change things?
    categoriesToRemove = []
    categoryKeys = categories.keys()
    duplicateCategories = {}
    for x in range(len(categoryKeys)):
        for y in range(x, len(categoryKeys)):
            if x != y:
                category1 = categoryKeys[x]
                category2 = categoryKeys[y]
                ideaIds1 = categories[category1]
                ideaIds2 = categories[category2]
                sharedIdeaIds = helpers.intersect(ideaIds1, ideaIds2)
                if len(sharedIdeaIds) >= max(len(ideaIds1),len(ideaIds2))*constants.CASCADE_P:
                    duplicateCategory = category1 if len(ideaIds1) < len(ideaIds2) else category2
                    primaryCategory = category1 if duplicateCategory != category1 else category2
                    if duplicateCategory not in categoriesToRemove:
                        categoriesToRemove.append(duplicateCategory)
                    if primaryCategory not in duplicateCategories:
                        duplicateCategories[primaryCategory] = []
                    duplicateCategories[primaryCategory].append(duplicateCategory)
                    
    for category in categoriesToRemove:
        del categories[category]
    
    # BEHAVIOR: nested categories not created
    
    sql = "delete from question_categories where question_id=%s"
    dbConnection.cursor.execute(sql, (question.id))
 
    sql = "delete from categories where question_id=%s"
    dbConnection.cursor.execute(sql, (question.id))
    
    for category in categories:
        ideaIds = categories[category]
        sameAs = ", ".join(duplicateCategories[category]) if category in duplicateCategories else None
        sql = "insert into categories (question_id, category, same_as) values(%s, %s, %s)"
        dbConnection.cursor.execute(sql, (question.id, category, sameAs))
        categoryId = dbConnection.cursor.lastrowid
        for ideaId in ideaIds:
            sql = "insert into question_categories (question_id, idea_id, category_id) values(%s, %s, %s)"
            dbConnection.cursor.execute(sql, (question.id, ideaId, categoryId))

    dbConnection.conn.commit()
        
CASCADE_CLASSES = [ CascadeSuggestedCategory, CascadeBestCategory, CascadeFitCategoryPhase1, CascadeFitCategoryPhase2, CascadeFitCategorySubsequentPhase1, CascadeFitCategorySubsequentPhase2 ]