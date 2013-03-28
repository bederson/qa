#!/usr/bin/env python
#
# Copyright 2013 Ben Bederson - http://www.cs.umd.edu/~bederson
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
import webapp2
import json
import logging
import random
import string
import StringIO
import csv
import time
import webapp2
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
PHASE_TAG_BY_SIMILARITY = 4

def get_default_template_values(requestHandler, person, question):
    """Return a dictionary of template values used for login template"""        
    
    client_id = None
    token = None
    user_login = None
    
    if person:            
        client_id, token = connect(person)
        url = users.create_logout_url("/logout") if person.user else "/logout"
        url_linktext = 'Logout'
        logged_in = "true"
        user_login = person.user if not question or not question.nicknameAuthentication else person.nickname

    else:
        if question and question.nicknameAuthentication:
            url = "/loginpage?question_id="+question.code
            url_linktext = "Login w/ Nickname"
        else:
            url = "/login?page="+requestHandler.request.uri
            if question:
                url += "&question_id="+question.code
            url = users.create_login_url(url)
            url_linktext = 'Login w/ Google Account'
        logged_in = "false"

    session = gaesessions.get_current_session()
    msg = session.pop("msg") if session.has_key("msg") else ""
        
    template_values = {
        'client_id': client_id,
        'token': token,
        'user_login': user_login if user_login else "",
        'user_nickname': person.nickname if person else "",
        'url': url,
        'url_linktext': url_linktext,
        'logged_in': logged_in,
        'admin': Person.isAdmin(requestHandler) or (question and person and person.user and question.author == person.user),
        'msg': msg
    }
    return template_values

#####################
# Channel support
#####################
def connect(person):
    """User has connected, so remember that"""
    client_id = str(random.randint(1000000000000, 10000000000000)) + "_" + str(person.key().id())
    token = channel.create_channel(client_id)
    return client_id, token

# Check: is question_id needed since person_id can be parsed from client_id and question is associated with person
def send_message(client_id, question_id, message):
    """Send message to all listeners (except self) to this topic"""
    questionObj = Question.getQuestionById(question_id)
    if questionObj:
        others = Person.all()
        others = others.filter("question = ", questionObj)
        others = others.filter("client_id !=", client_id)
        for person in others:
            for client_id in person.client_ids:
                channel.send_message(client_id, json.dumps(message))

#####################
# Page Handlers
#####################

class BaseHandler(webapp2.RequestHandler):
    def initUserContext(self, admin=False, create=False):
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
           
        # if admin, force check for authenticated user not affiliated with any specific question
        if admin:
            question = None
            nickname = None
        
        # check if person_key stored in session
        # if so use to retrieve logged in user 
        session = gaesessions.get_current_session()
        person_key = session.pop("person_key") if session.has_key("person_key") else None
        person = Person.getPerson(question, nickname, person_key)
                    
        # if no person found
        # create person if create is true, OR,
        # create person if question requires login authentication and person already logged in
        user = users.get_current_user()
        if not person and (create or (question and not question.nicknameAuthentication and user)):            
            person = Person.createPerson(question, nickname)
            # store person_key in session so new person can be retrieved from the datastore
            session["person_key"] = person.key().id()

        return person        

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
        template_values["phase"] = Question.getPhase(question_id)
        if questionObj:
            template_values["title"] = questionObj.title
            template_values["question"] = questionObj.question
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
        phase = Question.getPhase(question_id)
        template_values["phase"] = phase
        if phase == PHASE_TAG_BY_CLUSTER:
            template_values["cluster_id"] = ClusterAssignment.getAssignmentId(question_id)
        elif phase == PHASE_TAG_BY_NOTE:
            template_values["idea_id"] = IdeaAssignment.getCurrentAssignmentId(question_id)
            if questionObj:
                template_values["num_notes_to_tag"] = questionObj.getNumNotesToTagPerPerson()
                template_values["num_notes_tagged"] = questionObj.getNumNotesTaggedByUser()
        elif phase == PHASE_TAG_BY_SIMILARITY:
            # xx NOT COMPLETE
            if questionObj:
                template_values["num_notes_to_compare"] = questionObj.getNumNotesToComparePerPerson()
                template_values["num_notes_compared"] = questionObj.getNumNotesComparedByUser()

        path = os.path.join(os.path.dirname(__file__), '../html/tag.html')
        self.response.out.write(template.render(path, template_values))

class ResultsPageHandler(BaseHandler):
    def get(self):
        person = self.initUserContext()
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        template_values = get_default_template_values(self, person, questionObj)
        template_values["phase"] = Question.getPhase(question_id)
        if questionObj:
            template_values["title"] = questionObj.title
            template_values["question"] = questionObj.question

        path = os.path.join(os.path.dirname(__file__), '../html/results.html')
        self.response.out.write(template.render(path, template_values))

