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
            
        if helpers.isRunningLocally():
            # only import MySQLdb when running locally since not available on GAE
            import MySQLdb
            self.conn = MySQLdb.connect("localhost", constants.LOCAL_DB_USER, constants.LOCAL_DB_PWD, constants.DATABASE_NAME)
            self.cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
        else:
            # BEHAVIOR: connects as MySQL root
            # TODO: need to understand if/why non-root MySQL users should be used
            self.conn = rdbms.connect(constants.CLOUDSQL_INSTANCE, constants.DATABASE_NAME)
            self.cursor = self.conn.cursor(use_dict_cursor=True)
            
    def disconnect(self):
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        
        if self.conn:
            self.conn.close()
            self.conn = None
              
class Question():
    id = None
    title = None
    questionText = None
    nicknameAuthentication = False
    userId = None
    authenticatedUserId = None # not stored in database
    phase = 0
    cascadeK = 5
    cascadeM = 32
    cascadeT = 8
      
    @property
    def code(self):
        return self.id
    
    @property
    def question(self):
        return self.questionText
     
    @staticmethod
    def create(dbConnection, author, title, questionText, nicknameAuthentication=False):
        if author:
            # create unique 5 digit id
            # TODO: need better way to create question id
            idCreated = False
            while not idCreated:
                questionId = str(random.randint(10000, 99999))
                question = Question.getById(dbConnection, questionId)
                if not question:
                    idCreated = True
                        
            question = Question()
            properties = {
                "id" : questionId,
                "title" : title,
                "questionText" : questionText,
                "nicknameAuthentication" : nicknameAuthentication,
                "userId" : author.id,
                "authenticatedUserId" : author.authenticatedUserId
            }
            question.update(dbConnection, properties, create=True)
            return question
    
    # TODO: improve code by looping through all available properties
    # unfortunately vars() returns {} when object is newly constructed
    def update(self, dbConnection=None, properties={}, create=False):            
        updateProperties = []
        updateValues = ()
        if "id" in properties:
            self.id = properties["id"]
        if "title" in properties:
            self.title = properties["title"]
            updateProperties.append("title=%s")
            updateValues += (self.title,)
        if "questionText" in properties:
            self.questionText = properties["questionText"]
            updateProperties.append("question=%s")
            updateValues += (self.questionText,)
        if "nicknameAuthentication" in properties:
            self.nicknameAuthentication = properties["nicknameAuthentication"]
            updateProperties.append("nickname_authentication=%s")
            updateValues += (self.nicknameAuthentication,)
        if "userId" in properties:
            self.userId = properties["userId"]
            updateProperties.append("user_id=%s")
            updateValues += (self.userId,)
        if "phase" in properties:
            self.phase = properties["phase"]
            updateProperties.append("phase=%s")
            updateValues += (self.phase,)
        if "cascadeK" in properties:
            self.cascadeK = properties["cascadeK"]
            updateProperties.append("cascade_k=%s")
            updateValues += (self.cascadeK,)
        if "cascadeM" in properties:
            self.cascadeM = properties["cascadeM"]
            updateProperties.append("cascade_m=%s")
            updateValues += (self.cascadeM,)
        if "cascadeT" in properties:
            self.cascadeT = properties["cascadeT"]
            updateProperties.append("cascade_t=%s")
            updateValues += (self.cascadeT,)

        if dbConnection:
            if create:
                sql = "insert into questions (id, title, question, nickname_authentication, user_id) values (%s, %s, %s, %s, %s)"
                dbConnection.cursor.execute(sql, (self.id, self.title, self.questionText, self.nicknameAuthentication, self.userId))
                dbConnection.conn.commit()
            
            else:
                sql = "update questions set {0} where id=%s".format(",".join(updateProperties))
                dbConnection.cursor.execute(sql, updateValues + (self.id,));
                dbConnection.conn.commit()
           
    def delete(self, dbConnection):
        dbConnection.cursor.execute("delete from questions where id={0}".format(self.id))
        dbConnection.cursor.execute("delete from question_ideas where question_id={0}".format(self.id))
        dbConnection.cursor.execute("delete user_clients from users,user_clients where users.id=user_clients.user_id and question_id={0}".format(self.id))
        dbConnection.conn.commit()
        self = Question()
        return self
        
    def isAuthor(self):
        # BEHAVIOR: question author must be authenticated user
        user = users.get_current_user()
        return user and self.authenticatedUserId and user.user_id()==self.authenticatedUserId
                
    @staticmethod
    def getById(dbConnection, questionId):
        sql = "select * from questions,users where questions.user_id=users.id and questions.id=%s"
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return Question.getFromDBRow(row) if row else None

    @staticmethod                
    def getByUser(dbConnection, asDict=False):
        questions = []
        user = users.get_current_user()
        if user:
            sql = "select * from questions,users where questions.user_id=users.id and authenticated_user_id=%s"
            dbConnection.cursor.execute(sql, (user.user_id()))
            rows = dbConnection.cursor.fetchall()
            for row in rows:
                question = Question.getFromDBRow(row)
                if asDict:
                    question = question.toDict()
                questions.append(question)
        return questions
     
    @staticmethod
    def getFromDBRow(row):
    # TODO/COMMENT: row must include authenticated_user_id from users table
        question = None
        if row:
            question = Question()
            # TODO/FIX: how to protect against multiple columns with same name
            question.id = row["id"]
            question.title = row["title"]
            question.questionText = row["question"]
            question.nicknameAuthentication = row["nickname_authentication"]
            question.userId = row["user_id"]
            question.authenticatedUserId = row["authenticated_user_id"]
            question.phase = row["phase"]
            question.cascadeK = row["cascade_k"]
            question.cascadeM = row["cascade_m"]
            question.cascadeT = row["cascade_t"]
        return question
    
    @staticmethod
    def getStats(dbConnection, questionId):
        stats = {
            "question_id" : questionId,
            "num_ideas" : Idea.getCountForQuestion(dbConnection, questionId),
            # TODO/FIX: may not include question author in count (not sure)
            "num_users" : Person.getCountForQuestion(dbConnection, questionId)
        }
        return stats
               
    def toDict(self):
        return {
            "id": self.id,
            "title": self.title,
            "question": self.questionText,
            "nickname_authentication": self.nicknameAuthentication,
            "user_id": self.userId,
            "phase": self.phase,
            "cascade_k": self.cascadeK,
            "cascade_m": self.cascadeM,
            "cascade_t": self.cascadeT
        } 

