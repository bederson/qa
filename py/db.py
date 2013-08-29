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
import datetime
import math
import random
from google.appengine.api import memcache
from google.appengine.api import rdbms
from google.appengine.api import users
from lib import gaesessions

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
    fields = []

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
    fields = [ "id", "title", "question", "nickname_authentication", "user_id", "active", "cascade_complete", "cascade_k", "cascade_k2", "cascade_m", "cascade_p", "cascade_t" ]  
    
    # makes it harder to revert back to previous versions of QA
    
    def __init__(self):
        self.id = None
        self.title = None
        self.question = None
        self.nickname_authentication = False
        self.user_id = None
        self.authenticated_user_id = None # stored in users table
        self.active = 0
        self.cascade_complete = 0
        self.cascade_k = 0
        self.cascade_k2 = 0
        self.cascade_m = 0
        self.cascade_p = 0
        self.cascade_t = 0
        
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
        question.active = 1
            
        sql = "insert into questions (id, title, question, nickname_authentication, user_id, active) values (%s, %s, %s, %s, %s, %s)"
        dbConnection.cursor.execute(sql, (question.id, question.title, question.question, question.nickname_authentication, question.user_id, question.active))
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

    def setActive(self, dbConnection, active):
        if self.active != active:
            if not active:
                self.deleteIncompleteCascadeJobs(dbConnection, commit=False)
            self.update(dbConnection, { "active" : active, "id" : self.id })
        
    def getCascadeJob(self, dbConnection, person):
        # return the earliest job that needs to be done (e.g., return suggest category job before match category job)
        # if no job, and cascade is not complete, then user must wait         
        job = None
        for cls in CASCADE_CLASSES:
            job = cls.getJob(dbConnection, self, person)
            if job:
                break
        return job
        
    def saveCascadeJob(self, dbConnection, job, person):        
        if job:
            # POTENTIAL BUG: concurrency issue may allow more than one user to be assigned to a job
            # if so, the first job submitted is saved but it might be by a different user than is assigned the job
            # so save the current user with the job
            # do not currently check if user_id is null when assigning job because don't currently have
            # a way to guarantee job is not in process of getting assigned
            cls = getCascadeClass(job["type"])
            cls.saveJob(dbConnection, self, job["tasks"], person=person)
            
            # TODO: record stop / start time (from first idea to cascade complete)
            # TODO: check how to update counts/times concurrently
            
    def cancelCascadeJob(self, dbConnection, job):
        count = 0
        if job:
            cls = getCascadeClass(job["type"])
            for task in job["tasks"]:
                count += cls.unassign(dbConnection, self.id, task["id"])
        return count
        
    def recordCascadeUnsavedTask(self, dbConnection, step, unsavedCount):
        try:
            dbConnection.conn.begin()
            sql = "select * from cascade_stats where question_id=%s for update"
            dbConnection.cursor.execute(sql, (self.id))
            sql = "update cascade_stats set step{0}_unsaved_count = step{0}_unsaved_count + {1} where question_id=%s".format(step, unsavedCount)
            dbConnection.cursor.execute(sql, (self.id))
            dbConnection.conn.commit()
        except:
            dbConnection.conn.rollback()
                    
    def updateCascadeStats(self, dbConnection):                    
        if self.cascade_complete:              
            # user count updated (based on how many people performed step 3)
            sql = "select count(distinct user_id) as ct from cascade_fit_categories_phase1 where question_id=%s and user_id is not null"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            userCount = row["ct"] if row else 0
                         
            # category count
            sql = "select count(*) as ct from categories where question_id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            categoryCount = row["ct"] if row else 0
            
            # uncategorized count
            sql = "select count(*) as ct from question_ideas left join question_categories on question_ideas.id=question_categories.idea_id where question_ideas.question_id=%s and category_id is null"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            uncategorizedCount = row["ct"] if row else 0

            sql = "update cascade_stats set user_count=%s, category_count=%s, uncategorized_count=%s  where question_id=%s"
            dbConnection.cursor.execute(sql, (userCount, categoryCount, uncategorizedCount, self.id))
        
        dbConnection.conn.commit()
       
    def getQuestionStats(self, dbConnection):
        stats = {}
        stats["question_id"] = self.id
        stats["user_count"] = Person.getCountForQuestion(dbConnection, self.id)
        stats["active_user_count"] = Person.getCountForQuestion(dbConnection, self.id, loggedIn=True)    
        stats["idea_count"] = Idea.getCountForQuestion(dbConnection, self.id) 
        stats["cascade_stats"] = self.getCascadeStats(dbConnection) if self.cascade_complete else None
        return stats
    
    def getCascadeStats(self, dbConnection):
        stats = None
        sql = "select * from cascade_stats where question_id=%s"
        dbConnection.cursor.execute(sql, (self.id))
        row = dbConnection.cursor.fetchone()
        if row:
            stats = {}
            stats["user_count"] = row["user_count"]
            stats["idea_count"] = row["idea_count"]
            stats["category_count"] = row["category_count"]
            stats["uncategorized_count"] = row["uncategorized_count"]
            for i in range(len(CASCADE_CLASSES)):
                stats["step{0}_job_count".format(i+1)] = row["step{0}_job_count".format(i+1)]
                                
        return stats
           
    def delete(self, dbConnection, dataOnly=False, onDeleteStudents=None):
        if not dataOnly:
            dbConnection.cursor.execute("delete from questions where id={0}".format(self.id))            
        dbConnection.cursor.execute("delete from question_ideas where question_id={0}".format(self.id))
        self.deleteCascade(dbConnection, commit=False)

        if onDeleteStudents:
            onDeleteStudents(dbConnection, self.id)
        dbConnection.cursor.execute("delete user_clients from users,user_clients where users.id=user_clients.user_id and question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from users where question_id={0}".format(self.id))
        
        dbConnection.conn.commit()
        self = Question()
        return self
    
    def deleteCascade(self, dbConnection, commit=True):
        self.update(dbConnection, { "cascade_k" : 0, "cascade_k2" : 0, "cascade_m" : 0, "cascade_p" : 0, "cascade_t" : 0, "cascade_complete" : 0, "id" : self.id }, commit=False)
        dbConnection.cursor.execute("delete from cascade_suggested_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_best_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_fit_categories_phase1 where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_stats where question_id={0}".format(self.id))
        deleteCascadeMemcache(self)
        if commit:
            dbConnection.conn.commit()
            
    def deleteIncompleteCascadeJobs(self, dbConnection, commit=True):
        if not self.cascade_complete:
            dbConnection.cursor.execute("update cascade_suggested_categories set user_id=null where question_id={0} and suggested_category is null and skipped=0".format(self.id))
            dbConnection.cursor.execute("update cascade_best_categories set user_id=null where question_id={0} and best_category is null and none_of_the_above=0".format(self.id))
            dbConnection.cursor.execute("update cascade_fit_categories_phase1 set user_id=null where question_id={0} and fit=-1".format(self.id))
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
    def getByUser(dbConnection):
        questions = []
        user = users.get_current_user()
        if user:
            sql = "select {0}, users.authenticated_user_id from questions,users where questions.user_id=users.id and authenticated_user_id=%s".format(Question.fieldsSql())
            dbConnection.cursor.execute(sql, (user.user_id()))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                question = Question.createFromData(row)
                questionDict = question.toDict()
                questions.append(questionDict)
        return questions

