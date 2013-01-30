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
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from cluster import KMeansClustering

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
class MainHandler(webapp2.RequestHandler):
    def get(self):
		template_values = {}

		client_id, token = connect()		# New user connection
		template_values['client_id'] = client_id
		template_values['token'] = token

		path = os.path.join(os.path.dirname(__file__), 'main.html')
		self.response.out.write(template.render(path, template_values))

class NewHandler(webapp2.RequestHandler):
	def post(self):
		client_id = self.request.get('client_id')
		idea = self.request.get('idea')
		if len(idea) > 2:
			if len(idea) > 500:
				idea = idea[:500]
			idea = idea.replace("\n", "")
			count = Idea.all().count() + 1
			ideaObj = Idea()
			ideaObj.text = idea
			ideaObj.index = count
			ideaObj.put()

			# Update clients
			message = {
				"op": "new",
				"text": idea,
			}
			send_message(client_id, message)		# Update other clients about this change

class ResultsHandler(webapp2.RequestHandler):
    def get(self):
		template_values = {}

		client_id, token = connect()		# New user connection
		template_values['client_id'] = client_id
		template_values['token'] = token

		path = os.path.join(os.path.dirname(__file__), 'results.html')
		self.response.out.write(template.render(path, template_values))

class QueryHandler(webapp2.RequestHandler):
    def get(self):
		data = doCluster(2)
		result = json.dumps({'ideas': data})
		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(result)

class ConnectedHandler(webapp2.RequestHandler):
	# Notified when clients connect
	def post(self):
		client_id = self.request.get("from")
		# logging.info("CONNECT: %s", client_id)
		# Not doing anything here yet...

class DisconnectedHandler(webapp2.RequestHandler):
	# Notified when clients disconnect
	def post(self):
		client_id = self.request.get("from")
		# logging.info("DISCONNECT: %s", client_id)
		connection = Connection().all()
		connection.filter("client_id =", client_id)
		db.delete(connection);

#####################
# Text Support
#####################

def doCluster(k):
	vectors, texts, phrases = computeBagsOfWords()
	cl = KMeansClustering(vectors)
	clusters = cl.getclusters(k)

	# logging.info("TEXTS")
	# logging.info(texts)
	# logging.info("CLUSTERS")
	# logging.info(clusters)
	
	result = []
	for cluster in clusters:
		entry = []
		if type(cluster) is tuple:
			# Cluster only has a single tuple, not a collection of them
			index = cluster[-1:][0]
			text = texts[index]
			phrase = phrases[index]
			entry.append([text, phrase])
		else:
			for vector in cluster:
				index = vector[-1:][0]
				text = texts[index]
				phrase = phrases[index]
				entry.append([text, phrase])
		result.append(entry)
	return result

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
	# logging.info("ALL WORDS")
	# logging.info(all_words)
	# logging.info("PHRASES")
	# logging.info(phrases)

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
    ('/', MainHandler),
	('/results', ResultsHandler),
	('/query', QueryHandler),
	('/new', NewHandler),
	('/_ah/channel/connected/', ConnectedHandler),
	('/_ah/channel/disconnected/', DisconnectedHandler)
], debug=True)
