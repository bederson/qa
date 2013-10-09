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
import urllib
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
    def init(self, initUser=True, adminRequired=False, initSession=True, loggingOut=False):                    
        # Get the current browser session, if any
        # Otherwise, create one
        self.session = gaesessions.get_current_session()
        if initSession and self.session.sid is None:
            self.session.start()
                    
        # Google recommends that a new connection be created to service each HTTP request, 
        # and re-used for the duration of that request (since the time to create a new connection is 
        # similar to that required to test the liveness of an existing connection).
        # https://developers.google.com/cloud-sql/faq#connections
        self.dbConnection = DatabaseConnection()
        self.dbConnection.connect()
        
        self.question = None
        questionId = self.request.get("question_id")
        if questionId:
            self.question = Question.getById(self.dbConnection, questionId)

        self.person = None
        if initUser:
            self.initUserContext(adminRequired=adminRequired, loggingOut=loggingOut)
                            
    def destroy(self):
        if self.dbConnection:
            self.dbConnection.disconnect()
                
    def initUserContext(self, adminRequired=False, loggingOut=False):
        nickname = self.request.get("nickname", None)
        question = self.question
        
        # if question allows nickname authentication and nickname not provided,
        # check if stored in session
        if question is not None and question.nickname_authentication and not nickname:
            questionValues = self.session.get(question.id) if self.session.has_key(question.id) else None
            nickname = questionValues["nickname"] if questionValues else None

        # force check for authenticated Google user not affiliated with a specific question
        if adminRequired:
            question = None
            nickname = None
            
        # get person, and update login status if needed
        self.person = Person.getPerson(self.dbConnection, question, nickname)

        # only allow nickname authenticated user to login to one session
        if self.person is not None and nickname is not None and self.person.session_sid is not None and self.person.session_sid != self.session.sid:
            self.person = None
        
        if self.person is not None and not self.person.is_logged_in:
            self.person.login(self.dbConnection)
                    
    def isUserLoggedIn(self):
        return self.person is not None and self.person.is_logged_in
    
    def isAdminLoggedIn(self):
        return Person.isAdmin() or (self.question is not None and Person.isAuthor(self.question))
    
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
            nicknameAuthenticationAllowed = self.question is not None and self.question.nickname_authentication and not Person.isAuthor(self.question)
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
            template_values["cascade_complete"] = self.question.cascade_complete
                
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
            self.session['msg'] = "Question inactive"
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
        templateValues["change_nickname_allowed"] = json.dumps(self.person is not None and self.person.authenticated_user_id is not None)
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

class ResultsTestPageHandler(BaseHandler):
    def get(self):
        self.init()    
        self.checkRequirements(userRequired=True, questionRequired=True, activeQuestionRequired=False)
        templateValues = self.getDefaultTemplateValues()
        path = os.path.join(os.path.dirname(__file__), '../html/results-keshif.html')
        self.response.out.write(template.render(path, templateValues))        
        self.destroy()
        
class AdminPageHandler(BaseHandler):
    def get(self):
        self.init(adminRequired=True)
        self.checkRequirements(authenticatedUserRequired=True, optionalQuestionCode=True, editPrivilegesRequired=True)
        # set question to None so not used when creating channel client id
        # but if one passed in, it has already been checked for validity
        self.question = None
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
        elif not self.person.is_logged_in:
            self.person.login(self.dbConnection)
        
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
                elif not self.person.is_logged_in:
                    self.person.login(self.dbConnection)

                self.session[self.question.id] = { "nickname": nickname }
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
                self.person.login(self.dbConnection)
                            
            data = {
                "status" : 1, 
                "question" : self.question.toDict(), 
                "url" : getIdeaPageUrl(self.question) if self.person is not None else getLoginUrl(getIdeaPageUrl(self.question), self.question) 
            }
        
        self.writeResponseAsJson(data)
        self.destroy()
                     