class Person(DBObject):               
    table = "users"
    fields = [ "id", "authenticated_user_id", "authenticated_nickname", "nickname", "question_id", "latest_login_timestamp", "latest_logout_timestamp", "session_sid" ]   
    onCreate = None
    onLogin = None
    onLogout = None
    
    def __init__(self):
        self.id = None
        self.authenticated_user_id = None
        self.authenticated_nickname = None
        self.nickname = None
        self.question_id = None
        self.latest_login_timestamp = None
        self.latest_logout_timestamp = None
        self.is_logged_in = False # not stored in db
        self.session_sid = None
    
    @staticmethod
    def create(dbConnection, question=None, nickname=None):
        user = users.get_current_user()
        authenticatedUserId = user.user_id() if user else None
        authenticatedNickname = user.nickname() if user else None

        # Person must be either an authenticated Google user
        # or login with a nickname (if the question allows)
        if not authenticatedUserId and not nickname:
            return None
        
        session = gaesessions.get_current_session()
        
        person = Person()
        person.authenticated_user_id = authenticatedUserId
        person.authenticated_nickname = authenticatedNickname
        person.nickname = nickname if nickname else (Person.cleanNickname(user.nickname()) if user else None)
        person.question_id = question.id if question else None
        person.session_sid = session.sid if session and authenticatedUserId is None else None
          
        sql = "insert into users (authenticated_user_id, authenticated_nickname, nickname, question_id, session_sid, latest_login_timestamp, latest_logout_timestamp) values (%s, %s, %s, %s, %s, now(), null)"
        dbConnection.cursor.execute(sql, (person.authenticated_user_id, person.authenticated_nickname, person.nickname, person.question_id, person.session_sid))
        person.id = dbConnection.cursor.lastrowid
        dbConnection.conn.commit()
        person.is_logged_in=True   
        
        if Person.onCreate:
            Person.onCreate(person, dbConnection)
            
        return person
    
    @classmethod
    def createFromData(cls, data):
        person = super(Person, cls).createFromData(data)
        if person:
            person.is_logged_in = person.latest_login_timestamp is not None and person.latest_logout_timestamp is None
        return person
              
    def login(self, dbConnection):
        if not self.is_logged_in:
            session = gaesessions.get_current_session()
            updateValues = ()
            sql = "update users set latest_login_timestamp=now(), latest_logout_timestamp=null"
            # store session id with nickname authenticated users
            if self.authenticated_user_id is None and session is not None:
                sql += ", session_sid=%s"
                updateValues += (session.sid,)
            sql += " where id=%s"
            updateValues += (self.id,)
            dbConnection.cursor.execute(sql, updateValues)
            dbConnection.conn.commit()
            self.session_sid = session.sid if session else None
            self.is_logged_in = True
            
            if Person.onLogin:
                Person.onLogin(self, dbConnection)
  
    def logout(self, dbConnection, userRequestedLogout=True, commit=True):
        if self.is_logged_in:
            # if a Google authenticated user is actively logging out (clicked on Logout), 
            # modify all records associated with this user            
            if userRequestedLogout and self.authenticated_user_id:
                sql = "update users set latest_logout_timestamp=now(), session_sid=null where authenticated_user_id=%s"
                dbConnection.cursor.execute(sql, (self.authenticated_user_id))
                # do not need to delete rows from user_clients since since "logout" message is sent to each client
                # which in response calls /logout
                #sql = "delete from user_clients using user_clients, users where user_clients.user_id=users.id and authenticated_user_id=%s"
                #dbConnection.cursor.execute(sql, (self.authenticated_user_id))
    
            # otherwise, logout this specific user instance
            else:
                sql = "update users set latest_logout_timestamp=now(), session_sid=null where id=%s"
                dbConnection.cursor.execute(sql, (self.id))
                # do not need to delete rows from user_clients since ChannelDisconnectedHandler will do this
                #sql = "delete from user_clients where user_id=%s"
                #dbConnection.cursor.execute(sql, (self.id))
                        
            if commit:
                dbConnection.conn.commit()

            self.session_sid = None                
            self.is_logged_in = False
            
            if Person.onLogout:
                Person.onLogout(self, dbConnection)
                        
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
    
    def getClientIds(self, dbConnection, question):
        sql = "select client_id from user_clients where user_id={0}".format(self.id)
        if question:
            sql += " and client_id like '%\_{0}\_%'".format(question.id)
        dbConnection.cursor.execute(sql)
        rows = dbConnection.cursor.fetchall()
        return [ row["client_id"] for row in rows ]
                                                                                      
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
    def getPerson(dbConnection, question=None, nickname=None):
        person = None
        user = users.get_current_user()

        # if question allows nickname authentication and nickname given, check for user
        # question author does not have to login with nickname if already authenticated
        if question is not None and question.nickname_authentication and nickname is not None and not question.isAuthor():
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
            if not person and question is not None and question.isAuthor:
                person = Person.create(dbConnection, question=question)
                
        return person
     
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
    def getCountForQuestion(dbConnection, questionId, loggedIn=False):
        sql = "select count(*) as ct from users where question_id=%s"
        if loggedIn:
            sql += " and latest_login_timestamp is not null and latest_logout_timestamp is null"
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
    fields = [ "id", "question_id", "user_id", "idea", "item_set" ]
        
    def __init__(self):
        self.id = None
        self.question_id = None
        self.user_id = None
        self.idea = None
        self.item_set = constants.CASCADE_INITIAL_ITEM_SET
    
    @staticmethod
    def create(dbConnection, question, userId, ideaText):
        idea = Idea()
        idea.question_id = question.id
        idea.user_id = userId
        idea.idea = ideaText
        idea.item_set = toggleCascadeItemSet(question) # toggle ideas between initial item set and subsequent item set used by Cascade
        
        sql = "insert into question_ideas (question_id, user_id, idea, item_set) values (%s, %s, %s, %s)"
        dbConnection.cursor.execute(sql, (idea.question_id, idea.user_id, idea.idea, idea.item_set))
        idea.id = dbConnection.cursor.lastrowid
        dbConnection.conn.commit()
        
        # check if cascade options have been initialized yet
        # TODO: options calculated based on # of active users so options will be *wrong* if first idea submitted before most people are logged in
        # TODO: what happens if k adjusted as things progress?
        if question.cascade_k == 0:
            userCount = Person.getCountForQuestion(dbConnection, question.id, loggedIn=True)
            if userCount > 1:
                cascade_k = 2
                cascade_k2 = 1
            else:
                cascade_k = 1
                cascade_k2 = 1
            
            properties = {
                "cascade_k" : cascade_k,
                "cascade_k2" : cascade_k2,
                "cascade_p" : constants.CASCADE_P,
                "cascade_t" : 3,
                "id" : question.id
            }
            question.update(dbConnection, properties)
                        
        # create CascadeSuggestCategory and CascadeFitCategory jobs for new idea
        if idea.item_set == constants.CASCADE_INITIAL_ITEM_SET:
            CascadeSuggestedCategory.create(dbConnection, question, idea.id)
        
        sql = "select * from categories where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            CascadeFitCategory.create(dbConnection, question, idea.id, row["category"])
                         
        return idea
       
    @staticmethod
    def getById(dbConnection, ideaId):
        sql = "select {0} from question_ideas where id=%s".format(Idea.fieldsSql())
        dbConnection.cursor.execute(sql, (ideaId))
        row = dbConnection.cursor.fetchone()
        return Idea.createFromData(row)
        
    @staticmethod
    def getByQuestion(dbConnection, question, asDict=False, includeCreatedOn=False):
        ideas = []
        if question:
            sql = "select {0},{1},question_ideas.created_on as idea_created_on from question_ideas,users where question_ideas.user_id=users.id and question_ideas.question_id=%s order by created_on desc".format(Idea.fieldsSql(), Person.fieldsSql())
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
                    if includeCreatedOn:
                        idea["created_on"] = row["idea_created_on"]
                                           
                ideas.append(idea)
        return ideas
        
    @staticmethod
    def getByCategories(dbConnection, question, asDict=False, includeCreatedOn=False):
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
            sql = "select {0},{1},question_ideas.created_on as idea_created_on,category,same_as from question_ideas ".format(Idea.fieldsSql(), Person.fieldsSql())
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
                    if includeCreatedOn:
                        idea["created_on"] = row["idea_created_on"]
                    
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

