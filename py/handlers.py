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
import os
import json
import logging
import random
import string
import StringIO
import csv
import time
import collections
import webapp2
import helpers
from lib import gaesessions
from models import *
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from cluster import KMeansClustering

STOP_WORDS = [ "all", "also", "and", "any", "been", "did", "for", "not", "had", "now", "she", "that", "the", "this", "was", "were" ]
PHASE_NOTES = 1
PHASE_TAG_BY_CLUSTER = 2
PHASE_TAG_BY_NOTE = 3
PHASE_COMPARE_BY_SIMILARITY = 4

def get_default_template_values(requestHandler, person, question):
    """Return a dictionary of template values used for login template"""        
    
    page = requestHandler.request.path
    requiresGoogleAuthentication = page == "/admin" or not question or not question.nicknameAuthentication
    
    # user already logged in    
    if person:
        client_id, token = connect(person)
        #helpers.log("*** NEW CHANNEL CREATED ***")
        url_linktext = 'Logout'
        url = users.create_logout_url("/logout") if person.user else "/logout"
         
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
        template_values['user_login'] = person.user if requiresGoogleAuthentication else person.nickname
        template_values['user_nickname'] = person.nickname
        googleUser = users.get_current_user()
        template_values['admin'] = Person.isAdmin(requestHandler) or (googleUser and (not question or question.author == googleUser))

    if question:
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

# Check: is question_id needed since person_id can be parsed from client_id and question is associated with person
def send_message(from_client_id, question_id, message):
    """Send message to all listeners (except self) to this topic"""
    questionObj = Question.getQuestionById(question_id)
    if questionObj:
        users = Person.all().filter("question = ", questionObj)
        for person in users:
            for to_client_id in person.client_ids:
                if to_client_id != from_client_id:
                    channel.send_message(to_client_id, json.dumps(message))

#####################
# Page Handlers
#####################

class BaseHandler(webapp2.RequestHandler):
    def initUserContext(self, force_check=False, create=False):
        # Get the current browser session, if any
        # Otherwise, create one
        session = gaesessions.get_current_session()          
        if session.sid is None:
            session.start()
            
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)
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
        
        person = Person.getPerson(question, nickname)
        user = users.get_current_user()
                            
        # if no person found
        # create person if create is true, OR,
        # create person if question requires login authentication and person already logged in
        if not person and (create or (question and not question.nicknameAuthentication and user)):            
            person = Person.createPerson(question, nickname)

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
        person = self.initUserContext()       
        template_values = get_default_template_values(self, person, None)
        
        path = os.path.join(os.path.dirname(__file__), '../html/main.html')
        self.response.out.write(template.render(path, template_values))
        
class IdeaPageHandler(BaseHandler):
    def get(self):        
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        template_values = get_default_template_values(self, person, questionObj)
        if questionObj:
            template_values["change_nickname_allowed"] = json.dumps(not questionObj.nicknameAuthentication)

        path = os.path.join(os.path.dirname(__file__), '../html/idea.html')
        self.response.out.write(template.render(path, template_values))

# Participant page to enter new tags
class TagPageHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        template_values = get_default_template_values(self, person, questionObj)
        if questionObj:
            phase = Question.getPhase(questionObj)
            if phase == PHASE_TAG_BY_CLUSTER:
                template_values["cluster_id"] = ClusterAssignment.getAssignmentId(question_id, person)
            elif phase == PHASE_TAG_BY_NOTE:
                assignment = IdeaAssignment.getCurrentAssignment(questionObj, person)
                template_values["idea_id"] = assignment.idea.key().id() if assignment else -1
                if questionObj:
                    template_values["num_notes_to_tag"] = questionObj.getNumNotesToTagPerPerson()
                    template_values["num_notes_tagged"] = questionObj.getNumNotesTaggedByUser(person)

        path = os.path.join(os.path.dirname(__file__), '../html/tag.html')
        self.response.out.write(template.render(path, template_values))

