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
import json
import os
import string
import webapp2
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from lib import gaesessions
from db import *

#####################
# Page Handlers
#####################

class BaseHandler(webapp2.RequestHandler):
    dbConnection = None
    person = None
    question = None
    session = None

    def init(self, initUser=True, admin=False):
        # Get the current browser session, if any
        # Otherwise, create one
        self.session = gaesessions.get_current_session()
        if self.session.sid is None:
            self.session.start()
        
        if self.dbConnection:
            self.dbConnection.disconnect()
            
        self.dbConnection = DatabaseConnection()
        self.dbConnection.connect()
            
        questionId = self.request.get("question_id")
        if questionId:
            self.question = Question.getById(self.dbConnection, questionId)   

        if initUser:
            self.person = self.initUserContext(admin=admin)
                
    def destroy(self):
        if self.dbConnection:
            self.dbConnection.disconnect()
                
    def initUserContext(self, admin=False):
        nickname = self.request.get("nickname")
        question = self.question
        helpers.log("NICKNAME={0}".format(nickname))
                    
        # if question allows nickname authentication
        # check if nickname stored in session, if not provided
        if question and question.nicknameAuthentication and not nickname:
            questionValues = self.session.get(question.code) if self.session.has_key(question.code) else None
            nickname = questionValues["nickname"] if questionValues else None
           
        # if requested, force check for authenticated user
        # TODO: admin really just means authenticated user required
        if admin:
            question = None
            nickname = None
            helpers.log("SET NICKNAME TO NONE")

        
        person = Person.getPerson(self.dbConnection, question, nickname)
        helpers.log("INIT USER CONTEXT: person={0}, nickname={1}".format(person.id if person else None, nickname))
                            
        # if no person found, create user (if user logged in or nickname provided)
        if not person:
            helpers.log("CREATING PERSON: {0}, {1}".format(question.id if question else None, nickname))
            person = Person.create(self.dbConnection, question=question, nickname=nickname)

        return person        

    def getDefaultTemplateValues(self, userRequired=True):
        """Return a dictionary of default template values"""                
        # if user logged in, add channel
        # TODO: currently a channel is created every time a user loads a page
        # is it possible to do once per session? not sure if it can be passed between pages
        # TODO/FIX: when should channel be created; not initialized on client side for all page types
        if self.person:
            clientId, token = createChannel(self.question, self.person)
            urlLink = 'Logout'
            logoutUrl = "/logout?user="+str(self.person.id)
            url = users.create_logout_url(logoutUrl) if self.person.authenticatedUserId else logoutUrl
            
        # TODO: fix comments, etc.                   
        if not self.person:
            nicknameAuthenticationAllowed = self.question and self.question.nicknameAuthentication and not self.question.isAuthor()

            # no one logged in, and nickname authentication allowed
            if nicknameAuthenticationAllowed:
                urlLink = "Login w/ Nickname"
                url = "/nickname_login" + ("?question_id=" + str(self.question.id) if self.question else "")
                
            # no one logged in, and user authentication required
            else:
                urlLink = 'Login w/ Google Account'
                url = "/login?page=" + self.request.uri + ("&question_id="+str(self.question.code) if self.question else "")
                url = users.create_login_url(url)
                    
        template_values = {}
        template_values['logged_in'] = "true" if self.person else "false"       
        template_values['url_linktext'] = urlLink
        template_values['url'] = url
        template_values['msg'] = self.session.pop("msg") if self.session.has_key("msg") else ""
          
        if self.person:
            template_values['client_id'] = clientId
            template_values['token'] = token
            template_values['user_login'] = self.person.authenticatedNickname if self.person.authenticatedNickname else self.person.nickname
            template_values['user_nickname'] = self.person.nickname
            template_values['admin'] = Person.isAdmin() or (self.question and self.question.isAuthor())
            
        if self.question:
            template_values["question_id"] = self.question.id
            template_values["phase"] = self.question.phase
            template_values["title"] = self.question.title
            template_values["question"] = self.question.question
                
        return template_values

    # TODO: add version for json and add to action handlers
    
    def checkRequirements(self, userRequired=False, authenticatedUserRequired=False, questionRequired=False, validQuestionCode=False):
        # check if authenticated user logged in
        ok = True
        
        if userRequired:
            ok = self.checkIfUserLoggedIn()
            
        if authenticatedUserRequired:
            ok = self.checkIfAuthenticatedUserLoggedIn()
        
        # check if valid question
        if ok and questionRequired:
            ok = self.checkIfQuestion()
            
        # question code is optional, but if provided must be valid
        if ok and validQuestionCode:
            ok = self.checkIfValidQuestionCode()
            
        return ok
            
    def checkIfUserLoggedIn(self):
        ok = True
        if not self.person:
            self.session['msg'] = "Please login"
            ok = False
        return ok
    
    def checkIfAuthenticatedUserLoggedIn(self):
        ok = True
        if not self.person or not self.person.authenticatedUserId:
            self.session['msg'] = "Please login"
            ok = False
        return ok
    
    def checkIfQuestion(self):  
        ok = True  
        if not self.request.get("question_id"):
            self.session['msg'] = "Question code required"
            ok = False
        elif not self.question:
            self.session['msg'] = "Invalid question code"
            ok = False
        return ok
    
    def checkIfValidQuestionCode(self):
        ok = True
        if self.request.get("question_id") and not self.question:
            self.session['msg'] = "Invalid question code"
            ok = False
        return ok
        
    def writeResponseAsJson(self, data):
        self.response.headers.add_header('Content-Type', 'application/json', charset='utf-8')
        self.response.out.write(helpers.to_json(data))
        
    def redirectWithMsg(self, msg=None, dst="/"):        
        if msg is not None:
            self.session['msg'] = msg
        self.redirect(dst)
     