# TODO: update comments
# BEHAVIOR: cascade jobs for step 1 are created when cascade is enabled, and for subsequent jobs whenever the previous job is completed
# BEHAVIOR: currently any existing cascade data is deleted if cascade is disabled and then re-enabled
# BEHAVIOR: users are restricted to unique tasks when running on GAE; >= k users required to complete cascade 
# BEHAVIOR: users can can do as many jobs as they can when running locally, but are restricted to unique tasks on GAE
# BEHAVIOR: introduced cascade_k2 to use for steps 3-5 (category fit tasks) since step 3/5 can be very expensive in terms of # of tasks
# BEHAVIOR: categories with fewer than CASCADE_Q items removed
# BEHAVIOR: duplicate categories merged (the % of overlapping items used to detect duplicates is defined by cascade_p)
# BEHAVIOR: nested categories not generated
    
class CascadeSuggestedCategory(DBObject):
    type = constants.SUGGEST_CATEGORY
    table = "cascade_suggested_categories"
    fields = [ "id", "question_id", "idea_id", "idea", "suggested_category", "skipped", "user_id" ]
        
    def __init__(self):
        self.id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas table
        self.suggested_category = None
        self.skipped = 0
        self.user_id = None
            
    @staticmethod
    def create(dbConnection, question, ideaId):
        insertValues = [ "({0}, {1})".format(question.id, ideaId) for i in range(question.cascade_k) ]
        sql = "insert into cascade_suggested_categories (question_id, idea_id) values {0}".format(",".join(insertValues))
        dbConnection.cursor.execute(sql)
        count = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return count
                
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
    def getJob(dbConnection, question, person):      
        tasks = []
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
            tasks.append(task)
             
        # if not, assign new tasks
        # do not check if user already performed task on idea when running locally
        if len(tasks) == 0:
            sql = "select cascade_suggested_categories.*,idea from cascade_suggested_categories,question_ideas where "
            sql += "cascade_suggested_categories.idea_id=question_ideas.id "
            sql += "and cascade_suggested_categories.question_id=%s " 
            sql += "and cascade_suggested_categories.user_id is null "
            sql += "and idea_id not in (select distinct idea_id from cascade_suggested_categories where question_id=%s and user_id=%s) " if not helpers.allowDuplicateJobs() else ""
            sql += "group by idea_id order by rand() limit {0} ".format(question.cascade_t)

            if helpers.allowDuplicateJobs():
                dbConnection.cursor.execute(sql, (question.id,))
            else:
                dbConnection.cursor.execute(sql, (question.id, question.id, person.id))
            rows = dbConnection.cursor.fetchall()

            for row in rows:
                task = CascadeSuggestedCategory.createFromData(row)
                task.assignTo(dbConnection, person, commit=False)
                tasks.append(task)
            dbConnection.conn.commit()
        
        return { "tasks" : tasks, "type" : CascadeSuggestedCategory.type } if len(tasks) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):   
        sql = "update cascade_suggested_categories set user_id=%s where id=%s"
        dbConnection.cursor.execute(sql, (person.id, self.id))
        if commit:
            dbConnection.conn.commit()

    @staticmethod
    def unassign(dbConnection, questionId, taskId):
        sql = "update cascade_suggested_categories set user_id=null where question_id=%s and id=%s"
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0
            
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        unsavedTasks = []
        for task in job:
            taskId = task["id"]
            suggestedCategory = task["suggested_category"]
            # save suggested category
            if suggestedCategory != "":
                sql = "update cascade_suggested_categories set suggested_category=%s"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and (suggested_category is null and skipped=0)"
                dbConnection.cursor.execute(sql, (suggestedCategory, taskId))                    
            # if skipped, mark it so not assigned in future
            else:
                sql = "update cascade_suggested_categories set skipped=1"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and (suggested_category is null and skipped=0)"
                dbConnection.cursor.execute(sql, (taskId))
            dbConnection.conn.commit()
            
            rowsUpdated = dbConnection.cursor.rowcount
            if rowsUpdated is None or rowsUpdated <= 0:
                unsavedTasks.append(taskId)
            
            # create CascadeBestCategory jobs for ideas with completed CascadeSuggestCategory jobs
            if question.cascade_k > 1:
                sql = "select idea_id, count(*) as ct from cascade_suggested_categories where question_id=%s and cascade_suggested_categories.idea_id=(select idea_id from cascade_suggested_categories where id=%s) and (suggested_category is not null or skipped=1)"
                dbConnection.cursor.execute(sql, (question.id, taskId))
                row = dbConnection.cursor.fetchone()
                if row["ct"] >= question.cascade_k:
                    CascadeBestCategory.create(dbConnection, question, row["idea_id"])
            else:
                CascadeBestCategory.create(dbConnection, question, task["idea_id"])

        if len(unsavedTasks) > 0:
            helpers.log("WARNING: CascadeSuggestedCategory tasks not saved: {0}".format(", ".join(unsavedTasks)))
            question.recordCascadeUnsavedTask(dbConnection, CascadeSuggestedCategory.type, len(unsavedTasks))
                               
