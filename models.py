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

import logging
import random
from google.appengine.ext import db
from google.appengine.api import users

class Question(db.Model):
	title = db.StringProperty()
	question = db.StringProperty()
	author = db.UserProperty(auto_current_user_add=True)
	code = db.StringProperty()

	@staticmethod
	def getQuestionById(questionIdStr):
		questionObj = None
		try:
			questionObj = Question.all().filter("code = ", questionIdStr).get()
		except:
			pass
		return questionObj

	@staticmethod
	def getQuestionsByUser():
		questions = Question.all().filter("author = ", users.get_current_user())
		return questions

	@staticmethod
	def delete(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			clusterObjs = Cluster.all().filter("question =", questionObj)
			db.delete(clusterObjs)
			ideaObjs = Idea.all().filter("question =", questionObj)
			db.delete(ideaObjs)
			tagObjs = Tag.all().filter("question =", questionObj)
			db.delete(tagObjs)
			appObjs = App.all().filter("question =", questionObj)
			db.delete(appObjs)
			connectionObjs = Connection.all().filter("question =", questionObj)
			db.delete(connectionObjs)
			db.delete(questionObj)

	@staticmethod
	def createQuestion(title, question):
		codeNeeded = True
		while codeNeeded:
			code = str(random.randint(10000, 99999))
			q = Question.all().filter("code = ", code).get()
			if not q:
				codeNeeded = False

		questionObj = Question()
		questionObj.title = title
		questionObj.question = question
		questionObj.code = code
		questionObj.put()
		return code

class App(db.Model):
	phase = db.IntegerProperty(default=0)
	question = db.ReferenceProperty(Question)

	@staticmethod
	def getApp(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			app = App.all().filter("question =", questionObj)
			if app.count() == 0:
				appObj = App()
				appObj.question = questionObj
				appObj.put()
			else:
				appObj = app.get()
		else:
			appObj = None
		return appObj
	
	@staticmethod
	def getPhase(questionIDStr):
		return App.getApp(questionIDStr).phase

	@staticmethod
	def setPhase(phase, questionIDStr):
		appObj = App.getApp(questionIDStr)
		appObj.phase = phase
		appObj.put()

class Cluster(db.Model):
	text = db.StringProperty()
	index = db.IntegerProperty()
	question = db.ReferenceProperty(Question)

	@staticmethod
	def createCluster(text, index, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			clusterObj = Cluster()
			clusterObj.text = text
			clusterObj.index = index
			clusterObj.question = questionObj
			clusterObj.put()
			return clusterObj
		else:
			return None

	@staticmethod
	def getRandomClusterIndex(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			count = Cluster.all().filter("question =", questionObj).count()
			if count == 0:
				return -1
			else:
				return random.randint(0, count-1)
		else:
			return -1

	@staticmethod
	def numClusters(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			return Cluster.all().filter("question =", questionObj).count()
		else:
			return 0

	@staticmethod
	def deleteAllClusters(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			db.delete(Cluster.all().filter("question =", questionObj))

class Idea(db.Model):
	author = db.UserProperty(auto_current_user_add=True)
	date = db.DateProperty(auto_now=True)
	text = db.StringProperty()
	index = db.IntegerProperty()
	cluster = db.ReferenceProperty(Cluster)
	question = db.ReferenceProperty(Question)

	@staticmethod
	def createIdea(idea, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			if len(idea) > 500:
				idea = idea[:500]
			idea = idea.replace("\n", "")
			count = Idea.all().count()
			ideaObj = Idea()
			ideaObj.text = idea
			ideaObj.index = count
			ideaObj.question = questionObj
			ideaObj.put()

	@staticmethod
	def assignCluster(index, clusterObj, questionIdStr):
		"""Assigns specified cluster to the 'index' idea"""
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			ideaObj = Idea.all()
			ideaObj = ideaObj.filter("index =", index)
			ideaObj = ideaObj.filter("question =", questionObj)
			ideaObj = ideaObj.get()
			if ideaObj:
				ideaObj.cluster = clusterObj
				ideaObj.put()

class ClusterAssignment(db.Model):
	author = db.UserProperty(auto_current_user_add=True)
	cluster = db.ReferenceProperty(Cluster)
	question = db.ReferenceProperty(Question)

	@staticmethod
	def getAssignment(questionIdStr):
		"""Determines the cluster assigned to this author"""
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			ca = ClusterAssignment.all()
			ca = ca.filter("author =", users.get_current_user())
			ca = ca.filter("question =", questionObj)
			if ca.count() == 0:
				cluster_index = Cluster.getRandomClusterIndex(questionIdStr)
				if cluster_index >= 0:
					caObj = ClusterAssignment()
					caObj.cluster = Cluster.all().filter("index =", cluster_index).get()
					caObj.question = questionObj
					caObj.put()
				return cluster_index
			else:
				caObj = ca.get()
				return ca.get().cluster.index
		else:
			return -1

	@staticmethod
	def deleteAllClusterAssignments(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			db.delete(ClusterAssignment.all().filter("question =", questionObj))

class Tag(db.Model):
	author = db.UserProperty(auto_current_user_add=True)
	tag = db.StringProperty()
	cluster = db.ReferenceProperty(Cluster)
	question = db.ReferenceProperty(Question)

	@staticmethod
	def createTag(tag, cluster_index, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		cluster = Cluster.all().filter("question =", questionObj).filter("index =", cluster_index).get()
		if cluster:
			tagObj = Tag()
			tagObj.tag = tag
			tagObj.cluster = cluster
			tagObj.question = questionObj
			tagObj.put()

	@staticmethod
	def getTags(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		tags = Tag.all().filter("question =", questionObj)
		return tags

	@staticmethod
	def getTagsByUser(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		tags = Tag.all().filter("question =", questionObj).filter("author = ", users.get_current_user())
		return tags

	@staticmethod
	def deleteAllTags(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		db.delete(Tag.all().filter("question =", questionObj))

class Connection(db.Model):
	client_id = db.StringProperty()
	question = db.ReferenceProperty(Question)