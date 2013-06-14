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
import random
import string
import webapp2
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from lib import gaesessions
from db import *

def get_default_template_values(requestHandler, person, question):
    """Return a dictionary of template values used for login template"""        
    
    page = requestHandler.request.path
    requiresGoogleAuthentication = page == "/admin" or not question or not question.nicknameAuthentication
    
    # user already logged in    
    if person:
        # TODO: need to implement
        #client_id, token = connect(person)
        client_id = ""
        token = ""
        url_linktext = 'Logout'
        url = users.create_logout_url("/logout") if person.authenticatedUserId else "/logout"
         
    # no one logged in, and Google authentication required
    elif requiresGoogleAuthentication:
        url_linktext = 'Login w/ Google Account'
        url = "/login?page=" + requestHandler.request.uri + ("&question_id="+question.code if question else "")
        url = users.create_login_url(url)
        
    # no one logged in, and nickname authentication allowed
    else:
        url_linktext = "Login w/ Nickname"
        url = "/loginpage" + ("?question_id=" + question.code if question else "")
        
    session = gaesessions.get_current_session()
    msg = session.pop("msg") if session.has_key("msg") else ""

    template_values = {}
    template_values['logged_in'] = "true" if person else "false"       
    template_values['url_linktext'] = url_linktext
    template_values['url'] = url
    template_values['msg'] = msg
        
    if person:
        template_values['client_id'] = client_id
        template_values['token'] = token
        # the displayed user login should be the nickname if on question page (e.g., url has question_id param)
        # and nickname authentication is allowed; otherwise the Google login should be displayed
        # TODO: FIX - show login not id
        template_values['user_login'] = person.authenticatedUserId if requiresGoogleAuthentication else person.nickname
        template_values['user_nickname'] = person.nickname
        googleUser = users.get_current_user()
        template_values['admin'] = True # TODO: FIX!! Person.isAdmin(requestHandler) or (googleUser and (not question or question.author == googleUser))

    if question:
        template_values["question_id"] = question.code
        template_values["phase"] = question.phase
        template_values["title"] = question.title
        template_values["question"] = question.question
            
    return template_values

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

    def dbConnect(self):
        if self.dbConnection:
            self.dbConnection.disconnect()
            
        self.dbConnection = DatabaseConnection()
        self.dbConnection.connect()
    
    def dbDisconnect(self):
        if self.dbConnection:
            self.dbConnection.disconnect()
                
    def initUserContext(self, force_check=False, create=False):        
        # Get the current browser session, if any
        # Otherwise, create one
        session = gaesessions.get_current_session()          
        if session.sid is None:
            session.start()
            
        questionId = self.request.get("question_id")        
        question = Question.getById(self.dbConnection, questionId)
        nickname = self.request.get("nickname")
                        
        # if question allows nickname authentication
        # check if nickname stored in session, if not provided
        if question and question.nicknameAuthentication and not nickname:
            questionValues = session.get(question.code) if session.has_key(question.code) else None
            nickname = questionValues["nickname"] if questionValues else None
           
        # if requested, force check for authenticated user not affiliated with any specific question
        if force_check:
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

    def writeResponseAsJson(self, data):
        self.response.headers.add_header('Content-Type', 'application/json', charset='utf-8')
        self.response.out.write(helpers.to_json(data))
        
    def redirectWithMsg(self, msg=None, dst="/"):        
        if msg is not None:
            session = gaesessions.get_current_session()
            session['msg'] = msg
        self.redirect(dst)
    
class MainPageHandler(BaseHandler):
    def get(self):
        self.dbConnect()
        person = self.initUserContext()       
        template_values = get_default_template_values(self, person, None)        
        path = os.path.join(os.path.dirname(__file__), '../html/main.html')
        self.response.out.write(template.render(path, template_values))
        self.dbDisconnect()

class IdeaPageHandler(BaseHandler):
    def get(self):       
        self.dbConnect() 
        person = self.initUserContext()
        questionId = self.request.get("question_id")
        question = Question.getById(self.dbConnection, questionId)
        template_values = get_default_template_values(self, person, question)
        if question:
            template_values["change_nickname_allowed"] = json.dumps(not question.nicknameAuthentication)

        path = os.path.join(os.path.dirname(__file__), '../html/idea.html')
        self.response.out.write(template.render(path, template_values))
        self.dbDisconnect()
     
