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
import json
import os
import re
import string
import StringIO
import time
import webapp2
from google.appengine.api import users
from google.appengine.api import taskqueue
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

    def init(self, initUser=True, adminRequired=False):
        # Get the current browser session, if any
        # Otherwise, create one
        self.session = gaesessions.get_current_session()
        if self.session.sid is None:
            self.session.start()
        
        if self.dbConnection:
            self.dbConnection.disconnect()
            
        # Google recommends that a new connection be created to service each HTTP request, 
        # and re-used for the duration of that request (since the time to create a new connection is 
        # similar to that required to test the liveness of an existing connection).
        # https://developers.google.com/cloud-sql/faq#connections
        self.dbConnection = DatabaseConnection()
        self.dbConnection.connect()
            
        questionId = self.request.get("question_id")
        if questionId:
            self.question = Question.getById(self.dbConnection, questionId)

        if initUser:
            self.initUserContext(adminRequired=adminRequired)
                
    def destroy(self):
        if self.dbConnection:
            self.dbConnection.disconnect()
                
    def initUserContext(self, adminRequired=False):
        nickname = self.request.get("nickname", None)
        question = self.question
                    
        # if question allows nickname authentication and nickname not provided,
        # check if stored in session
        if question and question.nickname_authentication and not nickname:
            questionValues = self.session.get(question.id) if self.session.has_key(question.id) else None
            nickname = questionValues["nickname"] if questionValues else None
           
        # force check for authenticated Google user not affiliated with a specific question
        if adminRequired:
            question = None
            nickname = None
        
        # get person, and update login status if needed
        self.person = Person.getPerson(self.dbConnection, question, nickname)
        if self.person:
            self.person.login(self.dbConnection)        

    def isUserLoggedIn(self):
        return self.person and self.person.is_logged_in
    
    def isAdminLoggedIn(self):
        return Person.isAdmin() or (self.question and self.question.isAuthor())
    
    def getDefaultTemplateValues(self, connect=True):
        """Return a dictionary of default template values""" 
        
        # check if user logged in 
        loggedIn = self.isUserLoggedIn()        
        if loggedIn:
            # create a new channel if connect is true
            if connect:
                clientId, token = createChannel(self.question, self.person)
            
            url = getLogoutUrl(self.question)    
            urlLink = 'Logout'
        
        # otherwise, user not logged in
        else:
            nicknameAuthenticationAllowed = self.question and self.question.nickname_authentication and not self.question.isAuthor()
            url = getLoginUrl(self.request.uri, self.question)
            urlLink = "Login w/ Nickname" if nicknameAuthenticationAllowed else "Login w/ Google Account"
                    
        template_values = {}
        template_values['logged_in'] = json.dumps(loggedIn)  
        template_values['url_linktext'] = urlLink
        template_values['url'] = url
        template_values['msg'] = self.session.pop("msg") if self.session.has_key("msg") else ""
          
        if loggedIn:
            template_values['client_id'] = clientId
            template_values['token'] = token
            template_values['user_login'] = self.person.authenticated_nickname if self.person.authenticated_nickname else self.person.nickname
            template_values['user_nickname'] = self.person.nickname
            template_values['admin'] = self.isAdminLoggedIn()
            
        if self.question:
            template_values["question_id"] = self.question.id
            template_values["title"] = self.question.title
            template_values["question"] = self.question.question
            template_values["active"] = self.question.active
            template_values["phase"] = self.question.phase
                
        return template_values
    
    def checkRequirements(self, userRequired=False, authenticatedUserRequired=False, optionalQuestionCode=False, questionRequired=False, activeQuestionRequired=True, editPrivilegesRequired=False):
        ok = True
        
        # check if user logged in
        if ok and userRequired:
            ok = self.checkIfUserLoggedIn()

        # check if authenticated user logged in            
        if ok and authenticatedUserRequired:
            ok = self.checkIfAuthenticatedUserLoggedIn()
        
        # question code is optional, but if provided must be valid
        if ok and optionalQuestionCode:
            ok = self.checkOptionalQuestionCode()
            
        # check if valid question
        if ok and questionRequired:
            ok = self.checkIfQuestion(activeQuestionRequired)
            
        # check if user has edit privileges for question
        if ok and editPrivilegesRequired:
            ok = self.checkIfHasEditPrivileges()
            
        return ok
            
    def checkIfUserLoggedIn(self):
        ok = self.isUserLoggedIn()
        if not ok:
            self.session['msg'] = "Please login"
        return ok
    
    def checkIfAuthenticatedUserLoggedIn(self):
        ok = self.isUserLoggedIn() and self.person.authenticated_user_id
        if not ok:
            self.session['msg'] = "Please login"
        return ok

    def checkOptionalQuestionCode(self):
        ok = not self.request.get("question_id") or self.question
        if not ok:
            self.session['msg'] = "Invalid question code"
        return ok
    
    def checkIfQuestion(self, activeQuestionRequired=True):  
        ok = True  
        if not self.request.get("question_id"):
            self.session['msg'] = "Question code required"
            ok = False
        elif not self.question:
            self.session['msg'] = "Invalid question code"
            ok = False
        elif activeQuestionRequired and not self.question.active:
            self.session['msg'] = "Question not active"
            ok = False
        return ok
          
    def checkIfHasEditPrivileges(self):
        # check if user has permission to modify this question, if question defined
        ok = True
        if self.question:
            ok = self.isAdminLoggedIn()
            if not ok:
                self.session['msg'] = "You do not have permission to edit this question"
        return ok
  
    def writeResponseAsJson(self, data):
        self.response.headers.add_header('Content-Type', 'application/json', charset='utf-8')
        self.response.out.write(helpers.toJson(data))
        
    def writeResponseAsFile(self, encodedContent, contentType, filename, encoding):
        # Filename may consist of only letters, numbers, period, underscore, and hyphen.
        assert re.match(r"^[-_.a-zA-Z0-9]+$", filename) is not None, repr(filename)

        if encoding is not None:
            contentType += "; charset=%s"%encoding

        self.response.headers["Content-Type"] = contentType
        self.response.headers["Content-Disposition"] = 'attachment; filename="%s"'%filename
        self.response.out.write(encodedContent)
        
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