class CascadeBestCategory(DBObject):
    type = constants.BEST_CATEGORY
    table = "cascade_best_categories"
    fields = [ "id", "question_id", "idea_id", "idea", "suggested_categories", "best_category", "none_of_the_above", "user_id" ]
    
    def __init__(self):
        self.id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas
        self.suggested_categories = [] # stored in cascade_suggested_categories
        self.best_category = None
        self.none_of_the_above = 0
        self.user_id = None
     
    @staticmethod
    def create(dbConnection, question, ideaId):
        insertValues = [ "({0}, {1})".format(question.id, ideaId) for i in range(question.cascade_k) ]
        sql = "insert into cascade_best_categories (question_id, idea_id) values {0}".format(",".join(insertValues))
        dbConnection.cursor.execute(sql)
        count = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return count
               
    @classmethod
    def createFromData(cls, data, dbConnection=None):
        task = super(CascadeBestCategory, cls).createFromData(data)
        if task and dbConnection:
            # suggested_categories are the unique, case-insensitive categories suggested for this idea in step 1
            sql = "select idea,suggested_category from cascade_suggested_categories,question_ideas where cascade_suggested_categories.idea_id=question_ideas.id and cascade_suggested_categories.idea_id=%s and suggested_category is not null"
            dbConnection.cursor.execute(sql, (task.idea_id))
            rows = dbConnection.cursor.fetchall()
            lowerCaseSuggestedCategories = []
            for row in rows:
                task.idea = row["idea"]
                suggestedCategory = row["suggested_category"]
                if suggestedCategory.lower() not in lowerCaseSuggestedCategories:
                    task.suggested_categories.append(row["suggested_category"])
                    lowerCaseSuggestedCategories.append(suggestedCategory.lower())
        return task

    @staticmethod
    def getJob(dbConnection, question, person):     
        tasks = []
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
            tasks.append(task)
             
        # if not, assign new tasks
        # do not check if user already performed task on idea when running locally
        if len(tasks) == 0:
            sql = "select * from cascade_best_categories where "
            sql += "question_id=%s " 
            sql += "and user_id is null "
            sql += "and idea_id not in (select distinct idea_id from cascade_best_categories where question_id=%s and user_id=%s) " if not helpers.allowDuplicateJobs() else ""
            sql += "group by idea_id order by rand() limit 1"
            if helpers.allowDuplicateJobs():
                dbConnection.cursor.execute(sql, (question.id,))
            else:
                dbConnection.cursor.execute(sql, (question.id, question.id, person.id))
            
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                task = CascadeBestCategory.createFromData(row, dbConnection)
                task.assignTo(dbConnection, person, commit=False)
                tasks.append(task)
            dbConnection.conn.commit()
                    
        return { "tasks" : tasks, "type" : CascadeBestCategory.type } if len(tasks) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):
        sql = "update cascade_best_categories set user_id=%s where id=%s"
        dbConnection.cursor.execute(sql, (person.id, self.id))
        if commit:
            dbConnection.conn.commit()
    
    @staticmethod
    def unassign(dbConnection, questionId, taskId):
        sql = "update cascade_best_categories set user_id=null where question_id=%s and id=%s"
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0
             
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        unsavedTasks = []
        for task in job:
            taskId = task["id"]
            bestCategory = task["best_category"]
            # save best category
            if bestCategory != "":
                sql = "update cascade_best_categories set best_category=%s"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and (best_category is null and none_of_the_above=0)"
                dbConnection.cursor.execute(sql, (bestCategory, taskId))   
                                 
            # vote for none of the above
            else:
                sql = "update cascade_best_categories set none_of_the_above=1"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and (best_category is null and none_of_the_above=0)"
                dbConnection.cursor.execute(sql, (taskId))
            
            dbConnection.conn.commit()

            rowsUpdated = dbConnection.cursor.rowcount
            if rowsUpdated is None or rowsUpdated <= 0:
                unsavedTasks.append(taskId)
                
            # create new CascadeFitCategory jobs
            sql = "select * from cascade_best_categories where question_id={0} and idea_id=(select idea_id from cascade_best_categories where id={1}) and (best_category is not null or none_of_the_above=1) and (best_category not in (select category from categories where question_id={0}))".format(question.id, taskId)
            dbConnection.cursor.execute(sql)
            rows = dbConnection.cursor.fetchall()
            # TODO: wait until all votes are in so user can compare to one another?
            # TODO / FRIDAY: continue here
            if len(rows) >= question.cascade_k:
                categoryVotes = {}
                for row in rows:
                    ideaId = row["idea_id"]
                    category = row["best_category"]
                    if category:
                        if category not in categoryVotes:
                            categoryVotes[category] = []
                        categoryVotes[category].append(row)
                    
                # TODO: consider whether or not it would be better to assign tasks in idea_id groups    
                # need to add new match tasks as new ideas, etc. come in ...
                # TODO: flag this idea as already fitting category?
                sql = "select * from question_ideas where question_id=%s"
                dbConnection.cursor.execute(sql, (question.id))
                ideaRows = dbConnection.cursor.fetchall()
                        
                votingThreshold = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>=3 else 1
                for category in categoryVotes:
                    if len(categoryVotes[category]) >= votingThreshold:
                        # TODO / COMMENT: categories holds "best" categories temporarily
                        sql = "insert into categories (question_id, category) values(%s, %s)"
                        dbConnection.cursor.execute(sql, (question.id, category))
                        dbConnection.conn.commit()
                        
                        # TODO: add getJob/saveJob to taskqueue? taskqueue.add(url="/cascade_init_step", params={ 'question_id' : self.question.id })
                        # TODO: notify any waiting users when new jobs available
                        # TODO: ideas may be added concurrently so its possible some might get missed or tasks duplicated when creating new cascade task as result of adding new idea?
                        for ideaRow in ideaRows:
                            CascadeFitCategory.create(dbConnection, question, ideaRow["id"], category)
                                
        if len(unsavedTasks) > 0:
            helpers.log("WARNING: CascadeBestCategory tasks not saved: {0}".format(", ".join(unsavedTasks)))
            question.recordCascadeUnsavedTask(dbConnection, CascadeBestCategory.type, len(unsavedTasks))
                        
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