class AdminPageHandler(BaseHandler):
    def get(self):
        person = self.initUserContext(admin=True)
        questionObj = None
        
        # check if question_key
        # newly created questions may not be searchable by question_id immediately
        # but they should be retrievable with a question_key
        question_key = self.request.get("question_key")
        if question_key:
            questionObj = Question.get_by_id(long(question_key))
            
        question_id = self.request.get("question_id")
        if question_id and not questionObj:
            questionObj = Question.getQuestionById(question_id)
        
        # check if user logged in
        if not person or not person.user:
            self.redirectWithMsg("Please login")
            return
            
        # check if valid question code
        if (question_id or question_key) and not questionObj:
            self.redirectWithMsg("Invalid question code", "/admin")
            return
        
        # check if question owned by logged in user
        if questionObj and not Person.isAdmin(self) and questionObj.author != users.get_current_user():
            self.redirectWithMsg("You are not allowed to edit this question", "/admin")
            return 

        template_values = get_default_template_values(self, person, questionObj)        
        if questionObj:
            template_values["phase"] = questionObj.phase
            template_values["title"] = questionObj.title
            template_values["question"] = questionObj.question
            template_values["num_notes_to_tag_per_person"] = questionObj.numNotesToTagPerPerson
            template_values["num_notes_to_compare_per_person"] = questionObj.numNotesToComparePerPerson
            template_values["num_ideas"] = Idea.numIdeas(question_id)
            template_values["num_tags_by_cluster"] = questionObj.getNumTagsByCluster()
            template_values["num_tags_by_idea"] = questionObj.getNumTagsByIdea()

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
            template_values["title"] = questionObj.title
            template_values["question"] = questionObj.question
            template_values["phase"] = questionObj.phase
        path = os.path.join(os.path.dirname(__file__), '../html/login.html')
        self.response.out.write(template.render(path, template_values))
        
#####################
# Action Handlers
#####################

class LoginHandler(BaseHandler):
    def get(self):
        nickname = self.request.get("nickname")
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
        url = getPhaseUrl(person.question)
        self.redirect(url)

def getPhaseUrl(question=None):
    url = "/"
    if question:
        if question.phase <= PHASE_NOTES:
            url = "/idea?question_id="+question.code
        elif question.phase == PHASE_TAG_BY_CLUSTER or question.phase == PHASE_TAG_BY_NOTE:
            url = "/tag?question_id="+question.code
        elif question.phase == PHASE_TAG_BY_SIMILARITY:
            # xx NOT COMPLETE
            url = "/"
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
            
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data)) 
                           
class QueryHandler(BaseHandler):
    def get(self):
        self.initUserContext()
        request = self.request.get("request")
        question_id = self.request.get("question_id")

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
            data = {"phase": Question.getPhase(question_id)}
        elif request == "clustertags":
            tags = []
            for tagObj in ClusterTag.getTags(question_id):
                tag = cleanTag(tagObj.tag)
                cluster = tagObj.cluster
                if cluster:
                    item = {"tag": tag, "cluster": cluster.key().id(), "author": Person.toDict(tagObj.author)}
                    tags.append(item)
            data = {"tags": tags, "num_clusters": Cluster.numClusters(question_id)}
        elif request == "ideatags":
            tags = []
            for tagObj in IdeaTag.getTags(question_id):
                tag = cleanTag(tagObj.tag)
                idea = tagObj.idea
                if idea:
                    item = {"tag": tag, "idea_id": idea.key().id(), "author": Person.toDict(tagObj.author)}
                    tags.append(item)
            data = {"tags": tags}
        elif request == "myclustertags":
            tags = []
            for tag in ClusterTag.getTagsByUser(question_id):
                tags.append(tag.tag)
            data = {"tags": tags}
        elif request == "myideatags":
            tags = []
            idea_id = self.request.get("idea_id")
            for tag in IdeaTag.getTagsByUser(idea_id):
                tags.append(tag.tag)
            data = {"tags": tags}
        elif request == "question":
            questionObj = Question.getQuestionById(question_id)
            if questionObj:
                data = {
                    "title": questionObj.title,
                    "question": questionObj.question,
                    "nicknameAuthentication": questionObj.nicknameAuthentication,
                    "numTagsByCluster": questionObj.getNumTagsByCluster(),
                    "numTagsByIdea": questionObj.getNumTagsByIdea(),
                }
            else:
                data = {
                    "title": "", 
                    "question": "",
                    "nicknameAuthentication": False,
                    "msg": "Invalid code - it should be 5 digits"
                }
        elif request == "questions":
            questions = []
            for question in Question.getQuestionsByUser():
                questions.append({"title": question.title, "question": question.question, "nickname_authentication": question.nicknameAuthentication, "question_id": question.code})
            data = {"questions": questions}

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data))

class NewQuestionHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        title = self.request.get('title')
        question = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication') == "1" if True else False
        data = {}
        if len(title) >= 5 and len(question) >= 5:
            question = Question.createQuestion(title, question, nicknameAuthentication)
            if question:
                question_id = question.code
                question_key = question.key().id()
                # question_key was getting truncated somewhere so saved as string instead
                data = {"question_id": question_id, "question_key": str(question_key)}
                # Update clients
                message = {
                    "op": "newquestion"
                }
                send_message(client_id, question_id, message)        # Update other clients about this change

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data))

class EditQuestionHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        question_id = self.request.get("question_id")
        title = self.request.get('title')
        question = self.request.get('question')
        nicknameAuthentication = self.request.get('nickname_authentication') == "1" if True else False
        data = {}
        if len(title) >= 5 and len(question) >= 5:
            question_id = Question.editQuestion(question_id, title, question, nicknameAuthentication)
            data = {"question_id": question_id}

            # Update clients
            message = {
                "op": "newquestion"
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data))
                
class NewIdeaHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        idea = self.request.get('idea')
        question_id = self.request.get("question_id")
        if len(idea) >= 1:            # Don't limit idea length until there is a way to give feedback about short ideas
            ideaObj = Idea.createIdea(idea, question_id)

            # Update clients
            message = {
                "op": "newidea",
                "text": idea,
                "author": Person.toDict(ideaObj.author)
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class NewClusterTagHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        tag = self.request.get('tag')
        cluster_id = int(self.request.get('cluster_id'))
        question_id = self.request.get("question_id")
        if len(tag) >= 1:
            clusterTagObj = ClusterTag.createClusterTag(tag, cluster_id, question_id)

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
        self.initUserContext()
        client_id = self.request.get('client_id')
        tag = self.request.get('tag')
        idea_id = int(self.request.get('idea_id'))
        question_id = self.request.get("question_id")
        if len(tag) >= 1:
            ideaTagObj = IdeaTag.createIdeaTag(tag, idea_id, question_id)

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
        self.initUserContext()
        client_id = self.request.get('client_id')
        num_clusters = int(self.request.get('num_clusters'))
        question_id = self.request.get("question_id")
        data = doCluster(num_clusters, question_id)

        # Update clients
        message = {
            "op": "refresh"
        }
        send_message(client_id, question_id, message)        # Update other clients about this change

class IdeaAssignmentHandler(BaseHandler):
    def get(self):
        self.initUserContext()
        question_id = self.request.get("question_id")
        IdeaAssignment.getNewAssignmentId(question_id)

class PhaseHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        phase = int(self.request.get('phase'))
        question_id = self.request.get("question_id")
        Question.setPhase(phase, question_id)

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

class NumNotesToComparePerPersonHandler(BaseHandler):
    def post(self):
        self.initUserContext()
        client_id = self.request.get('client_id')
        num_notes_to_compare_per_person = int(self.request.get('num_notes_to_compare_per_person'))
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        if questionObj:
            questionObj.setNumNotesToComparePerPerson(num_notes_to_compare_per_person)

        message = {
            "op": "num_notes_to_compare_per_person",
            "num_notes_to_compare_per_person": num_notes_to_compare_per_person,
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

def doCluster(k, question_id):
    if k == 1:
        uncluster(question_id)
        return

    if k > Idea.all().count():
        return

    vectors, texts, phrases, ids = computeBagsOfWords(question_id)
    cl = KMeansClustering(vectors)
    clusters = cl.getclusters(k)

    # Delete existing clusters from database
    Cluster.deleteAllClusters(question_id)
    
    clusterNum = 0
    for cluster in clusters:
        clusterObj = Cluster.createCluster("Cluster #" + str(clusterNum + 1), clusterNum, question_id)
        entry = []
        if type(cluster) is tuple:
            # Cluster may only have a single tuple instead of a collection of them
            index = cluster[-1:][0]
            text = texts[index]
            phrase = phrases[index]
            idea_id = ids[index]
            Idea.assignCluster(idea_id, clusterObj)
        else:
            for vector in cluster:
                index = vector[-1:][0]
                text = texts[index]
                phrase = phrases[index]
                idea_id = ids[index]
                entry.append([text, phrase])
                Idea.assignCluster(idea_id, clusterObj)
        clusterNum += 1

    # Clean up any existing tags and cluster assignments since clusters have been reformed
    ClusterTag.deleteAllTags(question_id)
    ClusterAssignment.deleteAllClusterAssignments(question_id)

def uncluster(question_id):
    questionObj = Question.getQuestionById(question_id)
    if questionObj:
        Cluster.deleteAllClusters(question_id)
        ClusterTag.deleteAllTags(question_id)

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