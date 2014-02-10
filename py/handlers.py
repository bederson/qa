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
import base64
import datetime
import json
import os
import random
import re
import string
import StringIO
import time
import urllib
import webapp2
from google.appengine.api import users
from google.appengine.api import taskqueue
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from google.appengine.api.logservice import logservice
from lib import gaesessions
from db import *

#####################
# Page Handlers
#####################

class BaseHandler(webapp2.RequestHandler):
    def init(self, questionId=None, initUser=True, adminRequired=False):   
        
        # get the current browser session, if any
        # otherwise, create one
        self.session = gaesessions.get_current_session()
        if self.session.sid is None:
            self.session.start()
                    
        # Google recommends that a new connection be created to service each HTTP request, 
        # and re-used for the duration of that request (since the time to create a new connection is 
        # similar to that required to test the liveness of an existing connection).
        # https://developers.google.com/cloud-sql/faq#connections
        self.dbConnection = DatabaseConnection()
        self.dbConnection.connect()
        
        # get question, if any
        # check for question_id in request, if not passed in
        if not questionId:
            questionId = self.request.get("question_id")  
        self.question = Question.getById(self.dbConnection, questionId) if questionId else None

        # get user, if any
        self.person = None
        if initUser:
            # get person and update login status, if needed
            # if adminRequired, force check for Google authenticated instructor (question=None)
            self.person = Person.getPerson(self.dbConnection, question=self.question if not adminRequired else None, session=self.session)
            if self.person and not self.person.is_logged_in:
                self.person.login(self.dbConnection, question=self.question, session=self.session)
                
    def destroy(self):
        if self.dbConnection:
            self.dbConnection.disconnect()
                    
    def isUserLoggedIn(self):
        return self.person is not None and self.person.is_logged_in

    def isAuthorLoggedIn(self):
        return self.question is not None and Person.isAuthor(self.question)
        
    def isAdminLoggedIn(self):
        return Person.isAdmin(self.person)
    
    def getDefaultTemplateValues(self, connect=True, adminConnect=False):
        """Return a dictionary of default template values""" 
        
        # check if user logged in 
        loggedIn = self.isUserLoggedIn() 
        isAdmin = self.isAdminLoggedIn()
        isAuthor = self.isAuthorLoggedIn()       
        if loggedIn:
            # create a new channel if connect is true
            if connect:
                clientId, token = createChannel(self.question if not adminConnect else None, self.person)
            
            url = getLogoutUrl(self.question)    
            urlLink = 'Logout'
        
        # otherwise, user not logged in
        else:
            nicknameAuthenticationAllowed = self.question is not None and self.question.authentication_type == constants.NICKNAME_AUTHENTICATION and not isAuthor
            url = getLoginUrl(self.request.uri, self.question)
            urlLink = "Login w/ Nickname" if nicknameAuthenticationAllowed else "Login w/ Google Account"
                    
        template_values = {}
        template_values['user_id'] = self.person.id if loggedIn else -1
        template_values['admin'] = True if loggedIn and (isAuthor or isAdmin) else False
        template_values['login_logout_linktext'] = urlLink
        template_values['login_logout_url'] = url
        template_values['msg'] = self.session.pop("msg") if self.session.has_key("msg") else ""
          
        if loggedIn:
            template_values['client_id'] = clientId
            template_values['token'] = token
            template_values['user_login'] = self.person.getLogin()

        if self.question:
            template_values["question_id"] = self.question.id
            template_values["question_title"] = self.question.title
            template_values["question_text"] = self.question.question
            template_values["question_active"] = json.dumps(self.question.active == 1)
            template_values["cascade_complete"] = json.dumps(self.question.cascade_complete == 1)
                
        return template_values
    
    def checkRequirements(self, userRequired=False, authenticatedUserRequired=False, optionalQuestionCode=False, questionRequired=False, activeQuestionRequired=True, editPrivilegesRequired=False, questionId=None):
        ok = True
        
        # check if user logged in
        if ok and userRequired:
            ok = self.checkIfUserLoggedIn()

        # check if authenticated user logged in            
        if ok and authenticatedUserRequired:
            ok = self.checkIfAuthenticatedUserLoggedIn()
        
        # question code is optional, but if provided must be valid
        if ok and optionalQuestionCode:
            ok = self.checkOptionalQuestionCode(questionId=questionId)
            
        # check if valid question
        if ok and questionRequired:
            ok = self.checkIfQuestion(activeQuestionRequired, questionId=questionId)
            
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

    def checkOptionalQuestionCode(self, questionId=None):
        if not questionId:
            questionId = self.request.get("question_id")
        ok = not questionId or self.question
        if not ok:
            self.session['msg'] = "Invalid question code"
        return ok
    
    def checkIfQuestion(self, activeQuestionRequired=True, questionId=None):
        ok = True
        if not questionId:
            questionId = self.request.get("question_id")
        if not questionId:
            self.session['msg'] = "Question code required"
            ok = False
        elif not self.question:
            self.session['msg'] = "Invalid question code"
            ok = False
        elif activeQuestionRequired and not self.question.active:
            self.session['msg'] = "Inactive question"
            ok = False
        return ok
          
    def checkIfHasEditPrivileges(self):
        # check if user has permission to modify this question, if question defined
        ok = True
        if self.question:
            ok = self.isAuthorLoggedIn() or self.isAdminLoggedIn()
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
        
    def getStartUrl(self):
        url = None
        if self.question:
            url = self.request.host_url
            url = url.replace("http://","")
            url += getIdeaPageUrl(self.question, short=True)
        return url
     
