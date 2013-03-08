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
from models import *
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from cluster import KMeansClustering
from webapp2_extras import sessions

STOP_WORDS = [ "all", "also", "and", "any", "been", "did", "for", "not", "had", "now", "she", "that", "the", "this", "was", "were" ]
PHASE_NOTES = 1
PHASE_TAG_BY_CLUSTER = 2
PHASE_TAG_BY_NOTE = 3


def get_default_template_values(requestHandler, question_id):
    """Return a dictionary of template values used for login template"""        

    client_id = None
    token = None
    question = Question.getQuestionById(question_id) if question_id is not None else None
    person = Person.getPerson(question=question)
    isLocalAdmin = users.get_current_user() and "http://localhost" in requestHandler.request.uri
    
    if question:
        nickname = None
        user = users.get_current_user()
        # FIX: need to check if user logged in via google or nickname
        if not person and (user or nickname):
            person = Person.getOrCreatePerson(question=question)
           
        if person:
            client_id, token = connect(person)
        
    if person:
        url = users.create_logout_url("/logout?page="+requestHandler.request.uri)
        url_linktext = 'Logout'
        logged_in = "true"
    else:
        url = users.create_login_url("/login?page="+requestHandler.request.uri)
        url_linktext = 'Login w/ Google Account'
        logged_in = "false"
    
    template_values = {
        'client_id': client_id,
        'token': token,
        'user': person.user if person is not None else "",
        'user_nickname': person.nickname if person is not None else "",
        'url': url,
        'url_linktext': url_linktext,
        'logged_in': logged_in,
        'admin': users.is_current_user_admin() or isLocalAdmin,
        'msg': requestHandler.session.pop("msg") if requestHandler.session.has_key("msg") else ""
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

class BasePageHandler(webapp2.RequestHandler):
    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)
        try:
            webapp2.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)
            
    @webapp2.cached_property
    def session(self):
        return self.session_store.get_session()
            
    def redirectWithMsg(self, msg=None, dst="/"):
        if msg is not None:
            self.session['msg'] = msg
        self.redirect(dst)
    
class MainPageHandler(BasePageHandler):
    def get(self):        
        template_values = get_default_template_values(self, None)
        
        path = os.path.join(os.path.dirname(__file__), '../html/main.html')
        self.response.out.write(template.render(path, template_values))
        
class IdeaPageHandler(BasePageHandler):
    def get(self):        
        question_id = self.request.get("question_id")
        template_values = get_default_template_values(self, question_id)
        template_values["phase"] = Question.getPhase(question_id)
        questionObj = Question.getQuestionById(question_id)
        if questionObj:
            template_values["title"] = questionObj.title
            template_values["question"] = questionObj.question

        path = os.path.join(os.path.dirname(__file__), '../html/idea.html')
        self.response.out.write(template.render(path, template_values))

# Participant page to enter new tags
class TagPageHandler(BasePageHandler):
    def get(self):
        question_id = self.request.get("question_id")
        template_values = get_default_template_values(self, question_id)
        phase = Question.getPhase(question_id)
        template_values["phase"] = phase
        if phase == PHASE_TAG_BY_CLUSTER:
            template_values["cluster_id"] = ClusterAssignment.getAssignmentId(question_id)
        elif phase == PHASE_TAG_BY_NOTE:
            template_values["idea_id"] = IdeaAssignment.getCurrentAssignmentId(question_id)
            questionObj = Question.getQuestionById(question_id)
            if questionObj:
                template_values["num_notes_to_tag"] = questionObj.getNumNotesToTagPerPerson()
                template_values["num_notes_tagged"] = questionObj.getNumNotesTaggedByUser()

        path = os.path.join(os.path.dirname(__file__), '../html/tag.html')
        self.response.out.write(template.render(path, template_values))

