#!/usr/bin/env python
#
# Copyright 2014 Ben Bederson - http://www.cs.umd.edu/~bederson
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
from lib.stemming.porter2 import stem

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
    fields = [ "id", "title", "question", "authentication_type", "user_id", "active", "cascade_k", "cascade_k2", "cascade_m", "cascade_p", "cascade_s", "cascade_t", "cascade_complete" ]  
    onCascadeSettingsChanged = None
    onNewCategory = None
    onFitComplete = None
    onMoreJobs = None
    
    def __init__(self):
        self.id = None
        self.title = None
        self.question = None
        self.authentication_type = constants.GOOGLE_AUTHENTICATION
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
    def create(dbConnection, authorId, title, questionText, authenticationType=constants.GOOGLE_AUTHENTICATION):
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
        question.authentication_type = authenticationType
        question.user_id = authorId
        question.active = 1
            
        sql = "insert into questions (id, title, question, authentication_type, user_id, active) values (%s, %s, %s, %s, %s, %s)"
        dbConnection.cursor.execute(sql, (question.id, question.title, question.question, question.authentication_type, question.user_id, question.active))
        dbConnection.conn.commit()
        
        question.setCascadeSettings(dbConnection)
            
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

    @staticmethod
    def copy(dbConnection, question):
        # create new question
        # (cascade_* data and question_discuss data not copied to new question)
        newQuestion = Question.create(dbConnection, question.user_id, "{0} (Copy)".format(question.title), question.question, question.authentication_type)

        # copy users to new question
        newUserIds = {}
        sql = "select * from users where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            oldUserId = row["id"]                      
            sql = "insert into users (authenticated_user_id, authenticated_nickname, nickname, question_id) values (%s, %s, %s, %s)"
            dbConnection.cursor.execute(sql, (row["authenticated_user_id"], row["authenticated_nickname"], row["nickname"], newQuestion.id))
            newUserId = dbConnection.cursor.lastrowid
            dbConnection.conn.commit()
            newUserIds[oldUserId] = newUserId
        
        # copy ideas to new question
        sql = "select * from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            oldUserId = row["user_id"]
            newUserId = newUserIds[oldUserId]
            Idea.create(dbConnection, newQuestion, newUserId, row["idea"])

        return newQuestion
        
    def setActive(self, dbConnection, active):
        if self.active != active:
            if not active and not self.cascade_complete:
                dbConnection.cursor.execute("update cascade_suggested_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeSuggestCategory.incompleteCondition))
                dbConnection.cursor.execute("update cascade_best_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeBestCategory.incompleteCondition))
                dbConnection.cursor.execute("update cascade_equal_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeEqualCategory.incompleteCondition))
                dbConnection.cursor.execute("update cascade_fit_categories_phase1 set user_id=null where question_id={0} and {1}".format(self.id, CascadeFitCategory.incompleteCondition))
                dbConnection.cursor.execute("update cascade_fit_categories_phase2 set user_id=null where question_id={0} and {1}".format(self.id, CascadeVerifyCategory.incompleteCondition))
                dbConnection.conn.commit()
            self.update(dbConnection, { "active" : active, "id" : self.id })
    
    def setCascadeSettings(self, dbConnection):
        # if fewer than cascade_k students logged in, they will need to wait until
        # cascade_k jobs are completed before they can continue     
        # NO LONGER USED to set default cascade settings
        #userCount = Person.getCountForQuestion(dbConnection, self.id, loggedIn=True)
        
        properties = {
            "cascade_k" : constants.CASCADE_K,
            "cascade_k2" : constants.CASCADE_K2,
            "cascade_m" : constants.CASCADE_M,
            "cascade_p" : constants.CASCADE_P,
            "cascade_s" : constants.CASCADE_S,
            "cascade_t" : constants.CASCADE_T,
            "id" : self.id
        }
        self.update(dbConnection, properties)
           
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
        dbConnection.cursor.execute("update cascade_equal_categories set user_id=null where question_id={0} and {1}".format(self.id, CascadeEqualCategory.incompleteCondition))
        dbConnection.cursor.execute("update cascade_fit_categories_phase1 set user_id=null where question_id={0} and {1}".format(self.id, CascadeFitCategory.incompleteCondition))
        dbConnection.cursor.execute("update cascade_fit_categories_phase2 set user_id=null where question_id={0} and {1}".format(self.id, CascadeVerifyCategory.incompleteCondition))
        dbConnection.conn.commit()
            
    def clearWaiting(self, dbConnection):
        sql = "update user_clients,users set waiting_since=null where user_clients.user_id=users.id and question_id=%s"
        dbConnection.cursor.execute(sql, (self.id))
        dbConnection.conn.commit()
                    
    def cascadeComplete(self, dbConnection, skippedCategories=[]):
        self.update(dbConnection, { "cascade_complete" : 1, "id" : self.id })
        recordCascadeEndTime(self) 
        stats = self.recordCascadeStats(dbConnection, skippedCategories)
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
            sql = "select count(*) as ct from categories where question_id=%s and skip=0"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            categoryCount = row["ct"] if row else 0
            
            # idea count
            ideaCount = Idea.getCountForQuestion(dbConnection, self.id)
            
            # uncategorized count
            sql = "select count(*) as ct from question_ideas left join question_categories on question_ideas.id=question_categories.idea_id where question_ideas.question_id=%s and category_id is null and duplicate_of is null"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            uncategorizedCount = row["ct"] if row else 0
            
            # total duration
            totalDuration = getCascadeDuration(self)
            
            # get min, max, and the average user response time
            sql = "select min(response_time) as min_response_time, max(response_time) as max_response_time, avg(response_time) as avg_response_time from (select user_id,unix_timestamp(max(created_on))-unix_timestamp(start_time) as response_time from question_ideas join (select question_id, min(created_on) as start_time from question_ideas where question_id=%s) question_ideas2 on question_ideas.question_id=question_ideas2.question_id and question_ideas.question_id=%s group by user_id having response_time>0) response_times"
            dbConnection.cursor.execute(sql, (self.id, self.id))
            row = dbConnection.cursor.fetchone()
            minResponseTime = row["min_response_time"] if row else 0
            maxResponseTime = row["max_response_time"] if row else 0
            # Decimal is not JOSN serializable so error if not cast to float
            avgResponseTime = float(row["avg_response_time"]) if row else 0
            
            stats["cascade_user_count"] = userCount
            stats["idea_count"] = ideaCount
            stats["category_count"] = categoryCount
            stats["uncategorized_count"] = uncategorizedCount
            stats["total_duration"] = totalDuration
            stats["min_response_time"] = minResponseTime
            stats["max_response_time"] = maxResponseTime
            stats["avg_response_time"] = avgResponseTime
            
        return stats
                            
    def recordCascadeStats(self, dbConnection, skippedCategories=[]): 
        stats = {}                  
        if self.cascade_complete:      
            stats = self.calculateCascadeStats(dbConnection)        
            sql = "update cascade_stats set user_count=%s, category_count=%s, idea_count=%s, uncategorized_count=%s, min_response_time=%s, max_response_time=%s, avg_response_time=%s, total_duration=%s, skipped_categories=%s where question_id=%s"
            dbConnection.cursor.execute(sql, (stats["cascade_user_count"], stats["category_count"], stats["idea_count"], stats["uncategorized_count"], stats["min_response_time"], stats["max_response_time"], stats["avg_response_time"], stats["total_duration"], ", ".join(skippedCategories) if skippedCategories and len(skippedCategories)>0 else None, self.id))
            dbConnection.conn.commit()
        return stats
                
    def getQuestionStats(self, dbConnection):
        stats = {}
        stats["question_id"] = self.id
        stats["active_user_count"] = Person.getCountForQuestion(dbConnection, self.id, loggedIn=True)    
        stats["idea_user_count"] = Idea.getAuthorCountForQuestion(dbConnection, self.id)
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
            stats["cascade_user_count"] = row["user_count"] if row else 0
            stats["idea_count"] = row["idea_count"] if row else 0
            stats["category_count"] = row["category_count"] if row else 0
            stats["uncategorized_count"] = row["uncategorized_count"] if row else 0
            stats["min_response_time"] = row["min_response_time"] if row else 0
            stats["max_response_time"] = row["max_response_time"] if row else 0
            # Decimal is not JOSN serializable so error if not cast to float
            stats["avg_response_time"] = float(row["avg_response_time"]) if row else 0
            stats["total_duration"] = row["total_duration"] if row else 0

        else:
            stats = {}
            # category count while cascade in progress
            sql = "select count(*) as ct from categories where question_id=%s and skip=0"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            stats["category_count"] = row["ct"] if row else 0

            # number of CascadeFitCategory jobs
            sql = "select count(*) as ct from cascade_fit_categories_phase1 where question_id=%s"
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            stats["total_fit_count"] = row["ct"] if row else 0
                            
            # number of CascadeFitCategory jobs completed so far
            sql = "select count(*) as ct from cascade_fit_categories_phase1 where question_id=%s and {0}".format(CascadeFitCategory.completeCondition)
            dbConnection.cursor.execute(sql, (self.id))
            row = dbConnection.cursor.fetchone()
            stats["completed_fit_count"] = row["ct"] if row else 0
            
            if constants.VERIFY_CATEGORIES:
                # number of CascadeVerifyCategory jobs
                sql = "select count(*) as ct from cascade_fit_categories_phase2 where question_id=%s"
                dbConnection.cursor.execute(sql, (self.id))
                row = dbConnection.cursor.fetchone()
                stats["total_verify_count"] = row["ct"] if row else 0

                # number of CascadeVerifyCategory jobs completed so far                
                sql = "select count(*) as ct from cascade_fit_categories_phase2 where question_id=%s and {0}".format(CascadeVerifyCategory.completeCondition)
                dbConnection.cursor.execute(sql, (self.id))
                row = dbConnection.cursor.fetchone()
                stats["completed_verify_count"] = row["ct"] if row else 0
                            
        return stats
           
    def delete(self, dbConnection, dataOnly=False, onDeleteStudents=None):
        if not dataOnly:
            dbConnection.cursor.execute("delete from questions where id={0}".format(self.id))            
        dbConnection.cursor.execute("delete from question_ideas where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_discuss where question_id={0}".format(self.id))
        self.deleteCascade(dbConnection, commit=False)

        if onDeleteStudents:
            onDeleteStudents(dbConnection, self.id)
        dbConnection.cursor.execute("delete user_clients from users,user_clients where users.id=user_clients.user_id and question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from users where question_id={0}".format(self.id))
        dbConnection.conn.commit()
        
        self = Question()
        return self
    
    def deleteCascade(self, dbConnection, commit=True):
        self.update(dbConnection, { "cascade_complete" : 0, "id" : self.id }, commit=False)
        dbConnection.cursor.execute("update user_clients,users set waiting_since=null where user_clients.user_id=users.id and question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_suggested_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_best_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_equal_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_fit_categories_phase1 where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_fit_categories_phase2 where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from categories where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from cascade_stats where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from reviews where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from fit_reviews where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete from group_reviews where question_id={0}".format(self.id))
        if commit:
            dbConnection.conn.commit()

        clearMemcache(self)
                                        
    @staticmethod
    def getById(dbConnection, questionId):
        question = None
        if questionId:
            sql = "select {0}, authenticated_user_id from questions,users where questions.user_id=users.id and questions.id=%s".format(Question.fieldsSql())
            dbConnection.cursor.execute(sql, (questionId))
            row = dbConnection.cursor.fetchone()
            question = Question.createFromData(row)
        return question

    @staticmethod                
    def getByUser(dbConnection, includeAll=False):
        questions = []
        user = users.get_current_user()
        if includeAll:
            sql = "select {0}, authenticated_user_id, authenticated_nickname from questions,users where questions.user_id=users.id order by last_update desc".format(Question.fieldsSql())
            dbConnection.cursor.execute(sql)
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                question = Question.createFromData(row)
                questionDict = question.toDict()
                questionDict["author"] = row["authenticated_nickname"]
                questions.append(questionDict)
                    
        elif user:
            sql = "select {0}, authenticated_user_id, authenticated_nickname from questions,users where questions.user_id=users.id and authenticated_user_id=%s order by last_update desc".format(Question.fieldsSql())
            dbConnection.cursor.execute(sql, (user.user_id()))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                question = Question.createFromData(row)
                questionDict = question.toDict()
                questions.append(questionDict)
                                
        return questions
    
class Person(DBObject):               
    table = "users"
    fields = [ "id", "authenticated_user_id", "authenticated_nickname", "nickname", "question_id", "latest_login_timestamp", "latest_logout_timestamp", "session_sid", "admin" ]   
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
        self.admin = 0
    
    @staticmethod
    def create(dbConnection, question=None, nickname=None, session=None):
        # if Person authenticated via Google, make sure user logged in
        user = users.get_current_user()
        if question and question.authentication_type == constants.GOOGLE_AUTHENTICATION and not user:
            return None
        
        # if Person authenticated via nickname, make sure nickname provided
        if question and question.authentication_type == constants.NICKNAME_AUTHENTICATION and not nickname:
            return None

        # if authenticated via Google to a question with Google authentication, 
        # or as an instructor (not to any question in particular), get authenticated info
        authenticatedUserId = None
        authenticatedNickname = None
        if user and (not question or question.authentication_type == constants.GOOGLE_AUTHENTICATION):
            authenticatedUserId = user.user_id()
            authenticatedNickname = user.nickname()       

        person = Person()
        person.authenticated_user_id = authenticatedUserId
        person.authenticated_nickname = authenticatedNickname
        person.nickname = nickname if nickname else (Person.cleanNickname(authenticatedNickname) if authenticatedNickname else None)
        person.question_id = question.id if question else None
        # pass in session since it is empty sometimes if retrieved via gaesessions.get_current_session
        person.session_sid = session.sid if session and question and (question.authentication_type == constants.NO_AUTHENTICATION or question.authentication_type == constants.NICKNAME_AUTHENTICATION) else None
          
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
                         
    def login(self, dbConnection, question=None, session=None):
        if not self.is_logged_in:
            # update session id for students using no authentication or nickname authentication
            # pass in session since it is empty sometimes if retrieved via gaesessions.get_current_session
            self.session_sid = session.sid if session and question and (question.authentication_type == constants.NO_AUTHENTICATION or question.authentication_type == constants.NICKNAME_AUTHENTICATION) else None
            sql = "update users set latest_login_timestamp=now(), latest_logout_timestamp=null, session_sid=%s where id=%s"
            dbConnection.cursor.execute(sql, (self.session_sid, self.id))
            dbConnection.conn.commit()
            self.is_logged_in = True
            
            if Person.onLogin:
                Person.onLogin(self, dbConnection)
  
    def logout(self, dbConnection, userRequestedLogout=True):
        if self.is_logged_in:
            # user actively logged out (clicked on Logout)
            if userRequestedLogout:
                # if Google authenticated user, modify *all* logged in records associated with this user            
                if self.authenticated_user_id:
                    sql = "update users set latest_logout_timestamp=now(), session_sid=null where authenticated_user_id=%s and latest_logout_timestamp is null"
                    dbConnection.cursor.execute(sql, (self.authenticated_user_id))
                # otherwise, modify this specific user instance
                else:
                    sql = "update users set latest_logout_timestamp=now(), session_sid=null where id=%s"
                    dbConnection.cursor.execute(sql, (self.id))
                
                self.session_sid = None     
    
            # user passively logged out (closed browser, etc.)
            # do not change session_sid since they might go back again
            else:
                sql = "update users set latest_logout_timestamp=now() where id=%s"
                dbConnection.cursor.execute(sql, (self.id))
                        
            dbConnection.conn.commit()
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
   
    def getNickname(self):
        # if no nickname available, use Student<id>
        return self.nickname if self.nickname else "Student{0}".format(self.id) if self.id else None
    
    def getLogin(self):
        return self.authenticated_nickname if self.authenticated_nickname else self.getNickname()

    def getIdentity(self, admin=False):
        identity = {}        
        identity["user_nickname"] = self.getNickname()
        identity["user_identity"] = None
        if admin and self.authenticated_nickname:
            hasHiddenIdentity = self.nickname and Person.cleanNickname(self.authenticated_nickname) != self.nickname
            if hasHiddenIdentity:
                identity["user_identity"] = self.authenticated_nickname
        return identity
            
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
    def isAuthor(question):
        # BEHAVIOR: check if currently authenticated user is the question author
        # currently only authenticated users can create questions
        user = users.get_current_user()
        return user and question and question.authenticated_user_id and user.user_id()==question.authenticated_user_id
   
    @staticmethod
    def isAdmin(person):
        # TODO/FIX: would like a way to check if current authenticated user is admin (if any)
        #  when active page user is non-authenticated - but without a database query for each check
        return person and person.admin == 1
    
    @staticmethod
    def getPerson(dbConnection, question=None, session=None):
        person = None
        user = users.get_current_user()

        # find Google authenticated instructor
        if not question and user:
            sql = "select {0} from users where question_id is null and authenticated_user_id=%s".format(Person.fieldsSql())
            dbConnection.cursor.execute(sql, (user.user_id()))
            row = dbConnection.cursor.fetchone()
            person = Person.createFromData(row)
        
        # find Google authenticated student
        elif question and question.authentication_type==constants.GOOGLE_AUTHENTICATION and user:
            sql = "select {0} from users where question_id=%s and authenticated_user_id=%s".format(Person.fieldsSql())
            dbConnection.cursor.execute(sql, (question.id, user.user_id()))
            row = dbConnection.cursor.fetchone()
            person = Person.createFromData(row)

            # if not found, create new one
            if not person:
                person = Person.create(dbConnection, question=question, session=session)
                    
        # find student by session
        # pass in session since it is empty sometimes if retrieved via gaesessions.get_current_session
        elif question and (question.authentication_type==constants.NO_AUTHENTICATION or question.authentication_type==constants.NICKNAME_AUTHENTICATION) and session:
            sql = "select {0} from users where question_id=%s and session_sid=%s".format(Person.fieldsSql())
            dbConnection.cursor.execute(sql, (question.id, session.sid))
            row = dbConnection.cursor.fetchone()
            person = Person.createFromData(row)            
            
            # if not found and no authentication required, create new one
            if not person and question.authentication_type==constants.NO_AUTHENTICATION:
                person = Person.create(dbConnection, question=question, session=session)
              
#             if person and user:
#                 helpers.log("check if authenticated user ... if so, if they are admin make non-authenticated users as admin")
#                 sql = "select * from users where question_id is null and authenticated_user_id=%s"
#                 dbConnection.cursor.execute(sql, (user.user_id()))
#                 row = dbConnection.cursor.fetchone() 
#                 if row:
#                     person.admin = 1 if row["admin"] == 1 else 0  
                
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
    fields = [ "id", "question_id", "user_id", "idea", "item_set", "duplicate_of", "created_on" ]
        
    def __init__(self):
        self.id = None
        self.question_id = None
        self.user_id = None
        self.idea = None
        self.item_set = constants.CASCADE_INITIAL_ITEM_SET
        self.duplicate_of = None
        self.created_on = None
    
    @staticmethod
    def create(dbConnection, question, userId, ideaText):
        idea = Idea()
        idea.question_id = question.id
        idea.user_id = userId
        # capitalize first letter in idea for consistency
        idea.idea =ideaText.strip().capitalize() if ideaText is not None else ""
        
        # check for duplicate ideas
        idea.duplicate_of = None
        if constants.CHECK_FOR_DUPLICATE_RESPONSES:
            # TODO/FIX: should remove punctuation when checking for duplicate
            sql = "select * from question_ideas where question_id=%s and idea=%s and duplicate_of is null"
            dbConnection.cursor.execute(sql, (idea.question_id, idea.idea))
            row = dbConnection.cursor.fetchone()
            idea.duplicate_of = row["id"] if row else None
        isDuplicate = idea.duplicate_of is not None

        # get item set (initial or subsequent)
        # place any duplicate items in subsequent item set
        idea.item_set = getNewCascadeItemSet(question) if not isDuplicate else constants.CASCADE_SUBSEQUENT_ITEM_SET
        
        sql = "insert into question_ideas (question_id, user_id, idea, item_set, duplicate_of) values (%s, %s, %s, %s, %s)"
        dbConnection.cursor.execute(sql, (idea.question_id, idea.user_id, idea.idea, idea.item_set, idea.duplicate_of))
        idea.id = dbConnection.cursor.lastrowid
        dbConnection.conn.commit()
        
        # initialize cascade stats when first idea added
        # TODO/FIX: so query doesn't have to be performed for every idea added; use memcache?
        sql = "select count(*) as ct from cascade_stats where question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        if row["ct"] == 0:
            sql = "insert into cascade_stats (question_id) values (%s)"
            dbConnection.cursor.execute(sql, (question.id))            
            dbConnection.conn.commit()   
            recordCascadeStartTime(question) 

        # create any new cascade jobs
        if not isDuplicate:
            Idea.createCascadeJobs(dbConnection, question, idea)
                                 
        return idea
    
    def isDuplicate(self):
        return self.duplicate_of is not None
      
    @staticmethod
    def getAuthor(data):
        author = {
            "id" : data[Person.tableField("id")],
            "authenticated_nickname" : data[Person.tableField("authenticated_nickname")],
            "nickname" : data[Person.tableField("nickname")]
        }
        return author
                               
    @staticmethod
    def createCascadeJobs(dbConnection, question, idea):
        moreJobs = False
        # create CascadeSuggestCategory job for idea
        if idea.item_set == constants.CASCADE_INITIAL_ITEM_SET:
            CascadeSuggestCategory.create(dbConnection, question, idea.id)
            moreJobs = True
        
        # create CascadeFitCategory jobs for idea
        fitCount = CascadeFitCategory.createForAllCategories(dbConnection, question, idea.id)            
        if fitCount > 0:
            moreJobs = True
        
        if moreJobs and Question.onMoreJobs:
            question.onMoreJobs(dbConnection, moreFitJobs=fitCount)
                   
    @staticmethod
    def getById(dbConnection, ideaId):
        sql = "select {0} from question_ideas where id=%s".format(Idea.fieldsSql())
        dbConnection.cursor.execute(sql, (ideaId))
        row = dbConnection.cursor.fetchone()
        return Idea.createFromData(row)
        
    @staticmethod
    def getByQuestion(dbConnection, question, person):
        ideas = []
        duplicates = []
        ideaIndices = {}
        
        if question and person:
            sql = "select {0},{1} from question_ideas,users where question_ideas.user_id=users.id and question_ideas.question_id=%s order by created_on desc".format(Idea.fieldsSql(), Person.fieldsSql())
            dbConnection.cursor.execute(sql, (question.id))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                idea = Idea.createFromData(row)
                ideaDict = idea.toDict(author=Idea.getAuthor(row), admin=Person.isAdmin(person) or Person.isAuthor(question))
                if idea.isDuplicate():
                    duplicates.append(ideaDict)
                else:
                    ideas.append(ideaDict)
                    ideaIndices[idea.id] = len(ideas)-1
                    
            for duplicate in duplicates:
                ideaId = duplicate["duplicate_of"]
                i = ideaIndices[ideaId]
                if "duplicates" not in ideas[i]:
                    ideas[i]["duplicates"] = []
                ideas[i]["duplicates"].append(duplicate)
                    
        return ideas
           
    @staticmethod
    def getByCategories(dbConnection, question, person, useTestCategories=False):
        category = None
        categoryIdeas = []
        categoryGroups = []
        uncategorizedIdeas = []
        categorySizes = {}
        ideaCategoriesMap = {}
        ideaIds = []
        duplicates = {}
                
        categoriesTable = "categories" if not useTestCategories else "categories2"
        questionCategoriesTable = "question_categories" if not useTestCategories else "question_categories2"
        
        if question:                    
            # group alphabetically by category name
            sql = "select {0},{1},subcategories,category,same_as from question_ideas ".format(Idea.fieldsSql(), Person.fieldsSql())
            sql += "left join {0} on question_ideas.id={0}.idea_id ".format(questionCategoriesTable)
            sql += "left join {0} on {1}.category_id={0}.id ".format(categoriesTable, questionCategoriesTable)
            sql += "left join users on question_ideas.user_id=users.id where "
            sql += "question_ideas.question_id=%s "
            sql += "order by category,idea"
            dbConnection.cursor.execute(sql, (question.id))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                idea = Idea.createFromData(row)
                ideaDict = idea.toDict(author=Idea.getAuthor(row), admin=Person.isAdmin(person) or Person.isAuthor(question))
                ideaCategory = row["category"]
                                                        
                if idea.isDuplicate():
                    if idea.duplicate_of not in duplicates:
                        duplicates[idea.duplicate_of] = []
                    duplicates[idea.duplicate_of].append(ideaDict)
                    
                else:
                    if ideaCategory: 
                        ideaSameAs = row["same_as"].split(":::") if row["same_as"] else []
                        categorySubcategories = row["subcategories"].split(":::") if row["subcategories"] else []

                        if not category:
                            category = ideaCategory
                            sameAs = ideaSameAs
                            subcategories = categorySubcategories
                                                
                        if category != ideaCategory:
                            if len(categoryIdeas) > 0:
                                categoryGroups.append({ "category" : category , "subcategories" : subcategories, "same_as" : sameAs, "ideas" : categoryIdeas })
                                categorySizes[category] = len(categoryIdeas);
                            category = ideaCategory
                            sameAs = ideaSameAs
                            subcategories = categorySubcategories
                            categoryIdeas = []
                            
                        categoryIdeas.append(ideaDict)
                            
                    else:
                        uncategorizedIdeas.append(ideaDict)
                                
                    if idea.id not in ideaCategoriesMap:
                        ideaCategoriesMap[idea.id] = []
                    ideaCategoriesMap[idea.id].append(ideaCategory)
            
                # record idea ids, including any duplicates
                ideaIds.append(idea.id)
                                   
            if len(categoryIdeas) > 0:
                categoryGroups.append({ "category" : category, "subcategories" : subcategories, "same_as" : sameAs, "ideas" : categoryIdeas })
               
        # update also in and duplicates
        for i, group in enumerate(categoryGroups):
            for j, ideaDict in enumerate(group["ideas"]):
                ideaId = ideaDict["id"]
                alsoIn = []
                if len(ideaCategoriesMap[ideaId]) > 0:
                    alsoIn = ideaCategoriesMap[ideaId][:]
                    alsoIn.remove(group["category"])
                categoryGroups[i]["ideas"][j]["also_in"] = alsoIn
                
                if ideaId in duplicates:
                    categoryGroups[i]["ideas"][j]["duplicates"] = duplicates[ideaId]
        
        for i, ideaDict in enumerate(uncategorizedIdeas):
            ideaId = ideaDict["id"]
            if ideaId in duplicates:
                uncategorizedIdeas[i]["duplicates"]= duplicates[ideaId]
                                
        return categoryGroups, uncategorizedIdeas, len(set(ideaIds))
    
    @staticmethod
    def getCountForQuestion(dbConnection, questionId):
        sql = "select count(*) as ct from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return row["ct"] if row else 0

    @staticmethod
    def getAuthorCountForQuestion(dbConnection, questionId):
        sql = "select count(distinct user_id) as ct from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return row["ct"] if row else 0
              
    def toDict(self, author=None, admin=False):
        objDict = super(Idea, self).toDict()
        if author:
            person = Person()
            person.id = author["id"] if "id" in author else None
            person.nickname = author["nickname"] if "nickname" in author else None
            person.authenticated_nickname = author["authenticated_nickname"] if "authenticated_nickname" in author else None
            identity = person.getIdentity(admin=admin)
            objDict["author"] = identity["user_nickname"]
            objDict["author_identity"] = identity["user_identity"]   
            objDict["author_anonymous"] = person.nickname is None         
        return objDict
                     
###################
##### CASCADE #####
###################

# BEHAVIOR: new cascade jobs are created when new ideas are submitted submitted and existing cascade jobs are completed
# BEHAVIOR: users are restricted to unique cascade jobs when running on GAE which means >= k users required to complete cascade 
# BEHAVIOR: introduced cascade_k2 to use for category fit jobs since large number of fit jobs required to complete cascade
# BEHAVIOR: categories with fewer than CASCADE_Q items removed
# BEHAVIOR: duplicate categories merged (two categories are checked if the smaller is >= MIN_DUPLICATE_SIZE_PERCENTAGE of the larger and CASCADE_P % of the category items overlap)
# BEHAVIOR: subcategories are nested (two categories are checked if the smaller is < MIN_DUPLICATE_SIZE_PERCENTAGE of the larger and CASCADE_P % of the category items overlap)
    
# BEHAVIOR: fit tasks are performed for both the initial item set and subsequent item set using the same categories
# This is different than Cascade where the fit tasks for the initial item set are done and then 
# an initial taxonomy is created.  The fit tasks on the subsequent item set are done using categories 
# from the initial taxonomy (which requires less fit tasks because there are less categories).  A
# second iteration is performed on any uncategorized items.
#
# In our implementation, completing the fit task on the initial item set first would increase the chances 
# that items in the subsequent item set are not categorized at all if the instructor generates the taxonomy early.
# The Cascade approach assumes that there are fewer categories after the initial taxonomy is created
# which seems to depend on removing duplicate categories.  Should duplicates be found after the initial item set or
# wait until all items are fit?  Currently we wait until all items are fit to identify duplicates and nested categories.
# Our current solution creates roughly 1.5x more tasks than 1 Cascade iteration but ~75% of the tasks required 
# for 2 iterations.

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
    def create(dbConnection, question, ideaId, count=None):
        count = question.cascade_k if count is None else count     
        insertValues = [ "({0}, {1})".format(question.id, ideaId) for i in range(count) ]
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
        
        return { "tasks" : tasks, "type" : CascadeSuggestCategory.type, "categories" : getCategories(question) } if len(tasks) > 0 else None
                 
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        for task in job:
            taskId = task["id"]
            
            # save suggested category
            # capitalize first letter of category for consistency
            suggestedCategory = task["suggested_category"].strip().capitalize() if task["suggested_category"] is not None else ""
            if suggestedCategory != "":
                sql = "update cascade_suggested_categories set suggested_category=%s"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and {0}".format(CascadeSuggestCategory.incompleteCondition)
                dbConnection.cursor.execute(sql, (suggestedCategory, taskId)) 
                
                # record category, but may be removed when voting for best category or checking for duplicates
                # categories removed/skipped because they are equivalent will be removed
                # categories that don't pass CascadeBestCategory are not removed because they might be ok for another idea
                recordCategory(question, suggestedCategory)
                                
            # if skipped, mark it so not assigned in future
            else:
                sql = "update cascade_suggested_categories set skipped=1"
                sql += ", user_id={0} ".format(person.id) if person else " "
                sql += "where id=%s and {0}".format(CascadeSuggestCategory.incompleteCondition)                
                dbConnection.cursor.execute(sql, (taskId))
                
            dbConnection.conn.commit()
                        
            # create any new cascade jobs
            CascadeSuggestCategory.createCascadeJobs(dbConnection, question, task)
    
    @staticmethod
    def createCascadeJobs(dbConnection, question, task): 
        jobComplete = False
        suggestedCategories = []
        skippedCategoryCount = 0
        
        # check if task performed k times
        # do not need to check using db query if k=1 but needed to check how many times task has really been tried
        sql = "select idea_id, suggested_category from cascade_suggested_categories where question_id=%s and cascade_suggested_categories.idea_id=(select idea_id from cascade_suggested_categories where id=%s) and {0}".format(CascadeSuggestCategory.completeCondition)
        dbConnection.cursor.execute(sql, (question.id, task["id"]))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            if row["suggested_category"] and row["suggested_category"] not in suggestedCategories:
                suggestedCategories.append(row["suggested_category"])
            elif not row["suggested_category"]:
                skippedCategoryCount += 1

        completedTaskCount = len(rows)
        jobComplete = completedTaskCount >= question.cascade_k

        # if no categories suggested (but at least one required) and task completed k times,
        # create one more CascadeSuggestCategory job
        if constants.SUGGEST_CATEGORY_AGAIN and len(suggestedCategories) == 0 and completedTaskCount==question.cascade_k:
            jobComplete = False
            CascadeSuggestCategory.create(dbConnection, question, task["idea_id"], count=1)
            if Question.onMoreJobs:
                question.onMoreJobs(dbConnection)
        
        else:    
            # check how many categories suggested (could have just skipped them all)
            multipleCategoriesSuggested = len(suggestedCategories) > 1
            onlyOneCategorySuggested = len(suggestedCategories) == 1
    
            # create CascadeBestCategory jobs for task idea if CascadeSuggestCategory job complete
            # and there is more than one suggested category
            moreJobs = False
            if jobComplete:
                if multipleCategoriesSuggested:    
                    CascadeBestCategory.create(dbConnection, question, task["idea_id"])
                    moreJobs = True
                       
                elif onlyOneCategorySuggested:
                    sql = "select count(*) as ct from categories where question_id=%s and category=%s"
                    dbConnection.cursor.execute(sql, (question.id, suggestedCategories[0]))
                    row = dbConnection.cursor.fetchone()
                    isNewCategory = row["ct"] == 0
                    rows = [ { "best_category": suggestedCategories[0], "is_new_category": isNewCategory } for i in range(completedTaskCount-skippedCategoryCount) ] 
                    rows.extend([ { "best_category": None, "is_new_category": False } for i in range(skippedCategoryCount) ])
                    CascadeBestCategory.createCascadeJobs(dbConnection, question, rows=rows)
                
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
            sql = "select idea,suggested_category from cascade_suggested_categories,question_ideas where question_ideas.question_id=%s and cascade_suggested_categories.idea_id=question_ideas.id and cascade_suggested_categories.idea_id=%s and suggested_category is not null"
            dbConnection.cursor.execute(sql, (task.question_id, task.idea_id))
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
            
            # create any new cascade jobs
            CascadeBestCategory.createCascadeJobs(dbConnection, question, task=task)
    
    @staticmethod
    def createCascadeJobs(dbConnection, question, task=None, rows=None):    
        # create cascade jobs if CascadeBestCategory job is complete
        if rows is None:
            sql = "select *, (best_category not in (select category from categories where question_id={0})) as is_new_category ".format(question.id)
            sql += "from cascade_best_categories where question_id={0} and ".format(question.id)
            sql += "idea_id=(select idea_id from cascade_best_categories where id={0}) and ".format(task["id"])
            sql += "{0}".format(CascadeBestCategory.completeCondition)
            dbConnection.cursor.execute(sql)
            rows = dbConnection.cursor.fetchall()
        
        equalCount = 0
        fitCount = 0
        if len(rows) >= question.cascade_k:
            categoryVotes = {}
            for row in rows:
                category = row["best_category"]
                isNewCategory = category and row["is_new_category"] == 1
                if isNewCategory:
                    if category not in categoryVotes:
                        categoryVotes[category] = []
                    categoryVotes[category].append(row)
                
            # check if any "best" categories pass the voting threshold
            # if so ...
            # temporarily save to the categories table, and
            # create CascadeFitCategory jobs for all ideas  
            # TODO: consider whether or not the task idea should be marked as already fitting this category
            votingThreshold = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k>=3 else 1
            for category in categoryVotes:
                if len(categoryVotes[category]) >= votingThreshold:
                    categoryStems = [];
                    categoryWords = category.split(" ")
                    for i in xrange(len(categoryWords)):
                        word = helpers.cleanWord(categoryWords[i])
                        word = word.replace("-", "")
                        if word and word != "":
                            wordStem = stem(word)
                            if wordStem and wordStem != "":
                                categoryStems.append(wordStem)
                    categoryStems.sort()
                                        
                    # check if category to be added matches any existing categories by stems
                    # if not, add; otherwise skip (this stem could be better but only one the first one is saved)
                    # TODO/FIX: stop words do not have stems so categories with only stop words might get added multiple times
                    stemsDoNotMatchExistingCategory = True
                    if len(categoryStems) > 0:
                        sql = "select count(*) as ct from categories where question_id=%s and stems=%s"
                        dbConnection.cursor.execute(sql, (question.id, ":::".join(categoryStems)))
                        row = dbConnection.cursor.fetchone()
                        # TODO/FIX: check # of stems too?
                        stemsDoNotMatchExistingCategory = row["ct"] == 0
                        
                    if stemsDoNotMatchExistingCategory:   
                        sql = "insert into categories (question_id, category, stems) values(%s, %s, %s)"
                        dbConnection.cursor.execute(sql, (question.id, category, ":::".join(categoryStems) if len(categoryStems) > 0 else None))
                        dbConnection.conn.commit()
    
                        if Question.onNewCategory:
                            question.onNewCategory(dbConnection, category)
        
                        # create CascadeEqualCategory jobs for any existing categories that have similar stems
                        if constants.FIND_EQUAL_CATEGORIES:
                            similarCategories = []
                            sql = "select * from categories where question_id=%s and category!=%s and stems is not null and skip=0"
                            dbConnection.cursor.execute(sql, (question.id, category))
                            rows = dbConnection.cursor.fetchall()
                            for row in rows:
                                category2 = row["category"]
                                category2Stems = row["stems"].split(":::")
                                stemMatches = helpers.intersect(categoryStems, category2Stems)
                                # calculate percentage of stems that overlap between categories
                                # stem counts can be zero if category contains only stop words
                                similarPercentage = (float(len(stemMatches)) / min(len(categoryStems), len(category2Stems)))*100 if len(categoryStems) > 0 and len(category2Stems) > 0 else 0
                                if similarPercentage >= constants.SIMILAR_STEM_PERCENTAGE:
                                    similarCategories.append(category2)
                                
                            if len(similarCategories) > 0:
                                equalCount = CascadeEqualCategory.createForCategories(dbConnection, question, category, similarCategories)
                                                        
                        # create CategoryFitCategory jobs
                        # if more than k CascadeBestCategory tasks are performed for this category
                        # category may be a duplicate but hasn't been flagged as such yet
                        # TODO/FIX: CascadeFitCategory tasks may get created more than k2 times for this category
                        fitCount = CascadeFitCategory.createForAllIdeas(dbConnection, question, category)
                        
                    # category matches stems of an existing category so remove it
                    else:
                        removeCategory(question, category)
                                        
        if equalCount+fitCount>0 and Question.onMoreJobs:
            question.onMoreJobs(dbConnection, moreFitJobs=fitCount)
            
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
                suggestedCategories.append(row["suggested_category"])
            objDict["idea"] = idea
            objDict["suggested_categories"] = suggestedCategories
            
        return objDict

class CascadeEqualCategory(DBObject):
    type = constants.EQUAL_CATEGORY
    table = "cascade_equal_categories"
    fields = [ "id", "question_id", "category1", "category2", "equal", "user_id" ]
    completeCondition = "(equal!=-1)"
    incompleteCondition = "(equal=-1)"
    
    def __init__(self):
        self.id = None
        self.question_id = None
        self.category1 = None
        self.category2 = None
        self.equal = -1
        self.user_id = None
     
    @staticmethod
    def create(dbConnection, question, category1, category2):
        insertValues = []
        categories = ()
        for i in range(question.cascade_k2):
            insertValues.append("({0}, %s, %s)".format(question.id))
            categories += (category1, category2)

        sql = "insert into cascade_equal_categories (question_id, category1, category2) values {0}".format(",".join(insertValues))
        dbConnection.cursor.execute(sql, tuple(categories))
        dbConnection.conn.commit()
        return question.cascade_k2
    
    @staticmethod
    def createForCategories(dbConnection, question, category, similarCategories=None):
        if similarCategories is None:
            sql = "select * from categories where question_id=%s and category!=%s and skip=0"
            dbConnection.cursor.execute(sql, (question.id, category))
            rows = dbConnection.cursor.fetchall()
            similarCategories = [row["category"] for row in rows]
                    
        count = 0
        for similarCategory in similarCategories:
            count += CascadeEqualCategory.create(dbConnection, question, category, similarCategory)
        return count
        
    @staticmethod
    def getJob(dbConnection, question, person): 
        tasks = []
        # check if job already assigned
        sql = "select * from cascade_equal_categories where "
        sql += "question_id=%s and "
        sql += "user_id=%s and "
        sql += CascadeEqualCategory.incompleteCondition
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeEqualCategory.createFromData(row)
            tasks.append(task)
                     
        # if not, assign new tasks
        # do not check if user already performed task when running locally
        if len(tasks) == 0:
            sql = "select * from cascade_equal_categories where "
            sql += "question_id=%s " 
            sql += "and user_id is null "
            sql += "and (category1, category2) not in (select distinct category1, category2 from cascade_equal_categories where question_id=%s and user_id=%s) " if not helpers.allowDuplicateJobs() else ""
            sql += "group by category1, category2 order by rand() limit {0}".format(constants.CASCADE_S)
            if helpers.allowDuplicateJobs():
                dbConnection.cursor.execute(sql, (question.id,))
            else:
                dbConnection.cursor.execute(sql, (question.id, question.id, person.id))
            
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                task = CascadeEqualCategory.createFromData(row)
                task.assignTo(dbConnection, person, commit=False)
                tasks.append(task)
            dbConnection.conn.commit()
                    
        return { "tasks" : tasks, "type" : CascadeEqualCategory.type } if len(tasks) > 0 else None
                  
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        # TODO/FIX: currently categorization is considered complete if all fit tasks have been completed
        # so even if there are incomplete CascadeEqualCategory jobs, the categories will be generated 
        # when all fit tasks are complete
        for task in job:
            taskId = task["id"]
            equal = task["equal"]
            sql = "update cascade_equal_categories set equal=%s"
            sql += ", user_id={0} ".format(person.id) if person else " "
            sql += "where id=%s and {0}".format(CascadeEqualCategory.incompleteCondition)
            dbConnection.cursor.execute(sql, (equal, taskId))
            dbConnection.conn.commit()
            
            CascadeEqualCategory.processEqualCategories(dbConnection, question, task)
    
    @staticmethod
    def processEqualCategories(dbConnection, question, task):
        # checks for equal categories and flags one to skip when creating future jobs
        # any existing jobs are removed for skipped categories

        sql = "select * from cascade_equal_categories where question_id={0} and ".format(question.id)
        sql += "category1=(select category1 from cascade_equal_categories where id={0}) and ".format(task["id"])
        sql += "category2=(select category2 from cascade_equal_categories where id={0}) and ".format(task["id"])
        sql += "{0}".format(CascadeEqualCategory.completeCondition)
        dbConnection.cursor.execute(sql)
        rows = dbConnection.cursor.fetchall()

        # check if tasks complete for category pair
        if len(rows) >= question.cascade_k2:
            equalVoteCount = 0
            for row in rows:
                category1 = row["category1"]
                category2 = row["category2"]
                if row["equal"] == 1:
                    equalVoteCount += 1
            
            # check if category pair has been voted to be equal                    
            votingThreshold = min([constants.DEFAULT_VOTING_THRESHOLD,question.cascade_k2])
            if equalVoteCount >= votingThreshold:
                try:
                    # use transaction since too many categories might get flagged to skip if concurrency issues come up
                    # TODO/FIX: generates error, at least when running locally
                    #dbConnection.begin()
                    # TODO/FIX: generates error if transaction not started
                    #sql = "select * from categories where question_id=%s and (category=%s or category=%s) and skip=1 on update"
                    sql = "select * from categories where question_id=%s and (category=%s or category=%s) and skip=1"
                    dbConnection.cursor.execute(sql, (question.id, category1, category2))
                    rows = dbConnection.cursor.fetchall()
                                             
                    # if neither category has been skipped already:
                    # flag category2 as category to skip in future, and
                    # delete any pending fit jobs for category2
                    if len(rows) == 0:
                        sql = "update categories set skip=1 where question_id=%s and category=%s"
                        dbConnection.cursor.execute(sql, (question.id, category2))
                        removeCategory(question, category2)
                        sql = "delete from cascade_fit_categories_phase1 where question_id=%s and category=%s"
                        dbConnection.cursor.execute(sql, (question.id, category2))
                        if constants.VERIFY_CATEGORIES:
                            sql = "delete from cascade_fit_categories_phase2 where question_id=%s and category=%s"
                            dbConnection.cursor.execute(sql, (question.id, category2))
                    dbConnection.conn.commit()
                except:
                    helpers.log("ERROR: Problem processing completed CascadeEqualCategory tasks")
                    # TODO/FIX: generates error, at least when running locally
                    #dbConnection.rollback()
                    
    def assignTo(self, dbConnection, person, commit=True):
        self.update(dbConnection, { "user_id": person.id, "id": self.id }, commit=commit)
    
    @staticmethod
    def unassign(dbConnection, questionId, taskId):
        sql = "update cascade_equal_categories set user_id=null where question_id=%s and id=%s"
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0
    
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
    
    @classmethod
    def create(cls, dbConnection, question, ideaId, category, count=None, commit=True):
        count = question.cascade_k2 if count is None else count
        insertValues = ["({0}, {1}, %s)".format(question.id, ideaId) for i in range(count)]
        categories = (category for i in range(count))
        sql = "insert into {0} (question_id, idea_id, category) values {1}".format(cls.table, ",".join(insertValues))
        dbConnection.cursor.execute(sql, tuple(categories))
        if commit:
            dbConnection.conn.commit()
    
    @classmethod
    def createForAllIdeas(cls, dbConnection, question, category, itemSet=None):
        sql = "select * from question_ideas where question_id=%s and duplicate_of is null"
        if itemSet is not None:
            sql += " and item_set={0}".format(itemSet)
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        insertValues = []
        for row in rows:
            insertValues.extend(["({0}, {1}, %s)".format(question.id, row["id"]) for i in range(question.cascade_k2)])
        categories = (category for i in range(len(rows)*question.cascade_k2))
        sql = "insert into {0} (question_id, idea_id, category) values {1}".format(cls.table, ",".join(insertValues))
        dbConnection.cursor.execute(sql, tuple(categories))
        count = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return count
     
    @classmethod
    def createForAllCategories(cls, dbConnection, question, ideaId, recheck=0):
        sql = "select * from categories where question_id=%s and skip=0"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        count = 0
        if len(rows) > 0:
            insertValues = []
            categories = ()
            for row in rows:
                insertValues.extend(["({0}, {1}, %s, {2})".format(question.id, ideaId, recheck) for i in range(question.cascade_k2)])
                categories += (row["category"],)  
            sql = "insert into {0} (question_id, idea_id, category, recheck) values {1}".format(cls.table, ",".join(insertValues))
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
        rowsUpdated = 0
        for task in job:
            taskId = task["id"]
            fit = task["fit"]
            sql = "update cascade_fit_categories_phase1 "
            sql += "set fit=%s, user_id={0} ".format(person.id) if person else " "
            sql += "where id=%s and {0}".format(CascadeFitCategory.incompleteCondition)
            dbConnection.cursor.execute(sql, (fit, taskId))
            rowsUpdated += dbConnection.cursor.rowcount
        dbConnection.conn.commit()

        if Question.onFitComplete:
            question.onFitComplete(dbConnection, rowsUpdated)
        
        if constants.VERIFY_CATEGORIES:
            verifyFitCount = CascadeFitCategory.createCascadeJobs(dbConnection, question, job)
            if verifyFitCount == 0 and CascadeVerifyCategory.isStepComplete(dbConnection, question):
                GenerateCascadeHierarchy(dbConnection, question)

        elif CascadeFitCategory.isStepComplete(dbConnection, question):
            GenerateCascadeHierarchy(dbConnection, question)
   
    @classmethod
    def createCascadeJobs(cls, dbConnection, question, job):
        # create CascadeVerifyCategory jobs for CascadeFitCategory tasks marked as fitting a category

        # find completed tasks that fit category
        fitTasks = []
        if question.cascade_k2 > 1:     
            minCount = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>=3 else 1

            taskConditions = []
            categories = ()
            for task in job:
                taskConditions.append("(idea_id={0} and category=%s)".format(task["idea_id"]))
                categories += (task["category"],)
                
            sql = "select idea_id,category,sum(fit) as fitvotes,count(*) as ct from {0},question_ideas where ".format(cls.table)
            sql += "{0}.question_id={1} ".format(CascadeFitCategory.table, question.id)
            sql += "and {0}.idea_id=question_ideas.id ".format(CascadeFitCategory.table)
            sql += "and ({0}) ".format(" or ".join(taskConditions))
            sql += "and {0} ".format(CascadeFitCategory.completeCondition)
            sql += "group by idea_id,category "
            sql += "having ct >= {0}".format(question.cascade_k2)            
            dbConnection.cursor.execute(sql, categories)
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                if row["fitvotes"] >= minCount:
                    fitTasks.append({ "idea_id": row["idea_id"], "category": row["category"] })
                            
        else:
            for task in job:
                fit = task["fit"]
                if fit == 1:
                    fitTasks.append(task)
            
        # create CascadeVerifyCategory for any completed tasks that passed voting threshold
        count = 0
        if len(fitTasks) > 0:
            insertValues = []
            categories = ()
            for task in fitTasks:
                for i in range(question.cascade_k2):
                    insertValues.extend(["({0}, {1}, %s)".format(question.id, task["idea_id"])])
                    categories += (task["category"],)
                
            sql = "insert into {0} (question_id, idea_id, category) values {1}".format(CascadeVerifyCategory.table, ",".join(insertValues))
            dbConnection.cursor.execute(sql, tuple(categories))
            count = dbConnection.cursor.rowcount
            dbConnection.conn.commit()
                            
            if Question.onMoreJobs:
                question.onMoreJobs(dbConnection, moreVerifyJobs=count)
                
        return count
                 
    def assignTo(self, dbConnection, person, commit=True):
        self.update(dbConnection, { "user_id": person.id, "id": self.id }, commit=commit)
    
    @classmethod
    def unassign(cls, dbConnection, questionId, taskId):
        sql = "update {0} set user_id=null where question_id=%s and id=%s".format(cls.table)
        dbConnection.cursor.execute(sql, (questionId, taskId))
        rowsUpdated = dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        return rowsUpdated if rowsUpdated is not None and rowsUpdated > 0 else 0

    @classmethod
    def isStepComplete(cls, dbConnection, question):
        sql = "select count(*) as ct from {0} where question_id=%s and {1}".format(cls.table, cls.incompleteCondition)
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        allTasksCompleted = row["ct"] == 0
        
        # if checking CascadeVerifyCategory step
        # also check that CascadeFitCategory step is complete since
        # verify tasks may not have been generated for all fit tasks yet
        if cls == CascadeVerifyCategory and allTasksCompleted:
            sql = "select count(*) as ct from {0} where question_id=%s and {1}".format(CascadeFitCategory.table, CascadeFitCategory.incompleteCondition)
            dbConnection.cursor.execute(sql, (question.id))
            row = dbConnection.cursor.fetchone()
            allTasksCompleted = row["ct"] == 0
            
        # need to check if any tasks exist for cases when 
        # this function is called as result of manually generating categories
        # (CascadeVerifyCategory tasks may not exist for older questions)
        tasksExist = False
        if allTasksCompleted:
            sql = "select count(*) as ct from {0} where question_id=%s".format(cls.table)
            dbConnection.cursor.execute(sql, (question.id))
            row = dbConnection.cursor.fetchone()
            tasksExist = row["ct"] > 0
                    
        return allTasksCompleted and tasksExist

    @staticmethod
    def recheckUncategorized(dbConnection, question):
        # recheck any uncategorized items (only once and not if categories force generated)
        # if verify categories, create CascadeVerifyCategory tasks for all uncategorized ideas  
        # (skip performing CascadeFitCategory tasks again)
        
        cls = CascadeVerifyCategory if constants.VERIFY_CATEGORIES else CascadeFitCategory
        sql = "select count(*) as ct from {0} where question_id=%s and recheck=1".format(cls.table)
        dbConnection.cursor.execute(sql, (question.id))
        row = dbConnection.cursor.fetchone()
        notCheckedYet = row["ct"] == 0 
        count = 0
        if notCheckedYet:
            minCount = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>=3 else 1
            
            # create cls tasks on all categories
            # for any ideas that did not fit any categories (uncategorized)
            sql = "select idea_id, sum(fit) as fit_votes from cascade_fit_categories_phase1 where "
            sql += "question_id=%s and "
            sql += "fit!=-1 "
            sql += "group by idea_id "
            sql += "having fit_votes<%s"
            dbConnection.cursor.execute(sql, (question.id, minCount))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                count += cls.createForAllCategories(dbConnection, question, row["idea_id"], recheck=1)
                
            # create cls tasks on all categories 
            # for any ideas that were not verified to fit any categories (uncategorized)
            if constants.VERIFY_CATEGORIES: 
                sql = "select idea_id, sum(fit) as fit_votes from cascade_fit_categories_phase2 where "
                sql += "question_id=%s and "
                sql += "fit!=-1 "
                sql += "group by idea_id "
                sql += "having fit_votes<%s"
                dbConnection.cursor.execute(sql, (question.id, minCount))
                rows = dbConnection.cursor.fetchall()
                for row in rows:
                    count += cls.createForAllCategories(dbConnection, question, row["idea_id"], recheck=1)
                
            if count > 0 and Question.onMoreJobs:
                fitCount = count if not constants.VERIFY_CATEGORIES else 0
                verifyCount = count if constants.VERIFY_CATEGORIES else 0
                question.onMoreJobs(dbConnection, moreFitJobs=fitCount, moreVerifyJobs=verifyCount)
                
        return True if count > 0 else False
    
class CascadeVerifyCategory(CascadeFitCategory):
    type = constants.VERIFY_CATEGORY
    table = "cascade_fit_categories_phase2"
                            
    @staticmethod
    def getJob(dbConnection, question, person): 
        tasks = []
        # check if job already assigned
        sql = "select cascade_fit_categories_phase2.*,idea from cascade_fit_categories_phase2,question_ideas where "
        sql += "cascade_fit_categories_phase2.idea_id=question_ideas.id and "
        sql += "cascade_fit_categories_phase2.question_id=%s and "
        sql += "cascade_fit_categories_phase2.user_id=%s and "
        sql += CascadeVerifyCategory.incompleteCondition
            
        dbConnection.cursor.execute(sql, (question.id, person.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task = CascadeVerifyCategory.createFromData(row)
            tasks.append(task)
             
        # if not, assign new tasks
        # ask user to check whether all categories fit or not for an idea (regardless of how many)
        if len(tasks) == 0:
            # find any fit categories that still need to be verified
            sql = "select idea_id from cascade_fit_categories_phase2 where "
            sql += "question_id=%s "
            sql += "and user_id is null "
            sql += "and (idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase2 where question_id=%s and user_id=%s) " if not helpers.allowDuplicateJobs() else ""
            sql += "order by rand() limit 1"
            if helpers.allowDuplicateJobs():
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
                sql += "and (cascade_fit_categories_phase2.idea_id,category) not in (select idea_id,category from cascade_fit_categories_phase2 where question_id=%s and user_id=%s) " if not helpers.allowDuplicateJobs() else ""
                sql += "group by category order by rand() limit {0}".format(question.cascade_s)                    
                if helpers.allowDuplicateJobs():
                    dbConnection.cursor.execute(sql, (question.id, ideaId))
                else:
                    dbConnection.cursor.execute(sql, (question.id, ideaId, question.id, person.id))
                
                rows = dbConnection.cursor.fetchall()
                for row in rows:
                    task = CascadeVerifyCategory.createFromData(row)
                    task.assignTo(dbConnection, person, commit=False)
                    tasks.append(task)
                dbConnection.conn.commit()
                
        return { "tasks" : tasks, "type" : CascadeVerifyCategory.type } if len(tasks) > 0 else None
       
    @staticmethod
    def saveJob(dbConnection, question, job, person=None):
        fitVotes = 0
        rowsUpdated = 0
        for task in job:
            taskId = task["id"]
            fit = task["fit"]
            if fit == 1:
                fitVotes += 1
            sql = "update cascade_fit_categories_phase2 set fit=%s"
            sql += ", user_id={0} ".format(person.id) if person else " "
            sql += "where id=%s and {0}".format(CascadeVerifyCategory.incompleteCondition)
            dbConnection.cursor.execute(sql, (fit, taskId))
            rowsUpdated += dbConnection.cursor.rowcount
        dbConnection.conn.commit()
        
        if Question.onVerifyComplete:
            question.onVerifyComplete(dbConnection, rowsUpdated)
        
        if CascadeVerifyCategory.isStepComplete(dbConnection, question):
            GenerateCascadeHierarchy(dbConnection, question)

class Review():        
    @staticmethod
    def getReviewGroup(dbConnection, reviewId):
        reviewGroup = []
        sql = "select * from reviews,questions where reviews.question_id=questions.id and review_id=%s"
        dbConnection.cursor.execute(sql, (reviewId))
        rows = dbConnection.cursor.fetchall()
        reviewCount = None
        for row in rows:
            question = Question.createFromData(row)
            if not reviewCount:
                reviewCount = row["review_count"]
            elif reviewCount != row["review_count"]:
                helpers.log("WARNING: review_count is not the same for review group {0}".format(reviewId))
                
            reviewGroup.append({ "question": question, "review_id": reviewId, "review_count": reviewCount })
                    
        return reviewGroup
                
    @staticmethod
    def createJobs(dbConnection, reviewGroup):            
        if len(reviewGroup) == 0:
            return

        FitReview.createJobs(dbConnection, reviewGroup)
        CategoryGroupReview.createJobs(dbConnection, reviewGroup)
    
    @staticmethod
    def getJob(dbConnection, reviewId, reviewerId, questionId):
        job = FitReview.getJob(dbConnection, reviewId, reviewerId, questionId)
        if not job:
            job = CategoryGroupReview.getJob(dbConnection, reviewId, reviewerId, questionId)
        return job
    
    @staticmethod    
    def saveJob(dbConnection, job, reviewerId):
        if job:
            if job["type"] == constants.REVIEW_RESPONSE_FIT:
                FitReview.saveJob(dbConnection, job, reviewerId)
            elif job["type"] == constants.REVIEW_CATEGORY_GROUP:
                CategoryGroupReview.saveJob(dbConnection, job, reviewerId)
        
    @staticmethod
    def getCurrentQuestionId(dbConnection, reviewId, reviewerId):
        stats = Review.getStats(dbConnection, reviewId, reviewerId)
        waitingToStart = []
        inProgress = None
        for questionId in stats:
            complete = stats[questionId]["complete"]
            incomplete = stats[questionId]["incomplete"]
            if complete>0 and incomplete>0:
                inProgress = questionId
            if complete==0:
                waitingToStart.append(questionId)
                
        return inProgress if inProgress else (random.choice(waitingToStart) if len(waitingToStart) > 0 else None)

    @staticmethod
    def getStats(dbConnection, reviewId, reviewerId):
        stats = {}
        stats1 = FitReview.getStats(dbConnection, reviewId, reviewerId)
        stats2 = CategoryGroupReview.getStats(dbConnection, reviewId, reviewerId)
        for question_id in stats1:
            if question_id not in stats:
                stats[question_id] = {}
                stats[question_id]["question_text"] = stats1[question_id]["question_text"]
                stats[question_id]["response_fit_complete"] = 0
                stats[question_id]["response_fit_incomplete"] = 0
                stats[question_id]["category_group_complete"] = 0
                stats[question_id]["category_group_incomplete"] = 0
                
            stats[question_id]["response_fit_complete"] += stats1[question_id]["complete"]
            stats[question_id]["response_fit_incomplete"] += stats1[question_id]["incomplete"]
            stats[question_id]["category_group_complete"] += stats2[question_id]["complete"]
            stats[question_id]["category_group_incomplete"] += stats2[question_id]["incomplete"]        
            stats[question_id]["complete"] = stats[question_id]["response_fit_complete"] + stats[question_id]["category_group_complete"]
            stats[question_id]["incomplete"] = stats[question_id]["response_fit_incomplete"] + stats[question_id]["category_group_incomplete"]

        return stats
                
class FitReview(DBObject):
    type = constants.REVIEW_RESPONSE_FIT
    table = "fit_reviews"
    fields = [ "id", "review_id", "reviewer_id", "question_id", "idea_id", "idea", "category", "fit_rating" ]
    completeCondition = "(fit_rating!=-1)"
    incompleteCondition = "(fit_rating=-1)"
   
    def __init__(self):
        self.id = None
        self.review_id = None
        self.reviewer_id = None
        self.question_id = None
        self.idea_id = None
        self.idea = None # stored in question_ideas table
        self.category = None
        self.fit_rating = -1
    
    @classmethod
    def createFromData(cls, data):
        task = super(FitReview, cls).createFromData(data)
        if task:
            ideaField = "idea" if "idea" in data else Idea.tableField("idea") if Idea.tableField("idea") in data else None
            if ideaField:
                task.idea = data[ideaField]
            else:
                helpers.log("WARNING: idea not included in task data")
        return task
    
    @staticmethod
    def createJobs(dbConnection, reviewGroup):            
        if len(reviewGroup) == 0:
            return

        reviewId = reviewGroup[0]["review_id"]
        
        # delete existing fit review for group (if any)
        dbConnection.cursor.execute("delete from fit_reviews where review_id=%s", (reviewId))
        dbConnection.conn.commit()
                
        # TODO/FIX: depending on how many ideas/categories/questions this could time out if it takes too long
        for groupItem in reviewGroup:
            question = groupItem["question"]
            reviewCount = groupItem["review_count"]
            if constants.REVIEW_FINAL_FITS_ONLY:
                categoryGroups = getCategoryGroups(dbConnection, question)
                for category in categoryGroups:
                    ideaIds = categoryGroups[category]
                    for ideaId in ideaIds:
                        sql = "insert into fit_reviews (review_id, reviewer_id, question_id, idea_id, category) values(%s, %s, %s, %s, %s)"
                        for i in range(reviewCount):
                            reviewerId = i+1
                            dbConnection.cursor.execute(sql, (reviewId, reviewerId, question.id, ideaId, category))
                dbConnection.conn.commit()
            
            else:            
                ideaIds = []
                sql = "select * from question_ideas where question_id=%s order by id"
                dbConnection.cursor.execute(sql, (question.id))
                rows = dbConnection.cursor.fetchall()
                for row in rows:
                    ideaIds.append(row["id"])
                
                categories = []
                sql = "select distinct(category) from cascade_fit_categories_phase1 where question_id=%s order by category"
                dbConnection.cursor.execute(sql, (question.id))
                rows = dbConnection.cursor.fetchall()
                for row in rows:
                    categories.append(row["category"])
            
                for ideaId in ideaIds:
                    for category in categories:
                        sql = "insert into fit_reviews (review_id, reviewer_id, question_id, idea_id, category) values(%s, %s, %s, %s, %s)"
                        for i in range(reviewCount):
                            reviewerId = i+1
                            dbConnection.cursor.execute(sql, (reviewId, reviewerId, question.id, ideaId, category))
                dbConnection.conn.commit()
                                                   
    @staticmethod
    def getJob(dbConnection, reviewId, reviewerId, questionId):
        # find an idea that still needs to be checked
        sql = "select idea_id from fit_reviews where "
        sql += "question_id=%s "
        sql += "and review_id=%s "
        sql += "and reviewer_id=%s "
        sql += "and {0} ".format(FitReview.incompleteCondition)
        sql += "order by rand() limit 1"
        dbConnection.cursor.execute(sql, (questionId, reviewId, reviewerId))
        row = dbConnection.cursor.fetchone()
        ideaId = row["idea_id"] if row else None
    
        # now find categories to check for this idea
        tasks = []
        if ideaId:
            sql = "select fit_reviews.*,question_ideas.idea from fit_reviews,question_ideas where "
            sql += "fit_reviews.idea_id=question_ideas.id "
            sql += "and fit_reviews.question_id=%s "
            sql += "and review_id=%s "
            sql += "and reviewer_id=%s "
            sql += "and idea_id=%s "
            sql += "and {0} ".format(FitReview.incompleteCondition)
            sql += "order by category"
            dbConnection.cursor.execute(sql, (questionId, reviewId, reviewerId, ideaId))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                task = FitReview.createFromData(row)
                tasks.append(task)
                       
        return { "question_id": questionId, "tasks" : tasks, "type": constants.REVIEW_RESPONSE_FIT } if len(tasks) > 0 else None
                         
    @staticmethod
    def saveJob(dbConnection, job, reviewerId):
        questionId = job["question_id"]
        for task in job["tasks"]:
            taskId = task["id"]
            fitRating = task["fit_rating"]
            sql = "update fit_reviews "
            sql += "set fit_rating=%s "
            sql += "where id=%s"
            dbConnection.cursor.execute(sql, (fitRating, taskId))
        dbConnection.conn.commit()

    @staticmethod
    def getStats(dbConnection, reviewId, reviewerId):
        stats = {}
        dbConnection.cursor.execute("select * from reviews,questions where reviews.question_id=questions.id and review_id=%s", (reviewId))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            questionId = row["question_id"]
            questionText = row["question"]
            if questionId not in stats:
                stats[questionId] = { "question_text": questionText, "incomplete": 0, "complete": 0 }
            
            sql = "select fit_rating, count(*) as ct from fit_reviews where "
            sql += "question_id=%s "
            sql += "and review_id=%s "
            sql += "and reviewer_id=%s "
            sql += "group by fit_rating"
            dbConnection.cursor.execute(sql, (questionId, reviewId, reviewerId))
            rows2 = dbConnection.cursor.fetchall()
            for row2 in rows2:    
                stats[questionId]["complete"] += row2["ct"] if row2["fit_rating"] != -1 else 0
                stats[questionId]["incomplete"] += row2["ct"] if row2["fit_rating"] == -1 else 0
        
        return stats
    
class CategoryGroupReview(DBObject):
    type = constants.REVIEW_CATEGORY_GROUP
    table = "group_reviews"
    fields = [ "id", "review_id", "reviewer_id", "question_id", "category", "ideas", "group_rating" ]
    completeCondition = "(group_rating!=-1)"
    incompleteCondition = "(group_rating=-1)"
   
    def __init__(self):
        self.id = None
        self.review_id = None
        self.reviewer_id = None
        self.question_id = None
        self.category = None
        self.ideas = []
        self.group_rating = -1
   
    @classmethod
    def createFromData(cls, data, dbConnection):
        task = super(CategoryGroupReview, cls).createFromData(data)
        
        # TODO/FIX: need to pass in cascade_k2 to calculate minCount; assume 1 for now since cascade_k2 never above 2 currently
        #minCount = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>=3 else 1
        minCount = 1
            
        task.ideas = []
        sql = "select idea_id,idea,count(*) as ct from {0},question_ideas where ".format(CascadeVerifyCategory.table)
        sql += "{0}.idea_id=question_ideas.id ".format(CascadeVerifyCategory.table)
        sql += "and {0}.question_id=%s ".format(CascadeVerifyCategory.table)
        sql += "and category=%s "
        sql += "and fit=1 "
        sql += "group by idea_id "
        sql += "having ct>=%s "
        sql += "order by idea"
        dbConnection.cursor.execute(sql, (task.question_id, task.category, minCount))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            task.ideas.append(row["idea"])
                         
        return task
    
    @staticmethod
    def createJobs(dbConnection, reviewGroup):            
        if len(reviewGroup) == 0:
            return

        reviewId = reviewGroup[0]["review_id"]
        
        # delete existing jobs (if any)
        dbConnection.cursor.execute("delete from group_reviews where review_id=%s", (reviewId))
        dbConnection.conn.commit()
                
        # find categories to check
        # (these are generated categories - ones with responses - not interim categories)
        for groupItem in reviewGroup:
            question = groupItem["question"]
            reviewCount = groupItem["review_count"]
            categoryGroups = getCategoryGroups(dbConnection, question)
            for category in categoryGroups:            
                sql = "insert into group_reviews (review_id, reviewer_id, question_id, category) values(%s, %s, %s, %s)"
                for i in range(reviewCount):
                    reviewerId = i+1
                    dbConnection.cursor.execute(sql, (reviewId, reviewerId, question.id, category))
        dbConnection.conn.commit()
                                                        
    @staticmethod
    def getJob(dbConnection, reviewId, reviewerId, questionId):
        # find an category group that still needs to be checked
        sql = "select * from group_reviews where "
        sql += "question_id=%s "
        sql += "and review_id=%s "
        sql += "and reviewer_id=%s "
        sql += "and {0} ".format(CategoryGroupReview.incompleteCondition)
        sql += "order by rand() limit 1"
        dbConnection.cursor.execute(sql, (questionId, reviewId, reviewerId))
        row = dbConnection.cursor.fetchone()
    
        tasks = []
        if row:               
            task = CategoryGroupReview.createFromData(row, dbConnection)
            tasks.append(task)
                                   
        return { "question_id": questionId, "tasks" : tasks, "type": constants.REVIEW_CATEGORY_GROUP } if len(tasks) > 0 else None
                     
    @staticmethod
    def saveJob(dbConnection, job, reviewerId):
        questionId = job["question_id"]
        for task in job["tasks"]:
            taskId = task["id"]
            groupRating = task["group_rating"]
            sql = "update group_reviews "
            sql += "set group_rating=%s "
            sql += "where id=%s"
            dbConnection.cursor.execute(sql, (groupRating, taskId))
        dbConnection.conn.commit()
    
    @staticmethod
    def getStats(dbConnection, reviewId, reviewerId):
        stats = {}
        dbConnection.cursor.execute("select * from reviews,questions where reviews.question_id=questions.id and review_id=%s", (reviewId))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            questionId = row["question_id"]
            questionText = row["question"]
            if questionId not in stats:
                stats[questionId] = { "question_text": questionText, "incomplete": 0, "complete": 0 }
            
            sql = "select group_rating, count(*) as ct from group_reviews where "
            sql += "question_id=%s "
            sql += "and review_id=%s "
            sql += "and reviewer_id=%s "
            sql += "group by group_rating"
            dbConnection.cursor.execute(sql, (questionId, reviewId, reviewerId))
            rows2 = dbConnection.cursor.fetchall()
            for row2 in rows2:    
                stats[questionId]["complete"] += row2["ct"] if row2["group_rating"] != -1 else 0
                stats[questionId]["incomplete"] += row2["ct"] if row2["group_rating"] == -1 else 0
        
        return stats
                                                                    
def GenerateCascadeHierarchy(dbConnection, question, forced=False, forTesting=False): 
    
    questionCategoriesTable = "question_categories" if not forTesting else "question_categories2"
    categoriesTable = "categories" if not forTesting else "categories2"
                
    # delete any remaining fit tasks that should have been deleted because category was found equal to another category
    if constants.FIND_EQUAL_CATEGORIES:
        sql = "delete from cascade_fit_categories_phase1 where question_id=%s and category in (select category from categories where question_id=%s and skip=1)"
        dbConnection.cursor.execute(sql, (question.id, question.id))
        if constants.VERIFY_CATEGORIES:
            sql = "delete from cascade_fit_categories_phase2 where question_id=%s and category in (select category from categories where question_id=%s and skip=1)"
            dbConnection.cursor.execute(sql, (question.id, question.id))
        dbConnection.conn.commit()
    
    # recheck any uncategorized items (only once and not if categories force generated)
    if constants.RECHECK_UNCATEGORIZED and not forced:
        moreJobs = CascadeFitCategory.recheckUncategorized(dbConnection, question)
        if moreJobs:
            return {}
                                 
    # get category groups based on current CascadeCategoryFit tasks and CascadeVerifyFit tasks
    categoryGroups = getCategoryGroups(dbConnection, question)
    ideaCount = Idea.getCountForQuestion(dbConnection, question.id)
    
    # remove any categories based on size (too big, too small)        
    categoriesToRemove = []
    for category in categoryGroups:
        # remove any categories with less than q items
        if len(categoryGroups[category]) < constants.CASCADE_Q:
            categoriesToRemove.append(category)
            
        # remove any loose categories (with >= p % of all items)
        # TODO/FIX: should # categories be taken into consideration?
        elif constants.DELETE_LOOSE_CATEGORIES and len(categoryGroups[category]) >= ideaCount * (question.cascade_p/100.0):
            categoriesToRemove.append(category)
        
    for category in categoriesToRemove:
        del categoryGroups[category]
    
    # find duplicate categories and subcategories
    duplicateCategories = {}
    nestedCategories = {}
    if question.cascade_p > 0:
        results = mergeAndNestCategories(categoryGroups, overlapPercentage=question.cascade_p)
        categoryGroups = results["category_groups"]
        duplicateCategories = results["duplicate_categories"]
        nestedCategories = results["nested_categories"]
            
        # check for duplicates and subcategories again if duplicates found during the first pass
        if constants.MERGE_NEST_CATEGORIES_AGAIN and len(duplicateCategories.keys()) > 0:
            results = mergeAndNestCategories(categoryGroups, overlapPercentage=question.cascade_p)
            categoryGroups = results["category_groups"]
            duplicateCategories2 = results["duplicate_categories"]                    
            nestedCategories = results["nested_categories"]
            
            for category in duplicateCategories2:
                if category not in duplicateCategories:
                    duplicateCategories[category] = duplicateCategories2[category]
                else:
                    duplicateCategories[category].extend(duplicateCategories2[category])
                    for mergedCategory in duplicateCategories2[category]:
                        if mergedCategory in duplicateCategories:
                            previousMergedCategories = duplicateCategories[mergedCategory]
                            duplicateCategories[category].extend(previousMergedCategories)
                        
                if category not in categoryGroups:
                    del duplicateCategories[category]
                    
    # find any skipped categories before they are deleted from db
    # a category is skipped because it was found to be equal to another category (CascadeEqualCategory)
    skippedCategories = []
    if constants.FIND_EQUAL_CATEGORIES:
        sql = "select * from categories where question_id=%s and skip=1"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            skippedCategories.append(row["category"])
     
    # delete question categories and categories tables
    sql = "delete from {0} where question_id=%s".format(questionCategoriesTable)
    dbConnection.cursor.execute(sql, (question.id))

    sql = "delete from {0} where question_id=%s".format(categoriesTable)
    dbConnection.cursor.execute(sql, (question.id))
           
    # TODO: inserts are faster if done as a group
    for category in categoryGroups:
        # NOTE: category stems and skip attributes not maintained in final categories table
        ideaIds = categoryGroups[category]
        sameAs = ":::".join(duplicateCategories[category]) if category in duplicateCategories else None
        subcategories = ":::".join(nestedCategories[category]) if category in nestedCategories else None
        sql = "insert into {0} (question_id, category, same_as, subcategories) values(%s, %s, %s, %s)".format(categoriesTable)
        dbConnection.cursor.execute(sql, (question.id, category, sameAs, subcategories))
        categoryId = dbConnection.cursor.lastrowid
        for ideaId in ideaIds:
            sql = "insert into {0} (question_id, idea_id, category_id) values(%s, %s, %s)".format(questionCategoriesTable)
            dbConnection.cursor.execute(sql, (question.id, ideaId, categoryId))
                    
    dbConnection.conn.commit()
                   
    stats = {}
    if not forTesting:
        stats = question.cascadeComplete(dbConnection, skippedCategories)
    return stats

# get category groups using the results of CascadeFitCategory tasks and/or CascadeVerifyCategory tasks
# a category group is a list of idea ids contained in a category, keyed by category name
def getCategoryGroups(dbConnection, question):
    # TODO: how should voting threshold be determined; different depending on whether or not categories are verified?
    minCount = constants.DEFAULT_VOTING_THRESHOLD if question.cascade_k2>=3 else 1
        
    verifiedFits = {}
    verifyComplete = False    
    if constants.VERIFY_CATEGORIES:
        # check if verified tasks are complete
        # if not, use fit tasks to generate hierarchy and update with completed verify tasks
        verifyComplete = CascadeVerifyCategory.isStepComplete(dbConnection, question)
        if not verifyComplete:
            sql = "select idea_id,category,sum(fit) as fitvotes, count(*) as ct from {0} where ".format(CascadeVerifyCategory.table)
            sql += "question_id=%s "
            sql += "and {0}".format(CascadeVerifyCategory.completeCondition)
            sql += "group by idea_id,category "
            sql += "having ct>=%s"
            dbConnection.cursor.execute(sql, (question.id, question.cascade_k2))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                ideaId = row["idea_id"]
                category = row["category"]
                categoryFits = row["fitvotes"] >= minCount
                verifyKey = "{0}:::{1}".format(ideaId, category)
                verifiedFits[verifyKey] = categoryFits

    categoryGroups = {}
    fitCls = CascadeVerifyCategory if constants.VERIFY_CATEGORIES and verifyComplete else CascadeFitCategory      
    sql = "select idea_id,idea,category,count(*) as ct from {0},question_ideas where ".format(fitCls.table)
    sql += "{0}.idea_id=question_ideas.id ".format(fitCls.table)
    sql += "and {0}.question_id=%s ".format(fitCls.table)
    sql += "and fit=1 "
    sql += "group by idea_id,category "
    sql += "having ct>=%s"
    dbConnection.cursor.execute(sql, (question.id, minCount))
    rows = dbConnection.cursor.fetchall()        
    for row in rows:
        category = row["category"]
        ideaId = row["idea_id"]
        
        addIdeaToCategory = True
        if constants.VERIFY_CATEGORIES:
            verifyKey = "{0}:::{1}".format(ideaId, category)
            if verifyKey in verifiedFits:
                addIdeaToCategory = verifiedFits[verifyKey]
        
        if addIdeaToCategory:        
            if category not in categoryGroups:
                categoryGroups[category] = []
            categoryGroups[category].append(ideaId)

    return categoryGroups

def mergeAndNestCategories(categoryGroups, overlapPercentage=constants.CASCADE_P):
    duplicateCategories = {}
    nestedCategories = {}
    categoriesToRemove = []
    
    if overlapPercentage > 0:
        categoryKeys = categoryGroups.keys()
        for x in range(len(categoryKeys)):
            for y in range(x, len(categoryKeys)):
                if x != y:
                    category1 = categoryKeys[x]
                    category2 = categoryKeys[y]
                    ideaIds1 = categoryGroups[category1]
                    ideaIds2 = categoryGroups[category2]
    
                    sharedIdeaIds = helpers.intersect(ideaIds1, ideaIds2)
                    sizePercentage = (min(len(ideaIds1),len(ideaIds2)) / float(max(len(ideaIds1),len(ideaIds2))))*100
                    duplicateThreshold = min(len(ideaIds1),len(ideaIds2))*(overlapPercentage/100.0)
                    nestedThreshold = min(len(ideaIds1),len(ideaIds2))*(overlapPercentage/100.0)
                       
                    # find duplicate categories (that have more than p % of overlapping items)
                    if sizePercentage >= constants.MIN_DUPLICATE_SIZE_PERCENTAGE and len(sharedIdeaIds) >= duplicateThreshold:
                        duplicateCategory = category1 if len(ideaIds1) < len(ideaIds2) else category2
                        primaryCategory = category1 if duplicateCategory != category1 else category2
                        if duplicateCategory not in categoriesToRemove:
                            categoriesToRemove.append(duplicateCategory)
                        if primaryCategory not in duplicateCategories:
                            duplicateCategories[primaryCategory] = []
                        duplicateCategories[primaryCategory].append(duplicateCategory)
    
                    # find subcategories (make sure they aren't flagged to be removed)   
                    if constants.FIND_SUBCATEGORIES and sizePercentage < constants.MIN_DUPLICATE_SIZE_PERCENTAGE and len(sharedIdeaIds) >= nestedThreshold:
                        primaryCategory = category1 if len(ideaIds1) > len(ideaIds2) else category2
                        subCategory = category2 if primaryCategory == category1 else category1
                        if primaryCategory not in categoriesToRemove or subCategory not in categoriesToRemove:
                            if primaryCategory not in nestedCategories:
                                nestedCategories[primaryCategory] = []
                            nestedCategories[primaryCategory].append(subCategory)

        # merge items in duplicate categories with primary (larger) category
        for primaryCategory in duplicateCategories: 
            for duplicateCategory in duplicateCategories[primaryCategory]:
                duplicateIdeaIds = categoryGroups[duplicateCategory]
                categoryGroups[primaryCategory] = helpers.union(categoryGroups[primaryCategory], duplicateIdeaIds)
                        
        # remove duplicate categories                    
        for category in categoriesToRemove:
            del categoryGroups[category]
            
    return { "category_groups": categoryGroups, "duplicate_categories": duplicateCategories, "nested_categories": nestedCategories }
                            
def clearMemcache(question):
    client = memcache.Client() 
    client.delete("categories_{0}".format(question.id))
    client.delete("cascade_start_time_{0}".format(question.id))
    client.delete("cascade_end_time_{0}".format(question.id))
    client.delete("cascade_item_set_{0}".format(question.id))
 
def getCategories(question):
    client = memcache.Client()
    key = "categories_{0}".format(question.id)
    categories = client.get(key)
    return categories if categories else []
    
def recordCategory(question, category):
    client = memcache.Client()
    key = "categories_{0}".format(question.id)
    categories = client.get(key)
    if not categories:
        categories = []
    if category not in categories:
        categories.append(category)
        categories.sort()
    helpers.saveToMemcache(key, categories)

def removeCategory(question, category):
    client = memcache.Client()
    key = "categories_{0}".format(question.id)
    categories = client.get(key)
    if not categories:
        categories = []
    if category in categories:
        categories.remove(category)
    helpers.saveToMemcache(key, categories)

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

def getNewCascadeItemSet(question):
    client = memcache.Client()
    key = "cascade_item_set_{0}".format(question.id)

    itemSetRatio = constants.ITEM_SET_RATIOS[question.cascade_m]
    xInitial = itemSetRatio["initial"]
    xSubsequent = itemSetRatio["subsequent"]
    newItemSet = constants.CASCADE_INITIAL_ITEM_SET
        
    i = 0
    MAX_RETRIES = 15
    while i <= MAX_RETRIES:
        itemSetInfo = client.gets(key)
        if itemSetInfo is None:
            newItemIndex = 1
            newItemSet = constants.CASCADE_INITIAL_ITEM_SET
            client.add(key, { "item_index": newItemIndex, "initial_item_set_count": 1 })
            break
        else:
            newItemIndex = itemSetInfo["item_index"] + 1
            initialItemSetCount = itemSetInfo["initial_item_set_count"]

            # if max number items already in initial item set, place item
            # in subsequent item set       
            if initialItemSetCount >= constants.MAX_INITIAL_ITEM_SET_SIZE:
                newItemSet = constants.CASCADE_SUBSEQUENT_ITEM_SET
                
            elif newItemIndex <= xInitial:
                newItemSet = constants.CASCADE_INITIAL_ITEM_SET
                
            elif newItemIndex <= xInitial + xSubsequent:
                newItemSet = constants.CASCADE_SUBSEQUENT_ITEM_SET
                
            else:
                newItemSet = constants.CASCADE_INITIAL_ITEM_SET
                newItemIndex = 1
                
            if client.cas(key, { "item_index": newItemIndex, "initial_item_set_count": initialItemSetCount + 1 if newItemSet == constants.CASCADE_INITIAL_ITEM_SET else initialItemSetCount }):
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

CASCADE_CLASSES = [ CascadeSuggestCategory, CascadeBestCategory, CascadeEqualCategory, CascadeFitCategory, CascadeVerifyCategory ]

class DiscussFlag(DBObject):               
    table = "question_discuss"
    fields = [ "question_id", "idea_id", "user_id" ]
    
    def __init__(self):
        self.question_id = None
        self.idea_id = None
        self.user_id = None
        self.user_nickname = None
        self.user_identity = None
    
    @staticmethod
    def create(dbConnection, question, ideaId, person, admin=False, insertInDb=True):
        discuss = DiscussFlag()
        discuss.question_id = question.id
        discuss.idea_id = ideaId
        discuss.user_id = person.id
        identity = person.getIdentity(admin=admin)
        discuss.user_nickname = identity["user_nickname"]
        discuss.user_identity = identity["user_identity"]
        
        if insertInDb:
            # TODO/FIX: could INSERT IGNORE be used other places (w/ unique index) to prevent duplicate records from being added
            sql = "insert ignore into question_discuss (question_id, idea_id, user_id) values (%s, %s, %s)"
            dbConnection.cursor.execute(sql, (question.id, ideaId, person.id))
            dbConnection.conn.commit()
        
        return discuss
    
    @classmethod
    def createFromData(cls, data, admin=False):
        discuss = super(DiscussFlag, cls).createFromData(data)
        if "nickname" in data and "authenticated_nickname" in data:
            person = Person()
            person.nickname = data["nickname"]
            person.authenticated_nickname = data["authenticated_nickname"]
            identity = person.getIdentity(admin=admin)
            discuss.user_nickname = identity["user_nickname"]
            discuss.user_identity = identity["user_identity"]
        else:
            helpers.log("WARNING: nickname and authenticated_nickname not included in data")            
        return discuss
   
    @staticmethod
    def delete(dbConnection, question, ideaId, person, admin=False):        
        sql = "delete from question_discuss where question_id=%s and idea_id=%s and user_id=%s"
        dbConnection.cursor.execute(sql, (question.id, ideaId, person.id))
        dbConnection.conn.commit()
        return DiscussFlag.create(dbConnection, question, ideaId, person, admin=admin, insertInDb=False)
         
    @staticmethod
    def getFlags(dbConnection, question, ideaId=None, admin=False):
        flags = []
        sql = "select * from question_discuss, users where question_discuss.user_id=users.id and question_discuss.question_id=%s"
        sql += " and idea_id=%s" if ideaId else ""
        dbConnection.cursor.execute(sql, (question.id, ideaId) if ideaId else (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            discuss = DiscussFlag.createFromData(row, admin=admin)
            flags.append(discuss.toDict())
        
        return flags
    
    def toDict(self, admin=False, person=None):
        objDict = super(DiscussFlag, self).toDict()
        objDict["user_nickname"] = self.user_nickname
        objDict["user_identity"] = self.user_identity
        
        # force inclusion of user identity if admin and person defined
        # may already be defined if created with admin=True
        # used when sending discuss messages between admin and non-admin users
        if person:
            identity = person.getIdentity(admin=admin)
            objDict["user_nickname"] = identity["user_nickname"]
            objDict["user_identity"] = identity["user_identity"]

        return objDict
          
# TODO / DB: no longer using the following db fields (not deleted from public database, MAY BE OUT OF DATE):
#    questions: phase, cascade_iteration, cascade_step, cascade_step_count
#    questions: nickname_authentication (but not until replaced with authentication_type)
#    cascade_suggested_categories: cascade_iteration
#    cascade_best_categories: cascade_iteration
#    cascade_fit_categories_phase1: cascade_iteration, subsequent
#    task_queue_debug