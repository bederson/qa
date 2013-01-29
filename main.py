#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
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
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from cluster import KMeansClustering

#####################
# Channel support
#####################
def connect(topicid):
	"""User has connected, so remember that"""
	user_id = str(random.randint(1000000000000, 10000000000000))
	client_id = user_id + topicid
	token = channel.create_channel(client_id)
	conns = Connection.all()
	conns = conns.filter('client_id =', client_id)
	conns = conns.filter('topic =', Idea.get_by_id(int(topicid)))
	if conns.count() == 0:
		conn = Connection()
		conn.client_id = client_id
		conn.topic = Idea.get_by_id(int(topicid))
		conn.put()

	return client_id, token

def send_message(client_id, topicid, message):
	"""Send message to all listeners (except self) to this topic"""
	conns = Connection.all()
	conns = conns.filter('topic =', Idea.get_by_id(int(topicid)))
	conns = conns.filter('client_id !=', client_id)
	for conn in conns:
		channel.send_message(conn.client_id, json.dumps(message))

#####################
# Model
#####################
class Idea(db.Model):
	date = db.DateProperty(auto_now=True)
	text = db.StringProperty()
	index = db.IntegerProperty()

#####################
# Page Handlers
#####################
class MainHandler(webapp2.RequestHandler):
    def get(self):
		thanks = self.request.get('thanks')
		template_values = {"thanks": thanks}
		path = os.path.join(os.path.dirname(__file__), 'main.html')
		self.response.out.write(template.render(path, template_values))

class SubmitHandler(webapp2.RequestHandler):
	def post(self):
		idea = self.request.get('idea')
		if len(idea) > 2:
			count = Idea.all().count() + 1
			ideaObj = Idea()
			ideaObj.text = idea
			ideaObj.index = count
			ideaObj.put()

class ResultsHandler(webapp2.RequestHandler):
    def get(self):

		template_values = {}
		path = os.path.join(os.path.dirname(__file__), 'results.html')
		self.response.out.write(template.render(path, template_values))

class QueryHandler(webapp2.RequestHandler):
    def get(self):
		# ideas = Idea.all()
		# data = []
		# for ideaObj in ideas:
		# 	data.append(ideaObj.text)

		data = doCluster(2)
		result = json.dumps({'ideas': data})
		self.response.headers['Content-Type'] = 'application/json'
		self.response.out.write(result)

def doCluster(k):
	vectors, texts = computeBagsOfWords()
	cl = KMeansClustering(vectors)
	clusters = cl.getclusters(k)

	logging.info("CLUSTERS")
	logging.info(clusters)
	logging.info("PHRASES")
	logging.info(texts)
	
	result = []
	for cluster in clusters:
		entry = []
		for vector in cluster:
			index = vector[-1:][0]
			text = texts[index]
			entry.append(text)
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

	return vectors, texts

STOP_WORDS = [ "and", "been", "the", "was", "were", "she", "did", "all", "not" ]
def isStopWord(word):
	return (word in STOP_WORDS)
	
app = webapp2.WSGIApplication([
    ('/', MainHandler),
	('/results', ResultsHandler),
	('/query', QueryHandler),
	('/submit', SubmitHandler)
], debug=True)