class ResultsPageHandler(BasePageHandler):
    def get(self):
        question_id = self.request.get("question_id")
        template_values = get_default_template_values(self, question_id)
        template_values["phase"] = Question.getPhase(question_id)
        questionObj = Question.getQuestionById(question_id)
        if questionObj:
            template_values["title"] = questionObj.title
            template_values["question"] = questionObj.question

        path = os.path.join(os.path.dirname(__file__), '../html/results.html')
        self.response.out.write(template.render(path, template_values))

class AdminPageHandler(BasePageHandler):
    def get(self):
        if not users.get_current_user():
            self.redirectWithMsg('Please login to access admin page');
            return
            
        question_id = self.request.get("question_id")
        template_values = get_default_template_values(self, None)
        if question_id:
            template_values["phase"] = Question.getPhase(question_id)
            questionObj = Question.getQuestionById(question_id)
            if questionObj:
                template_values["title"] = questionObj.title
                template_values["question"] = questionObj.question
                template_values["num_notes_to_tag_per_person"] = questionObj.numNotesToTagPerPerson
                template_values["num_ideas"] = Idea.numIdeas(question_id)
                template_values["num_tags_by_cluster"] = questionObj.getNumTagsByCluster()
                template_values["num_tags_by_idea"] = questionObj.getNumTagsByIdea()

        path = os.path.join(os.path.dirname(__file__), '../html/admin.html')
        self.response.out.write(template.render(path, template_values))

#####################
# Action Handlers
#####################
class LoginHandler(webapp2.RequestHandler):
    def get(self):
        nickname = self.request.get("nickname", None)
        question_id = self.request.get("question_id", None)
        question = Question.getQuestionById(question_id) if question_id is not None else None
        person = Person.getOrCreatePerson(nickname=nickname, question=question)         
        page = self.request.get("page", "/")
        self.redirect(str(page))

class LogoutHandler(webapp2.RequestHandler):
    def get(self):
        nickname = self.request.get("nickname", None)
        question_id = self.request.get("question_id", None)
        question = Question.getQuestionById(question_id) if question_id is not None else None
        person = Person.logoutPerson(nickname=nickname, question=question)  
        page = self.request.get("page", "/")
        self.redirect(str(page))

class NicknameHandler(webapp2.RequestHandler):
    def post(self):
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
            
            # TODO: update clients with user nickname
            # Update clients
            message ={
                "op": "nickname",
                "text": "",
                "author": Person.cleanNickname(person.user)
            }
            send_message(clientId, questionId, message)      # Update other clients about this change
            
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data)) 
                           
class QueryHandler(webapp2.RequestHandler):
    def get(self):
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
                    item = {"tag": tag, "cluster": cluster.key().id(), "author": tagObj.author.nickname}
                    tags.append(item)
            data = {"tags": tags, "num_clusters": Cluster.numClusters(question_id)}
        elif request == "ideatags":
            tags = []
            for tagObj in IdeaTag.getTags(question_id):
                tag = cleanTag(tagObj.tag)
                idea = tagObj.idea
                if idea:
                    item = {"tag": tag, "idea_id": idea.key().id(), "author": tagObj.author.nickname}
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
                    "numTagsByCluster": questionObj.getNumTagsByCluster(),
                    "numTagsByIdea": questionObj.getNumTagsByIdea(),
                }
            else:
                data = {
                    "title": "", 
                    "question": "", 
                    "msg": "Invalid code - it should be 5 digits"
                }
        elif request == "questions":
            questions = []
            for question in Question.getQuestionsByUser():
                questions.append({"title": question.title, "question": question.question, "question_id": question.code})
            data = {"questions": questions}

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data))

class NewQuestionHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        title = self.request.get('title')
        question = self.request.get('question')
        data = {}
        if len(title) >= 5 and len(question) >= 5:
            question = Question.createQuestion(title, question)
            if question:
                question_id = question.code
                data = {"question_id": question_id}
                # Update clients
                message = {
                    "op": "newquestion"
                }
                send_message(client_id, question_id, message)        # Update other clients about this change

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data))

class EditQuestionHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        title = self.request.get('title')
        question = self.request.get('question')
        question_id = self.request.get("question_id")
        data = {}
        if len(title) >= 5 and len(question) >= 5:
            question_id = Question.editQuestion(question_id, title, question)
            data = {"question_id": question_id}

            # Update clients
            message = {
                "op": "newquestion"
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(data))
                
class NewIdeaHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        idea = self.request.get('idea')
        question_id = self.request.get("question_id")
        if len(idea) >= 1:            # Don't limit idea length until there is a way to give feedback about short ideas
            Idea.createIdea(idea, question_id)

            # Update clients
            message = {
                "op": "newidea",
                "text": idea,
                "author": Person.cleanNickname(users.get_current_user())
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class NewClusterTagHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        tag = self.request.get('tag')
        cluster_id = int(self.request.get('cluster_id'))
        question_id = self.request.get("question_id")
        if len(tag) >= 1:
            ClusterTag.createClusterTag(tag, cluster_id, question_id)

            # Update clients
            message = {
                "op": "newtag",
                "tag": tag,
                "cluster_id": cluster_id,
                "author": Person.cleanNickname(users.get_current_user())
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class NewIdeaTagHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        tag = self.request.get('tag')
        idea_id = int(self.request.get('idea_id'))
        question_id = self.request.get("question_id")
        if len(tag) >= 1:
            IdeaTag.createIdeaTag(tag, idea_id, question_id)

            # Update clients
            message = {
                "op": "newtag",
                "tag": tag,
                "idea_id": idea_id,
                "author": Person.cleanNickname(users.get_current_user())
            }
            send_message(client_id, question_id, message)        # Update other clients about this change

class DeleteHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        question_id = self.request.get("question_id")
        Question.delete(question_id)

        # Update clients
        message = {
            "op": "delete"
        }
        send_message(client_id, question_id, message)        # Update other clients about this change

class ClusterHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        num_clusters = int(self.request.get('num_clusters'))
        question_id = self.request.get("question_id")
        data = doCluster(num_clusters, question_id)

        # Update clients
        message = {
            "op": "refresh"
        }
        send_message(client_id, question_id, message)        # Update other clients about this change

class IdeaAssignmentHandler(webapp2.RequestHandler):
    def get(self):
        question_id = self.request.get("question_id")
        IdeaAssignment.getNewAssignmentId(question_id)

class PhaseHandler(webapp2.RequestHandler):
    def post(self):
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

class NumNotesToTagPerPersonHandler(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('client_id')
        num_notes_to_tag_per_person = int(self.request.get('num_notes_to_tag_per_person'))
        question_id = self.request.get("question_id")
        questionObj = Question.getQuestionById(question_id)
        if questionObj:
            questionObj.setNumNotesToTagPerPerson(num_notes_to_tag_per_person)

        message = {
            "op": "num_notes_to_tag_per_person",
            "num_notes_to_tag_per_person": num_notes_to_tag_per_person
        }
        send_message(client_id, question_id, message)        # Update other clients about this change

class MigrateHandler(webapp2.RequestHandler):
    def get(self):
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
        # FRIDAY: check for client_id AND user id
        # FRIDAY: connect does not have users.get_current_user!!
        clientId = self.request.get("from")
        Person.addClientId(clientId)    
            
class DisconnectedHandler(webapp2.RequestHandler):
    # Notified when clients disconnect
    def post(self):
        clientId = self.request.get("from")
        Person.removeClientId(clientId)

#####################
# Text Support
#####################

def getIdea(ideaIdStr):
    ideaObj = Idea.getIdeaById(ideaIdStr)
    if ideaObj:
        idea = {
            "idea": ideaObj.text,
            "author": ideaObj.author.nickname
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
                "author": ideaObj.author.nickname
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
                "author": ideaObj.author.nickname
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
            "author": ideaObj.author.nickname
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