class CascadeFitCategory(DBObject):
    type = constants.FIT_CATEGORY
    table = "cascade_fit_categories_phase1"
    fields = [ "id", "question_id", "idea_id", "idea", "category", "fit", "user_id" ]
   
    def __init__(self):
        self.id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas table
        self.category = None
        self.fit = 0
        self.user_id = None
    
    @staticmethod
    def create(dbConnection, question, ideaId, category):
        insertValues = ["({0}, {1}, %s)".format(question.id, ideaId) for i in range(question.cascade_k2)]
        categories = (category for i in range(question.cascade_k2))
        sql = "insert into cascade_fit_categories_phase1 (question_id, idea_id, category) values {0}".format(",".join(insertValues))
        dbConnection.cursor.execute(sql, tuple(categories))
        count = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return count
                
    @classmethod
    def createFromData(cls, data):
        task = super(CascadeFitCategory, cls).createFromData(data)
        if task:
            ideaField = "idea" if "idea" in data else Idea.tableField("idea") if Idea.tableField("idea") in data else None
            if ideaField:
                task.idea = data[ideaField]
            else:
                helpers.log("WARNING: idea not included in task data")
        return task
            
    @staticmethod
    def getJob(dbConnection, question, person): 
        tasks = []
        # check if job already assigned
        sql = "select cascade_fit_categories_phase1.*,idea from cascade_fit_categories_phase1,question_ideas where "
        sql += "cascade_fit_categories_phase1.idea_id=question_ideas.id and "
        sql += "cascade_fit_categories_phase1.question_id=%s and "
        sql += "cascade_fit_categories_phase1.user_id=%s and "
        sql += "fit=-1"
            
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeFitCategory.createFromData(row)
            tasks.append(task)
             
        # if not, assign new tasks
        # do not check if user already performed task on idea when running locally
        # ask user to check whether all categories fit or not for an idea (regardless of how many)
        if len(tasks) == 0:
            # find an idea that still needs categories checked
            sql = "select idea_id from cascade_fit_categories_phase1 where "
            sql += "question_id=%s "
            sql += "and user_id is null "
            sql += "and (idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase1 where question_id=%s and user_id=%s) " if not helpers.allowDuplicateJobs() else ""
            sql += "order by rand() limit 1"
            if helpers.allowDuplicateJobs():
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
                sql += "and (cascade_fit_categories_phase1.idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase1 where question_id=%s and user_id=%s) " if not helpers.allowDuplicateJobs() else ""
                sql += "group by category order by rand() limit {0}".format(question.cascade_t)                    
                if helpers.allowDuplicateJobs():
                    dbConnection.cursor.execute(sql, (question.id, ideaId))
                else:
                    dbConnection.cursor.execute(sql, (question.id, ideaId, question.id, person.id))
                
                rows = dbConnection.cursor.fetchall()
                for row in rows:
                    task = CascadeFitCategory.createFromData(row)
                    task.assignTo(dbConnection, person, commit=False)
                    tasks.append(task)
                dbConnection.conn.commit()
                
        return { "tasks" : tasks, "type" : CascadeFitCategory.type } if len(tasks) > 0 else None
     
    def assignTo(self, dbConnection, person, commit=True):
        sql = "update cascade_fit_categories_phase1 set user_id=%s where id=%s"
        dbConnection.cursor.execute(sql, (person.id, self.id))
        if commit:
            dbConnection.conn.commit()
    
    @staticmethod
    def unassign(dbConnection, questionId, taskId):
        sql = "update cascade_fit_categories_phase1 set user_id=null where question_id=%s and id=%s"
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0
            
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        unsavedTasks = []
        for task in job:
            taskId = task["id"]
            fit = task["fit"]
            sql = "update cascade_fit_categories_phase1 set fit=%s"
            sql += ", user_id={0} ".format(person.id) if person else " "
            sql += "where id=%s and fit=-1"
            dbConnection.cursor.execute(sql, (fit, taskId))
            rowsUpdated = dbConnection.cursor.rowcount
            if rowsUpdated is None or rowsUpdated <= 0:
                unsavedTasks.append(taskId)
        dbConnection.conn.commit()
        
        if len(unsavedTasks) > 0:
            helpers.log("WARNING: CascadeFitCategory tasks not saved: {0}".format(", ".join(unsavedTasks)))
            question.recordCascadeUnsavedTask(dbConnection, CascadeBestCategory.type, len(unsavedTasks))
            
        if CascadeFitCategory.isStepComplete(dbConnection, question):
            GenerateCascadeHierarchy(dbConnection, question)
                
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_fit_categories_phase1 where question_id=%s and fit=-1"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0
              