class Person():               
    id = None
    authenticatedUserId = None
    authenticatedNickname = None
    nickname = None
    questionId = None
    isLoggedIn = False
          
    @staticmethod
    def create(dbConnection, question=None, nickname=None):
        user = users.get_current_user()
        authenticatedUserId = user.user_id() if user else None
        authenticatedNickname = user.nickname() if user else None

        # Person must be either an authenticated google user
        # or with a nickname (if the question allows)
        if not authenticatedUserId and not nickname:
            return None
        
        # BEHAVIOR: authenticated_user_id is stored as string in database
        # Should it be saved as long instead?        
        person = Person()
        properties = {
            "id" : dbConnection.cursor.lastrowid,
            "authenticatedUserId" : authenticatedUserId,
            "authenticatedNickname" : authenticatedNickname,
            "nickname" : nickname if nickname else (Person.cleanNickname(user.nickname()) if user else None),
            "questionId" : question.id if question else None
        }
        person.update(dbConnection, properties, create=True)
        return person
    
    def update(self, dbConnection=None, properties={}, create=False):    
        if "id" in properties:
            self.id = properties["id"]
        if "authenticatedUserId" in properties:
            self.authenticatedUserId = properties["authenticatedUserId"]
        if "authenticatedNickname" in properties:
            self.authenticatedNickname = properties["authenticatedNickname"]
        if "nickname" in properties:
            self.nickname = properties["nickname"]
        if "questionId" in properties:
            self.questionId = properties["questionId"]

        if dbConnection:
            if create:
                # TODO: remember to changed timestamps when login/logout
                sql = "insert into users (authenticated_user_id, authenticated_nickname, nickname, question_id, latest_login_timestamp, latest_logout_timestamp) values (%s, %s, %s, %s, now(), null)"
                dbConnection.cursor.execute(sql, (self.authenticatedUserId, self.authenticatedNickname, self.nickname, self.questionId))
                self.id = dbConnection.cursor.lastrowid
                dbConnection.conn.commit()
                self.isLoggedIn=True
            
            else:
                # BEHAVIOR: assume only nickname can be modified after creation
                # TODO: consider updating authenticated_user_id when user logs in since it can change?
                sql = "update users set nickname=%s where id=%s"
                dbConnection.cursor.execute(sql, (self.nickname, self.id))
                dbConnection.conn.commit()
    
    def addClientId(self, dbConnection, clientId, commit=True):   
        sql = "insert into user_clients (user_id, client_id) values(%s, %s)"
        dbConnection.cursor.execute(sql, (self.id, clientId))
        if commit:
            dbConnection.conn.commit()
     
    # TODO: remember to remove all client ids when user logs out
    # TODO: is user_id and client_id enough or even just client_id?
    def removeClientId(self, dbConnection, clientId, commit=True):
        sql = "delete from user_clients where user_id=%s and client_id=%s"
        dbConnection.cursor.execute(sql, (self.id, clientId))
        
        # TODO: if no more client ids, should logout
        
        if commit:
            dbConnection.conn.commit()
      
    # TODO: record login/logout of users
    # TODO: record phase step completion times
    # TODO/COMMENT: logout this user from *all* activity
    @staticmethod
    def logout(dbConnection, personId):
        if personId:                
            sql = "update users set latest_logout_timestamp=now() where id=%s"
            dbConnection.cursor.execute(sql, (personId))
            sql = "delete from user_clients where user_id=%s"
            dbConnection.cursor.execute(sql, (personId))
            dbConnection.conn.commit()
            
    @staticmethod
    def getPerson(dbConnection, question=None, nickname=None):
        person = None
        user = users.get_current_user()

        # check for user if nickname given and question allows nickname authentication
        if question and not question.isAuthor() and question.nicknameAuthentication and nickname:
            sql = "select * from users where question_id=%s and nickname=%s"
            dbConnection.cursor.execute(sql, (question.id, nickname))
            row = dbConnection.cursor.fetchone()
            person = Person.getFromDBRow(row)
            
        # TODO: remember to update latest_login_timestamp and latest_logout_timestamp
        
        # if authenticated user logged in, check for user if
        # no question provided or question requires user authentication
        
        # TODO/FIX: only check client counts for nicknames?
        # TODO/FIX: destroy channels after some specified period?
        
        if user:
            if question:
                sql = "select * from users where authenticated_user_id=%s and question_id=%s"
                dbConnection.cursor.execute(sql, (user.user_id(), question.id))
            # TODO/COMMENT: teacher
            else:
                sql = "select * from users where authenticated_user_id=%s"
                dbConnection.cursor.execute(sql, (user.user_id()))
            row = dbConnection.cursor.fetchone()
            person = Person.getFromDBRow(row)
                                
        return person
    
    @staticmethod
    def getById(dbConnection, userId):
        person = None
        if userId:
            sql = "select * from users where id=%s"
            dbConnection.cursor.execute(sql, (userId))
            row = dbConnection.cursor.fetchone()
            person = Person.getFromDBRow(row) if row else None
        return person
    
    @staticmethod
    def getFromDBRow(row):
        person = None
        if row:
            person = Person()
            person.id = row["id"]
            person.authenticatedUserId = row["authenticated_user_id"]
            person.authenticatedNickname = row["authenticated_nickname"]
            person.nickname = row["nickname"]
            person.isLoggedIn = row["latest_logout_timestamp"] is None
        return person
                                                                 
    @staticmethod
    def cleanNickname(nickname=None):
        cleanedNickname = nickname
        if nickname:
            cleanedNickname = nickname[:nickname.index("@")] if nickname.count("@") > 0 else nickname
        return cleanedNickname
     
    @staticmethod
    def doesNicknameExist(dbConnection, questionId, nickname):
        sql = "select * from users where question_id=%s and nickname=%s"
        dbConnection.cursor.execute(sql, (questionId, nickname))
        row = dbConnection.cursor.fetchone()
        return row is not None
    
    @staticmethod
    def isAdmin():
        return users.is_current_user_admin()
    
    # TODO: create database indexes
    
    @staticmethod
    def getCountForQuestion(dbConnection, questionId):
        sql = "select count(*) as ct from users where question_id=%s and latest_login_timestamp is not null and latest_logout_timestamp is null"
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return row["ct"] if row else 0
        
    def toDict(self):
        return {
            "id": self.id,
            "nickname": self.nickname
        } 
     
    @staticmethod
    def equals(person1, person2):        
        usersMatch = person1.id == person2.id    