# Participant page that uses Cascade to create categories for ideas
# TODO: check if ideas exist for question; if not, do not enable cascade
# TODO: when cascade step changed, notify user but do not assigned task automatically
class CascadePageHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)         
        template_values = get_default_template_values(self, person, question)
        path = os.path.join(os.path.dirname(__file__), '../html/cascade.html')
        self.response.out.write(template.render(path, template_values))
                
class ResultsPageHandler(BaseHandler):
    def get(self):
        pass
#         person = self.initUserContext()
#         question_id = self.request.get("question_id")
#         questionObj = Question.getQuestionById(question_id)
#         
#         # if no person found, check if question author trying to view results page
#         # if so, display page even if nickname authentication required
#         isQuestionAuthor = False
#         if not person:
#             user = users.get_current_user()        
#             isQuestionAuthor = questionObj and user and questionObj.author == user
#             if isQuestionAuthor:
#                 person = Person.all().filter("question =", None).filter("user =", user).get()
# 
#         template_values = get_default_template_values(self, person, questionObj)
#         if isQuestionAuthor and person:
#             user_login = template_values["user_login"] = person.user
#             
#         path = os.path.join(os.path.dirname(__file__), '../html/results.html')
#         self.response.out.write(template.render(path, template_values))

class AdminPageHandler(BaseHandler):
    def get(self):
        self.dbConnect()
        person = self.initUserContext(force_check=True)
        questionObj = None
        
        # check if new_question_id stored in session
        # newly created questions may not be searchable immediately
        # but they should be retrievable with a key
        # would not be required if js did not immediately reload page
        # with question_id as url param (which forces new question search)
        session = gaesessions.get_current_session()
        question_id = session.pop("new_question_key") if session.has_key("new_question_key") else None                
        if question_id:
            questionObj = Question.getById(question_id)
            
        question_id = self.request.get("question_id")
        if question_id and not questionObj:
            questionObj = Question.getById(self.dbConnection, question_id)
        
        session = gaesessions.get_current_session()
        
        # check if user logged in
        if not person or not person.authenticatedUserId:
            questionObj = None
            session['msg'] = "Please login"
            
        # check if valid question code
        elif question_id and not questionObj:
            session['msg'] = "Invalid question code"
        
        # check if question owned by logged in user
        elif questionObj and (not questionObj.isAuthor(person) and not Person.isAdmin()):
            questionObj = None
            session['msg'] = "You do not have permission to edit this question"

        template_values = get_default_template_values(self, person, questionObj) 
        # TODO: FIX!!
#         if questionObj:
#             cascade = Cascade.getCascadeForQuestion(questionObj)            
#             template_values["cascade_k"] = cascade.k
#             template_values["cascade_m"] = cascade.m
#             template_values["cascade_t"] = cascade.t
#             template_values["num_ideas"] = Idea.getNumIdeas(questionObj)

        path = os.path.join(os.path.dirname(__file__), '../html/admin.html')
        self.response.out.write(template.render(path, template_values))
        self.dbDisconnect()
        
class LoginPageHandler(BaseHandler):
    def get(self):
        self.dbConnect()
        person = self.initUserContext()       
        question_id = self.request.get("question_id")
        questionObj = Question.getById(self.dbConnection, question_id)
        template_values = get_default_template_values(self, person, questionObj)        
        path = os.path.join(os.path.dirname(__file__), '../html/login.html')
        self.response.out.write(template.render(path, template_values))
        self.dbDisconnect()
        
#####################
# Action Handlers
#####################

class LoginHandler(BaseHandler):
    def get(self):
        self.dbConnect()
        nickname = self.request.get("nickname")
        page = self.request.get("page")
        questionId = self.request.get("question_id")
        question = Question.getById(self.dbConnection, questionId)

        # if question allows nickname authentication
        # store nickname in session if ok
        if question:
            person = Person.getPerson(self.dbConnection, question, nickname)
            if person and len(person.client_ids) > 0:
                if question.nicknameAuthentication:
                    self.redirectWithMsg("Someone is already logged in as " + nickname, "/loginpage?question_id="+questionId)
                else:
                    self.redirectWithMsg(str(person.user) + " is already logged in", dst="/")
                return
                
            if question.nicknameAuthentication and nickname:
                specialChars = set('$\'"*,')
                if any((c in specialChars) for c in nickname):
                    self.redirectWithMsg("Nickname can not contain " + "".join(specialChars), "/loginpage?question_id="+questionId)
                    return
                
                session = gaesessions.get_current_session()
                session[questionId] = { "nickname": nickname }

        person = self.initUserContext(create=True)
        url = str(page) if page else getPhaseUrl(person.question)
        
        self.dbDisconnect()
        self.redirect(url)