class LogoutHandler(BaseHandler):
    def get(self):
        self.init(loggingOut=True)
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
            
            # questions created by user
            if request == "questions":
                questions = Question.getByUser(self.dbConnection)                                            
                data = { "questions": questions }
                        
            # stats for question (# ideas, cascade stats if complete, etc.)
            elif request == "stats" and self.question:
                data = self.question.getQuestionStats(self.dbConnection)
                                
            # ideas for question (grouped if categories exist; otherwise returned as uncategorized)
            elif request == "ideas" and self.question:
                groupBy = self.request.get("group_by", None)
                if groupBy == "category":
                    useTestCategories = self.request.get("test", "0") == "1"
                    categorizedIdeas, uncategorizedIdeas, numIdeas = Idea.getByCategories(self.dbConnection, self.question, includeAlsoIn=True, useTestCategories=useTestCategories)
                    data = { "question": self.question.toDict(), "categorized": categorizedIdeas, "uncategorized": uncategorizedIdeas, "count" : numIdeas }        
                else:
                    ideas = Idea.getByQuestion(self.dbConnection, self.question, asDict=True)
                    data = { "question": self.question.toDict(), "ideas": ideas }

            # for testing Keshif
            elif request == "ideas_test" and self.question:      
                ideaData = []      
                sql = "select id, user_id, idea from question_ideas where question_id=%s order by id"
                self.dbConnection.cursor.execute(sql, (self.question.id))
                rows = self.dbConnection.cursor.fetchall()
                headerRow = ["id", "user_id", "idea"]
                ideaData.append(headerRow)
                for row in rows:
                    dataRow = [ row[colHeader] for colHeader in headerRow ]
                    ideaData.append(dataRow)
               
                userData = []      
                sql = "select id, authenticated_nickname, nickname from users where question_id=%s order by id"
                self.dbConnection.cursor.execute(sql, (self.question.id))
                rows = self.dbConnection.cursor.fetchall()
                headerRow = ["id", "authenticated_nickname", "nickname"]
                userData.append(headerRow)
                for row in rows:
                    dataRow = [ row[colHeader] for colHeader in headerRow ]
                    userData.append(dataRow)
                
                # TODO/FIX: only works if k2=1
                fitData = []      
                sql = "select user_id, idea_id, category from cascade_fit_categories_phase1 where question_id=%s and fit=1 order by id"
                self.dbConnection.cursor.execute(sql, (self.question.id))
                rows = self.dbConnection.cursor.fetchall()
                headerRow = ["user_id", "idea_id", "category"]
                fitData.append(headerRow)
                for row in rows:
                    dataRow = [ row[colHeader] for colHeader in headerRow ]
                    fitData.append(dataRow)  
                    
                data = { "question": self.question.toDict(), "ideas" : ideaData, "users" : userData, "fits" : fitData }

        self.writeResponseAsJson(data)

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
        
        elif len(title) < 4 or len(questionText) < 4:
            data = { "status" : 0, "msg" : "Title and question must must be at least 4 characters" }
                     
        else:
            self.question = Question.create(self.dbConnection, self.person.id, title, questionText, nicknameAuthentication)
            data = { "status": 1, "question": self.question.toDict() }
            #sendMessage(self.dbConnection, clientId, self.question, { "op" : "newquestion" })

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
        
        elif len(title) < 4 or len(questionText) < 4:
            data = { "status" : 0, "msg" : "Title and question must must be at least 4 characters" }

        else:            
            properties = {
                "title" : title,
                "question" : questionText,
                "nickname_authentication" : nicknameAuthentication,
                "id" : self.question.id
            }
            self.question.update(self.dbConnection, properties)            
            data = { "status": 1, "question": self.question.toDict() }
            #sendMessage(self.dbConnection, clientId, self.question, { "op": "editquestion" })
            
        self.writeResponseAsJson(data)
        self.destroy()


class CopyQuestionHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get('client_id')

        ok = self.checkRequirements(authenticatedUserRequired=True, questionRequired=True, editPrivilegesRequired=True)
        if ok:
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
            totalDuration = cascadeStats["total_duration"]  
            totalDurationFormatted = str(datetime.timedelta(seconds=totalDuration)) if totalDuration else "-"
              
            # write out ideas with categories
            if self.question.cascade_complete:
                categorizedIdeas, uncategorizedIdeas, numIdeas = Idea.getByCategories(self.dbConnection, self.question, includeCreatedOn=True)

                # write out stats                
                excelWriter.writerow(("Statistics",))
                excelWriter.writerow(("# users", stats["user_count"]))
                excelWriter.writerow(("# ideas", stats["idea_count"]))
                excelWriter.writerow(("# categories", cascadeStats["category_count"]))
                excelWriter.writerow(("# uncategorized", len(uncategorizedIdeas)))
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
                excelWriter.writerow(("# users", stats["user_count"]))
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
            filename = "xparty_question_{0}_as_of_{1}.txt".format(self.question.id, (datetime.datetime.now()-utcOffset).strftime("%Y%m%d-%H%M%S"))
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
                    "nickname" : self.person.nickname, 
                    "authenticated_nickname" : self.person.authenticated_nickname if not self.question.nickname_authentication else None 
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
                
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else:
            # queue the request to save and get a new cascade job
            # (requests will timeout if not responded to within roughly 30 seconds, 
            #  but added to a taskqueue do not have this time deadline)
            taskqueue.add(url="/cascade_save_and_get_next_job", params ={ "question_id": self.question.id, "client_id": clientId, "job": job, "waiting": waiting })
            data = { "status" : 1 }
                
        self.writeResponseAsJson(data)
        self.destroy()
        
class CascadeSaveAndGetNextJobHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        waiting = self.request.get("waiting", "0") == "1"

        # get person
        questionId, personId, isAdmin = getInfoFromClient(clientId)
        person = Person.getById(self.dbConnection, personId)
            
        # userRequired=True does not seem to work within taskqueue so cannot check
        ok = self.checkRequirements(questionRequired=True) and person is not None        
        if ok:          
            # save job (if any)
            jobToSave = helpers.fromJson(self.request.get("job", None))
            if jobToSave:
                self.question.saveCascadeJob(self.dbConnection, jobToSave, person)
                # if cascade complete, notify any waiting clients that categories are ready
                if self.question.cascade_complete:
                    stats = self.question.getCascadeStats(self.dbConnection)
                    sendMessage(self.dbConnection, None, self.question, { "op": "categories", "question_id": self.question.id, "cascade_stats" : stats })
          
            job = self.question.getCascadeJob(self.dbConnection, person)
            sendMessageToClient(clientId, { "op": "job", "question_id" : self.question.id, "job": { "tasks" : [task.toDict() for task in job["tasks"]], "type" : job["type"] } if job else None })
            
            if job and waiting:
                Person.working(self.dbConnection, clientId)
                
            if not job:
                Person.waiting(self.dbConnection, clientId)
                
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
   
class CategoryHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else:
            stats = GenerateCascadeHierarchy(self.dbConnection, self.question)
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
            stats = GenerateCascadeHierarchy(self.dbConnection, self.question, forTesting=True)          
            data = { "status" : 1, "question_id" : self.question.id, "cascade_stats" : stats }
                
        self.writeResponseAsJson(data)
        self.destroy()

class DiscussIdeaHandler(BaseHandler):
    def post(self):
        self.init()
        clientId = self.request.get("client_id")
        ideaId = self.request.get("idea_id")
        
        ok = self.checkRequirements(userRequired=True, questionRequired=True)
        if not ok:
            data = { "status" : 0, "msg" : self.session.pop("msg") }
             
        else:
            idea = Idea.getById(self.dbConnection, ideaId)
            count = idea.flagToDiscuss(self.dbConnection)          
            data = { "status" : 1, "count" : count }
                
        self.writeResponseAsJson(data)
        self.destroy()                                          
#####################
# Channel support
#####################
          
class ChannelConnectedHandler(BaseHandler):
    # Notified when clients connect
    def post(self):
        self.init(initUser=False, initSession=False)
        clientId = self.request.get("from")
        questionId, personId, isAdmin = getInfoFromClient(clientId)
        person = Person.getById(self.dbConnection, personId)
        if person:
            person.addClient(self.dbConnection, clientId) 
        self.destroy()   
            
class ChannelDisconnectedHandler(BaseHandler):
    # Notified when clients disconnect
    def post(self):
        self.init(initUser=False, initSession=False)
        clientId = self.request.get("from")
        questionId, personId, isAdmin = getInfoFromClient(clientId)
        person = Person.getById(self.dbConnection, personId)
        if person:
            numClients = person.removeClient(self.dbConnection, clientId, returnNumClients=True)
            if numClients == 0 and person.is_logged_in:
                person.logout(self.dbConnection, userRequestedLogout=False)
        self.destroy()

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

def onMoreJobs(question, dbConnection):
    # notify waiting clients about more jobs
    # only mark as working again if job assigned to them (after they request one)
    sql = "select * from users,user_clients where users.id=user_clients.user_id and question_id=%s and waiting_since is not null order by waiting_since desc"
    dbConnection.cursor.execute(sql, (question.id))
    rows = dbConnection.cursor.fetchall()
    for row in rows:
        clientId = row["client_id"]
        sendMessageToClient(clientId, { "op": "morejobs", "question_id": question.id })

def onCascadeSettingsChanged(question, dbConnection):
    sendMessageToAdmin(dbConnection, question.id, { "op": "cascadesettings", "question_id": question.id, "cascade_k": question.cascade_k, "cascade_k2": question.cascade_k2, "cascade_m": "50%", "cascade_s" : question.cascade_s, "cascade_t": question.cascade_t } )
    
def onNewCategory(question, dbConnection, category):
    sendMessageToAdmin(dbConnection, question.id, { "op": "newcategory", "question_id": question.id } )

def onFitComplete(question, dbConnection, count):
    sendMessageToAdmin(dbConnection, question.id, { "op": "fitcomplete", "question_id": question.id, "count": count } )
    
Question.onCascadeSettingsChanged = onCascadeSettingsChanged    
Question.onMoreJobs = onMoreJobs
Question.onNewCategory = onNewCategory
Question.onFitComplete = onFitComplete
          
#####################
# URL routines
#####################

def getLoginUrl(page, question=None):
    if question:
        if question.nickname_authentication:
            url = "/nickname_page?question_id=" + str(question.id)            
        else:
            page = page if page else getIdeaPageUrl(question)
            url = users.create_login_url("/login?page=" + urllib.quote(page) + "&question_id=" + str(question.id))
    else:
        page = page if page else getHomePageUrl()
        url = users.create_login_url("/login?page=" + urllib.quote(page))

    return url

def getLogoutUrl(question=None):
    url = "/logout"
    if question:
        url += "?question_id=" + str(question.id)
    return url
  
def getHomePageUrl():
    return "/"

def getIdeaPageUrl(question=None):
    url = "/idea"
    if question:
        url += "?question_id=" + str(question.id)
    return url

def getCascadePageUrl(question=None):
    url = "/cascade"
    if question:
        url += "?question_id=" + str(question.id)
    return url

def getResultsPageUrl(question=None):
    url = "/results"
    if question:
        url += "?question_id=" + str(question.id)
    return url