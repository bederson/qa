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
import time
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
    fields = [ "id", "title", "question", "nickname_authentication", "user_id", "active", "cascade_k", "cascade_k2", "cascade_m", "cascade_p", "cascade_s", "cascade_t", "cascade_complete" ]  
    onCascadeSettingsChanged = None
    onNewCategory = None
    onFitComplete = None
    onMoreJobs = None
    
    def __init__(self):
        self.id = None
        self.title = None
        self.question = None
        self.nickname_authentication = False
        self.user_id = None
        self.authenticated_user_id = None # stored in users table
        self.active = 0
        self.cascade_k = 0
        self.cascade_k2 = 0
        self.cascade_m = 0
        self.cascade_p = 0
        self.cascade_s = 0
        self.cascade_t = 0
        self.cascade_complete = 0
        
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
            if not active and not self.cascade_complete:
                dbConnection.cursor.execute("update cascade_suggested_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeSuggestCategory.incompleteCondition))
                dbConnection.cursor.execute("update cascade_best_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeBestCategory.incompleteCondition))
                dbConnection.cursor.execute("update cascade_fit_categories_phase1 set user_id=null where question_id={0} and {1}".format(self.id, CascadeFitCategory.incompleteCondition))
                dbConnection.conn.commit()
            self.update(dbConnection, { "active" : active, "id" : self.id })
    
    def setCascadeSettings(self, dbConnection):
        userCount = Person.getCountForQuestion(dbConnection, self.id, loggedIn=True)
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
            "cascade_s" : 4,
            "cascade_t" : 3,
            "id" : self.id
        }
        self.update(dbConnection, properties)
        
        if Question.onCascadeSettingsChanged:
            self.onCascadeSettingsChanged(dbConnection) 
           
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
            
    def unassignCascadeJob(self, dbConnection, job):
        count = 0
        if job:
            cls = getCascadeClass(job["type"])
            for task in job["tasks"]:
                count += cls.unassign(dbConnection, self.id, task["id"])
        return count
    
    def unassignIncompleteCascadeJobs(self, dbConnection):
        dbConnection.cursor.execute("update cascade_suggested_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeSuggestCategory.incompleteCondition))
        dbConnection.cursor.execute("update cascade_best_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeBestCategory.incompleteCondition))
        dbConnection.cursor.execute("update cascade_fit_categories_phase1 set user_id=null where question_id={0} and {1}".format(self.id, CascadeFitCategory.incompleteCondition))
        dbConnection.conn.commit()
    
    def clearWaiting(self, dbConnection):
        sql = "update user_clients,users set waiting_since=null where user_clients.user_id=users.id and question_id=%s"
        dbConnection.cursor.execute(sql, (self.id))
        dbConnection.conn.commit()
                    
    def cascadeComplete(self, dbConnection):
        self.update(dbConnection, { "cascade_complete" : 1, "id" : self.id })
        recordCascadeEndTime(self) 
        stats = self.recordCascadeStats(dbConnection)
        return stats
    
    def calculateCascadeStats(self, dbConnection):
        stats = {}                 
        if self.cascade_complete:              
            # user count updated (based on how many people category fit tasks)
            sql = "select count(distinct user_id) as ct from cascade_fit_categories_phase1 where question_id=%s and user_id is not null"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            userCount = row["ct"] if row else 0
                         
            # category count
            sql = "select count(*) as ct from categories where question_id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            categoryCount = row["ct"] if row else 0
            
            # idea count
            ideaCount = Idea.getCountForQuestion(dbConnection, self.id)
            
            # uncategorized count
            sql = "select count(*) as ct from question_ideas left join question_categories on question_ideas.id=question_categories.idea_id where question_ideas.question_id=%s and category_id is null"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            uncategorizedCount = row["ct"] if row else 0
            
            # total duration
            totalDuration = getCascadeDuration(self)
            
            stats["user_count"] = userCount
            stats["idea_count"] = ideaCount
            stats["category_count"] = categoryCount
            stats["uncategorized_count"] = uncategorizedCount
            stats["total_duration"] = totalDuration
            
        return stats
                            
    def recordCascadeStats(self, dbConnection): 
        stats = {}                  
        if self.cascade_complete:      
            stats = self.calculateCascadeStats(dbConnection)        
            sql = "update cascade_stats set user_count=%s, category_count=%s, idea_count=%s, uncategorized_count=%s, total_duration=%s where question_id=%s"
            dbConnection.cursor.execute(sql, (stats["user_count"], stats["category_count"], stats["idea_count"], stats["uncategorized_count"], stats["total_duration"], self.id))
            dbConnection.conn.commit()
        return stats
        
    def recordCascadeUnsavedTask(self, dbConnection, step, unsavedCount):
        # TODO: consider saving to memcache, and then save to db when cascade is complete
        try:
            dbConnection.conn.begin()
            sql = "select * from cascade_stats where question_id=%s for update"
            dbConnection.cursor.execute(sql, (self.id))
            sql = "update cascade_stats set step{0}_unsaved_count = step{0}_unsaved_count + {1} where question_id=%s".format(step, unsavedCount)
            dbConnection.cursor.execute(sql, (self.id))
            dbConnection.conn.commit()
        except:
            dbConnection.conn.rollback()
            # TODO: reissue task
                
    def getQuestionStats(self, dbConnection):
        stats = {}
        stats["question_id"] = self.id
        stats["user_count"] = Person.getCountForQuestion(dbConnection, self.id)
        stats["active_user_count"] = Person.getCountForQuestion(dbConnection, self.id, loggedIn=True)    
        stats["idea_count"] = Idea.getCountForQuestion(dbConnection, self.id) 
        stats["cascade_stats"] = self.getCascadeStats(dbConnection)
        return stats
    
    def getCascadeStats(self, dbConnection):
        stats = None
        if self.cascade_complete:
            sql = "select * from cascade_stats where question_id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            stats = {}
            stats["user_count"] = row["user_count"] if row else 0
            stats["idea_count"] = row["idea_count"] if row else 0
            stats["category_count"] = row["category_count"] if row else 0
            stats["uncategorized_count"] = row["uncategorized_count"] if row else 0
            stats["total_duration"] = row["total_duration"] if row else 0
        else:
            stats = {}
            # category count while cascade in progress
            sql = "select count(*) as ct from categories where question_id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            stats["category_count"] = row["ct"] if row else 0
            
            # number of CascadeFitCategory jobs completed so far
            sql = "select count(*) as ct from cascade_fit_categories_phase1 where question_id=%s and {0}".format(CascadeFitCategory.completeCondition)
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            stats["completed_fit_count"] = row["ct"] if row else 0
            
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
        self.update(dbConnection, { "cascade_k" : 0, "cascade_k2" : 0, "cascade_m" : 0, "cascade_p" : 0, "cascade_s" : 0, "cascade_t" : 0, "cascade_complete" : 0, "id" : self.id }, commit=False)
        dbConnection.cursor.execute("update user_clients,users set waiting_since=null where user_clients.user_id=users.id and question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_suggested_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_best_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_fit_categories_phase1 where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_stats where question_id={0}".format(self.id))
        if commit:
            dbConnection.conn.commit()

        clearMemcache(self)
                                        
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
            sql = "select {0}, users.authenticated_user_id from questions,users where questions.user_id=users.id and authenticated_user_id=%s order by last_update desc".format(Question.fieldsSql())
            dbConnection.cursor.execute(sql, (user.user_id()))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                question = Question.createFromData(row)
                questionDict = question.toDict()
                questions.append(questionDict)
                
            # FOR TESTING ONLY: allows question(s) not authored by user to displayed for selected user
#             if user.nickname() == "xx":
#                 sql = "select {0}, users.authenticated_user_id from questions,users where questions.user_id=users.id and questions.id=%s order by last_update desc".format(Question.fieldsSql())
#                 dbConnection.cursor.execute(sql, (32350))
#                 rows = dbConnection.cursor.fetchall()
#                 for row in rows:
#                     question = Question.createFromData(row)
#                     questionDict = question.toDict()
#                     questions.append(questionDict)
                
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
  
    def logout(self, dbConnection, userRequestedLogout=True):
        if self.is_logged_in:
            # if a Google authenticated user is actively logging out (clicked on Logout), 
            # modify all records associated with this user            
            if userRequestedLogout and self.authenticated_user_id:
                sql = "update users set latest_logout_timestamp=now(), session_sid=null where authenticated_user_id=%s"
                dbConnection.cursor.execute(sql, (self.authenticated_user_id))
    
            # otherwise, logout this specific user instance
            else:
                sql = "update users set latest_logout_timestamp=now(), session_sid=null where id=%s"
                dbConnection.cursor.execute(sql, (self.id))
                        
            dbConnection.conn.commit()
            self.session_sid = None     
            self.is_logged_in = False
            
            if Person.onLogout:
                Person.onLogout(self, dbConnection)
                        
    def addClient(self, dbConnection, clientId):   
        sql = "insert into user_clients (user_id, client_id) values(%s, %s)"
        dbConnection.cursor.execute(sql, (self.id, clientId))
        dbConnection.conn.commit()
     
    def removeClient(self, dbConnection, clientId, returnNumClients=False):
        sql = "delete from user_clients where client_id=%s"
        dbConnection.cursor.execute(sql, (clientId))
        dbConnection.conn.commit()
        
        numClients = 0
        if returnNumClients:
            sql = "select count(*) as ct from user_clients where user_id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            numClients = row["ct"] if row else 0
            
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
    def waiting(dbConnection, clientId):
        sql = "update user_clients set waiting_since=now() where client_id=%s"
        dbConnection.cursor.execute(sql, (clientId))
        dbConnection.conn.commit()
   
    @staticmethod
    def working(dbConnection, clientId):
        sql = "update user_clients set waiting_since=null where client_id=%s"
        dbConnection.cursor.execute(sql, (clientId))
        dbConnection.conn.commit()
                             
    @staticmethod
    def isAdmin():
        return users.is_current_user_admin()
    
    @staticmethod
    def isAuthor(question):
        # BEHAVIOR: check if currently authenticated user is the question author
        # currently only authenticated users can create questions
        user = users.get_current_user()
        return user and question and question.authenticated_user_id and user.user_id()==question.authenticated_user_id
   
    @staticmethod
    def getPerson(dbConnection, question=None, nickname=None):
        person = None
        user = users.get_current_user()

        # if question allows nickname authentication and nickname given, check for user
        # question author does not have to login with nickname if already authenticated
        if question is not None and question.nickname_authentication and nickname is not None and not Person.isAuthor(question):
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
            if not person and question is not None and Person.isAuthor(question):
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
        
        # initialize cascade settings when first idea added
        if question.cascade_k == 0:
            question.setCascadeSettings(dbConnection)
            sql = "insert into cascade_stats (question_id) values (%s)"
            dbConnection.cursor.execute(sql, (question.id))            
            dbConnection.conn.commit()   
            recordCascadeStartTime(question) 

        # create any new cascade jobs
        Idea.createCascadeJobs(dbConnection, question, idea)                         
        return idea
     
    @staticmethod
    def createCascadeJobs(dbConnection, question, idea):
        moreJobs = False
        # create CascadeSuggestCategory job for idea
        if idea.item_set == constants.CASCADE_INITIAL_ITEM_SET:
            CascadeSuggestCategory.create(dbConnection, question, idea.id)
            moreJobs = True
        
        # create CascadeFitCategory jobs for idea
        count = CascadeFitCategory.createForAllCategories(dbConnection, question, idea.id)
        if count > 0:
            moreJobs = True
        
        if moreJobs and Question.onMoreJobs:
            question.onMoreJobs(dbConnection)
            
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
                    idea = idea.toDict(author=author, admin=Person.isAdmin() or Person.isAuthor(question))
                    if includeCreatedOn:
                        idea["created_on"] = row["idea_created_on"]
                                           
                ideas.append(idea)
        return ideas
        
    @staticmethod
    def getByCategories(dbConnection, question, includeCreatedOn=False, includeAlsoIn=False, useTestCategories=False):
        ideaIds = []
        categorizedIdeas = []
        category = None
        categoryIdeas = []
        uncategorizedIdeas = []
        allIdeaCategories = {}
        categorySizes = {}
        
        categoriesTable = "categories" if not useTestCategories else "categories2"
        questionCategoriesTable = "question_categories" if not useTestCategories else "question_categories2"
        
        if question:
            # group alphabetically by category name
            sql = "select {0},{1},question_ideas.created_on as idea_created_on,subcategories,category,same_as from question_ideas ".format(Idea.fieldsSql(), Person.fieldsSql())
            sql += "left join {0} on question_ideas.id={0}.idea_id ".format(questionCategoriesTable)
            sql += "left join {0} on {1}.category_id={0}.id ".format(categoriesTable, questionCategoriesTable)
            sql += "left join users on question_ideas.user_id=users.id where "
            sql += "question_ideas.question_id=%s "
            sql += "order by category,idea"
            dbConnection.cursor.execute(sql, (question.id))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                ideaCategory = row["category"]
                ideaSameAs = row["same_as"]
                categorySubcategories = row["subcategories"].split(":::") if row["subcategories"] else []
                idea = Idea.createFromData(row)
                ideaId = idea.id
                ideaAuthor = {
                    "authenticated_nickname" : row[Person.tableField("authenticated_nickname")] if not question.nickname_authentication else None,
                    "nickname" : row[Person.tableField("nickname")]
                }
                idea = idea.toDict(author=ideaAuthor, admin=Person.isAdmin() or Person.isAuthor(question))
                if includeCreatedOn:
                    idea["created_on"] = row["idea_created_on"]
                    
                if ideaCategory: 
                    if not category:
                        category = ideaCategory
                        sameAs = ideaSameAs
                        subcategories = categorySubcategories
                                        
                    if category != ideaCategory:
                        if len(categoryIdeas) > 0:
                            categorizedIdeas.append({ "category" : category , "subcategories" : subcategories, "same_as" : sameAs, "ideas" : categoryIdeas })
                            categorySizes[category] = len(categoryIdeas);
                        category = ideaCategory
                        sameAs = ideaSameAs
                        subcategories = categorySubcategories
                        categoryIdeas = []
                        
                    categoryIdeas.append(idea)
                    
                else:
                    uncategorizedIdeas.append(idea)
        
                ideaIds.append(ideaId)
                
                if includeAlsoIn:
                    if ideaId not in allIdeaCategories:
                        allIdeaCategories[ideaId] = []
                    allIdeaCategories[ideaId].append(ideaCategory)
                                               
            if len(categoryIdeas) > 0:
                categorizedIdeas.append({ "category" : category, "subcategories" : subcategories, "same_as" : sameAs, "ideas" : categoryIdeas })
               
        if includeAlsoIn:
            for i, group in enumerate(categorizedIdeas):
                for j, idea in enumerate(group["ideas"]):
                    ideaId = idea["id"]
                    alsoIn = []
                    if len(allIdeaCategories[ideaId]) > 0:
                        alsoIn = allIdeaCategories[ideaId][:]
                        alsoIn.remove(group["category"])
                    categorizedIdeas[i]["ideas"][j]["also_in"] = alsoIn
                
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

# BEHAVIOR: new cascade jobs are created when new ideas are submitted submitted and existing cascade jobs are completed
# BEHAVIOR: users are restricted to unique cascade jobs when running on GAE which means >= k users required to complete cascade 
# BEHAVIOR: introduced cascade_k2 to use for category fit jobs since large number of fit jobs required to complete cascade
# BEHAVIOR: categories with fewer than CASCADE_Q items removed
# BEHAVIOR: duplicate categories merged (the % of overlapping items used to detect duplicates is defined by cascade_p)
# BEHAVIOR: nested categories not generated
    
class CascadeSuggestCategory(DBObject):
    type = constants.SUGGEST_CATEGORY
    table = "cascade_suggested_categories"
    fields = [ "id", "question_id", "idea_id", "idea", "suggested_category", "skipped", "user_id" ]
    completeCondition = "(suggested_category is not null or skipped=1)"
    incompleteCondition = "(suggested_category is null and skipped=0)"
        
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
        dbConnection.conn.commit()
                
    @classmethod
    def createFromData(cls, data):
        task = super(CascadeSuggestCategory, cls).createFromData(data)
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
        sql += CascadeSuggestCategory.incompleteCondition
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeSuggestCategory.createFromData(row)
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
                task = CascadeSuggestCategory.createFromData(row)
                task.assignTo(dbConnection, person, commit=False)
                tasks.append(task)
            dbConnection.conn.commit()
        
        return { "tasks" : tasks, "type" : CascadeSuggestCategory.type } if len(tasks) > 0 else None
                 
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        unsavedTasks = []
        for task in job:
            taskId = task["id"]
            suggestedCategory = task["suggested_category"].strip() if task["suggested_category"] is not None else ""
            # save suggested category
            if suggestedCategory != "":
                sql = "update cascade_suggested_categories set suggested_category=%s"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and {0}".format(CascadeSuggestCategory.incompleteCondition)
                dbConnection.cursor.execute(sql, (suggestedCategory, taskId))                    
            # if skipped, mark it so not assigned in future
            else:
                sql = "update cascade_suggested_categories set skipped=1"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and {0}".format(CascadeSuggestCategory.incompleteCondition)
                dbConnection.cursor.execute(sql, (taskId))
            dbConnection.conn.commit()
            
            rowsUpdated = dbConnection.cursor.rowcount
            if rowsUpdated is None or rowsUpdated <= 0:
                unsavedTasks.append(str(taskId))
            
            # create any new cascade jobs
            CascadeSuggestCategory.createCascadeJobs(dbConnection, question, task)

        if len(unsavedTasks) > 0:
            helpers.log("WARNING: CascadeSuggestCategory tasks not saved for question {0}: {1}".format(question.id, ", ".join(unsavedTasks)))
            question.recordCascadeUnsavedTask(dbConnection, CascadeSuggestCategory.type, len(unsavedTasks))
    
    @staticmethod
    def createCascadeJobs(dbConnection, question, task):
        # create CascadeBestCategory jobs for task idea if CascadeSuggestCategory job complete
        moreJobs = False
        if question.cascade_k > 1:
            sql = "select idea_id, suggested_category from cascade_suggested_categories where question_id=%s and cascade_suggested_categories.idea_id=(select idea_id from cascade_suggested_categories where id=%s) and {0}".format(CascadeSuggestCategory.completeCondition)
            dbConnection.cursor.execute(sql, (question.id, task["id"]))
            rows = dbConnection.cursor.fetchall()
            
            # make sure at least one category was suggested (could have just skipped them all)
            atLeastOneSuggestedCategory = False
            for row in rows:
                if row["suggested_category"]:
                    atLeastOneSuggestedCategory = True
                    break
                
            if len(rows) >= question.cascade_k and atLeastOneSuggestedCategory:
                CascadeBestCategory.create(dbConnection, question, row["idea_id"])
                moreJobs = True
                
        elif task["suggested_category"]:
            CascadeBestCategory.create(dbConnection, question, task["idea_id"])
            moreJobs = True
            
        if moreJobs and Question.onMoreJobs:
            question.onMoreJobs(dbConnection)
                
    def assignTo(self, dbConnection, person, commit=True):  
        self.update(dbConnection, { "user_id": person.id, "id": self.id }, commit=commit)

    @staticmethod
    def unassign(dbConnection, questionId, taskId):
        sql = "update cascade_suggested_categories set user_id=null where question_id=%s and id=%s"
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0
                               
class CascadeBestCategory(DBObject):
    type = constants.BEST_CATEGORY
    table = "cascade_best_categories"
    fields = [ "id", "question_id", "idea_id", "idea", "suggested_categories", "best_category", "none_of_the_above", "user_id" ]
    completeCondition = "(best_category is not null or none_of_the_above=1)"
    incompleteCondition = "(best_category is null and none_of_the_above=0)"
    
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
        dbConnection.conn.commit()
               
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
        sql += CascadeBestCategory.incompleteCondition
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
                sql += "where id=%s and {0}".format(CascadeBestCategory.incompleteCondition)
                dbConnection.cursor.execute(sql, (bestCategory, taskId))   
                                 
            # vote for none of the above
            else:
                sql = "update cascade_best_categories set none_of_the_above=1"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and {0}".format(CascadeBestCategory.incompleteCondition)
                dbConnection.cursor.execute(sql, (taskId))
            
            dbConnection.conn.commit()

            rowsUpdated = dbConnection.cursor.rowcount
            if rowsUpdated is None or rowsUpdated <= 0:
                unsavedTasks.append(str(taskId))
            
            # create any new cascade jobs
            CascadeBestCategory.createCascadeJobs(dbConnection, question, task)
                                
        if len(unsavedTasks) > 0:
            helpers.log("WARNING: CascadeBestCategory tasks not saved for question {0}: {1}".format(question.id, ", ".join(unsavedTasks)))
            question.recordCascadeUnsavedTask(dbConnection, CascadeBestCategory.type, len(unsavedTasks))
    
    @staticmethod
    def createCascadeJobs(dbConnection, question, task):
        moreJobs = False
        # create CascadeFitCategory jobs for task idea if CascadeBestCategory job is complete
        sql = "select * from cascade_best_categories where question_id={0} and ".format(question.id)
        sql += "idea_id=(select idea_id from cascade_best_categories where id={0}) and ".format(task["id"])
        sql += "{0} and ".format(CascadeBestCategory.completeCondition)
        sql += "(best_category not in (select category from categories where question_id={0}))".format(question.id)
        dbConnection.cursor.execute(sql)
        rows = dbConnection.cursor.fetchall()
        if len(rows) >= question.cascade_k:
            categoryVotes = {}
            for row in rows:
                ideaId = row["idea_id"]
                category = row["best_category"]
                if category:
                    if category not in categoryVotes:
                        categoryVotes[category] = []
                    categoryVotes[category].append(row)
                    
            # check if any "best" categories pass the voting threshold
            # if so ...
            # temporarily save to the categories table, and
            # create CascadeFitCategory jobs for all ideas  
            # TODO: consider whether or not the task idea should be marked as already fitting this category
            votingThreshold = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>3 else 1
            for category in categoryVotes:
                if len(categoryVotes[category]) >= votingThreshold:
                    sql = "insert into categories (question_id, category) values(%s, %s)"
                    dbConnection.cursor.execute(sql, (question.id, category))
                    dbConnection.conn.commit()
                    if Question.onNewCategory:
                        question.onNewCategory(dbConnection, category)
                    CascadeFitCategory.createForAllIdeas(dbConnection, question, category)
                    moreJobs = True
                    
        if moreJobs and Question.onMoreJobs:
            question.onMoreJobs(dbConnection)
            
    def assignTo(self, dbConnection, person, commit=True):
        self.update(dbConnection, { "user_id": person.id, "id": self.id }, commit=commit)
    
    @staticmethod
    def unassign(dbConnection, questionId, taskId):
        sql = "update cascade_best_categories set user_id=null where question_id=%s and id=%s"
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0
                    
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
    completeCondition = "(fit!=-1)"
    incompleteCondition = "(fit=-1)"
   
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
        dbConnection.conn.commit()
    
    @staticmethod
    def createForAllIdeas(dbConnection, question, category):
        sql = "select * from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        insertValues = []
        for row in rows:
            insertValues.extend(["({0}, {1}, %s)".format(question.id, row["id"]) for i in range(question.cascade_k2)])
        categories = (category for i in range(len(rows)*question.cascade_k2))
        sql = "insert into cascade_fit_categories_phase1 (question_id, idea_id, category) values {0}".format(",".join(insertValues))
        dbConnection.cursor.execute(sql, tuple(categories))
        count = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return count
     
    @staticmethod
    def createForAllCategories(dbConnection, question, ideaId):
        sql = "select * from categories where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        count = 0
        if len(rows) > 0:
            insertValues = []
            categories = ()
            for row in rows:
                insertValues.extend(["({0}, {1}, %s)".format(question.id, ideaId) for i in range(question.cascade_k2)])
                categories += (row["category"],)  
            sql = "insert into cascade_fit_categories_phase1 (question_id, idea_id, category) values {0}".format(",".join(insertValues))
            dbConnection.cursor.execute(sql, categories)
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
        sql += CascadeFitCategory.incompleteCondition
            
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
                sql += "group by category order by rand() limit {0}".format(question.cascade_s)                    
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
                 
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        unsavedTasks = []
        for task in job:
            taskId = task["id"]
            fit = task["fit"]
            sql = "update cascade_fit_categories_phase1 set fit=%s"
            sql += ", user_id={0} ".format(person.id) if person else " "
            sql += "where id=%s and {0}".format(CascadeFitCategory.incompleteCondition)
            dbConnection.cursor.execute(sql, (fit, taskId))
            rowsUpdated = dbConnection.cursor.rowcount
            if rowsUpdated is None or rowsUpdated <= 0:
                unsavedTasks.append(str(taskId))
        dbConnection.conn.commit()
        
        if Question.onFitComplete:
            question.onFitComplete(dbConnection, len(job)-len(unsavedTasks))
        
        if len(unsavedTasks) > 0:
            helpers.log("WARNING: CascadeFitCategory tasks not saved for question {0}: {1}".format(question.id, ", ".join(unsavedTasks)))
            question.recordCascadeUnsavedTask(dbConnection, CascadeBestCategory.type, len(unsavedTasks))
            
        if CascadeFitCategory.isStepComplete(dbConnection, question):
            GenerateCascadeHierarchy(dbConnection, question)
    
    def assignTo(self, dbConnection, person, commit=True):
        self.update(dbConnection, { "user_id": person.id, "id": self.id }, commit=commit)
    
    @staticmethod
    def unassign(dbConnection, questionId, taskId):
        sql = "update cascade_fit_categories_phase1 set user_id=null where question_id=%s and id=%s"
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0
                
    @staticmethod
    def isStepComplete(dbConnection, question):
        sql = "select count(*) as ct from cascade_fit_categories_phase1 where question_id=%s and {0}".format(CascadeFitCategory.incompleteCondition)
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        return row["ct"] == 0
              
def GenerateCascadeHierarchy(dbConnection, question, forTesting=False): 
    categoriesTable = "categories" if not forTesting else "categories2"
    questionCategoriesTable = "question_categories" if not forTesting else "question_categories2"

    categories = {}
    ideas = {}
    sql = "select idea_id,idea,category,count(*) as ct from cascade_fit_categories_phase1,question_ideas where "
    sql += "cascade_fit_categories_phase1.idea_id=question_ideas.id "
    sql += "and cascade_fit_categories_phase1.question_id=%s "
    sql += "and fit=1 "
    sql += "group by idea_id,category "
    sql += "having ct>=%s"
    # TODO: how should voting threshold be determined
    minCount = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>3 else 1
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
    
    duplicateCategories = {}
    nestedCategories = {}
    
    if question.cascade_p > 0 or constants.FIND_SUBCATEGORIES:
        categoriesToRemove = []
        categoryKeys = categories.keys()
        for x in range(len(categoryKeys)):
            for y in range(x, len(categoryKeys)):
                if x != y:
                    category1 = categoryKeys[x]
                    category2 = categoryKeys[y]
                    ideaIds1 = categories[category1]
                    ideaIds2 = categories[category2]

                    if question.cascade_p > 0:                            
                        sharedIdeaIds = helpers.intersect(ideaIds1, ideaIds2)
                        sizePercentage = (min(len(ideaIds1),len(ideaIds2)) / float(max(len(ideaIds1),len(ideaIds2))))*100
                        duplicateThreshold = min(len(ideaIds1),len(ideaIds2))*(question.cascade_p/100.0)
                        nestedThreshold = min(len(ideaIds1),len(ideaIds2))*(question.cascade_p/100.0)
                        
                        # find duplicate categories (that have more than p % of overlapping items)
                        duplicateFound = False
                        if sizePercentage >= constants.MIN_DUPLICATE_CATEGORY_PERCENTAGE and len(sharedIdeaIds) >= duplicateThreshold:
                            duplicateCategory = category1 if len(ideaIds1) < len(ideaIds2) else category2
                            primaryCategory = category1 if duplicateCategory != category1 else category2
                            if duplicateCategory not in categoriesToRemove:
                                categoriesToRemove.append(duplicateCategory)
                            if primaryCategory not in duplicateCategories:
                                duplicateCategories[primaryCategory] = []
                            duplicateCategories[primaryCategory].append(duplicateCategory)
                            duplicateFound = True

                        # find any nested categories (make sure they aren't flagged to be removed)   
                        if constants.FIND_SUBCATEGORIES and sizePercentage < constants.MIN_DUPLICATE_CATEGORY_PERCENTAGE and len(sharedIdeaIds) >= nestedThreshold:
                            primaryCategory = category1 if len(ideaIds1) > len(ideaIds2) else category2
                            subCategory = category2 if primaryCategory == category1 else category1
                            if primaryCategory not in categoriesToRemove or subCategory not in categoriesToRemove:
                                if primaryCategory not in nestedCategories:
                                    nestedCategories[primaryCategory] = []
                                nestedCategories[primaryCategory].append(subCategory)
        
        # remove duplicate categories               
        for category in categoriesToRemove:
            del categories[category]
        
    sql = "delete from {0} where question_id=%s".format(questionCategoriesTable)
    dbConnection.cursor.execute(sql, (question.id))
 
    sql = "delete from {0} where question_id=%s".format(categoriesTable)
    dbConnection.cursor.execute(sql, (question.id))
    
    # TODO: inserts are faster if done as a group
    for category in categories:
        ideaIds = categories[category]
        sameAs = ", ".join(duplicateCategories[category]) if category in duplicateCategories else None
        subcategories = ":::".join(nestedCategories[category]) if category in nestedCategories else None
        sql = "insert into {0} (question_id, category, same_as, subcategories) values(%s, %s, %s, %s)".format(categoriesTable)
        dbConnection.cursor.execute(sql, (question.id, category, sameAs, subcategories))
        categoryId = dbConnection.cursor.lastrowid
        for ideaId in ideaIds:
            sql = "insert into {0} (question_id, idea_id, category_id) values(%s, %s, %s)".format(questionCategoriesTable)
            dbConnection.cursor.execute(sql, (question.id, ideaId, categoryId))
                    
    dbConnection.conn.commit()
    
    stats = question.cascadeComplete(dbConnection) if not forTesting else question.getCascadeStats(dbConnection)
    return stats

def clearMemcache(question):
    client = memcache.Client() 
    client.delete("cascade_start_time_{0}".format(question.id))
    client.delete("cascade_end_time_{0}".format(question.id))
    client.delete("cascade_item_set_{0}".format(question.id))
    
def recordCascadeStartTime(question):
    helpers.saveToMemcache("cascade_start_time_{0}".format(question.id), datetime.datetime.now())
    
def recordCascadeEndTime(question):
    helpers.saveToMemcache("cascade_end_time_{0}".format(question.id), datetime.datetime.now())
    
def getCascadeDuration(question):
    client = memcache.Client()
    startTime = client.get("cascade_start_time_{0}".format(question.id))
    endTime = client.get("cascade_end_time_{0}".format(question.id))
    duration = time.mktime(endTime.timetuple())-time.mktime(startTime.timetuple()) if startTime and endTime else 0
    return duration

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
    
def getCascadeClass(type):
    if not type or type < 1 or type > len(CASCADE_CLASSES):
        helpers.log("WARNING: Unknown type passed to getCascadeClass")
        return None
    return CASCADE_CLASSES[type-1]

CASCADE_CLASSES = [ CascadeSuggestCategory, CascadeBestCategory, CascadeFitCategory ]

# TODO / DB: no longer using the following db fields (not deleted from public database):
#    questions: phase, cascade_iteration, cascade_step, cascade_step_count
#    cascade_stats: iteration_count, step[1-5]_job_count, step[1-5]_duration, step[4-5]_unsaved_count
#    cascade_times: delete table
#    cascade_suggested_categories: cascade_iteration
#    cascade_best_categories: cascade_iteration
#    cascade_fit_categories_phase1: cascade_iteration, subsequent
#    cascade_fit_categories_phase2: delete table

# TODO: cascade_m is currently 50%; might get better results if higher percentage used but then more jobs required; consider recording x first items to guarantee minimum cascade_m value
# TODO: fix waiting ui on cascade page (shown between jobs); change to loading
# TODO: consider saving dups instead of just recording unsaved count
# TODO: consider changing best category to checkboxes; would require more jobs
# TODO: remove duplicate ideas (common problem for questions w/ short answers)
# TODO: users often must wait between cascade step 1-2 (esp. if there are not many users)
# TODO: very small ks used; when should they be larger? use larger ks when > x students? what happens if ks adjusted as things progress? reconsider how voting threshold is calculated
# TODO: allow teacher to continue cascade after generating categories by force
# BEHAVIOR / BUG: options calculated based on # of active users so options will be *wrong* if first idea submitted before most people are logged in