class MainPageHandler(BaseHandler):
    def get(self):
        self.init()      
        templateValues = self.getDefaultTemplateValues(userRequired=False)
        path = os.path.join(os.path.dirname(__file__), '../html/main.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()

class NicknameLoginPageHandler(BaseHandler):
    # TODO/COMMENT: for nickname login
    def get(self):
        self.init()
        templateValues = self.getDefaultTemplateValues(userRequired=False)        
        path = os.path.join(os.path.dirname(__file__), '../html/login.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
        
class IdeaPageHandler(BaseHandler):
    def get(self): 
        self.init()      
        self.checkRequirements(userRequired=True, questionRequired=True)

        templateValues = self.getDefaultTemplateValues(userRequired=True)  
        if self.question:
            templateValues["change_nickname_allowed"] = json.dumps(not self.question.nicknameAuthentication)
            
        path = os.path.join(os.path.dirname(__file__), '../html/idea.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
     
# Participant page that uses Cascade to create categories for ideas
# TODO: check if ideas exist for question; if not, do not enable cascade
# TODO: when cascade step changed, notify user but do not assigned task automatically
class CascadePageHandler(BaseHandler):
    def get(self):
        self.init() 
        self.checkRequirements(userRequired=True, questionRequired=True)
        templateValues = self.getDefaultTemplateValues(userRequired=True)  
        path = os.path.join(os.path.dirname(__file__), '../html/cascade.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
                
class ResultsPageHandler(BaseHandler):
    def get(self):
        self.init()    
        self.checkRequirements(userRequired=True, questionRequired=True)
        templateValues = self.getDefaultTemplateValues(userRequired=True)  
        path = os.path.join(os.path.dirname(__file__), '../html/results.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()

class AdminPageHandler(BaseHandler):
    def get(self):
        self.init(admin=True)
        ok = self.checkRequirements(authenticatedUserRequired=True, validQuestionCode=True)

        # check if user has permission to modify question                
        if ok and self.question:
            hasEditPrivileges = Person.isAdmin() or self.question.isAuthor()
            if not hasEditPrivileges:
                self.question = None
                self.session['msg'] = "You do not have permission to edit this question"
            
        templateValues = self.getDefaultTemplateValues(userRequired=True)
        path = os.path.join(os.path.dirname(__file__), '../html/admin.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
                
#####################
# Action Handlers
#####################

class QuestionLoginHandler(BaseHandler):
    def post(self):
        self.init()
        ok = self.checkRequirements(questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
            
        else:
            if not self.person:
                if self.question.nicknameAuthentication:
                    url = "/nickname_login?question_id=" + str(self.question.id)
                
                else:
                    url = users.create_login_url(getPhaseUrl(self.question))
            
            else:
                # TODO: add to Person class
                if not self.person.isLoggedIn:
                    sql = "update users set latest_login_timestamp=now(), latest_logout_timestamp=null where id=%s"
                    self.dbConnection.cursor.execute(sql, (self.person.id))
                    self.dbConnection.conn.commit()
                    self.person.isLoggedIn = True 
                url = getPhaseUrl(self.question)
            
            data = { "status" : 1, "question" : self.question.toDict(), "url" : url }
        
        self.writeResponseAsJson(data)
        self.destroy()
        
class LoginHandler(BaseHandler):
    def post(self):
        self.login()
    
    def login(self, json=True):
        self.init(initUser=False)
        nickname = self.request.get("nickname")
        page = self.request.get("page")
        helpers.log("LOGINHANDLER: nickname={0}".format(nickname))

        data = { "status" : 1 }
        # if question allows nickname authentication
        # store nickname in session if ok
        if self.question:
            person = Person.getPerson(self.dbConnection, self.question, nickname)
            if person and person.isLoggedIn:
                if self.question.nicknameAuthentication:
                    helpers.log("MARK1")
                    # TODO: need to destroy stuff before redirecting
                    data = { "status" : 0, "msg" : "error1" }
                    #self.redirectWithMsg("Someone is already logged in as " + nickname, "/nickname_login?question_id="+str(self.question.id)+"&timestamp="+randint(0,9))
                else:
                    helpers.log("MARK2");
                    data = { "status" : 0, "msg" : "error2" }
                    #self.redirectWithMsg(str(person.user) + " is already logged in", dst="/")
                #return
                
            if data["status"] == 1 and self.question.nicknameAuthentication and nickname:
                specialChars = set('$\'"*,')
                if any((c in specialChars) for c in nickname):
                    data = { "status" : 0, "msg" : "error3" }
                    #self.redirectWithMsg("Nickname can not contain " + "".join(specialChars), "/nickname_login?question_id="+str(self.question.id))
                    #return
                
                # TOOD: check what else is stored in session
                else:
                    self.session[self.question.id] = { "nickname": nickname }

        if data["status"] == 1:
            self.person = self.initUserContext()
            data["url"] = str(page) if page else (getPhaseUrl(self.question) if self.question else "/")

        if json:
            self.writeResponseAsJson(data)       
        self.destroy()
        
        if not json:
            self.redirectWithMsg(data["msg"] if "msg" in data else "", data["url"] if data["status"] == 1 else "/")
        
    # TODO/COMMENT: Google authentication needs GET
    def get(self):
        # TODO: redirect if json False
        self.login(json=False)
        

def getPhaseUrl(question=None):
    url = "/"
    if question:
        if question.phase <= constants.PHASE_NOTES:
            url = "/idea?question_id=" + str(question.id)
        elif question.phase == constants.PHASE_CASCADE:
            url = "/cascade?question_id=" + str(question.id)
    return url

# TODO/FIX: self.person no longer exists by the time it gets here
class LogoutHandler(BaseHandler):
    def get(self):
        self.init()
        
        # TODO/Comment: pass person id (user_id) via logout url when 
        # logging out via google since person not longer set - but not sure why
        personId = self.request.get("user", None)
        # TODO: need to pass question id!!
        # TODO: should this be done in client disconnect instead??
        Person.logout(self.dbConnection, self.person.id if self.person else personId)
            
        session = gaesessions.get_current_session()
        if session.is_active():
            session.terminate(True)
            session.clear()
            session.regenerate_id()
        self.redirect("/")

# TODO: should separate user row be created for teachers when they "use" the question they created?
# TODO: allowed nickname to be deleted (if not required for authentication)
# TODO/FIX: add some ideas with user with nickname (not teacher) and refresh list; loses knowledge about true identity

class NicknameHandler(BaseHandler):
    def post(self):
        self.init()
        self.checkRequirements(userRequired=True, questionRequired=True)
        
        clientId = self.request.get("client_id")
        nickname = self.request.get("nickname")
        specialChars = set('$\'"*,')
                
        if self.session.has_key("msg"):
            data = { "status" : 0, "msg" : self.session.pop("msg") }

        elif not nickname or len(nickname) == 0:
            data = { "status" : 0, "msg" : "Empty nickname not allowed" }
            
        # check if nickname has changed
        elif self.person.nickname == nickname:
            data = { "status" : 0, "msg" : "" }
    
        elif any((c in specialChars) for c in nickname):
            data = { "status" : 0, "msg" : "Nickname can not contain " + "".join(specialChars) }
                
        elif Person.doesNicknameExist(self.dbConnection, self.question.id, nickname):
            data = { "status" : 0, "msg" : "Nickname already exists (" + nickname + ")" }
                            
        else:
            # TODO: check if nickname updated in client views
            self.person.update(self.dbConnection, { "nickname" : nickname })           
            data = { "status" : 1, "question_id": self.question.id, "user" : self.person.toDict() }
            message = {
                "op": "nickname",
                "user": self.person.toDict()
            }
            sendMessage(self.dbConnection, clientId, self.question.id, message)      
        
        self.writeResponseAsJson(data)
        self.destroy()
                           
class QueryHandler(BaseHandler):
    def get(self):
        request = self.request.get("request", None)
        if not request:
            return
        
        # TODO: admin is really instructor
        isAdminRequest = request in ("questions", "stats")
        self.init(admin=isAdminRequest)
        data = {}
        
        # questions created by user
        if request == "questions":
            questions = Question.getByUser(self.dbConnection, asDict=True)
            data = { "questions": questions }
                    
        # stats for specific question (# ideas, etc.)
        elif request == "stats" and self.question:
            data = Question.getStats(self.dbConnection, self.question.id)
                  
        # ideas for question
        elif request == "ideas" and self.question:
            ideas = Idea.getByQuestion(self.dbConnection, self.question, asDict=True)
            data = { "question": self.question.toDict(), "ideas": ideas }
                
        self.writeResponseAsJson(data)
        self.destroy()

class NewQuestionHandler(BaseHandler):
    def post(self):
        self.init()
        title = self.request.get('title')
        questionText = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication', '0') == "1"
        clientId = self.request.get('client_id')

        data = {}        
        if not self.person:
            data["status"] = 0
            data["msg"] = "Please log in"
        
        elif len(title) < 5 or len(questionText) < 5:
            data["status"] = 0
            data["msg"] = "Title and question must must be at least 5 characters"
                     
        else:
            self.question = Question.create(self.dbConnection, self.person, title, questionText, nicknameAuthentication)
            
            if not self.question:
                data["status"] = 0
                data["msg"] = "Error saving question"
                
            else:
                data = {"status": 1, "question": self.question.toDict() }
                sendMessage(self.dbConnection, clientId, self.question.id, { "op" : "newquestion" })

        self.writeResponseAsJson(data)
        self.destroy()

class EditQuestionHandler(BaseHandler):
    def post(self):
        # TODO: make sure checkRequirements used everywhere
        # TODO: force check required?
        # TODO: check user is question author
        self.init(admin=True);
        self.checkRequirements(authenticatedUserRequired=True, questionRequired=True)
        
        clientId = self.request.get('client_id')
        title = self.request.get('title')
        questionText = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication', '0') == "1"

        if self.session.has_key("msg"):
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        elif not self.question.isAuthor():
            data = { "status" : 0, "msg" : "You do not have permission to edit this question" }
        
        if len(title) < 5 or len(questionText) < 5:
            data = { "status" : 0, "msg" : "Title and question must must be at least 5 characters" }

        else:            
            properties = {
                "title" : title,
                "questionText" : questionText,
                "nicknameAuthentication" : nicknameAuthentication
            }
            self.question.update(self.dbConnection, properties)            
            data = { "status": 1, "question": self.question.toDict() }
            sendMessage(self.dbConnection, clientId, self.question.id, { "op": "newquestion" })
            
        self.writeResponseAsJson(data)
        self.destroy()
            
            
class DeleteQuestionHandler(BaseHandler):
    def post(self):
        # TODO: force check required?
        # TODO: check that user is question author
        self.init(admin=True)
        self.checkRequirements(authenticatedUserRequired=True, questionRequired=True)
        clientId = self.request.get('client_id')
        
        if self.session.has_key("msg"):
            data = { "status" : 0, "msg" : self.session.pop("msg") }
            
        else:
            self.question.delete(self.dbConnection)
            data = { "status": 1 }
            sendMessage(self.dbConnection, clientId, self.question.id, { "op": "delete" })
            
        self.writeResponseAsJson(data) 
        self.destroy()
  
# TODO: make sure clientIds are getting deleted when necessary
# TODO: memcache clientIds to speed things up?
        
class NewIdeaHandler(BaseHandler):
    # TODO: author vs user vs person
    # TODO: idea.toDict should include name of author
    def post(self):
        self.init()
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if ok:
            clientId = self.request.get('client_id')
            ideaText = self.request.get('idea')                
            if ideaText and ideaText != "":
                idea = Idea.create(self.dbConnection, self.question.id, self.person.id, ideaText)  
                msg = { "op": "newidea", "idea": idea.toDict(author=self.person, admin=False) }
                adminMsg = { "op": "newidea", "idea": idea.toDict(author=self.person, admin=True) }
                sendMessage(self.dbConnection, clientId, self.question.id, msg, adminMsg)
            
        self.destroy()
                    
class CascadeJobHandler(BaseHandler):
    def post(self):
        # TODO: FIX!!
        pass
#         person = self.initUserContext()
#         client_id = self.request.get('client_id')
#         question_id = self.request.get("question_id")
#         question = Question.getQuestionById(question_id)
#         data = {}              
#         
#         if not person:
#             data["status"] = 0
#             data["msg"] = "Please log in"
#                  
#         elif not question:
#             data["status"] = 0
#             data["msg"] = "Invalid question code"
#         
#         elif question.phase != constants.PHASE_CASCADE:
#             data["status"] = 0
#             data["msg"] = "Not currently enabled"
#             
#         else:
#             jobId = long(self.request.get("assignment_id", "-1"))
#             if jobId != -1:
#                 job = CascadeJob.get_by_id(jobId)
#                 if job:
#                     data = {}
#                     if job.step == 1:
#                         numCategories = int(self.request.get("num_categories"))
#                         categories = [ self.request.get("category_"+str(i+1)) for i in range(numCategories) ]
#                         data = { "categories" : categories }
#                     elif job.step == 2:
#                         bestCategoryIndexStr = self.request.get("best_category_index", "")
#                         data = { "best_category_index" : bestCategoryIndexStr if bestCategoryIndexStr.isdigit() else -1 }
#                     else:
#                         helpers.log("WARNING: Job not saved")
#                     
#                     job.completed(data)
#                 else:
#                     helpers.log("WARNING: Job not found (id={0})".format(jobId))
#             
#             cascade = Cascade.getCascadeForQuestion(question)
#             helpers.log("question={0}, cascade step={1}, person={2}".format(question.code, cascade.step, person))
#             jobData = CascadeJob.getJob(question, cascade.step, person)
#             job = jobData["job"]
#             isNewStep = jobData["new_step"]
#             
#             # Notify clients if new step
#             if isNewStep:
#                 message = {
#                     "op": "step",
#                     "step": job.step
#                 }
#                 send_message(client_id, question, message)
# 
#             data["status"] = 1
#             data["step"] = job.step if job else cascade.step
#             data["assignment"] = job.toDict() if job else None
#             
#         self.writeResponseAsJson(data)
                        
class PhaseHandler(BaseHandler):
    def post(self):
        self.init(admin=True)
        ok = self.checkRequirements(self, authenticatedUserRequired=True, questionRequired=True)
        
        # check if user has rights to modify question
        if ok:
            hasEditPrivileges = Person.isAdmin() or self.question.isAuthor()
            if not hasEditPrivileges:
                self.question = None
                self.session['msg'] = "You do not have permission to edit this question"

        clientId = self.request.get('client_id')
        phase = int(self.request.get('phase'))
     
        if self.session.has_key("msg"):
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else:
            self.question.update(self.dbConnection, { "phase" : phase })               
            data = { "status" : 1, "question" : self.question.toDict() }
            sendMessage(self.dbConnection, clientId, self.question.id, { "op" : "phase", "phase" : phase})

        self.writeResponseAsJson(data)            
        self.destroy()

class CascadeOptionsHandler(BaseHandler):
    def post(self):
        # TODO: check if question author
        self.init(adminCheck=True)
        self.checkRequirements(self, authenticatedUserRequired=True, questionRequired=True)
        
        clientId = self.request.get('client_id')

        if self.session.has_key("msg"):
            data = { "status" : 0, "msg" : self.session.pop("msg") }

        else:
            properties = {
                "cascadeK": int(self.request.get('cascade_k')),
                "cascadeM": int(self.request.get('cascade_m')),
                "cascadeT": int(self.request.get('cascade_t')) 
            }
            self.question.update(self.dbConnection, properties)
            data = { "status" : 1, "question" : self.question.toDict() }
            # TODO: notify other clients
        
        self.writeResponseAsJson(data)
        self.destroy()
        
#####################
# Channel support
#####################
          
# TODO: is there a way to store db connections as opposed to making a new one for every get/post
class ChannelConnectedHandler(BaseHandler):
    # Notified when clients connect
    def post(self):
        self.init(initUser=False)
        clientId = self.request.get("from")
        questionId, personId, isQuestionAuthor = getInfoFromClientId(clientId)
        person = Person.getById(self.dbConnection, personId)
        if person:
            person.addClientId(self.dbConnection, clientId)    
            
class ChannelDisconnectedHandler(BaseHandler):
    # Notified when clients disconnect
    def post(self):
        self.init(initUser=False)
        clientId = self.request.get("from")
        questionId, personId, isQuestionAuthor = getInfoFromClientId(clientId)
        person = Person.getById(self.dbConnection, personId)
        if person:
            person.removeClientId(self.dbConnection, clientId)
            # TODO: logout if no clientIds left

def createChannel(question, person):
    clientId = str(random.randint(1000000000000, 10000000000000))
    clientId += "_" + (str(question.id) if question else constants.EMPTY_CLIENT_TOKEN)
    clientId += "_" + (str(person.id) if person else constants.EMPTY_CLIENT_TOKEN)
    # BEHAVIOR: question authors are marked with a "_a" in the clientId
    # Should application admins also be marked?
    if question and question.isAuthor():
        clientId += "_a"                                     
    token = channel.create_channel(clientId)
    return clientId, token

def getInfoFromClientId(clientId):
    tokens = clientId.split("_")
    questionId = tokens[1] if len(tokens) >= 3 and tokens[1] != constants.EMPTY_CLIENT_TOKEN else None
    personId = tokens[2] if len(tokens) >= 3 and tokens[2] != constants.EMPTY_CLIENT_TOKEN else None
    isQuestionAuthor = "a" in tokens[3] if len(tokens) >= 4 else False
    return (questionId, personId, isQuestionAuthor)

# TODO: would it be better to store client ids in the HRD or memcache
# as opposed to having to make a db query for each message
def sendMessage(dbConnection, fromClientId, questionId, message, adminMessage=None):
    """Send message to all listeners (except self) to this topic"""
    if fromClientId and questionId:
        sql = "select * from users,user_clients where users.id=user_clients.user_id and question_id=%s"
        dbConnection.cursor.execute(sql, (questionId))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            toClientId = row["client_id"]
            toMessage = message
            if toClientId != fromClientId:
                if adminMessage:
                    clientQuestionId, clientPersonId, clientIsQuestionAuthor = getInfoFromClientId(toClientId)
                    if clientIsQuestionAuthor:
                        toMessage = adminMessage;
                channel.send_message(toClientId, json.dumps(toMessage))
                    
def cleanTag(tag):
    words = tag.split()
    cleanWords = []
    for word in words:
        cleanWords.append(cleanWord(word))
    cleanWords.sort()
    return string.join(cleanWords)

def cleanWord(word):
    word = word.lower()
    word = word.strip("`~!@#$%^&*()-_=+|;:',<.>/?")
    if isStopWord(word):
        word = ""
    return word
    
def isStopWord(word):
    return (word in constants.STOP_WORDS)