# Participant page to compare similarity of notes
class SimilarPageHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        phase = Question.getPhase(questionObj)

        isComparePhase = phase == PHASE_COMPARE_BY_SIMILARITY and questionObj
        maxNumToCompare = questionObj.getNumNotesToComparePerPerson() if isComparePhase else 0
        numNotesForComparison = questionObj.getNumNotesForComparison() if isComparePhase else 0
        assignment = SimilarIdeaAssignment.getCurrentAssignment(questionObj, person) if isComparePhase else None

        if assignment and len(assignment.compareToKeys) < numNotesForComparison:
            assignment = None
                    
        template_values = get_default_template_values(self, person, questionObj)
        template_values["assignment"] = helpers.to_json(assignment.toDict() if assignment else None)
        template_values["num_notes_to_compare"] = maxNumToCompare
        template_values["num_notes_for_comparison"] = numNotesForComparison
        path = os.path.join(os.path.dirname(__file__), '../html/similar.html')
        self.response.out.write(template.render(path, template_values))
        
class ResultsPageHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        
        # if no person found, check if question author trying to view results page
        # if so, display page even if nickname authentication required
        isQuestionAuthor = False
        if not person:
            user = users.get_current_user()        
            isQuestionAuthor = questionObj and user and questionObj.author == user
            if isQuestionAuthor:
                person = Person.all().filter("question =", None).filter("user =", user).get()

        template_values = get_default_template_values(self, person, questionObj)
        if isQuestionAuthor and person:
            user_login = template_values["user_login"] = person.user
            
        path = os.path.join(os.path.dirname(__file__), '../html/results.html')
        self.response.out.write(template.render(path, template_values))

class AdminPageHandler(BaseHandler):
    def get(self):
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
            questionObj = Question.get_by_id(question_id)
            
        question_id = self.request.get("question_id")
        if question_id and not questionObj:
            questionObj = Question.getQuestionById(question_id)
        
        session = gaesessions.get_current_session()
        
        # check if user logged in
        if not person or not person.user:
            questionObj = None
            session['msg'] = "Please login"
            
        # check if valid question code
        elif question_id and not questionObj:
            session['msg'] = "Invalid question code"
        
        # check if question owned by logged in user
        elif questionObj and not Person.isAdmin(self) and questionObj.author != users.get_current_user():
            questionObj = None
            session['msg'] = "You do not have permission to edit this question"

        template_values = get_default_template_values(self, person, questionObj) 
        if questionObj:
            template_values["num_notes_to_tag_per_person"] = questionObj.numNotesToTagPerPerson
            template_values["num_notes_to_compare_per_person"] = questionObj.numNotesToComparePerPerson
            template_values["num_notes_for_comparison"] = questionObj.numNotesForComparison
            template_values["num_ideas"] = Idea.getNumIdeas(questionObj)
            template_values["num_tags_by_cluster"] = questionObj.getNumTagsByCluster()
            template_values["num_tags_by_idea"] = questionObj.getNumTagsByIdea()
            template_values["num_similar_ideas"] = questionObj.getNumSimilarIdeas()
            template_values["num_clusters"] = Cluster.numClusters(questionObj)

        path = os.path.join(os.path.dirname(__file__), '../html/admin.html')
        self.response.out.write(template.render(path, template_values))
        
class LoginPageHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()       
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        template_values = get_default_template_values(self, person, questionObj)
        if questionObj:
            template_values["question_id"] = questionObj.code
        path = os.path.join(os.path.dirname(__file__), '../html/login.html')
        self.response.out.write(template.render(path, template_values))
        
#####################
# Action Handlers
#####################

class LoginHandler(BaseHandler):
    def get(self):
        nickname = self.request.get("nickname")
        page = self.request.get("page")
        questionId = self.request.get("question_id")
        question = Question.getQuestionById(questionId)

        # if question allows nickname authentication
        # store nickname in session if ok
        if question:
            person = Person.getPerson(question, nickname)
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
        self.redirect(url)