# TODO: do ideas, users, etc. need to be created w/in transactions to ensure
# same id not used when new database item created?
 
class Idea():
    id = None
    questionId = None
    userId = None
    ideaText = None
        
    @staticmethod
    def create(dbConnection, questionId, userId, ideaText):
        idea = Idea()
        properties = {
            "questionId" : questionId,
            "userId" : userId,
            "ideaText" : ideaText
        }
        idea.update(dbConnection, properties, create=True)
        return idea
    
    def update(self, dbConnection=None, properties={}, create=False):    
        if "id" in properties:
            self.id = properties["id"]
        if "questionId" in properties:
            self.questionId = properties["questionId"]
        if "userId" in properties:
            self.userId = properties["userId"]
        if "ideaText" in properties:
            self.ideaText = properties["ideaText"]

        if dbConnection:
            if create:
                sql = "insert into question_ideas (question_id, user_id, idea) values (%s, %s, %s)"
                dbConnection.cursor.execute(sql, (self.questionId, self.userId, self.ideaText))
                self.id = dbConnection.cursor.lastrowid
                dbConnection.conn.commit()
            else:
                # BEHAVIOR: assume only idea text can be modified after created
                sql = "update question_ideas set idea=%s where id=%s"
                dbConnection.cursor.execute(sql, (self.idea, self.id))
                dbConnection.conn.commit()
    
    @staticmethod
    def getById(dbConnection, ideaId):
        sql = "select * from question_ideas where id=%s"
        dbConnection.cursor.execute(sql, (ideaId))
        row = dbConnection.cursor.fetchone()
        return Idea.getFromDBRow(row) if row else None
    
    @staticmethod
    def getByUser(dbConnection, userId, asDict=False):
        ideas = []
        sql = "select * from question_ideas where user_id=%s"
        dbConnection.cursor.execute(sql, (userId))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            idea = Idea.getFromDBRow(row)
            if asDict:
                idea = idea.toDict()
            ideas.append(idea)
        return ideas
    
    # TODO: person vs. user (variable name)
    # TODO: could merge users and user_clients if only 1 client allowed per user/question pair
    
    @staticmethod
    def getByQuestion(dbConnection, question, asDict=False):
        ideas = []
        sql = "select * from question_ideas,users where question_ideas.user_id=users.id and question_ideas.question_id=%s"
        dbConnection.cursor.execute(sql, (question.id))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            idea = Idea.getFromDBRow(row)
            if asDict:
                author = Person()
                author.id = row["user_id"]
                author.authenticatedUserId = row["authenticated_user_id"]
                author.authenticatedNickname = row["authenticated_nickname"]
                author.nickname = row["nickname"]
                idea = idea.toDict(author=author, admin=Person.isAdmin() or (question and question.isAuthor()))
            ideas.append(idea)
        return ideas
    
    @staticmethod
    def getCountForQuestion(dbConnection, questionId):
        sql = "select count(*) as ct from question_ideas where question_id=%s"
        dbConnection.cursor.execute(sql, (questionId))
        row = dbConnection.cursor.fetchone()
        return row["ct"] if row else 0
    
    @staticmethod
    def getFromDBRow(row):
        idea = None
        if row:
            idea = Idea()
            idea.id = row["id"]
            idea.questionId = row["question_id"]
            idea.userId = row["user_id"]
            idea.ideaText = row["idea"]
        return idea
              
    # TODO: make sure client_ids being deleted when user logs out or window closed
      
    # TODO: Thursday new ideas showing on non-teacher result page can see real user identity!!
    def toDict(self, author=None, admin=False):
        dict = {
            "id" : self.id,
            "question_id" : self.questionId,
            "user_id" : self.userId,
            "idea" : self.ideaText
        }
        
        if author:
            dict["author"] = author.nickname if author.nickname else "Anonymous"
            if admin and author.authenticatedNickname and Person.cleanNickname(author.authenticatedNickname) != author.nickname:
                dict["author_identity"] = author.authenticatedNickname
                            
        return dict