def GenerateCascadeHierarchy(dbConnection, question):
    question.update(dbConnection, { "cascade_complete" : 1, "id" : question.id })
    categories = {}
    ideas = {}

    # if step 4 skipped, check for any categories that passed step 3 (this includes any subsequent items)      
    sql = "select idea_id,idea,category,count(*) as ct from cascade_fit_categories_phase1,question_ideas where "
    sql += "cascade_fit_categories_phase1.idea_id=question_ideas.id "
    sql += "and cascade_fit_categories_phase1.question_id=%s "
    sql += "and fit=1 "
    sql += "group by idea_id,category "
    sql += "having ct>=%s"
    # TODO: how should voting threshold be determined
    minCount = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>=3 else 1
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
    
    # remove any duplicate categories (that have more than p % of overlapping items)
    # TODO/FIX: consider whether not duplicate categories should only be removed last time it is called in case subsequent categories change things?
    duplicateCategories = {}
    if question.cascade_p > 0:
        categoriesToRemove = []
        categoryKeys = categories.keys()
        for x in range(len(categoryKeys)):
            for y in range(x, len(categoryKeys)):
                if x != y:
                    category1 = categoryKeys[x]
                    category2 = categoryKeys[y]
                    ideaIds1 = categories[category1]
                    ideaIds2 = categories[category2]
                    sharedIdeaIds = helpers.intersect(ideaIds1, ideaIds2)
                    if len(sharedIdeaIds) >= max(len(ideaIds1),len(ideaIds2))*(question.cascade_p/100.0):
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