def getPhaseUrl(question=None):
    url = "/"
    if question:
        if question.phase <= PHASE_NOTES:
            url = "/idea?question_id="+question.code
        elif question.phase == PHASE_TAG_BY_CLUSTER or question.phase == PHASE_TAG_BY_NOTE:
            url = "/tag?question_id="+question.code
        elif question.phase == PHASE_COMPARE_BY_SIMILARITY:
            url = "/similar?question_id="+question.code
    return url

class LogoutHandler(BaseHandler):
    def get(self):
        session = gaesessions.get_current_session()
        if session.is_active():
            session.terminate(True)
        self.redirect("/")

class NicknameHandler(BaseHandler):
    def post(self):
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
            
        elif Person.nicknameAlreadyExists(questionId, nickname):
            data["msg"] = "Nickname already exists (" + nickname + ")"
            
        else:
            person.setNickname(nickname)
            
            # Update clients
            message = {
                "op": "nickname",
                "text": "",
                "author": Person.toDict(person)
            }
            send_message(clientId, questionId, message)      # Update other clients about this change
        
        self.writeResponseAsJson(data)
                           
class QueryHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()
        request = self.request.get("request")
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)

        data = {}
        if request == "ideas":
            data = getIdeas(question_id)
        elif request == "ideasbycluster":
            cluster_id = self.request.get("cluster_id")
            data = getIdeasByCluster(int(cluster_id), question_id)
        elif request == "idea":
            idea_id = self.request.get("idea_id")
            data = getIdea(idea_id)
        elif request == "phase":
            data = {"phase": Question.getPhase(question)}
        elif request == "clustertags":
            tags = []
            for tagObj in ClusterTag.getTags(question_id):
                tag = cleanTag(tagObj.tag)
                cluster = tagObj.cluster
                if cluster:
                    item = {"tag": tag, "cluster": cluster.key().id(), "author": Person.toDict(tagObj.author)}
                    tags.append(item)
            data = {"tags": tags, "num_clusters": Cluster.numClusters(question) if question else 0}
        elif request == "ideatags":
            tags = []
            for tagObj in IdeaTag.getTags(question_id):
                tag = cleanTag(tagObj.tag)
                idea = tagObj.idea
                if idea:
                    item = {"tag": tag, "idea_id": idea.key().id(), "author": Person.toDict(tagObj.author)}
                    tags.append(item)
            data = {"tags": tags}
        elif request == "similarideas":
            ideas = [ idea.toDict() for idea in SimilarIdea.getAllSimilarIdeas(question) ]
            data = {"ideas": ideas}
        elif request == "myclustertags":
            tags = []
            for tag in ClusterTag.getTagsByUser(question_id, person):
                tags.append(tag.tag)
            data = {"tags": tags}
        elif request == "myideatags":
            tags = []
            idea_id = self.request.get("idea_id")
            user_tags = IdeaTag.getTagsByUser(idea_id, person)
            if user_tags:
                for tag in user_tags:
                    tags.append(tag.tag)
            data = {"tags": tags}
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
            for userQuestion in Question.getQuestionsByUser():
                userQuestions.append(userQuestion.toDict())
            data = {"questions": userQuestions}

        self.writeResponseAsJson(data)

class NewQuestionHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        client_id = self.request.get('client_id')
        title = self.request.get('title')
        questionText = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication') == "1" if True else False

        data = {}        
        if not person:
            data["status"] = 0
            data["msg"] = "Please log in"
        
        elif len(title) < 5 or len(questionText) < 5:
            data["status"] = 0
            data["msg"] = "Title and question must must be at least 5 characters"
                     
        else:
            question = Question.createQuestion(title, questionText, nicknameAuthentication)
            
            if not question:
                data["status"] = 0
                data["msg"] = "Error saving question"
                
            else:
                question_id = question.code
                session = gaesessions.get_current_session()
                session["new_question_key"] = question.key().id()
                
                data = {"status": 1, "question_id": question_id }
                # Update clients
                message = { "op": "newquestion" }
                send_message(client_id, question_id, message)        # Update other clients about this change

        self.writeResponseAsJson(data)

class EditQuestionHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        client_id = self.request.get('client_id')
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)
        title_text = self.request.get('title')
        question_text = self.request.get('question')

        nicknameAuthentication = self.request.get('nickname_authentication') == "1" if True else False
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
            send_message(client_id, question_id, message)        # Update other clients about this change

        self.writeResponseAsJson(data)
                
class NewIdeaHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        client_id = self.request.get('client_id')
        idea = self.request.get('idea')
        question_id = self.request.get("question_id")
        if len(idea) >= 1:            # Don't limit idea length until there is a way to give feedback about short ideas
            ideaObj = Idea.createIdea(idea, question_id, person)

            # Update clients
            message = {
                "op": "newidea",
                "text": idea,
                "author": Person.toDict(ideaObj.author)
            }
            send_message(client_id, question_id, message)        # Update other clients about this change
            
class NewClusterTagHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        client_id = self.request.get('client_id')
        tag = self.request.get('tag')
        cluster_id = int(self.request.get('cluster_id'))
        question_id = self.request.get("question_id")
        if len(tag) >= 1:
            clusterTagObj = ClusterTag.createClusterTag(tag, cluster_id, question_id, person)

            # Update clients
            message = {
                "op": "newtag",
                "tag": tag,
                "cluster_id": cluster_id,
                "author": Person.toDict(clusterTagObj.author)
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class NewIdeaTagHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        client_id = self.request.get('client_id')
        tag = self.request.get('tag')
        idea_id = int(self.request.get('idea_id'))
        question_id = self.request.get("question_id")
        if len(tag) >= 1:
            ideaTagObj = IdeaTag.createIdeaTag(tag, idea_id, question_id, person)

            # Update clients
            message = {
                "op": "newtag",
                "tag": tag,
                "idea_id": idea_id,
                "author": Person.toDict(ideaTagObj.author)
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class DeleteHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        question_id = self.request.get("question_id")
        Question.delete(question_id)

        # Update clients
        message = {
            "op": "delete"
        }
        send_message(client_id, question_id, message)        # Update other clients about this change

class ClusterHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        client_id = self.request.get("client_id")
        num_clusters = int(self.request.get("num_clusters"))
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)
        data = {}
        
        if not person:
            data["status"] = 0
            data["msg"] = "Please log in"
                 
        elif not question:
            data["status"] = 0
            data["msg"] = "Invalid question code"
           
        else: 
            data = doCluster(num_clusters, question)
            if data["status"] == 1:
                # Update clients
                message = {
                           "op": "refresh"
                }
                send_message(client_id, question_id, message)        # Update other clients about this change
            
        self.writeResponseAsJson(data)

class ClusterSimilarHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        client_id = self.request.get("client_id")
        num_clusters = int(self.request.get("num_clusters"))
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)
        data = {}
        
        if not person:
            data["status"] = 0
            data["msg"] = "Please log in"
                 
        elif not question:
            data["status"] = 0
            data["msg"] = "Invalid question code"
           
        else:       
            similarityDict = self.createSimilarityDict(question)
            if not similarityDict:
                data["status"] = 0
                data["msg"] = "Could not create clusters.  May need to compare more notes for similarity."
            
            else:
                clusters = self.clusterBySimilarity(similarityDict, num_clusters)
                # TODO: clusters not currently stored in database
               
                data["status"] = 1
                data["clusters"] = clusters
                # TODO: need to return unclustered items also
                
                # Update clients
                message = {
                    "op": "refresh"
                }
                send_message(client_id, question_id, message)        # Update other clients about this change
            
        self.writeResponseAsJson(data)
  
    def createSimilarityDict(self, question):
        # create dictionary with similarity counts
        # e.g., similarityDict[idea1_key][idea2_key] = <# users who said this pair of ideas was similar>
        # idea pairs that were never marked as similar are not contained in dictionary        
        similarityDict = collections.OrderedDict()                
        results = SimilarIdea.all().filter("question =", question)           
        for similarIdea in results:
            idea1 = similarIdea.idea
            idea2 = similarIdea.similar
            idea1_key = str(idea1.key().id())
            idea2_key = str(idea2.key().id())
                
            if idea1_key not in similarityDict:
                similarityDict[idea1_key] = {"idea": idea1.toDict()}
                    
            if idea2_key not in similarityDict:
                similarityDict[idea2_key] = {"idea": idea2.toDict()}
      
            if idea2_key not in similarityDict[idea1_key]:
                similarityDict[idea1_key][idea2_key] = 0
                    
            if idea1_key not in similarityDict[idea2_key]:
                similarityDict[idea2_key][idea1_key] = 0
                    
            similarityDict[idea1_key][idea2_key] += 1
            similarityDict[idea2_key][idea1_key] += 1
        
        return similarityDict
            
    def clusterBySimilarity(self, similarityDict, numClusters=5):
        # create two-dimensional vectors with similarity values (e.g., # of users who said items were the same)
        # cluster index appended to end of vector                    
        row = 0
        rowKeys = []
        similarityVectors = []
        for idea1_key in similarityDict:
            rowKeys.append(idea1_key)
            vector = []
            for idea2_key in similarityDict:
                # if idea1_key and idea2_key are equal, value is 1
                # if idea1 and idea2 were never marked as similar, value is 0
                # otherwise, value is # of user who marked idea1 and idea2 as similiar
                # TODO: for k-means clustering, what value should be used when idea1_key == idea2_key
                value = similarityDict[idea1_key][idea2_key] if idea2_key in similarityDict[idea1_key] else (1 if idea1_key == idea2_key else 0)
                flag = 1 if value > 0 else 0
                vector.append(flag)
                
            # FIX: Need better way to get idea index back from getclusters
            # vector.append(row)
            similarityVectors.append(tuple(vector))                    
            row += 1

        helpers.log("===================")
        for idea_key in similarityDict:
            helpers.log("{0}".format(similarityDict[idea_key]["idea"]["text"]))
        helpers.log("===================")
        helpers.log(similarityVectors)
        helpers.log("===================")
        cl = KMeansClustering(similarityVectors)
        clusterData = cl.getclusters(numClusters)
        clusters = clusterData["clusters"]
        clusteredIdeaIndices = clusterData["indices"]
        
        helpers.log(clusters)
        helpers.log("===================")
        helpers.log(clusteredIdeaIndices)
            
        ideaClusters = []
        clusterNum = 0
        for cluster in clusters:
            ideas = []
            if type(cluster) is tuple:
                # Cluster may only have a single tuple instead of a collection of them
                index = clusteredIdeaIndices[clusterNum][0]
                idea_key = rowKeys[index]
                idea = similarityDict[idea_key]["idea"]
                ideas.append(idea)
            else:
                j = 0
                for vector in cluster:
                    index = clusteredIdeaIndices[clusterNum][j]
                    idea_key = rowKeys[index]
                    idea = similarityDict[idea_key]["idea"]
                    ideas.append(idea)
                    j += 1
            ideaClusters.append(ideas)
            clusterNum += 1
        
        return ideaClusters
    
class IdeaAssignmentHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)
        IdeaAssignment.createNewAssignment(question, person)
        self.writeResponseAsJson({})

class SimilarIdeaHandler(BaseHandler):
    def post(self):
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)
        assignment_json = self.request.get("assignment")
        current_assignment = helpers.from_json(assignment_json) if assignment_json else None
        similar_to = self.request.get("similar_to")
        similar_to_index = int(similar_to) if similar_to and similar_to.isdigit() else None
        request_new_assignment = self.request.get("request_new", "0") == "1"
        data = {}              
        
        if not person:
            data["status"] = 0
            data["msg"] = "Please log in"
                 
        elif not question:
            data["status"] = 0
            data["msg"] = "Invalid question code"
        
        else:
            # save similar idea (if provided)
            if current_assignment and similar_to_index is not None:
                idea_id = long(current_assignment["idea"]["id"])
                compare_to_ideas = current_assignment["compare_to"]
                similar_idea_id = long(compare_to_ideas[similar_to_index]["id"])
                SimilarIdea.createSimilarIdea(idea_id, similar_idea_id, question, person)
            
            # get new assignment (if requested)
            new_assignment = None
            if request_new_assignment:
                new_assignment = SimilarIdeaAssignment.createNewAssignment(question, person)
            else:
                SimilarIdeaAssignment.unselectAllAssignments(question, person)
                      
            data["status"] = 1
            data["assignment"] = new_assignment.toDict() if new_assignment else None
    
        self.writeResponseAsJson(data)
        
class PhaseHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        phase = int(self.request.get('phase'))
        question_id = self.request.get("question_id")
        question = Question.getQuestionById(question_id)        
        if question:
            phase = Question.setPhase(phase, question)
    
            # Update clients
            message = {
                "op": "phase",
                "phase": phase
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class NumNotesToTagPerPersonHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        num_notes_to_tag_per_person = int(self.request.get('num_notes_to_tag_per_person'))
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        if questionObj:
            questionObj.setNumNotesToTagPerPerson(num_notes_to_tag_per_person)
            message = {
                "op": "num_notes_to_tag_per_person",
                "num_notes_to_tag_per_person": num_notes_to_tag_per_person,
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class CompareNotesOptionsHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        num_notes_to_compare_per_person = int(self.request.get('num_notes_to_compare_per_person'))
        num_notes_for_comparison = int(self.request.get('num_notes_for_comparison'))
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        if questionObj:
            questionObj.setCompareNotesOptions(num_notes_to_compare_per_person, num_notes_for_comparison)
            message = {
                "op": "compare_phase_options",
                "num_notes_to_compare_per_person": num_notes_to_compare_per_person,
                "num_notes_for_comparison": num_notes_for_comparison
            }
            send_message(client_id, question_id, message)        # Update other clients about this change
        
class MigrateHandler(BaseHandler):
    def get(self):
        self.initUserContext()
        for questionObj in Question.all():
            i = 0
            for ideaObj in Idea.all().filter("question =", questionObj):
                if i == 0:
                    ideaObj.rand = 1.0
                else:
                    ideaObj.rand = random.random()
                ideaObj.put()
                i += 1

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
    ideaObj = Idea.getIdeaById(ideaIdStr)
    if ideaObj:
        idea = {
            "idea": ideaObj.text,
            "author": Person.toDict(ideaObj.author)
        }
    else:
        idea = {}
    return idea

def getIdeas(questionIdStr):
    results = []
    questionObj = Question.getQuestionById(questionIdStr)
    if not questionObj:
        return results
    clusterObjs = Cluster.all().filter("question = ", questionObj).order("text")

    # Start with all the ideas that aren't in any cluster
    ideaObjs = Idea.all().filter("question = ", questionObj).filter("cluster =", None)
    if ideaObjs.count() > 0:
        entry = {"name": "Unclustered", "id": -1}
        ideas = []
        for ideaObj in ideaObjs:
            idea = {
                "idea": ideaObj.text,
                "idea_id": ideaObj.key().id(),
                "words": ideaObj.text.split(),
                "author": Person.toDict(ideaObj.author)
            }
            ideas.append(idea)
        entry["ideas"] = ideas
        results.append(entry)

    for clusterObj in clusterObjs:
        entry = {"name": clusterObj.text, "id": clusterObj.key().id()}
        ideaObjs = Idea.all().filter("cluster =", clusterObj)
        ideas = []
        for ideaObj in ideaObjs:
            idea = {
                "idea": ideaObj.text,
                "idea_id": ideaObj.key().id(),
                "words": ideaObj.text.split(),
                "author": Person.toDict(ideaObj.author)
            }
            ideas.append(idea)
        entry["ideas"] = ideas
        results.append(entry)
    return results

def getIdeasByCluster(cluster_id, questionIdStr):
    questionObj = Question.getQuestionById(questionIdStr)
    if not questionObj:
        return []

    clusterObj = Cluster.get_by_id(cluster_id)
    ideaObjs = Idea.all().filter("cluster =", clusterObj)
    ideas = []
    for ideaObj in ideaObjs:
        idea = {
            "idea": ideaObj.text,
            "words": ideaObj.text.split(),
            "author": Person.toDict(ideaObj.author)
        }
        ideas.append(idea)
    return ideas;

def doCluster(k, question):
    question_id = question.code if question else None
    if k == 1:
        uncluster(question)
        return { "status" : 1,  "num_clusters" : 0 }

    if k > Idea.all().filter("question = ", question).count():
        return { "status" : 0,  "msg" : "Not enough notes to create {0} clusters".format(k) }
    
    vectors, texts, phrases, ids = computeBagsOfWords(question_id)
    cl = KMeansClustering(vectors)
    clusterData = cl.getclusters(k)
    clusters = clusterData["clusters"]
    clusteredIdeaIndices = clusterData["indices"]

    # Delete existing clusters from database
    Cluster.deleteAllClusters(question)

    clusterNum = 0
    for cluster in clusters:
        clusterObj = Cluster.createCluster("Cluster #" + str(clusterNum + 1), clusterNum, question_id)
        entry = []
        if type(cluster) is tuple:
            # Cluster may only have a single tuple instead of a collection of them
            index = clusteredIdeaIndices[clusterNum][0]
            text = texts[index]
            phrase = phrases[index]
            idea_id = ids[index]
            Idea.assignCluster(idea_id, clusterObj)
        else:
            j = 0
            for vector in cluster:
                index = clusteredIdeaIndices[clusterNum][j]
                text = texts[index]
                phrase = phrases[index]
                idea_id = ids[index]
                entry.append([text, phrase])
                Idea.assignCluster(idea_id, clusterObj)
                j += 1
        clusterNum += 1

    # Clean up any existing tags and cluster assignments since clusters have been reformed
    ClusterTag.deleteAllTags(question)
    ClusterAssignment.deleteAllClusterAssignments(question)
    return { "status" : 1, "num_clusters" : clusterNum }

def uncluster(question):
    if question:
        Cluster.deleteAllClusters(question)
        ClusterTag.deleteAllTags(question)

def computeBagsOfWords(question_id):
    # First define vector by extracting every word
    all_words = set()
    phrases = []
    texts = []
    ids = []
    questionObj = Question.getQuestionById(question_id)
    if questionObj:
        ideas = Idea.all().filter("question = ", questionObj).order('__key__')
        for ideaObj in ideas:
            text = ideaObj.text
            texts.append(text)
            words = text.split()
            phrase = []
            for word in words:
                word = cleanWord(word)
                if len(word) > 2:
                    all_words.add(word)
                    phrase.append(word)
            phrases.append(phrase)
            ids.append(ideaObj.key().id())

    # Create an index for the words
    word_index = {}
    i = 0
    for word in all_words:
        word_index[word] = i
        i += 1

    # Then for each phrase, compute it's vector. Last element of vector is index
    vectors = []
    i = 0
    for phrase in phrases:
        vector = [0] * (len(word_index) + 1)
        for word in phrase:
            index = word_index[word]
            vector[index] += 1
        vector[len(word_index)] = i
        vectors.append(tuple(vector))
        i += 1

    return vectors, texts, phrases, ids

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
    return (word in STOP_WORDS)