class NicknameLoginPageHandler(BaseHandler):
    def get(self):
        self.init()
        self.checkRequirements(questionRequired=True)
        templateValues = self.getDefaultTemplateValues()        
        path = os.path.join(os.path.dirname(__file__), '../html/login.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
        
class IdeaPageHandler(BaseHandler):
    def get(self): 
        self.init()      
        self.checkRequirements(userRequired=True, questionRequired=True)
        templateValues = self.getDefaultTemplateValues()  
        templateValues["change_nickname_allowed"] = json.dumps(self.person and self.person.authenticated_user_id is not None)
        path = os.path.join(os.path.dirname(__file__), '../html/idea.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
     
class CascadePageHandler(BaseHandler):
    def get(self):
        self.init() 
        self.checkRequirements(userRequired=True, questionRequired=True)
        templateValues = self.getDefaultTemplateValues()  
        path = os.path.join(os.path.dirname(__file__), '../html/cascade.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
                
class ResultsPageHandler(BaseHandler):
    def get(self):
        self.init()    
        self.checkRequirements(userRequired=True, questionRequired=True, activeQuestionRequired=False)
        templateValues = self.getDefaultTemplateValues()
        path = os.path.join(os.path.dirname(__file__), '../html/results.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()

class AdminPageHandler(BaseHandler):
    def get(self):
        self.init(adminRequired=True)
        self.checkRequirements(authenticatedUserRequired=True, optionalQuestionCode=True, editPrivilegesRequired=True)            
        templateValues = self.getDefaultTemplateValues()
        path = os.path.join(os.path.dirname(__file__), '../html/admin.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
                
#####################
# Action Handlers
#####################

class LoginHandler(BaseHandler):    
    # called after successful Google authentication
    def get(self):
        self.init(initUser=False)
        page = self.request.get("page")

        self.person = Person.getPerson(self.dbConnection, self.question)              
        if not self.person:
            self.person = Person.create(self.dbConnection, question=self.question)
        else:
            self.person.login(self.dbConnection)
                     
        self.destroy()
        self.redirect(str(page) if page else (getPhaseUrl(self.question) if self.question else "/"))
                
class NicknameLoginHandler(BaseHandler):    
    def post(self):
        self.init(initUser=False)
        nickname = self.request.get("nickname")
        page = self.request.get("page")
        specialChars = set('$\'"*,')

        ok = self.checkRequirements(questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
            
        elif not self.question.nickname_authentication:
            data = { "status" : 0, "msg" : "This question does not allow nickname authentication" }
    
        elif not nickname:
            data = { "status" : 0, "msg" : "" }
        
        elif any((c in specialChars) for c in nickname):
                data = { "status" : 0, "msg" : "Nickname can not contain {0}".format("".join(specialChars)) }                
        
        else:
            self.person = Person.getPerson(self.dbConnection, self.question, nickname)  
            
            # check if someone is already logged in with same nickname
            if self.isUserLoggedIn():
                data = { "status" : 0, "msg" : "Someone is already logged in as {0}".format(nickname) }
                
            else:
                if not self.person:
                    self.person = Person.create(self.dbConnection, question=self.question, nickname=nickname)
                else:
                    self.person.login(self.dbConnection)

                self.session[self.question.id] = { "nickname": nickname }
                data = { "status" : 1, "url" : str(page) if page else (getPhaseUrl(self.question) if self.question else "/") }

        self.writeResponseAsJson(data)       
        self.destroy()

class QuestionLoginHandler(BaseHandler):
    # log user in to question
    # if user not logged in yet, return url to login
    # otherwise, return url for current phase of question
    def post(self):
        self.init()
        ok = self.checkRequirements(questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
               
        else:
            if self.person:
                self.person.login(self.dbConnection)
                                            
            data = { 
                "status" : 1, 
                "question" : self.question.toDict(), 
                "url" : getPhaseUrl(self.question) if self.person else getLoginUrl(self.request.uri, self.question) 
            }
        
        self.writeResponseAsJson(data)
        self.destroy()
                     
class LogoutHandler(BaseHandler):
    def get(self):
        self.init()
        ok = self.checkRequirements(userRequired=True)
        if ok:
            self.person.logout(self.dbConnection)
            session = gaesessions.get_current_session()
            if session.is_active():
                session.terminate(True)
                session.clear()
                session.regenerate_id()

        self.destroy()
        
        # redirect depending on whether logged in as Google user or via nickname
        self.redirect(users.create_logout_url("/") if self.person and self.person.authenticated_user_id else "/")

class NicknameHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        nickname = self.request.get("nickname")
        specialChars = set('$\'"*,')
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True)        
        if not ok:
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
            self.person.update(self.dbConnection, { "nickname" : nickname, "id" : self.person.id })           
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
        adminQueries = ("questions", "stats")
        data = {}

        if request:
            self.init(adminRequired=request in adminQueries)
            
            # questions created by user
            if request == "questions":
                questions = Question.getByUser(self.dbConnection, asDict=True)                        
                data = { "questions": questions }
                        
            # stats for question (# ideas, etc.)
            elif request == "stats" and self.question:
                data = Question.getStats(self.dbConnection, self.question.id)
                                
            # ideas for question (grouped if categories exist; otherwise returned as uncategorized)
            elif request == "ideas" and self.question:
                categorizedIdeas, uncategorizedIdeas, numIdeas = Idea.getByCategories(self.dbConnection, self.question, asDict=True)
                data = { "question": self.question.toDict(), "categorized": categorizedIdeas, "uncategorized": uncategorizedIdeas, "count" : numIdeas }
                
        self.writeResponseAsJson(data)
        self.destroy()

class NewQuestionHandler(BaseHandler):
    def post(self):
        self.init()
        title = self.request.get('title')
        questionText = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication', '0') == "1"
        clientId = self.request.get('client_id')

        ok = self.checkRequirements(authenticatedUserRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        elif len(title) < 5 or len(questionText) < 5:
            data = { "status" : 0, "msg" : "Title and question must must be at least 5 characters" }
                     
        else:
            self.question = Question.create(self.dbConnection, self.person, title, questionText, nicknameAuthentication)
            data = { "status": 1, "question": self.question.toDict() }
            #sendMessage(self.dbConnection, clientId, self.question.id, { "op" : "newquestion" })

        self.writeResponseAsJson(data)
        self.destroy()

class EditQuestionHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True);
        title = self.request.get('title')
        questionText = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication', '0') == "1"
        clientId = self.request.get('client_id')
        
        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, activeQuestionRequired=False, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        elif len(title) < 5 or len(questionText) < 5:
            data = { "status" : 0, "msg" : "Title and question must must be at least 5 characters" }

        else:            
            properties = {
                "title" : title,
                "question" : questionText,
                "nickname_authentication" : nicknameAuthentication,
                "id" : self.question.id
            }
            self.question.update(self.dbConnection, properties)            
            data = { "status": 1, "question": self.question.toDict() }
            #sendMessage(self.dbConnection, clientId, self.question.id, { "op": "editquestion" })
            
        self.writeResponseAsJson(data)
        self.destroy()
            
class DeleteQuestionHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True)
        clientId = self.request.get('client_id')

        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, activeQuestionRequired=False, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        else:
            self.question.delete(self.dbConnection)
            data = { "status" : 1 }
            sendMessage(self.dbConnection, clientId, self.question.id, { "op": "delete" })
            
        self.writeResponseAsJson(data) 
        self.destroy()
        
class DownloadQuestionHandler(BaseHandler):
    def get(self):
        self.init(adminRequired=True)

        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, activeQuestionRequired=False, editPrivilegesRequired=True)
        if ok:
            reportBuffer = StringIO.StringIO()
            excelWriter = helpers.UnicodeWriter(reportBuffer, "excel-tab", "utf8")
            
            utcOffsetMinutes = int(self.request.get("utc_offset_minutes", 0))
            utcOffset = datetime.timedelta(minutes=utcOffsetMinutes)
             
            # write out question info
            excelWriter.writerow(("Question",))
            excelWriter.writerow((self.question.title,))
            excelWriter.writerow((self.question.question,))
            excelWriter.writerow(("#{0}".format(self.question.id),))
            excelWriter.writerow(())
             
            # write out ideas with categories
            if self.question.cascade_complete:
                cascadeDuration = self.question.calculateCascadeDuration(self.dbConnection);
                # write out cascade parameters
                excelWriter.writerow(("Cascade Settings",))
                excelWriter.writerow(("Duration", cascadeDuration if cascadeDuration else "" ))
                excelWriter.writerow(("k", self.question.cascade_k))
                excelWriter.writerow(("k2", self.question.cascade_k2))
                excelWriter.writerow(("m", self.question.cascade_m))
                excelWriter.writerow(("p", self.question.cascade_m))
                excelWriter.writerow(("t", self.question.cascade_m))
                excelWriter.writerow(())
                
                headers = (
                    "Category",
                    "Same_As",
                    "Idea",
                    "Author",
                    "Author_Identity",
                    "Created_On",
                    "Idea_Id"
                )
                excelWriter.writerow(headers)
        
                categorizedIdeas, uncategorizedIdeas, numIdeas = Idea.getByCategories(self.dbConnection, self.question, asDict=True, includeCreatedOn=True)
                for categoryInfo in categorizedIdeas:   
                    category = categoryInfo["category"]
                    sameAs = categoryInfo["same_as"]
                    ideas = categoryInfo["ideas"]
                    for ideaDict in ideas:
                        line_parts = (
                            category,
                            sameAs if sameAs else "",
                            ideaDict["idea"],
                            ideaDict["author"],
                            ideaDict["author_identity"] if "author_identity" in ideaDict else "",
                            ideaDict["created_on"].strftime("%m/%d/%Y %H:%M:%S"),
                            ideaDict["id"]
                        )
                        excelWriter.writerow(line_parts)
                        
                for ideaDict in uncategorizedIdeas:   
                    line_parts = (
                        "NONE",
                        "",
                        ideaDict["idea"],
                        ideaDict["author"],
                        ideaDict["author_identity"] if "author_identity" in ideaDict else "",
                        ideaDict["created_on"].strftime("%m/%d/%Y %H:%M:%S"),
                        ideaDict["id"]
                    )
                    excelWriter.writerow(line_parts)
                                          
            # write out ideas generated so far
            else:
                headers = (
                    "Idea",
                    "Author",
                    "Author_Identity",
                    "Created_On",
                    "Idea_Id"
                )
                excelWriter.writerow(headers)
        
                ideas = Idea.getByQuestion(self.dbConnection, self.question, asDict=True, includeCreatedOn=True)
                for ideaDict in ideas:     
                    line_parts = (
                        ideaDict["idea"],
                        ideaDict["author"],
                        ideaDict["author_identity"] if "author_identity" in ideaDict else "",
                        ideaDict["created_on"].strftime("%m/%d/%Y %H:%M:%S"),
                        ideaDict["id"]
                    )
                    excelWriter.writerow(line_parts)  
                            
            reportText = reportBuffer.getvalue()
            reportBuffer.close()
    
            contentType = "text/tab-separated-values"
            filename = "qa_question_{0}_as_of_{1}.txt".format(self.question.id, (datetime.datetime.now()-utcOffset).strftime("%Y%m%d-%H%M%S"))
            self.writeResponseAsFile(encodedContent=reportText, contentType=contentType, filename=filename, encoding="UTF-8")
            
        self.destroy()
          
class NewIdeaHandler(BaseHandler):
    def post(self):
        self.init()
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        else:
            clientId = self.request.get('client_id')
            ideaText = self.request.get('idea')                
            if ideaText and ideaText != "":
                idea = Idea.create(self.dbConnection, self.question, self.person.id, ideaText)
                data = { "status" : 1 }            
                author = { 
                    "nickname" : self.person.nickname, 
                    "authenticated_nickname" : self.person.authenticated_nickname if not self.question.nickname_authentication else None 
                }
                msg = { "op": "newidea", "idea": idea.toDict(author=author, admin=False) }
                adminMsg = { "op": "newidea", "idea": idea.toDict(author=author, admin=True) }
                sendMessage(self.dbConnection, clientId, self.question.id, msg, adminMsg)
        
        self.writeResponseAsJson(data) 
        self.destroy()

class ActiveHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True)
        clientId = self.request.get('client_id')
        try:
            active = int(self.request.get('active'))
        except ValueError:
            active = 0
            
        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, activeQuestionRequired=False, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") } 
            
        else:
            self.question.setActive(self.dbConnection, active)
            data = { "status" : 1, "question" : self.question.toDict() }
            if active == 0:
                sendMessage(self.dbConnection, clientId, self.question.id, { "op" : "disable" })

        self.writeResponseAsJson(data)            
        self.destroy()
        
class PhaseHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True)
        clientId = self.request.get('client_id')
        try:
            phase = int(self.request.get('phase'))
        except ValueError:
            phase = None
            
        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
          
        elif phase == None:
            data = { "status" : 0, "msg" : "Invalid phase requested" }   
            
        else:
            self.question.setPhase(self.dbConnection, phase)
            data = { "status" : 1, "question" : self.question.toDict() }
            sendMessage(self.dbConnection, clientId, self.question.id, { "op" : "phase", "phase" : phase, "cascade_step" : self.question.cascade_step })

        self.writeResponseAsJson(data)            
        self.destroy()
                            
class CascadeJobHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")

        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        elif self.question.phase != constants.PHASE_CASCADE:
            data = { "status" : 0, "msg" : "Cascade not enabled currently" }
             
        else:
            # save job (if any)
            jobToSave = helpers.fromJson(self.request.get("job", None))
            if jobToSave:
                isStepComplete = self.question.saveCascadeJob(self.dbConnection, jobToSave)
                if isStepComplete:
                    taskqueue.add(url="/cascade_init_step", params={ 'question_id' : self.question.id })
               
            # return new job (if any available)
            newJob = None
            if (jobToSave and not isStepComplete) or not self.question.cascade_complete:
                newJob = self.question.getCascadeJob(self.dbConnection, self.person)
            data = { "status" : 1, "step" : self.question.cascade_step, "job": [task.toDict() for task in newJob] if newJob else [], "complete" : 1 if self.question.cascade_complete else 0 }
                   
        self.writeResponseAsJson(data)
        self.destroy()

class CascadeInitStepHandler(BaseHandler):
    def post(self):
        self.init()
        # userRequired=True does not seem to work within taskqueue so cannot check
        ok = self.checkRequirements(questionRequired=True)
        if ok:
            self.question.continueCascade(self.dbConnection)
            if self.question.cascade_complete:
                # notify any waiting clients that categories are ready
                sendMessage(self.dbConnection, None, self.question.id, { "op": "categories" })
            else:                    
                # notify any waiting clients that next step that is ready
                sendMessage(self.dbConnection, None, self.question.id, { "op": "step", "step": self.question.cascade_step })

class CascadeOptionsHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True)
        clientId = self.request.get('client_id')

        ok = self.checkRequirements(self, authenticatedUserRequired=True, questionRequired=True, activeQuestionRequired=False, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }

        else:
            properties = {
                "cascade_k" :  int(self.request.get('cascade_k')),
                "cascade_k2" : int(self.request.get('cascade_k2')),
                "cascade_m" :  int(self.request.get('cascade_m')),
                "cascade_p" :  int(self.request.get('cascade_p')),
                "cascade_t" :  int(self.request.get('cascade_t')),
                "id" : self.question.id
            }
            self.question.update(self.dbConnection, properties)
            data = { "status" : 1, "question" : self.question.toDict() }
        
        self.writeResponseAsJson(data)
        self.destroy()
        
#####################
# Channel support
#####################
          
class ChannelConnectedHandler(BaseHandler):
    # Notified when clients connect
    def post(self):
        self.init(initUser=False)
        clientId = self.request.get("from")
        questionId, personId, isAdmin = getInfoFromClient(clientId)
        person = Person.getById(self.dbConnection, personId)
        if person:
            person.addClient(self.dbConnection, clientId) 
        self.destroy()   
            
class ChannelDisconnectedHandler(BaseHandler):
    # Notified when clients disconnect
    def post(self):
        self.init(initUser=False)
        clientId = self.request.get("from")
        questionId, personId, isAdmin = getInfoFromClient(clientId)
        person = Person.getById(self.dbConnection, personId)
        if person:
            numClients = person.removeClient(self.dbConnection, clientId, returnNumClients=True, commit=False)
            if numClients == 0 and person.is_logged_in:
                person.logout(self.dbConnection, commit=False)
            self.dbConnection.conn.commit()
        self.destroy()

def createChannel(question, person):
    clientId = str(random.randint(1000000000000, 10000000000000))
    clientId += "_" + (str(question.id) if question else constants.EMPTY_CLIENT_TOKEN)
    clientId += "_" + (str(person.id) if person else constants.EMPTY_CLIENT_TOKEN)
    # question authors are marked with a "_a" in the clientId
    if question and question.isAuthor():
        clientId += "_a"                                     
    token = channel.create_channel(clientId)
    return clientId, token

def getInfoFromClient(clientId):
    tokens = clientId.split("_")
    questionId = tokens[1] if len(tokens) >= 3 and tokens[1] != constants.EMPTY_CLIENT_TOKEN else None
    personId = tokens[2] if len(tokens) >= 3 and tokens[2] != constants.EMPTY_CLIENT_TOKEN else None
    isAdmin = "a" in tokens[3] if len(tokens) >= 4 else False
    return (questionId, personId, isAdmin)

def sendMessage(dbConnection, fromClientId, questionId, message, adminMessage=None):
    """Send message to all listeners (except self if fromClientId specified) to this topic"""
    if questionId:
        # TODO: would it be better to store client ids memcache instead of requiring db query each time
        sql = "select client_id from users,user_clients where users.id=user_clients.user_id and question_id=%s"
        dbConnection.cursor.execute(sql, (questionId))
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            toClientId = row["client_id"]
            toMessage = message
            if not fromClientId or toClientId != fromClientId:
                if adminMessage:
                    clientQuestionId, clientPersonId, clientIsAdmin = getInfoFromClient(toClientId)
                    if clientIsAdmin:
                        toMessage = adminMessage
                channel.send_message(toClientId, json.dumps(toMessage))

#####################
# URL routines
#####################

def getLoginUrl(page=None, question=None):
    url = users.create_login_url("/login?page=" + page) if page else ""
    if question:
        if question.nickname_authentication:
            url = "/nickname_page?question_id=" + str(question.id)            
        else:
            url = users.create_login_url("/login?page=" + getPhaseUrl(question) + ("&question_id="+str(question.id) if question else ""))
    return url

def getLogoutUrl(question=None):
    url = "/logout"
    if question:
        url += "?question_id=" + str(question.id)
    return url
        
def getPhaseUrl(question=None):
    url = "/"
    if question:
        if question.phase <= constants.PHASE_NOTES:
            url = "/idea?question_id=" + str(question.id)
        elif question.phase == constants.PHASE_CASCADE:
            if not question.cascade_complete:
                url = "/cascade?question_id=" + str(question.id)
            else:
                url = "/results?question_id=" + str(question.id)
    return url