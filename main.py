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
from models import *
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from cluster import KMeansClustering

STOP_WORDS = [ "all", "also", "and", "any", "been", "did", "for", "not", "had", "now", "she", "that", "the", "this", "was", "were" ]


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

		path = os.path.join(os.path.dirname(__file__), 'main.html')
		self.response.out.write(template.render(path, template_values))

class IdeaPageHandler(webapp2.RequestHandler):
    def get(self):
		question_id = self.request.get("question_id")
		template_values = get_default_template_values(self, question_id)

		path = os.path.join(os.path.dirname(__file__), 'idea.html')
		self.response.out.write(template.render(path, template_values))

class ResultsPageHandler(webapp2.RequestHandler):
    def get(self):
		question_id = self.request.get("question_id")
		template_values = get_default_template_values(self, question_id)

		path = os.path.join(os.path.dirname(__file__), 'results.html')
		self.response.out.write(template.render(path, template_values))

class AdminPageHandler(webapp2.RequestHandler):
    def get(self):
		question_id = self.request.get("question_id")
		template_values = get_default_template_values(self, None)

		path = os.path.join(os.path.dirname(__file__), 'admin.html')
		self.response.out.write(template.render(path, template_values))

# Particpant page to enter new tags
class TagPageHandler(webapp2.RequestHandler):
    def get(self):
		question_id = self.request.get("question_id")
		template_values = get_default_template_values(self, question_id)
		template_values["cluster_index"] = ClusterAssignment.getAssignment(question_id)

		path = os.path.join(os.path.dirname(__file__), 'tag.html')
		self.response.out.write(template.render(path, template_values))

#####################
# Action Handlers
#####################
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

class NewIdeaHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		idea = self.request.get('idea')
		question_id = self.request.get("question_id")
		if len(idea) >= 0:			# Don't limit idea length until there is a way to give feedback about short ideas
			Idea.createIdea(idea, question_id)

			# Update clients
			message = {
				"op": "newidea",
				"text": idea,
				"author": cleanNickname(users.get_current_user())
			}
			send_message(client_id, question_id, message)		# Update other clients about this change

class NewTagHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		tag = self.request.get('tag')
		cluster_index = int(self.request.get('cluster_index'))
		question_id = self.request.get("question_id")
		if len(tag) > 2:
			Tag.createTag(tag, cluster_index, question_id)

			# Update clients
			message = {
				"op": "newtag",
				"tag": tag,
				"cluster_index": cluster_index,
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

class QueryHandler(webapp2.RequestHandler):
    def get(self):
		request = self.request.get("request")
		question_id = self.request.get("question_id")

		data = {}
		if request == "ideas":
			cluster_index = self.request.get("cluster_index")
			if cluster_index:
				data = getIdeasByCluster(int(cluster_index), question_id)
			else:
				data = getIdeas(question_id)
		elif request == "phase":
			data = {"phase": App.getPhase(question_id)}
		elif request == "tags":
			tags = []
			for tagObj in Tag.getTags(question_id):
				tag = cleanTag(tagObj.tag)
				if tagObj.cluster:
					item = {"tag": tag, "cluster": tagObj.cluster.index, "author": cleanNickname(tagObj.author)}
					tags.append(item)
			data = {"tags": tags, "num_clusters": Cluster.numClusters(question_id)}
		elif request == "mytags":
			tags = []
			for tag in Tag.getTagsByUser(question_id):
				tags.append(tag.tag)
			data = {"tags": tags}
		elif request == "question":
			questionObj = Question.getQuestionById(question_id)
			if questionObj:
				data = {"title": questionObj.title, "question": questionObj.question}
			else:
				data = {"title": "", "question": ""}
		elif request == "questions":
			questions = []
			for question in Question.getQuestionsByUser():
				questions.append({"title": question.title, "question": question.question, "question_id": question.code})
			data = {"questions": questions}

		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(json.dumps(data))

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

class PhaseHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		phase = int(self.request.get('phase'))
		question_id = self.request.get("question_id")
		App.setPhase(phase, question_id)

		# Update clients
		message = {
			"op": "phase",
			"phase": phase
		}
		send_message(client_id, question_id, message)		# Update other clients about this change

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

def getIdeas(questionIdStr):
	results = []
	questionObj = Question.getQuestionById(questionIdStr)
	if not questionObj:
		return results
	clusterObjs = Cluster.all().filter("question = ", questionObj).order("index")

	# Start with all the ideas that aren't in any cluster
	ideaObjs = Idea.all().filter("question = ", questionObj).filter("cluster =", None)
	if ideaObjs.count() > 0:
		entry = {"name": "Unclustered", "id": -1}
		ideas = []
		for ideaObj in ideaObjs:
			idea = {
				"idea": ideaObj.text,
				"words": ideaObj.text.split(),
				"author": cleanNickname(ideaObj.author)
			}
			ideas.append(idea)
		entry["ideas"] = ideas
		results.append(entry)

	for clusterObj in clusterObjs:
		entry = {"name": clusterObj.text, "id": clusterObj.index}
		ideaObjs = Idea.all().filter("cluster =", clusterObj)
		ideas = []
		for ideaObj in ideaObjs:
			idea = {
				"idea": ideaObj.text,
				"words": ideaObj.text.split(),
				"author": cleanNickname(ideaObj.author)
			}
			ideas.append(idea)
		entry["ideas"] = ideas
		results.append(entry)
	return results

def getIdeasByCluster(cluster_index, questionIdStr):
	questionObj = Question.getQuestionById(questionIdStr)
	if not questionObj:
		return []

	clusterObj = Cluster.all().filter("question = ", questionObj).filter("index =", cluster_index).get()
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
	if k > Idea.all().count():
		return

	vectors, texts, phrases = computeBagsOfWords()
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
			Idea.assignCluster(index, clusterObj, question_id)
		else:
			for vector in cluster:
				index = vector[-1:][0]
				text = texts[index]
				phrase = phrases[index]
				entry.append([text, phrase])
				Idea.assignCluster(index, clusterObj, question_id)
		clusterNum += 1

	# Clean up any existing tags and cluster assignments since clusters have been reformed
	Tag.deleteAllTags(question_id)
	ClusterAssignment.deleteAllClusterAssignments(question_id)

def computeBagsOfWords():
	# First define vector by extracting every word
	all_words = set()
	phrases = []
	texts = []
	ideas = Idea.all().order('index')
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

	# Create an index for the words
	word_index = {}
	i = 0
	for word in all_words:
		word_index[word] = i
		i += 1

	# Then for each phrase, compute it's vector
	vectors = []
	phraseNum = 0
	for phrase in phrases:
		vector = [0] * (len(word_index) + 1)
		for word in phrase:
			index = word_index[word]
			vector[index] += 1
		vector[len(word_index)] = phraseNum
		vectors.append(tuple(vector))
		phraseNum += 1

	return vectors, texts, phrases

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
	
app = webapp2.WSGIApplication([
	('/', MainPageHandler),
    ('/idea', IdeaPageHandler),
	('/results', ResultsPageHandler),
	('/admin', AdminPageHandler),
	('/tag', TagPageHandler),

	('/query', QueryHandler),
	('/newquestion', NewQuestionHandler),
	('/newidea', NewIdeaHandler),
	('/newtag', NewTagHandler),
	('/delete', DeleteHandler),
	('/cluster', ClusterHandler),
	('/set_phase', PhaseHandler),

	('/_ah/channel/connected/', ConnectedHandler),
	('/_ah/channel/disconnected/', DisconnectedHandler)
], debug=True)
