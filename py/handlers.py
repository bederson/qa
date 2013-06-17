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
# Channel support
#####################

def connect(person):
    """User has connected, so remember that"""
    client_id = str(random.randint(1000000000000, 10000000000000))
    if person:
        client_id += "_" + str(person.key().id())
    token = channel.create_channel(client_id)
    return client_id, token

def sendMessage(dbConnection, fromClientId, questionId, message):
    """Send message to all listeners (except self) to this topic"""
    # TODO: fromClientId not being passed currently
    if fromClientId and questionId:
        sql = "select * from question_clients where question_id=%s"
        rows = dbConnection.cursor.execute(sql, (questionId))
        helpers("SEND MESSAGE: rows={0}".format(rows))
        for row in rows:
            toClientId = row["client_id"]
            if toClientId != fromClientId:
                channel.send_message(toClientId, json.dumps(message))

#####################
# Page Handlers
#####################

class BaseHandler(webapp2.RequestHandler):
    dbConnection = None
    person = None
    question = None
    session = None

    def init(self, initDB=True, initUser=True, forceCheckUser=False, createUser=False):
        # Get the current browser session, if any
        # Otherwise, create one
        self.session = gaesessions.get_current_session()
        if self.session.sid is None:
            self.session.start()
        
        if initDB:
            if self.dbConnection:
                self.dbConnection.disconnect()
            
            self.dbConnection = DatabaseConnection()
            self.dbConnection.connect()
            
            questionId = self.request.get("question_id")
            if questionId:
                self.question = Question.getById(self.dbConnection, questionId)   

        if initUser:
            self.person = self.initUserContext(forceCheck=forceCheckUser, create=createUser)
                
    def destroy(self):
        if self.dbConnection:
            self.dbConnection.disconnect()
                
    def initUserContext(self, forceCheck=False, create=False):                    
        questionId = self.request.get("question_id")        
        question = Question.getById(self.dbConnection, questionId)
        nickname = self.request.get("nickname")
                        
        # if question allows nickname authentication
        # check if nickname stored in session, if not provided
        if question and question.nicknameAuthentication and not nickname:
            questionValues = self.session.get(question.code) if self.session.has_key(question.code) else None
            nickname = questionValues["nickname"] if questionValues else None
           
        # if requested, force check for authenticated user not affiliated with any specific question
        if forceCheck:
            question = None
            nickname = None
        
        person = Person.getPerson(self.dbConnection, question, nickname)
        user = users.get_current_user()
                            
        # if no person found
        # create person if create is true, OR,
        # create person if question requires login authentication and person already logged in
        if not person and (create or (question and not question.nicknameAuthentication and user)): 
            person = Person()
            person.create(self.dbConnection, question, nickname)

        return person        

    def getDefaultTemplateValues(self):
        """Return a dictionary of default template values"""        
        
        page = self.request.path
        requiresGoogleAuthentication = page == "/admin" or not self.question or not self.question.nicknameAuthentication
        
        # user already logged in    
        if self.person:
            # TODO: need to implement
            #client_id, token = connect(person)
            client_id = ""
            token = ""
            url_linktext = 'Logout'
            url = users.create_logout_url("/logout") if self.person.authenticatedUserId else "/logout"
             
        # no one logged in, and Google authentication required
        elif requiresGoogleAuthentication:
            url_linktext = 'Login w/ Google Account'
            url = "/login?page=" + self.request.uri + ("&question_id="+self.question.code if self.question else "")
            url = users.create_login_url(url)
            
        # no one logged in, and nickname authentication allowed
        else:
            url_linktext = "Login w/ Nickname"
            url = "/loginpage" + ("?question_id=" + self.question.code if self.question else "")
            
        template_values = {}
        template_values['logged_in'] = "true" if self.person else "false"       
        template_values['url_linktext'] = url_linktext
        template_values['url'] = url
        template_values['msg'] = self.session.pop("msg") if self.session.has_key("msg") else ""
            
        if self.person:
            template_values['client_id'] = client_id
            template_values['token'] = token
            # the displayed user login should be the nickname if on question page (e.g., url has question_id param)
            # and nickname authentication is allowed; otherwise the Google login should be displayed
            # TODO: FIX - show login not id
            template_values['user_login'] = self.person.authenticatedUserId if requiresGoogleAuthentication else self.person.nickname
            template_values['user_nickname'] = self.person.nickname
            template_values['admin'] = Person.isAdmin() or (not self.question or self.question.isAuthor(self.person))
    
        if self.question:
            template_values["question_id"] = self.question.id
            template_values["phase"] = self.question.phase
            template_values["title"] = self.question.title
            template_values["question"] = self.question.question
                
        return template_values

    def checkIfAuthenticatedUserLoggedIn(self):
        ok = True
        if not self.person or not self.person.authenticatedUserId:
            self.session['msg'] = "Please login"
            ok = False
        return ok
    
    def checkIfValidQuestion(self):  
        ok = True  
        if not self.question:
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
        templateValues = self.getDefaultTemplateValues()
        path = os.path.join(os.path.dirname(__file__), '../html/main.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()

class IdeaPageHandler(BaseHandler):
    def get(self): 
        self.init()      
        templateValues = self.getDefaultTemplateValues()  
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
        templateValues = self.getDefaultTemplateValues()  
        path = os.path.join(os.path.dirname(__file__), '../html/cascade.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
                
class ResultsPageHandler(BaseHandler):
    def get(self):
        self.init()      
        templateValues = self.getDefaultTemplateValues()  
        path = os.path.join(os.path.dirname(__file__), '../html/results.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()

class AdminPageHandler(BaseHandler):
    def get(self):
        self.init(forceCheckUser=True)      
        
        # check if new_question_id stored in session
        # newly created questions may not be searchable immediately
        # but they should be retrievable with a key
        # would not be required if js did not immediately reload page
        # with question_id as url param (which forces new question search)
        
        # TODO/FIX: session variable needed anymore?
#         session = gaesessions.get_current_session()
#         questionId = session.pop("new_question_key") if session.has_key("new_question_key") else None                
#         if questionId:
#             question = Question.getById(questionId)

        # TODO: Tuesday - how to fix logic flow
        ok = self.checkIfAuthenticatedUserLoggedIn()
        
        # check if valid question, if question_id provided
        if ok and self.request.get("question_id"):
            ok = self.checkIfValidQuestion()
        
        # check if question owned by logged in user
        if ok:
            if self.question and (not self.question.isAuthor(self.person) and not Person.isAdmin()):
                self.question = None
                self.session['msg'] = "You do not have permission to edit this question"
            
        templateValues = self.getDefaultTemplateValues()
        if self.question:
            templateValues["cascade_k"] = self.question.cascadeK
            templateValues["cascade_m"] = self.question.cascadeM
            templateValues["cascade_t"] = self.question.cascadeT

        path = os.path.join(os.path.dirname(__file__), '../html/admin.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
        
class LoginPageHandler(BaseHandler):
    def get(self):
        self.init()
        templateValues = self.getDefaultTemplateValues()        
        path = os.path.join(os.path.dirname(__file__), '../html/login.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
        
#####################
# Action Handlers
#####################

class LoginHandler(BaseHandler):
    def get(self):
        self.init(initDB=True, initUser=False)
        nickname = self.request.get("nickname")
        page = self.request.get("page")

        # if question allows nickname authentication
        # store nickname in session if ok
        if self.question:
            person = Person.getPerson(self.dbConnection, self.question, nickname)
            if person and len(person.client_ids) > 0:
                if self.question.nicknameAuthentication:
                    self.redirectWithMsg("Someone is already logged in as " + nickname, "/loginpage?question_id="+self.question.id)
                else:
                    self.redirectWithMsg(str(person.user) + " is already logged in", dst="/")
                return
                
            if self.question.nicknameAuthentication and nickname:
                specialChars = set('$\'"*,')
                if any((c in specialChars) for c in nickname):
                    self.redirectWithMsg("Nickname can not contain " + "".join(specialChars), "/loginpage?question_id="+self.question.id)
                    return
                
                # TOOD: check what else is stored in session
                self.session[self.question.id] = { "nickname": nickname }

        self.person = self.initUserContext(create=True)
        url = str(page) if page else getPhaseUrl(self.question)
        
        self.destroy()
        self.redirect(url)

def getPhaseUrl(question=None):
    url = "/"
    if question:
        if question.phase <= constants.PHASE_NOTES:
            url = "/idea?question_id=" + question.code
        elif question.phase == constants.PHASE_CASCADE:
            url = "/cascade?question_id=" + question.code
    return url

class LogoutHandler(BaseHandler):
    def get(self):
        session = gaesessions.get_current_session()
        if session.is_active():
            session.terminate(True)
        self.redirect("/")

class NicknameHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        nickname = self.request.get("nickname")
        person = Person.getPersonFromClientId(clientId)

        specialChars = set('$\'"*,')
        nicknameNotChanged = False
        if person.user is not None:
            # base nickname on login if none provided
            if len(nickname) == 0:
                nickname = Person.cleanNickname(person.user)

            # check if nickname changed
            nicknameNotChanged = person is not None and person.nickname == nickname
        
        data = { "question_id": self.question.id, "nickname": nickname, "msg": "" }
        
        if nicknameNotChanged:
            pass    # do nothing
        
        elif len(nickname) == 0:
            data["msg"] = "Empty nickname not allowed"

        elif any((c in specialChars) for c in nickname):
            data["msg"] = "Nickname can not contain " + "".join(specialChars)
            
        elif Person.doesNicknameExist(self.dbConnection, self.question.id, nickname):
            data["msg"] = "Nickname already exists (" + nickname + ")"
            
        else:
            person.setNickname(nickname)
            
            # Update clients
            message = {
                "op": "nickname",
                "text": "",
                "author": Person.toDict(person)
            }
            sendMessage(self.dbConnection, clientId, self.question.id, message)      # Update other clients about this change
        
        self.writeResponseAsJson(data)
        self.destroy()
                           
class QueryHandler(BaseHandler):
    def get(self):
        self.init()
        request = self.request.get("request")
        data = {}
        
        # questions created by user
        if request == "questions":
            questions = Question.getByUser(self.dbConnection, asDict=True)
            data = { "questions": questions }
            
        # details about specific question
        elif request == "question":       
            if self.question:
                data = self.question.toDict()
                
            else:
                question = Question()
                data = question.toDict()
                data["msg"] = "Invalid code - it should be 5 digits"
        
        # stats for specific question (# ideas, etc.)
        elif request == "stats" and self.question:
            data = Question.getStats(self.dbConnection, self.question.id)
                  
        # ideas for question
        elif request == "ideas" and self.question:
            ideas = Idea.getByQuestion(self.dbConnection, self.question.id, asDict=True)
            data = { "ideas": ideas }
            
        elif request == "idea":
            ideaId = self.request.get("idea_id")
            idea = Idea.getById(self.dbConnection, ideaId)
            if idea:
                data = idea.toDict()
            else:
                idea = Idea()
                data = idea.toDict()
                data["msg"] = "Idea not found"
        
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
                data = {"status": 1, "question_id": self.question.id }
                sendMessage(self.dbConnection, clientId, self.question.id, { "op" : "newquestion" })

        self.writeResponseAsJson(data)
        self.destroy()

class EditQuestionHandler(BaseHandler):
    def post(self):
        self.init(forceCheckUser=True);
        clientId = self.request.get('client_id')
        title_text = self.request.get('title')
        question_text = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication', '0') == "1"
        data = {}
        # TODO: checked in default template values; do same for json handlers?
        if not self.person or not self.person.user:
            data["status"] = 0
            data["msg"] = "Please log in"
                 
        elif not self.question:
            data["status"] = 0
            data["msg"] = "Invalid question code"
            
        elif self.question.author != self.person.user:
            data["status"] = 0
            data["msg"] = "You do not have permission to edit this question"
        
        elif len(title_text) < 5 or len(question_text) < 5:
            data["status"] = 0
            data["msg"] = "Title and question must must be at least 5 characters"

        else:
            self.question.editQuestion(title_text, question_text, nicknameAuthentication)
            data = { "status": 1, "question": self.question.toDict() }
            sendMessage(self.dbConnection, clientId, self.question.id, { "op": "newquestion" })
            
        self.writeResponseAsJson(data)
        self.destroy()
                
class NewIdeaHandler(BaseHandler):
    # TODO: author vs user vs person
    # TODO: idea.toDict should include name of author
    def post(self):
        self.init()
        clientId = self.request.get('client_id')
        ideaText = self.request.get('idea')
        # TODO: check whether or not question id exists or not?
        if ideaText and ideaText != "":
            idea = Idea.create(self.dbConnection, self.question.id, self.person.id, ideaText)
            sendMessage(self.dbConnection, clientId, self.question.id, { "op": "newidea", "idea": idea.toDict() })    
        self.destroy()
            
class DeleteHandler(BaseHandler):
    def post(self):
        self.init(forceCheckUser=True);
        clientId = self.request.get('client_id')
        if self.question:
            self.question.delete(self.dbConnection)
            sendMessage(self.dbConnection, clientId, self.question.id, { "op": "delete" })
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
        self.init(forceCheckUser=True)
        clientId = self.request.get('client_id')
        phase = int(self.request.get('phase'))
     
        if self.question:
            self.question.setPhase(self.dbConnection, phase)
            sendMessage(self.dbConnection, clientId, self.question.id, { "op" : "phase", "phase" : phase})
            
        self.destroy()

class CascadeOptionsHandler(BaseHandler):
    def post(self):
        # TODO: FIX!!
        pass
#         self.initUserContext(force_check=True)
#         client_id = self.request.get('client_id')
#         question_id = self.request.get("question_id")
#         questionObj = Question.getQuestionById(question_id)
#         k = int(self.request.get('cascade_k'))
#         m = int(self.request.get('cascade_m'))
#         t = int(self.request.get('cascade_t'))
#         if questionObj:
#             cascade = Cascade.getCascadeForQuestion(questionObj)
#             cascade.setOptions(k, m, t)

class ConnectedHandler(webapp2.RequestHandler):
    # Notified when clients connect
    def post(self):
        clientId = self.request.get("from")
        person = Person.getPersonFromClientId(clientId)
        if person:
            person.addClientId(clientId)    
            
class DisconnectedHandler(webapp2.RequestHandler):
    # Notified when clients disconnect
    def post(self):
        clientId = self.request.get("from")
        person = Person.getPersonFromClientId(clientId)
        if person:
            person.removeClientId(clientId)
    
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