def getPhaseUrl(question=None):
    url = "/"
    if question:
        if question.phase <= constants.PHASE_NOTES:
            url = "/idea?question_id="+question.code
        elif question.phase == constants.PHASE_CASCADE:
            url = "/cascade?question_id="+question.code
    return url

class LogoutHandler(BaseHandler):
    def get(self):
        session = gaesessions.get_current_session()
        if session.is_active():
            session.terminate(True)
        self.redirect("/")

class NicknameHandler(BaseHandler):
    def post(self):
        self.dbConnect()
        self.initUserContext()
        clientId = self.request.get("client_id")
        questionId = self.request.get("question_id")
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
        
        data = { "question_id": questionId, "nickname": nickname, "msg": "" }
        
        if nicknameNotChanged:
            pass    # do nothing
        
        elif len(nickname) == 0:
            data["msg"] = "Empty nickname not allowed"

        elif any((c in specialChars) for c in nickname):
            data["msg"] = "Nickname can not contain " + "".join(specialChars)
            
        elif Person.doesNicknameExist(self.dbConnection, questionId, nickname):
            data["msg"] = "Nickname already exists (" + nickname + ")"
            
        else:
            person.setNickname(nickname)
            
            # Update clients
            message = {
                "op": "nickname",
                "text": "",
                "author": Person.toDict(person)
            }
            sendMessage(self.dbConnection, clientId, questionId, message)      # Update other clients about this change
        
        self.writeResponseAsJson(data)
        self.dbDisconnect()
                           
class QueryHandler(BaseHandler):
    def get(self):
        self.dbConnect()
        person = self.initUserContext()
        request = self.request.get("request")
        questionId = self.request.get("question_id")
        question = Question.getById(self.dbConnection, questionId)

        data = {}
        if request == "ideas":
            data = getIdeas(questionId)
        elif request == "idea":
            idea_id = self.request.get("idea_id")
            data = getIdea(idea_id)
        elif request == "phase":
            data = {"phase": Question.getPhase(question)}
        elif request == "question":
            if question:
                data = question.toDict()
            else:
                data = {
                    "title": "", 
                    "question": "",
                    "nicknameAuthentication": False,
                    "msg": "Invalid code - it should be 5 digits"
                }
        elif request == "questions":
            userQuestions = []
            for userQuestion in Question.getByUser(self.dbConnection):
                userQuestions.append(userQuestion.toDict())
            data = {"questions": userQuestions}

        self.writeResponseAsJson(data)
        self.dbDisconnect()

class NewQuestionHandler(BaseHandler):
    def post(self):
        self.dbConnect()
        person = self.initUserContext()
        title = self.request.get('title')
        questionText = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication', '0') == "1"
        clientId = self.request.get('client_id')

        data = {}        
        if not person:
            data["status"] = 0
            data["msg"] = "Please log in"
        
        elif len(title) < 5 or len(questionText) < 5:
            data["status"] = 0
            data["msg"] = "Title and question must must be at least 5 characters"
                     
        else:
            question = Question.create(self.dbConnection, person, title, questionText, nicknameAuthentication)
            
            if not question:
                data["status"] = 0
                data["msg"] = "Error saving question"
                
            else:
                data = {"status": 1, "question_id": question.id }
                sendMessage(self.dbConnection, clientId, question.id, { "op" : "newquestion" })

        self.writeResponseAsJson(data)
        self.dbDisconnect()