class MainPageHandler(BaseHandler):
    def get(self):
        self.init()      
        templateValues = self.getDefaultTemplateValues()
        path = os.path.join(os.path.dirname(__file__), '../html/main.html')
        self.response.out.write(template.render(path, templateValues))                
        self.destroy()

class NicknameLoginPageHandler(BaseHandler):
    def get(self, questionId):
        self.init(questionId=questionId)
        self.checkRequirements(questionRequired=True, questionId=questionId)
        templateValues = self.getDefaultTemplateValues()        
        path = os.path.join(os.path.dirname(__file__), '../html/login.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
        
class IdeaPageHandler(BaseHandler):
    def get(self, questionId):
        self.init(questionId=questionId)
        ok = self.checkRequirements(userRequired=True, questionRequired=True, questionId=questionId)
        templateValues = self.getDefaultTemplateValues()
        templateValues["user_nickname"] = self.person.getNickname() if self.person else None
        # allow Google authenticated students and non-authenticated students to change nickname
        # nicknames for non-authenticated students do not have to be unique
        templateValues["change_nickname_allowed"] = json.dumps(ok and self.person is not None and (self.question.authentication_type==constants.GOOGLE_AUTHENTICATION or self.question.authentication_type==constants.NO_AUTHENTICATION))
        templateValues["start_url"] = self.getStartUrl() if ok and not self.question.cascade_complete else ""
        path = os.path.join(os.path.dirname(__file__), '../html/idea.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
     
class CascadePageHandler(BaseHandler):
    def get(self, questionId):
        self.init(questionId=questionId) 
        ok = self.checkRequirements(userRequired=True, questionRequired=True, questionId=questionId)
        templateValues = self.getDefaultTemplateValues()
        templateValues["start_url"] = self.getStartUrl() if ok and not self.question.cascade_complete else ""
        path = os.path.join(os.path.dirname(__file__), '../html/cascade.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
        
class ResultsPageHandler(BaseHandler):
    def get(self, questionId):
        self.init(questionId=questionId)    
        ok = self.checkRequirements(userRequired=True, questionRequired=True, activeQuestionRequired=False, questionId=questionId)
        templateValues = self.getDefaultTemplateValues()
        templateValues["start_url"] = self.getStartUrl() if ok and not self.question.cascade_complete else ""
        
        # TODO/FIX: Would like to add Admin button to all pages for system admins but
        # what to check if users.get_current_user() returns value if google user authenticated
        # in browser or only if authenticated in QA
        # if user logged in to page is not admin
        # check if authenticated user is admin (since some questions allow non-authenticated users)
#         sentFromAdminPage = self.request.referer and "/admin" in self.request.referer        
#         if not templateValues["admin"] and sentFromAdminPage and not self.person.authenticated_user_id:
#             authenticatedPerson = Person.getPerson(self.dbConnection)
#             templateValues["admin"] = Person.isAdmin(authenticatedPerson)
        
        path = os.path.join(os.path.dirname(__file__), '../html/results.html')
        self.response.out.write(template.render(path, templateValues))        
        self.destroy()

class Results2PageHandler(BaseHandler):
    def get(self, questionId):
        self.init(questionId=questionId)    
        ok = self.checkRequirements(userRequired=True, questionRequired=True, activeQuestionRequired=False, questionId=questionId)
        templateValues = self.getDefaultTemplateValues()
        templateValues["start_url"] = self.getStartUrl() if ok and not self.question.cascade_complete else ""        
        path = os.path.join(os.path.dirname(__file__), '../html/results2.html')
        self.response.out.write(template.render(path, templateValues))        
        self.destroy()
                
class ResultsTestPageHandler(BaseHandler):
    def get(self, questionId):
        self.init(questionId=questionId)    
        self.checkRequirements(userRequired=True, questionRequired=True, activeQuestionRequired=False, questionId=questionId)
        templateValues = self.getDefaultTemplateValues()
        path = os.path.join(os.path.dirname(__file__), '../html/results-keshif.html')
        self.response.out.write(template.render(path, templateValues))        
        self.destroy()
        
class AdminPageHandler(BaseHandler):
    def get(self, questionId=None):
        self.init(adminRequired=True, questionId=questionId)
        self.checkRequirements(authenticatedUserRequired=True, optionalQuestionCode=True, editPrivilegesRequired=True, questionId=questionId)
        templateValues = self.getDefaultTemplateValues(adminConnect=True)
        templateValues['system_admin'] = json.dumps(True) if self.isAdminLoggedIn() else json.dumps(False) 
        path = os.path.join(os.path.dirname(__file__), '../html/admin.html')
        self.response.out.write(template.render(path, templateValues))        
        self.destroy()

class StartPageHandler(BaseHandler):
    def get(self, questionId=None):
        self.init(adminRequired=True, questionId=questionId)
        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, editPrivilegesRequired=True, questionId=questionId)        
        templateValues = self.getDefaultTemplateValues(adminConnect=True)
        templateValues["start_url"] = self.getStartUrl() if ok else ""
        path = os.path.join(os.path.dirname(__file__), '../html/start.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()

class ReviewPageHandler(BaseHandler):
    def get(self, reviewId, reviewerId):
        self.init(initUser=False) 
        templateValues = self.getDefaultTemplateValues(connect=False)
        templateValues["review_id"] = reviewId
        templateValues["reviewer_id"] = reviewerId
        templateValues["user_login"] = "Reviewer {0}".format(reviewerId)
        templateValues['login_logout_linktext'] = None
        templateValues['login_logout_url'] = None  
        path = os.path.join(os.path.dirname(__file__), '../html/review.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
        
class WebLogPageHandler(BaseHandler):
    def get(self, questionId=None):
        self.init()
        ok = self.checkRequirements(authenticatedUserRequired=True)
        templateValues = self.getDefaultTemplateValues(adminConnect=True)
        path = os.path.join(os.path.dirname(__file__), '../html/weblog.html')
        self.response.out.write(template.render(path, templateValues))
        self.destroy()
                               
#####################
# Action Handlers
#####################

class LoginHandler(BaseHandler):    
    # called after successful Google authentication
    def get(self, questionId=None):
        self.init(initUser=False, questionId=questionId)
        page = self.request.get("page")

        self.person = Person.getPerson(self.dbConnection, question=self.question, session=self.session)  
        if not self.person:
            self.person = Person.create(self.dbConnection, question=self.question, session=self.session)
        elif not self.person.is_logged_in:
            self.person.login(self.dbConnection, question=self.question, session=self.session)
        
        self.destroy()
        self.redirect(str(page) if page else (getIdeaPageUrl(self.question) if self.question else getHomePageUrl()))
                
class NicknameLoginHandler(BaseHandler):    
    def post(self):
        self.init(initUser=False)
        nickname = self.request.get("nickname")
        page = self.request.get("page")
        specialChars = set('$\'"*,')

        ok = self.checkRequirements(questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
            
        elif self.question.authentication_type != constants.NICKNAME_AUTHENTICATION:
            data = { "status" : 0, "msg" : "This question does not allow nickname authentication" }
    
        elif not nickname:
            data = { "status" : 0, "msg" : "" }
        
        elif any((c in specialChars) for c in nickname):
                data = { "status" : 0, "msg" : "Nickname can not contain {0}".format("".join(specialChars)) }                
        
        else:
            self.person = Person.getPerson(self.dbConnection, question=self.question, session=self.session)
            
            # check if someone is already logged in with same nickname
            if self.isUserLoggedIn():
                data = { "status" : 0, "msg" : "Someone is already logged in as {0}".format(nickname) }
                
            else:
                if not self.person:
                    self.person = Person.create(self.dbConnection, question=self.question, nickname=nickname, session=self.session)
                elif not self.person.is_logged_in:
                    self.person.login(self.dbConnection, question=self.question, session=self.session)

                data = { "status" : 1, "url" : str(page) if page else (getIdeaPageUrl(self.question) if self.question else getHomePageUrl()) }

        self.writeResponseAsJson(data)       
        self.destroy()

class QuestionLoginHandler(BaseHandler):
    # log user in to question
    # if user not logged in yet, return url to login
    # otherwise, return url to start adding ideas
    def post(self):
        self.init()
        ok = self.checkRequirements(questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
               
        else:
            if self.person is not None and not self.person.is_logged_in:
                self.person.login(self.dbConnection, question=self.question, session=self.session)
                            
            data = {
                "status" : 1, 
                "question" : self.question.toDict(), 
                "url" : getIdeaPageUrl(self.question) if self.person is not None else getLoginUrl(getIdeaPageUrl(self.question), self.question) 
            }
        
        self.writeResponseAsJson(data)
        self.destroy()
                     
class LogoutHandler(BaseHandler):
    def get(self, questionId=None):
        sentFromAdminPage = self.request.referer and "/admin" in self.request.referer
        self.init(adminRequired=sentFromAdminPage, questionId=questionId)
        ok = self.checkRequirements(userRequired=True)
        if ok:
            self.person.logout(self.dbConnection, userRequestedLogout=True)
            
            if self.person.authenticated_user_id is not None:
                sendMessageToUser(self.dbConnection, None, self.person, { "op" : "logout" }, sendToAllAuthenticatedInstances=True)

            if self.session.is_active():
                self.session.terminate(True)
                self.session.clear()
                self.session.regenerate_id()
        self.destroy()
                
        # redirect depending on whether logged in as Google user or via nickname
        self.redirect(users.create_logout_url("/") if self.person is not None and self.person.authenticated_user_id else "/")
                    
class NicknameHandler(BaseHandler):
    def post(self, questionId=None):
        self.init(questionId=questionId)
        clientId = self.request.get("client_id")
        nickname = self.request.get("nickname")
        specialChars = set('$\'"*,')
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True, questionId=questionId)        
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }

        elif not nickname or len(nickname) == 0:
            data = { "status" : 0, "msg" : "Empty nickname not allowed" }
            
        # check if nickname has changed
        elif self.person.nickname == nickname:
            data = { "status" : 0, "msg" : "" }
    
        elif any((c in specialChars) for c in nickname):
            data = { "status" : 0, "msg" : "Nickname can not contain " + "".join(specialChars) }
                
        elif self.question.authentication_type != constants.NO_AUTHENTICATION and Person.doesNicknameExist(self.dbConnection, self.question.id, nickname):
            data = { "status" : 0, "msg" : "Nickname already exists (" + nickname + ")" }
                            
        else:
            self.person.update(self.dbConnection, { "nickname" : nickname, "id" : self.person.id })           
            data = { "status" : 1, "question_id": self.question.id, "authentication_type": self.question.authentication_type, "user" : self.person.toDict() }
            message = {
                "op": "nickname",
                "user": self.person.toDict()
            }
            sendMessage(self.dbConnection, clientId, self.question, message)      
        
        self.writeResponseAsJson(data)
        self.destroy()
                           
class QueryHandler(BaseHandler):
    def get(self):
        request = self.request.get("request", None)
        adminQueries = ("questions", "stats")
        data = {}

        if request:
            self.init(adminRequired=request in adminQueries)
            
            # questions created by user or possibly all if requested by admin
            if request == "questions":
                includeAll = self.request.get("include_all", "0")  == "1" if Person.isAdmin(self.person) else False
                questions = Question.getByUser(self.dbConnection, includeAll)     
                data = { "questions": questions }
                        
            # stats for question (# ideas, cascade stats if complete, etc.)
            elif request == "stats" and self.question:
                data = self.question.getQuestionStats(self.dbConnection)
                                
            # ideas for question (grouped if categories exist; otherwise returned as uncategorized)
            elif request == "ideas" and self.question:
                groupBy = self.request.get("group_by", None)
                if groupBy == "category":
                    useTestCategories = self.request.get("test", "0") == "1"
                    categorizedIdeas, uncategorizedIdeas, numIdeas = Idea.getByCategories(self.dbConnection, self.question, self.person, includeAlsoIn=True, useTestCategories=useTestCategories)
                    data = { "question": self.question.toDict(), "categorized": categorizedIdeas, "uncategorized": uncategorizedIdeas, "count" : numIdeas }        
                else:
                    ideas = Idea.getByQuestion(self.dbConnection, self.question, self.person)
                    data = { "question": self.question.toDict(), "ideas": ideas }
                
                includeDiscussFlags = self.request.get("discuss", "0") == "1"  
                isAuthor = self.isAuthorLoggedIn()
                isAdmin = self.isAdminLoggedIn()  
                if includeDiscussFlags:
                    data["discuss_flags"] = DiscussFlag.getFlags(self.dbConnection, self.question, admin=(isAuthor or isAdmin))
                    
                data["is_question_author"] = isAuthor

        self.writeResponseAsJson(data)
        
class NewQuestionHandler(BaseHandler):
    def post(self):
        self.init()
        title = self.request.get('title')
        questionText = self.request.get('question')
        authenticationType = self.request.get('authentication_type', str(constants.GOOGLE_AUTHENTICATION))
        clientId = self.request.get('client_id')

        ok = self.checkRequirements(authenticatedUserRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        elif len(title) < 4 or len(questionText) < 4:
            data = { "status" : 0, "msg" : "Title and question must must be at least 4 characters" }
                     
        else:
            self.question = Question.create(self.dbConnection, self.person.id, title, questionText, authenticationType)
            data = { "status": 1, "question": self.question.toDict() }

        self.writeResponseAsJson(data)
        self.destroy()

class EditQuestionHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True);
        title = self.request.get('title')
        questionText = self.request.get('question')
        authenticationType = self.request.get('authentication_type', str(constants.GOOGLE_AUTHENTICATION))
        clientId = self.request.get('client_id')
        
        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, activeQuestionRequired=False, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        elif len(title) < 4 or len(questionText) < 4:
            data = { "status" : 0, "msg" : "Title and question must must be at least 4 characters" }

        else:            
            properties = {
                "title" : title,
                "question" : questionText,
                "authentication_type" : authenticationType,
                "id" : self.question.id
            }
            self.question.update(self.dbConnection, properties)            
            data = { "status": 1, "question": self.question.toDict() }
            #sendMessage(self.dbConnection, clientId, self.question, { "op": "editquestion" })
            
        self.writeResponseAsJson(data)
        self.destroy()


class CopyQuestionHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True)
        clientId = self.request.get('client_id')
        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        else:
            new_question = Question.copy(self.dbConnection, self.question)
            data = { "status": 1, "new_question": new_question.toDict() }

        self.writeResponseAsJson(data)
        self.destroy()
                    
class DeleteQuestionHandler(BaseHandler):
    def post(self):
        self.init(adminRequired=True)
        clientId = self.request.get('client_id')
        dataOnly = self.request.get('data_only', False)
        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, activeQuestionRequired=False, editPrivilegesRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
        
        else:
            self.question.delete(self.dbConnection, dataOnly=dataOnly, onDeleteStudents=onDeleteStudents)
            data = { "status" : 1, "question" : self.question.toDict() if dataOnly else {} }                
            sendMessage(self.dbConnection, clientId, self.question, { "op": "delete" })
            
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
            
            stats = self.question.getQuestionStats(self.dbConnection)
            cascadeStats = stats["cascade_stats"] 
            avgResponseTime = round(cascadeStats["avg_response_time"]) if "avg_response_time" in cascadeStats else None
            avgResponseTimeFormatted = str(datetime.timedelta(seconds=avgResponseTime)) if avgResponseTime else "-"
            estProcessTime = cascadeStats["total_duration"]-avgResponseTime if "total_duration" in cascadeStats and "avg_response_time" in cascadeStats else None
            estProcessTimeFormatted = str(datetime.timedelta(seconds=estProcessTime)) if estProcessTime else "-"
            totalDuration = cascadeStats["total_duration"] if "total_duration" in cascadeStats else None
            totalDurationFormatted = str(datetime.timedelta(seconds=totalDuration)) if totalDuration else "-"
              
            # write out ideas with categories
            if self.question.cascade_complete:
                categorizedIdeas, uncategorizedIdeas, numIdeas = Idea.getByCategories(self.dbConnection, self.question, self.person, includeCreatedOn=True)

                # write out stats                
                excelWriter.writerow(("Statistics",))
                excelWriter.writerow(("# users", max(stats["idea_user_count"], cascadeStats["cascade_user_count"])))
                excelWriter.writerow(("# ideas", stats["idea_count"]))
                excelWriter.writerow(("# categories", cascadeStats["category_count"]))
                excelWriter.writerow(("# uncategorized", len(uncategorizedIdeas)))
                excelWriter.writerow(())
                excelWriter.writerow(("Average response time", avgResponseTimeFormatted, "(h:mm:ss)"))
                excelWriter.writerow(("Estimated process time", estProcessTimeFormatted, "(h:mm:ss)"))
                excelWriter.writerow(("Total duration", totalDurationFormatted, "(h:mm:ss)"))
                excelWriter.writerow(())
                                
                # write out cascade parameters
                excelWriter.writerow(("Cascade Settings",))
                excelWriter.writerow(("k", self.question.cascade_k))
                excelWriter.writerow(("k2", self.question.cascade_k2))
                excelWriter.writerow(("m", self.question.cascade_m))
                excelWriter.writerow(("p", self.question.cascade_p))
                excelWriter.writerow(("s", self.question.cascade_s))
                excelWriter.writerow(("t", self.question.cascade_t))
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
                excelWriter.writerow(("Counts",))
                excelWriter.writerow(("# users", stats["idea_user_count"]))
                excelWriter.writerow(("# ideas", stats["idea_count"]))
                excelWriter.writerow(())   
                    
                headers = (
                    "Idea",
                    "Author",
                    "Author_Identity",
                    "Created_On",
                    "Idea_Id"
                )
                excelWriter.writerow(headers)
        
                ideas = Idea.getByQuestion(self.dbConnection, self.question, self.person, includeCreatedOn=True)
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
                author = {
                    "id" : self.person.id,
                    "nickname" : self.person.nickname, 
                    "authenticated_nickname" : self.person.authenticated_nickname 
                }
                msg = { "op": "newidea", "idea": idea.toDict(author=author) }
                adminMsg = { "op": "newidea", "idea": idea.toDict(author=author, admin=True) }
                sendMessage(self.dbConnection, None, self.question, msg, adminMsg)
                data = { "status" : 1 }
        
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
            sendMessage(self.dbConnection, clientId, self.question, { "op" : "enable" if active == 1 else "disable" })

        self.writeResponseAsJson(data)            
        self.destroy()
                            
class CascadeJobHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        job = self.request.get("job")
        waiting = self.request.get("waiting")
        discuss = self.request.get("discuss")
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else:
            # queue the request to save and get a new cascade job
            # (requests will timeout if not responded to within roughly 30 seconds, 
            # but taskqueues do not have this time deadline)
            # check status of taskqueues at https://code.google.com/status/appengine since sometimes they run slow 
            taskqueue.add(url="/cascade_save_and_get_next_job", params ={ "question_id": self.question.id, "client_id": clientId, "user_id": self.person.id, "admin": "1" if self.isAdminLoggedIn() else "0", "job": job, "waiting": waiting, "discuss": discuss })
            data = { "status" : 1 }
                
        self.writeResponseAsJson(data)
        self.destroy()
        
class CascadeSaveAndGetNextJobHandler(webapp2.RequestHandler):
    def post(self):
        # this handler is called by the taskqueue
        # since it is called by the taskqueue, and not a user, it can not access things like the current user
        # information such as the current user must be passed into the job
        # question_id, user_id, and admin are passed as request parameters not by parsing clientId (which should be the same)

        clientId = self.request.get("client_id")
        questionId = self.request.get("question_id")
        personId = self.request.get("user_id")
        isAdmin = self.request.get("admin", "0") == "1"
                        
        dbConnection = DatabaseConnection()
        dbConnection.connect()
                            
        question = Question.getById(dbConnection, questionId)
        person = Person.getById(dbConnection, personId)
            
        ok = question is not None and person is not None 
        if ok:          
            # save job (if any)
            jobToSave = helpers.fromJson(self.request.get("job", None))
            if jobToSave:
                question.saveCascadeJob(dbConnection, jobToSave, person)
                # if cascade complete, notify any waiting clients that categories are ready
                if question.cascade_complete:
                    stats = question.getCascadeStats(dbConnection)
                    sendMessage(dbConnection, None, question, { "op": "categories", "question_id": question.id, "cascade_stats" : stats })

            if not question.cascade_complete:
                job = question.getCascadeJob(dbConnection, person)
                jobDict = { "tasks" : [task.toDict() for task in job["tasks"]], "type" : job["type"] } if job else None
                if jobDict and "categories" in job:
                    jobDict["categories"] = job["categories"]
        
                discuss = self.request.get("discuss", "0") == "1"
                if jobDict and discuss:
                    discussIdeas = []
                    jobDict["discuss_flags"] = []
                    for task in job["tasks"]:
                        if hasattr(task, "idea_id"):
                            if task.idea_id not in discussIdeas:
                                jobDict["discuss_flags"].extend(DiscussFlag.getFlags(dbConnection, question, ideaId=task.idea_id, admin=isAdmin))
                            discussIdeas.append(task.idea_id)
                
                sendMessageToClient(clientId, { "op": "job", "question_id" : question.id, "job": jobDict })
    
                waiting = self.request.get("waiting", "0") == "1"
                if job and waiting:
                    Person.working(dbConnection, clientId)
                        
                if not job:
                    Person.waiting(dbConnection, clientId)
                                
        dbConnection.disconnect()
                
class CancelCascadeJobHandler(BaseHandler):
    def post(self):
        self.init()
        job = helpers.fromJson(self.request.get("job", None))
        if self.question and job:
            count = self.question.unassignCascadeJob(self.dbConnection, job)
            if count > 0:
                # notify users who are waiting that more jobs are available
                onMoreJobs(self.question, self.dbConnection)

        self.writeResponseAsJson({ "status" : 1 })
        self.destroy()

class ReviewInitHandler(BaseHandler):
    def post(self):
        self.init()
        reviewId = int(self.request.get("review_id", -1))
        reviewerId = int(self.request.get("reviewer_id", -1))
        warning = None

        if reviewId == -1:
            data = { "status": 0, "msg": "Unknown review" }
               
        elif reviewerId == -1:
            data = { "status": 0, "msg": "Unknown reviewer" }
             
        else:  
            reviewGroup = Review.getReviewGroup(self.dbConnection, reviewId)
            reviewerIdValid = False
            if len(reviewGroup) > 0:
                reviewCount = reviewGroup[0]["review_count"]
                reviewerIdValid = reviewerId >=1 and reviewerId <= reviewCount
                    
            if len(reviewGroup) == 0:
                data = { "status": 0, "msg": "Review not found" }
            
            elif not reviewerIdValid:
                data = { "status": 0, "msg": "Reviewer not valid" }
                    
            else:
                # create jobs for *all* reviewers if not done yet
                self.dbConnection.cursor.execute("select count(*) as ct from fit_reviews where review_id=%s", (reviewId))
                row = self.dbConnection.cursor.fetchone()
                if row["ct"] == 0:            
                    Review.createJobs(self.dbConnection, reviewGroup)
                    
                stats = Review.getStats(self.dbConnection, reviewId, reviewerId)
                data = { "status": 1, "stats": stats }
        
        self.writeResponseAsJson(data)
        self.destroy()
        
class ReviewJobHandler(BaseHandler):
    def post(self):
        self.init()
        reviewId = int(self.request.get("review_id", -1))
        reviewerId = int(self.request.get("reviewer_id", -1))

        if reviewId == -1:
            data = { "status": 0, "msg": "Unknown review" }
               
        elif reviewerId == -1:
            data = { "status": 0, "msg": "Unknown reviewer" }
             
        else:
            job = None    
            currentQuestionId = None
                         
            # save job and then get new job for same question (if any)
            jobToSave = helpers.fromJson(self.request.get("job", None))
            if jobToSave:
                Review.saveJob(self.dbConnection, jobToSave, reviewerId)
                job = Review.getJob(self.dbConnection, reviewId, reviewerId, jobToSave["question_id"])
                        
            # if no new job yet, get job for current question (if any)
            if not job:
                currentQuestionId = Review.getCurrentQuestionId(self.dbConnection, reviewId, reviewerId)
                job = Review.getJob(self.dbConnection, reviewId, reviewerId, currentQuestionId)
               
            jobDict = { "question_id": job["question_id"], "tasks": [task.toDict() for task in job["tasks"]], "type": job["type"] } if job else None
            savedJobDict = { "question_id": jobToSave["question_id"], "task_count": len(jobToSave["tasks"]), "type": jobToSave["type"] }  if jobToSave else None
            data = { "status": 1, "review_id": reviewId, "reviewer_id": reviewerId, "job": jobDict, "saved_job": savedJobDict }
                
        self.writeResponseAsJson(data)
        self.destroy()

class LoadReviewResultsHandler(BaseHandler):
    def post(self):
        self.init()
        reviewId = int(self.request.get("review_id", -1))
        reviewerId = int(self.request.get("reviewer_id", -1))

        ok = self.checkRequirements(questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
            
        elif reviewId == -1:
            data = { "status": 0, "msg": "Unknown review" }
               
        elif reviewerId == -1:
            data = { "status": 0, "msg": "Unknown reviewer" }
             
        else:
            results = {}
            sql = "select * from fit_reviews,question_ideas where fit_reviews.question_id=question_ideas.question_id and fit_reviews.idea_id=question_ideas.id and fit_reviews.question_id=%s and review_id=%s and reviewer_id=%s order by category,idea"
            self.dbConnection.cursor.execute(sql, (self.question.id, reviewId, reviewerId))
            rows = self.dbConnection.cursor.fetchall()
            for row in rows:
                category = row["category"]
                if category not in results:
                    results[category] = { "ideas": [], "group_rating": -1 }
                results[category]["ideas"].append({ "idea_id": row["idea_id"], "idea": row["idea"], "rating": row["fit_rating"] })

            sql = "select * from group_reviews where question_id=%s and review_id=%s and reviewer_id=%s order by category"
            self.dbConnection.cursor.execute(sql, (self.question.id, reviewId, reviewerId))
            rows = self.dbConnection.cursor.fetchall()
            for row in rows:
                category = row["category"]
                if category in results:
                    results[category]["rating"] = row["group_rating"]
                     
            data = { "status": 1, "results": results }
                
        self.writeResponseAsJson(data)
        self.destroy()
           
class CategoryHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else:
            stats = GenerateCascadeHierarchy(self.dbConnection, self.question, forced=True)
            self.question.unassignIncompleteCascadeJobs(self.dbConnection)
            self.question.clearWaiting(self.dbConnection)            
            sendMessage(self.dbConnection, None, self.question, { "op": "categories", "question_id" : self.question.id, "cascade_stats" : stats })  
            data = { "status" : 1, "question_id" : self.question.id, "cascade_stats" : stats }
                
        self.writeResponseAsJson(data)
        self.destroy()

class TestCategoryHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else:
            stats = GenerateCascadeHierarchy(self.dbConnection, self.question, forced=True, forTesting=True)          
            data = { "status" : 1, "question_id" : self.question.id, "cascade_stats" : stats }
                
        self.writeResponseAsJson(data)
        self.destroy()

class DiscussIdeaHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        ideaId = int(self.request.get("idea_id"))
        addIdeaToDiscuss = self.request.get("add", "1") == "1"
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else: 
            if addIdeaToDiscuss: 
                flag = DiscussFlag.create(self.dbConnection, self.question, ideaId, self.person, admin=self.isAdminLoggedIn())     
            else:
                flag = DiscussFlag.delete(self.dbConnection, self.question, ideaId, self.person, admin=self.isAdminLoggedIn())            

            op = "discuss_idea" if addIdeaToDiscuss else "remove_discuss_idea"
            msg = { "op": op, "flag": flag.toDict(admin=False, person=self.person) }
            adminMsg = { "op": op, "flag": flag.toDict(admin=True, person=self.person) }
            sendMessage(self.dbConnection, clientId, self.question, msg, adminMsg)
            data = { "status" : 1, "flag" : flag.toDict() }
        
        self.writeResponseAsJson(data)
        self.destroy()        

class LoadWebLogHandler(BaseHandler):
    def post(self):
        self.init()
        ok = self.checkRequirements(authenticatedUserRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
            
        elif ok and not Person.isAdmin(self.person):
            data = { "status" : 0, "msg" : "Admin not logged in" }
            
        else:
            log = []
            req_log = None
            i = 0
            count = 20
            offset = self.request.get("offset", None)
            if offset:
                offset = base64.urlsafe_b64decode(str(offset))
            for req_log in logservice.fetch(offset=offset, version_ids=["dev", "13", "14"]):
                # TODO/FIX: only return cascade and idea requests for now
                if not req_log.resource.startswith("/cascade") and not req_log.resource.startswith("/idea"):
                    continue
                        
                reqLogData = {}
                reqLogData["timestamp"] = datetime.datetime.fromtimestamp(req_log.end_time).strftime('%D %T UTC')
                reqLogData["ip"] = req_log.ip
                reqLogData["method"] = req_log.method
                reqLogData["resource"] = req_log.resource
                reqLogData["start_time"] = req_log.start_time
                reqLogData["end_time"] = req_log.end_time
                reqLogData["latency"] = req_log.latency
                reqLogData["pending_time"] = req_log.pending_time
                reqLogData["was_loading_request"] = req_log.was_loading_request
                reqLogData["status"] = req_log.status
#                 reqLogData["app_log"] = []
                i += 1
    
#                 for app_log in req_log.app_logs:
#                     appLogData = {}
#                     appLogData["timestamp"] = datetime.datetime.fromtimestamp(app_log.time).strftime('%D %T UTC')
#                     appLogData["message"] = app_log.message
#                     reqLogData["app_log"].append(appLogData)
    
                log.append(reqLogData)
    
                if i >= count:
                    break
                
            data = { "status" : 1, "log" : log, "offset" : base64.urlsafe_b64encode(req_log.offset) if req_log and req_log.offset else None }
             
        self.writeResponseAsJson(data)
        self.destroy() 
                                              
#####################
# Channel support
#####################
          
class ChannelConnectedHandler(webapp2.RequestHandler):
    # Notified when clients connect
    def post(self):
        clientId = self.request.get("from")
        questionId, personId, isAdmin = getInfoFromClient(clientId)
        dbConnection = DatabaseConnection()
        dbConnection.connect()
        person = Person.getById(dbConnection, personId)
        if person:
            person.addClient(dbConnection, clientId) 
        dbConnection.disconnect()   
            
class ChannelDisconnectedHandler(webapp2.RequestHandler):
    # Notified when clients disconnect
    def post(self):
        clientId = self.request.get("from")
        questionId, personId, isAdmin = getInfoFromClient(clientId)
        dbConnection = DatabaseConnection()
        dbConnection.connect()
        person = Person.getById(dbConnection, personId)
        if person:
            numClients = person.removeClient(dbConnection, clientId, returnNumClients=True)
            if numClients == 0 and person.is_logged_in:
                person.logout(dbConnection, userRequestedLogout=False)
        dbConnection.disconnect()

def createChannel(question, person):
    clientId = str(random.randint(1000000000000, 10000000000000))
    clientId += "_" + (str(question.id) if question else constants.EMPTY_CLIENT_TOKEN)
    clientId += "_" + (str(person.id) if person else constants.EMPTY_CLIENT_TOKEN)
    # question authors are marked with a "_a" in the clientId
    if question is not None and Person.isAuthor(question):
        clientId += "_a"                                     
    token = channel.create_channel(clientId)
    return clientId, token

def getInfoFromClient(clientId):
    tokens = clientId.split("_")
    questionId = tokens[1] if len(tokens) >= 3 and tokens[1] != constants.EMPTY_CLIENT_TOKEN else None
    personId = tokens[2] if len(tokens) >= 3 and tokens[2] != constants.EMPTY_CLIENT_TOKEN else None
    isAdmin = "a" in tokens[3] if len(tokens) >= 4 else False
    return (questionId, personId, isAdmin)

def sendMessage(dbConnection, fromClientId, question, message, adminMessage=None):
    """Send message to all listeners (except self if fromClientId specified) to this topic"""
    if question:
        # send messages to both question users and question author (which may not be logged in to question explicitly)
        sql = "select client_id from user_clients,users where users.id=user_clients.user_id and ((question_id={0} and client_id like '%\_{0}\_%') or users.id={1})".format(question.id, question.user_id)
        dbConnection.cursor.execute(sql)
        rows = dbConnection.cursor.fetchall()
        for row in rows:
            toClientId = row["client_id"]
            toMessage = message
            if not fromClientId or toClientId != fromClientId:
                if adminMessage:
                    clientQuestionId, clientPersonId, clientIsAdmin = getInfoFromClient(toClientId)
                    if clientIsAdmin or clientPersonId==question.user_id:
                        toMessage = adminMessage
                channel.send_message(toClientId, json.dumps(toMessage))
            
def sendMessageToUser(dbConnection, fromClientId, person, message, sendToAllAuthenticatedInstances=False):
    if sendToAllAuthenticatedInstances and person.authenticated_user_id is not None:
        sql = "select client_id from user_clients, users where user_clients.user_id=users.id and authenticated_user_id=%s"
        dbConnection.cursor.execute(sql, (person.authenticated_user_id))
    else:
        sql = "select client_id from user_clients where user_id=%s"
        dbConnection.cursor.execute(sql, (person.id))
        
    rows = dbConnection.cursor.fetchall()
    for row in rows:
        toClientId = row["client_id"]
        if not fromClientId or toClientId != fromClientId:
            channel.send_message(toClientId, json.dumps(message))

def sendMessageToAdmin(dbConnection, questionId, message):
    sql = "select client_id from user_clients,questions where questions.user_id=user_clients.user_id and questions.id=%s"
    dbConnection.cursor.execute(sql, (questionId))    
    rows = dbConnection.cursor.fetchall()
    for row in rows:
        toClientId = row["client_id"]
        channel.send_message(toClientId, json.dumps(message))
        
def sendMessageToClient(clientId, message):
    channel.send_message(clientId, json.dumps(message))
                            
def onCreatePerson(person, dbConnection):
    if person and person.question_id:
        sendMessageToAdmin(dbConnection, person.question_id, { "op": "student_login", "question_id" : person.question_id, "user": person.toDict(), "is_new" : True })
    
def onLoginPerson(person, dbConnection):
    if person and person.question_id:
        sendMessageToAdmin(dbConnection, person.question_id, { "op": "student_login", "question_id" : person.question_id, "user": person.toDict(), "is_new" : False })

def onLogoutPerson(person, dbConnection):
    if person and person.question_id:
        sendMessageToAdmin(dbConnection, person.question_id, { "op": "student_logout", "question_id" : person.question_id, "user": person.toDict() })

Person.onCreate = onCreatePerson
Person.onLogin = onLoginPerson
Person.onLogout = onLogoutPerson

def onDeleteStudents(dbConnection, questionId):
    sql = "select client_id, user_id from users,user_clients where users.id=user_clients.user_id and question_id=%s"
    dbConnection.cursor.execute(sql, (questionId))    
    rows = dbConnection.cursor.fetchall()
    for row in rows:
        toClientId = row["client_id"]
        message =  { "op": "logout", "question_id" : questionId }
        channel.send_message(toClientId, json.dumps(message))

def onMoreJobs(question, dbConnection, moreFitJobs=0, moreVerifyJobs=0):
    # notify waiting clients about more jobs
    # only mark as working again if job assigned to them (after they request one)
    sql = "select * from users,user_clients where users.id=user_clients.user_id and question_id=%s and waiting_since is not null order by waiting_since desc"
    dbConnection.cursor.execute(sql, (question.id))
    rows = dbConnection.cursor.fetchall()
    for row in rows:
        clientId = row["client_id"]
        sendMessageToClient(clientId, { "op": "morejobs", "question_id": question.id })

    if moreFitJobs > 0 or moreVerifyJobs > 0:
        sendMessageToAdmin(dbConnection, question.id, { "op": "morejobs", "question_id": question.id, "fit_count": moreFitJobs, "verify_count": moreVerifyJobs } )
    
def onNewCategory(question, dbConnection, category):
    sendMessageToAdmin(dbConnection, question.id, { "op": "newcategory", "question_id": question.id } )

def onFitComplete(question, dbConnection, count):
    if count > 0:
        sendMessageToAdmin(dbConnection, question.id, { "op": "fitcomplete", "question_id": question.id, "count": count } )
    
def onVerifyComplete(question, dbConnection, count):
    if count > 0:
        sendMessageToAdmin(dbConnection, question.id, { "op": "verifycomplete", "question_id": question.id, "count": count } )
            
Question.onMoreJobs = onMoreJobs
Question.onNewCategory = onNewCategory
Question.onFitComplete = onFitComplete
Question.onVerifyComplete = onVerifyComplete
          
#####################
# URL routines
#####################

def getLoginUrl(page, question=None):
    url = None
    if question:
        if question.authentication_type == constants.NICKNAME_AUTHENTICATION:
            url = "/nickname_page/" + str(question.id)
          
        elif question.authentication_type == constants.GOOGLE_AUTHENTICATION:
            page = page if page else getIdeaPageUrl(question)
            url = users.create_login_url("/login/" + str(question.id) + "?page=" + urllib.quote(page))
    else:
        page = page if page else getHomePageUrl()
        url = users.create_login_url("/login?page=" + urllib.quote(page))

    return url

def getLogoutUrl(question=None):
    url = "/logout"
    url += "/" + str(question.id) if question else ""
    return url
  
def getHomePageUrl():
    return "/"
            
def getIdeaPageUrl(question=None, short=False):
    if short and question:
        url = "/" + str(question.id)       
    else:
        url = "/idea"
        url += "/" + str(question.id) if question else ""
    return url

def getCascadePageUrl(question=None):
    url = "/cascade"
    url += "/" + str(question.id) if question else ""
    return url

def getResultsPageUrl(question=None):
    url = "/results"
    url += "/" + str(question.id) if question else ""
    return url