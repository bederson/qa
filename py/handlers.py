#!/usr/bin/env python
#
# Copyright 2013 Ben Bederson - http://www.cs.umd.edu/~bederson
# University of Maryland
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#	  http://www.apache.org/licenses/LICENSE-2.0
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


def get_default_template_values(requestHandler, question_id):
	"""Return a dictionary of template values used for login template"""
	if question_id == None:
		client_id = None
		token = None
	else:
		client_id, token = connect(question_id)		# New user connection

	if users.get_current_user():
		url = users.create_logout_url(requestHandler.request.uri)
		url_linktext = 'Logout'
		logged_in = "true"
	else:
		url = users.create_login_url(requestHandler.request.uri)
		url_linktext = 'Login w/ Google Account'
		logged_in = "false"

	template_values = {
		'client_id': client_id,
		'token': token,
		'user': users.get_current_user(),
		'url': url,
		'url_linktext': url_linktext,
		'logged_in': logged_in,
		'admin': users.is_current_user_admin()
	}
	return template_values

#####################
# Channel support
#####################
def connect(question_id):
	"""User has connected, so remember that"""
	user_id = str(random.randint(1000000000000, 10000000000000)) + "_" + question_id
	client_id = user_id
	token = channel.create_channel(client_id)
	conns = Connection.all()
	conns = conns.filter("client_id =", client_id)
	if conns.count() == 0:
		questionObj = Question.getQuestionById(question_id)
		if questionObj:
			conn = Connection()
			conn.client_id = client_id
			conn.question = questionObj
			conn.put()

	return client_id, token

def send_message(client_id, question_id, message):
	"""Send message to all listeners (except self) to this topic"""
	questionObj = Question.getQuestionById(question_id)
	if questionObj:
		conns = Connection.all()
		conns = conns.filter("question = ", questionObj)
		conns = conns.filter("client_id !=", client_id)
		for conn in conns:
			channel.send_message(conn.client_id, json.dumps(message))

#####################
# Page Handlers
#####################
class MainPageHandler(webapp2.RequestHandler):
    def get(self):
		template_values = get_default_template_values(self, None)

		path = os.path.join(os.path.dirname(__file__), '../html/main.html')
		self.response.out.write(template.render(path, template_values))

class IdeaPageHandler(webapp2.RequestHandler):
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

# Particpant page to enter new tags
class TagPageHandler(webapp2.RequestHandler):
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

class ResultsPageHandler(webapp2.RequestHandler):
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

class AdminPageHandler(webapp2.RequestHandler):
    def get(self):
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
					item = {"tag": tag, "cluster": cluster.key().id(), "author": cleanNickname(tagObj.author)}
					tags.append(item)
			data = {"tags": tags, "num_clusters": Cluster.numClusters(question_id)}
		elif request == "ideatags":
			tags = []
			for tagObj in IdeaTag.getTags(question_id):
				tag = cleanTag(tagObj.tag)
				idea = tagObj.idea
				if idea:
					item = {"tag": tag, "idea_id": idea.key().id(), "author": cleanNickname(tagObj.author)}
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
				data = {"title": "", "question": ""}
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
			question_id = Question.createQuestion(title, question)
			data = {"question_id": question_id}

			# Update clients
			message = {
				"op": "newquestion"
			}
			send_message(client_id, question_id, message)		# Update other clients about this change

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
			send_message(client_id, question_id, message)		# Update other clients about this change

		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(json.dumps(data))

class NewIdeaHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		idea = self.request.get('idea')
		question_id = self.request.get("question_id")
		if len(idea) >= 1:			# Don't limit idea length until there is a way to give feedback about short ideas
			Idea.createIdea(idea, question_id)

			# Update clients
			message = {
				"op": "newidea",
				"text": idea,
				"author": cleanNickname(users.get_current_user())
			}
			send_message(client_id, question_id, message)		# Update other clients about this change

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
				"author": cleanNickname(users.get_current_user())
			}
			send_message(client_id, question_id, message)		# Update other clients about this change

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
				"author": cleanNickname(users.get_current_user())
			}
			send_message(client_id, question_id, message)		# Update other clients about this change

class DeleteHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		question_id = self.request.get("question_id")
		Question.delete(question_id)

		# Update clients
		message = {
			"op": "delete"
		}
		send_message(client_id, question_id, message)		# Update other clients about this change

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
		send_message(client_id, question_id, message)		# Update other clients about this change

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
		send_message(client_id, question_id, message)		# Update other clients about this change

class NumNotesToTagPerPersonHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		num_notes_to_tag_per_person = int(self.request.get('num_notes_to_tag_per_person'))
		question_id = self.request.get("question_id")
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			questionObj.setNumNotesToTagPerPerson(num_notes_to_tag_per_person)

		message = {
			"op": "num_notes_to_tag_per_person",
			"num_notes_to_tag_per_person": num_notes_to_tag_per_person
		}
		send_message(client_id, question_id, message)		# Update other clients about this change

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
		client_id = self.request.get("from")
		# logging.info("CONNECTED: %s", client_id)
		# Not doing anything here yet...

class DisconnectedHandler(webapp2.RequestHandler):
	# Notified when clients disconnect
	def post(self):
		client_id = self.request.get("from")
		# logging.info("DISCONNECTED: %s", client_id)
		connection = Connection().all()
		connection.filter("client_id =", client_id)
		db.delete(connection);

#####################
# Text Support
#####################

def getIdea(ideaIdStr):
	ideaObj = Idea.getIdeaById(ideaIdStr)
	if ideaObj:
		idea = {
			"idea": ideaObj.text,
			"author": cleanNickname(ideaObj.author)
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
				"author": cleanNickname(ideaObj.author)
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
				"author": cleanNickname(ideaObj.author)
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
			"author": cleanNickname(ideaObj.author)
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

def cleanNickname(user):
	if user:
		nickname = user.nickname()
		if nickname.count("@") == 0:
			return nickname
		else:
			return nickname[:nickname.index("@")]
	else:
		return "none"