class EditQuestionHandler(BaseHandler):
    def post(self):
        self.dbConnect();
        person = self.initUserContext(force_check=True)
        clientId = self.request.get('client_id')
        questionId = self.request.get("question_id")
        question = Question.getById(self.dbConnection, questionId)
        title_text = self.request.get('title')
        question_text = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication', '0') == "1"
        data = {}
        if not person or not person.user:
            data["status"] = 0
            data["msg"] = "Please log in"
                 
        elif not question:
            data["status"] = 0
            data["msg"] = "Invalid question code"
            
        elif question.author != person.user:
            data["status"] = 0
            data["msg"] = "You do not have permission to edit this question"
        
        elif len(title_text) < 5 or len(question_text) < 5:
            data["status"] = 0
            data["msg"] = "Title and question must must be at least 5 characters"

        else:
            question = question.editQuestion(title_text, question_text, nicknameAuthentication)
            data = { "status": 1, "question": question.toDict() }

            # Update clients
            message = {
                "op": "newquestion"
            }
            sendMessage(self.dbConnection, clientId, question.id, message)        # Update other clients about this change

        self.writeResponseAsJson(data)
        self.dbDisconnect()
                
class NewIdeaHandler(BaseHandler):
    def post(self):
        self.dbConnect()
        person = self.initUserContext()
        clientId = self.request.get('client_id')
        idea = self.request.get('idea')
        questionId = self.request.get("question_id")
        if len(idea) >= 1:
            ideaObj = Idea.createIdea(idea, questionId, person)
 
            # Update clients
            message = {
                "op": "newidea",
                "text": idea,
                "author": Person.toDict(ideaObj.author)
            }
            sendMessage(self.dbConnection, clientId, questionId, message)
            
        self.dbDisconnect()
            
class DeleteHandler(BaseHandler):
    def post(self):
        self.dbConnect();
        self.initUserContext(force_check=True)
        clientId = self.request.get('client_id')
        questionId = self.request.get("question_id")
        Question.delete(questionId)

        # Update clients
        message = {
            "op": "delete"
        }
        sendMessage(self.dbConnection, clientId, questionId, message)        # Update other clients about this change
        self.dbDisconnect()
        
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
        self.dbConnect()
        self.initUserContext(force_check=True)
        clientId = self.request.get('client_id')
        questionId = self.request.get("question_id")
        question = Question.getById(self.dbConnection, questionId)   
        phase = int(self.request.get('phase'))
     
        if question:
            question.setPhase(self.dbConnection, phase)
            sendMessage(self.dbConnection, clientId, questionId, { "op" : "phase", "phase" : phase})
            
        self.dbDisconnect()

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

#####################
# Text Support
#####################

def getIdea(ideaIdStr):
    # TODO: FIX!!
    return None
#     ideaObj = Idea.getIdeaById(ideaIdStr)
#     if ideaObj:
#         idea = {
#             "idea": ideaObj.text,
#             "author": Person.toDict(ideaObj.author)
#         }
#     else:
#         idea = {}
#     return idea

def getIdeas(questionIdStr):
    # TODO: FIX!!
    return None
#     questionObj = Question.getQuestionById(questionIdStr)
# 
#     # Any ideas that aren't in any cluster (ideas may not be clustered at all)
#     ideaObjs = Idea.all().filter("question = ", questionObj).filter("cluster =", None)
#     if ideaObjs.count() > 0:
#         ideas = []
#         for ideaObj in ideaObjs:
#             ideas.append(ideaObj.toDict())
#         
#     return ideas

def computeBagsOfWords(question):
    # TODO: FIX!!
    return None
#     # First define vector by extracting every word
#     all_words = set()
#     phrases = []
#     texts = []
#     ids = []
#     if question:
#         ideas = Idea.all().filter("question = ", question).order('__key__')
#         for ideaObj in ideas:
#             text = ideaObj.text
#             texts.append(text)
#             words = text.split()
#             phrase = []
#             for word in words:
#                 word = cleanWord(word)
#                 if len(word) > 2:
#                     all_words.add(word)
#                     phrase.append(word)
#             phrases.append(phrase)
#             ids.append(ideaObj.key().id())
# 
#     # Create an index for the words
#     word_index = {}
#     i = 0
#     for word in all_words:
#         word_index[word] = i
#         i += 1
# 
#     # Then for each phrase, compute it's vector. Last element of vector is index
#     vectors = []
#     i = 0
#     for phrase in phrases:
#         vector = [0] * (len(word_index) + 1)
#         for word in phrase:
#             index = word_index[word]
#             vector[index] += 1
#         vector[len(word_index)] = i
#         vectors.append(tuple(vector))
#         i += 1
# 
#     return vectors, texts, phrases, ids
    
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