#     
#     @staticmethod
#     def getNumIdeas(question):
#         return Idea.all().filter("question =", question).count() if question else 0
#             
#     @staticmethod
#     def getIdeaById(ideaIdStr):
#         ideaObj = Idea.get_by_id(int(ideaIdStr))
#         return ideaObj
# 
#     @staticmethod
#     def createIdea(idea, questionIdStr, person):
#         questionObj = Question.getQuestionById(questionIdStr)
#         if questionObj:
#             if len(idea) > 500:
#                 idea = idea[:500]
#             idea = idea.replace("\n", "")
#             ideaObj = Idea()
#             ideaObj.author = person
#             ideaObj.text = idea
#             ideaObj.question = questionObj
#             if Idea.all().filter("question =", questionObj).count() == 0:
#                 ideaObj.rand = 1.0
#             else:
#                 ideaObj.rand = random.random()
#             ideaObj.put()
#             return ideaObj
# 
#     @staticmethod
#     def getRandomIdea(questionObj):
#         rand = random.random()
#         return Idea.all().filter("question =", questionObj).order("rand").filter("rand >", rand).get()
# 
#     @staticmethod
#     def getRandomIdeas(questionObj, ideas, size=5):
#         numIdeas = len(ideas) if ideas else 0
#         if numIdeas >= size:
#             return random.sample(ideas, size)
#         else:
#             helpers.log("WARNING: Cannot return {0} random ideas since only {1} ideas available".format(size, numIdeas))
#             return []
# 
#     @staticmethod
#     def deleteAllIdeas(questionIdStr):
#         questionObj = Question.getQuestionById(questionIdStr)
#         if questionObj:
#             IdeaTag.deleteAllTags(questionIdStr)
#             IdeaAssignment.deleteAllIdeaAssignments(questionIdStr)
#             SimilarIdea.deleteAllSimilarIdeas(questionIdStr)
#             SimilarIdeaAssignment.deleteAllAssignments(questionIdStr)
#             db.delete(Idea.all().filter("question =", questionObj))
#                     
#     @staticmethod
#     def contains(ideas, match):
#         found = False
#         for idea in ideas:
#             if Idea.equals(idea, match):
#                 found = True
#                 break
#         return found
#     
#     @staticmethod
#     def equals(idea1, idea2):
#         textsMatch = idea1.text == idea2.text
#         questionsMatch = (idea1.question == None and idea2.question == None) or (idea1.question.code == idea2.question.code)
#         authorsMatch = Person.equals(idea1.author, idea2.author)
#         datesMatch = idea1.date == idea2.date
#         return textsMatch and questionsMatch and authorsMatch and datesMatch
#             
# ###################
# ##### CASCADE #####
# ###################
# 
# # BEHAVIOR: cascade jobs created when phase enabled
# # BEHAVIOR: when cascade params are changed, cascade jobs are re-created
# # BEHAVIOR: user currently allowed to do as many jobs per step as they can
# # BEHAVIOR: step 1 - displays up to t ideas at a time
# # BEHAVIOR: step 1 - does not remove any ideas authored by person, skipped or *seen before*
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
# ###################
# 
# NONE_OF_THE_ABOVE = "None of the above"
# DEFAULT_VOTING_THRESHOLD = 2
# 
# class Cascade(db.Model):
#     question = db.ReferenceProperty(Question)
#     step = db.IntegerProperty(default=1)
#     k = db.IntegerProperty(default=5)
#     m = db.IntegerProperty(default=32)
#     t = db.IntegerProperty(default=8)
# 
#     def setOptions(self, k, m, t):
#         optionsChanged = self.k != k or self.m != m or self.t != t
#         if optionsChanged:
#             self.k = k
#             self.m = m
#             self.t = t
#             self.put()
#             
#             # TODO/BUG CHECK: need to verify new parameters are being used when jobs re-created
#             # TODO/FIX: do not created jobs until cascade enabled
#             Cascade.init(self.question)
#         
#     # TODO: step needed as input, or just use value stored in Cascade?
#     @staticmethod
#     def init(question, step=1):        
#         cascade = Cascade.getCascadeForQuestion(question)
#         
#         # TODO: jobs might not be ready for step yet?  need to set later?
#         helpers.log("MEMCACHE: {0}_step = {1}".format(question.code, step))
#         memcache.set(key=question.code + "_step", value=step, time=3600)
#     
#         if step == 1:
#             Cascade.deleteJobs(question)
#             if cascade.step != 1:
#                 cascade.step = 1
#                 cascade.put()
#             cascade.createJobsForStep1()
#         
#         elif step == 2:
#             cascade.createJobsForStep2()
#             
#         elif step == 3:
#             cascade.createJobsForStep3()
# 
#         elif step == 4:
#             # TODO
#             pass
#         
#         elif step == 5:
#             # TODO
#             pass
#         
#     def createJobsForStep1(self):
#         jobs = []
#         taskGroup = []
#         ideaKeys = Idea.all(keys_only=True).filter("question = ", self.question).order("rand")
#         for i in range(self.k):
#             for ideaKey in ideaKeys:
#                 if len(taskGroup) == self.t:
#                     task = CascadeSuggestCategoryTask()
#                     task.question = self.question
#                     task.idea_keys = taskGroup
#                     task.put()
#                     
#                     job = CascadeJob()
#                     job.question = self.question
#                     job.cascade = self
#                     job.step = 1
#                     job.task = task
#                     job.worker = None
#                     jobKey = job.put()
#                     jobs.append(jobKey.id())
#                 
#                     taskGroup = []
#                 
#                 taskGroup.append(ideaKey)
#         
#         if len(taskGroup) > 0:
#             task = CascadeSuggestCategoryTask()
#             task.question = self.question
#             task.idea_keys = taskGroup
#             task.put()
#                     
#             job = CascadeJob()
#             job.question = self.question
#             job.cascade = self
#             job.step = 1
#             job.task = task
#             job.worker = None
#             jobKey = job.put()
#             jobs.append(jobKey.id())
#             
#         helpers.log("INIT MEMCACHE FOR STEP 1")
#         for jobId in jobs:
#             helpers.log("job = {0}".format(jobId))
#             
#         # TODO: Testing how memcache works
#         # TODO: memcache.add not found when compiled; added @UndefinedVariable to ignore error
#         memcache.set(key=self.question.code + "_available_jobs", value=jobs, time=3600)
#         memcache.set(key=self.question.code + "_assigned_jobs", value={}, time=3600)
#                                 
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
#     @staticmethod
#     def getCascadeForQuestion(question):
#         cascade = Cascade.all().filter("question =", question).get()            
#         if not cascade:
#             cascade = Cascade()
#             cascade.question = question
#             cascade.put()
#         return cascade
#                        
#     @staticmethod         
#     def deleteJobs(question):
#         db.delete(CascadeJob().all().filter("question =", question))
#         db.delete(CascadeSuggestCategoryTask().all().filter("question =", question))
#         db.delete(CascadeSelectBestTask().all().filter("question = ", question))
#         db.delete(CascadeCategoryFitTask().all().filter("question = ", question))
#         helpers.log("WARNING: Remember to delete cascade jobs for steps 3b-5")
#                  
# class CascadeTask(db.Model): 
#     question = db.ReferenceProperty(Question)
#    
#     def toDict(self):
#         return {
#             "question_id" : self.question.code
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
#         dict["ideas"] = [ idea.toDict() for idea in self.ideas ]
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
#         dict["idea"] = self.idea.toDict()
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
#         dict["ideas"] = [ idea.toDict() for idea in self.ideas ]
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
#         step = client.gets(question.code + "_step")
#         assert step is not None, "Step not initialized"
#         if step != jobStep:
#             helpers.log("WARNING: Jobs for step {0} not stored in memcache".format(jobStep))
#             return { "job": None, "newStep": False }
# 
#         # check if worker is already assigned a job
#         # TODO: ok to get all assigned jobs? or better to check only for this worker?
#         assignedJobsKey = question.code + "_assigned_jobs"
#         assignedJobs = client.gets(assignedJobsKey)
#         assert assignedJobs is not None, "Assigned jobs not initialized"
#         jobId = assignedJobs[workerKey] if workerKey in assignedJobs else None
# 
#         # if not, get new assignment
#         newStep = False
#         if not jobId:  
#             # TODO: need to limit to MAX_TRIES
#             availableJobsKey = question.code + "_available_jobs"
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
#             "question_code": self.question.code,
#             "step": self.step,
#             "task": self.task.toDict(),    
#             "worker": Person.toDict(self.worker),
#             "status": self.status
#         }