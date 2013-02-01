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

class App(db.Model):
	phase = db.IntegerProperty(default=0)

	@staticmethod
	def getApp():
		app = App.all()
		if app.count() == 0:
			appObj = App()
			appObj.put()
		else:
			appObj = app.get()
		return appObj
	
	@staticmethod
	def getPhase():
		return App.getApp().phase

	@staticmethod
	def setPhase(phase):
		appObj = App.getApp()
		appObj.phase = phase
		appObj.put()

class Cluster(db.Model):
	text = db.StringProperty()
	index = db.IntegerProperty()

	@staticmethod
	def getRandomCluster():
		count = Cluster.all().count()
		return random.randint(0, count-1)

	@staticmethod
	def numClusters():
		return Cluster.all().count()

class Idea(db.Model):
	author = db.UserProperty(auto_current_user_add=True)
	date = db.DateProperty(auto_now=True)
	text = db.StringProperty()
	index = db.IntegerProperty()
	cluster = db.ReferenceProperty(Cluster)

	@staticmethod
	def addIdea(idea):
		if len(idea) > 500:
			idea = idea[:500]
		idea = idea.replace("\n", "")
		count = Idea.all().count()
		ideaObj = Idea()
		ideaObj.text = idea
		ideaObj.index = count
		ideaObj.put()

class ClusterAssignment(db.Model):
	author = db.UserProperty(auto_current_user_add=True)
	cluster = db.ReferenceProperty(Cluster)

	@staticmethod
	def getAssignment():
		"""Determines the cluster assigned to this author"""
		ca = ClusterAssignment.all().filter("author =", users.get_current_user())
		if ca.count() == 0:
			caObj = ClusterAssignment()
			cluster_index = Cluster.getRandomCluster()
			caObj.cluster = Cluster.all().filter("index =", cluster_index).get()
			caObj.put()
			return cluster_index
		else:
			caObj = ca.get()
			return ca.get().cluster.index

	@staticmethod
	def deleteAllClusterAssignments():
		db.delete(ClusterAssignment.all())

class Tag(db.Model):
	author = db.UserProperty(auto_current_user_add=True)
	tag = db.StringProperty()
	cluster = db.ReferenceProperty(Cluster)

	@staticmethod
	def addTag(tag, cluster_index):
		cluster = Cluster.all().filter("index =", cluster_index).get()
		tagObj = Tag()
		tagObj.tag = tag
		tagObj.cluster = cluster
		tagObj.put()

	@staticmethod
	def getTags():
		tags = Tag.all()
		return tags

	@staticmethod
	def getTagsByUser():
		tags = Tag.all().filter("author = ", users.get_current_user())
		return tags

	@staticmethod
	def deleteAllTags():
		db.delete(Tag.all())

class Connection(db.Model):
	client_id = db.StringProperty()