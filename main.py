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
from models import *
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from cluster import KMeansClustering

def get_default_template_values(requestHandler):
	"""Return a dictionary of template values used for login template"""
	client_id, token = connect()		# New user connection

	if users.get_current_user():
		url = users.create_logout_url(requestHandler.request.uri)
		url_linktext = 'Logout'
		logged_in = "true"
	else:
		url = users.create_login_url(requestHandler.request.uri)
		url_linktext = 'Login'
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
def connect():
	"""User has connected, so remember that"""
	user_id = str(random.randint(1000000000000, 10000000000000))
	client_id = user_id
	token = channel.create_channel(client_id)
	conns = Connection.all()
	conns = conns.filter('client_id =', client_id)
	if conns.count() == 0:
		conn = Connection()
		conn.client_id = client_id
		conn.put()

	return client_id, token

def send_message(client_id, message):
	"""Send message to all listeners (except self) to this topic"""
	conns = Connection.all()
	conns = conns.filter('client_id !=', client_id)
	for conn in conns:
		channel.send_message(conn.client_id, json.dumps(message))

#####################
# Page Handlers
#####################
class MainPageHandler(webapp2.RequestHandler):
    def get(self):
		template_values = get_default_template_values(self)

		path = os.path.join(os.path.dirname(__file__), 'main.html')
		self.response.out.write(template.render(path, template_values))

class ResultsPageHandler(webapp2.RequestHandler):
    def get(self):
		template_values = get_default_template_values(self)

		path = os.path.join(os.path.dirname(__file__), 'results.html')
		self.response.out.write(template.render(path, template_values))

class AdminPageHandler(webapp2.RequestHandler):
    def get(self):
		template_values = get_default_template_values(self)

		path = os.path.join(os.path.dirname(__file__), 'admin.html')
		self.response.out.write(template.render(path, template_values))

# Particpant page to enter new tags
class TagPageHandler(webapp2.RequestHandler):
    def get(self):
		template_values = get_default_template_values(self)
		template_values["cluster_index"] = ClusterAssignment.getAssignment()

		path = os.path.join(os.path.dirname(__file__), 'tag.html')
		self.response.out.write(template.render(path, template_values))

# Admin page to show all tags
class TagsPageHandler(webapp2.RequestHandler):
    def get(self):
		template_values = get_default_template_values(self)

		path = os.path.join(os.path.dirname(__file__), 'tags.html')
		self.response.out.write(template.render(path, template_values))

#####################
# Action Handlers
#####################
class NewHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		idea = self.request.get('idea')
		if len(idea) > 2:
			Idea.addIdea(idea)

			# Update clients
			message = {
				"op": "new",
				"text": idea,
				"author": users.get_current_user().nickname()
			}
			send_message(client_id, message)		# Update other clients about this change

class NewTagHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		tag = self.request.get('tag')
		cluster_index = int(self.request.get('cluster_index'))
		if len(tag) > 2:
			Tag.addTag(tag, cluster_index)

			# Update clients
			message = {
				"op": "newtag",
				"tag": tag,
				"cluster_index": cluster_index,
				"author": users.get_current_user().nickname()
			}
			send_message(client_id, message)		# Update other clients about this change

class QueryHandler(webapp2.RequestHandler):
    def get(self):
		request = self.request.get("request")
		data = {}
		if request == "ideas":
			cluster_index = self.request.get("cluster_index")
			if cluster_index:
				data = getIdeasByCluster(int(cluster_index))
			else:
				data = getIdeas()
		elif request == "phase":
			data = {"phase": App.getPhase()}
		elif request == "tags":
			tags = []
			for tag in Tag.getTags():
				item = {"tag": tag.tag, "cluster": tag.cluster.index}
				tags.append(item)
			data = {"tags": tags, "num_clusters": Cluster.numClusters()}
		elif request == "mytags":
			tags = []
			for tag in Tag.getTagsByUser():
				tags.append(tag.tag)
			data = {"tags": tags}

		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(json.dumps(data))

class ClusterHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		num_clusters = int(self.request.get('num_clusters'))
		data = doCluster(num_clusters)

		# Update clients
		message = {
			"op": "refresh"
		}
		send_message(client_id, message)		# Update other clients about this change

class PhaseHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		phase = int(self.request.get('phase'))
		App.setPhase(phase)

		# Update clients
		message = {
			"op": "phase",
			"phase": phase
		}
		send_message(client_id, message)		# Update other clients about this change

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

def getIdeas():
	results = []
	clusterObjs = Cluster.all()

	# Start with all the ideas that aren't in any cluster
	ideaObjs = Idea.all().filter("cluster =", None)
	if ideaObjs.count() > 0:
		entry = {"name": "Unclustered"}
		ideas = []
		for ideaObj in ideaObjs:
			idea = {
				"idea": ideaObj.text,
				"words": ideaObj.text.split(),
				"author": ideaObj.author.nickname()
			}
			ideas.append(idea)
		entry["ideas"] = ideas
		results.append(entry)

	for clusterObj in clusterObjs:
		entry = {"name": clusterObj.text}
		ideaObjs = Idea.all().filter("cluster =", clusterObj)
		ideas = []
		for ideaObj in ideaObjs:
			idea = {
				"idea": ideaObj.text,
				"words": ideaObj.text.split(),
				"author": ideaObj.author.nickname()
			}
			ideas.append(idea)
		entry["ideas"] = ideas
		results.append(entry)
	return results

def getIdeasByCluster(cluster_index):
	clusterObj = Cluster.all().filter("index =", cluster_index).get()
	ideaObjs = Idea.all().filter("cluster =", clusterObj)
	ideas = []
	for ideaObj in ideaObjs:
		idea = {
			"idea": ideaObj.text,
			"words": ideaObj.text.split(),
			"author": ideaObj.author.nickname()
		}
		ideas.append(idea)
	return ideas;

def doCluster(k):
	if k > Idea.all().count():
		return

	vectors, texts, phrases = computeBagsOfWords()
	cl = KMeansClustering(vectors)
	clusters = cl.getclusters(k)

	# Delete existing clusters from database
	clusterObjs = Cluster.all()
	db.delete(clusterObjs)
	
	clusterNum = 1
	for cluster in clusters:
		clusterObj = Cluster()
		clusterObj.text = "Cluster" + str(clusterNum)
		clusterObj.index = clusterNum
		clusterObj.put()
		entry = []
		if type(cluster) is tuple:
			# Cluster may only have a single tuple instead of a collection of them
			index = cluster[-1:][0]
			text = texts[index]
			phrase = phrases[index]
			idea = Idea.all().filter("index =", index).get()
			idea.cluster = clusterObj
			idea.put()
		else:
			for vector in cluster:
				index = vector[-1:][0]
				text = texts[index]
				phrase = phrases[index]
				entry.append([text, phrase])
				idea = Idea.all().filter("index =", index).get()
				idea.cluster = clusterObj
				idea.put()
		clusterNum += 1

	Tag.deleteAllTags()
	ClusterAssignment.deleteAllClusterAssignments()

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
			word = word.lower()
			word = word.strip("`~!@#$%^&*()-_=+|;:',<.>/?")
			if (len(word) > 2) and not isStopWord(word):
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

STOP_WORDS = [ "all", "also", "and", "any", "been", "did", "for", "not", "had", "now", "she", "that", "the", "this", "was", "were" ]
def isStopWord(word):
	return (word in STOP_WORDS)
	
app = webapp2.WSGIApplication([
    ('/', MainPageHandler),
	('/results', ResultsPageHandler),
	('/admin', AdminPageHandler),
	('/tag', TagPageHandler),
	('/tags', TagsPageHandler),
	('/query', QueryHandler),
	('/new', NewHandler),
	('/newtag', NewTagHandler),
	('/cluster', ClusterHandler),
	('/set_phase', PhaseHandler),
	('/_ah/channel/connected/', ConnectedHandler),
	('/_ah/channel/disconnected/', DisconnectedHandler)
], debug=True)