def toggleCascadeItemSet(question):
    client = memcache.Client()
    key = "cascade_item_set_{0}".format(question.id)
    MAX_RETRIES = 15
    
    i = 0
    while i <= MAX_RETRIES: # Retry loop
        itemSet = client.gets(key)
        if itemSet is None:
            newItemSet = constants.CASCADE_INITIAL_ITEM_SET
            client.add(key, newItemSet)
            break
        else:
            newItemSet = constants.CASCADE_INITIAL_ITEM_SET if itemSet==constants.CASCADE_SUBSEQUENT_ITEM_SET else constants.CASCADE_SUBSEQUENT_ITEM_SET
            if client.cas(key, newItemSet):
                break
        i += 1
        if i > MAX_RETRIES:
            helpers.log("WARNING: Unable to toggle cascade item set")
     
    return newItemSet
    
def deleteCascadeMemcache(question):
    client = memcache.Client()
    key = "cascade_item_set_{0}".format(question.id)
    client.delete(key)
    
def getCascadeClass(type):
    if not type or type < 1 or type > len(CASCADE_CLASSES):
        helpers.log("ERROR: Unknown type passed to getCascadeClass")
        return None
    return CASCADE_CLASSES[type-1]

CASCADE_CLASSES = [ CascadeSuggestedCategory, CascadeBestCategory, CascadeFitCategory ]

# TODO / PUBLISH: added column item_set to question_ideas table in db
# TODO / PUBLISH: change db defaults for cascade settings to 0
# TODO: update database structure sql
# TODO: no longer using cascade_times table in db
# TODO: no longer using  iteration_count, stepX_duration, total_duration in cascade_stats table in db
# TODO: no longer using cascade_iteration or subsequent fileds in cascade_suggested_categories, cascade_best_categories, cascade_fit_categories_phase1
# TODO: no longer using cascade_fit_categores_phase2 table
# TODO: no longer using phase, cascade_iteration, cascade_step_count in questions table

