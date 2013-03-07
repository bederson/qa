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

import random
from google.appengine.ext import db
from google.appengine.api import users
	
####################
##### QUESTION #####
####################
class Question(db.Model):
	title = db.StringProperty()
	question = db.StringProperty()
	author = db.UserProperty(auto_current_user_add=True) # must be logged in to create a question; not a reference to Author
	code = db.StringProperty()
	phase = db.IntegerProperty(default=0)
	date = db.DateTimeProperty(auto_now=True)
	numNotesToTagPerPerson = db.IntegerProperty(default=5)

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

	@staticmethod
	def editQuestion(questionIdStr, title, question):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			questionObj.title = title
			questionObj.question = question
			questionObj.put()
			return questionObj.code
		else:
			return -1

	@staticmethod
	def delete(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			Cluster.deleteAllClusters(questionIdStr)
			Idea.deleteAllIdeas(questionIdStr)
			db.delete(Connection.all().filter("question =", questionObj))
			db.delete(questionObj)
			
	@staticmethod
	def getPhase(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			return questionObj.phase

	@staticmethod
	def setPhase(phase, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			questionObj.phase = phase
			questionObj.put()

	def getNumNotesToTagPerPerson(self):
		return self.numNotesToTagPerPerson

	def setNumNotesToTagPerPerson(self, numNotesToTagPerPerson):
		self.numNotesToTagPerPerson = numNotesToTagPerPerson
		self.put()

	def getNumNotesTaggedByUser(self):
		return IdeaAssignment.all().filter("author =", users.get_current_user()).filter("question =", self).count()

	def getNumTagsByCluster(self):
		return ClusterTag.all().filter("question =", self).count()

	def getNumTagsByIdea(self):
		return IdeaTag.all().filter("question =", self).count()

######################
##### AUTHOR #####
######################
class Author(db.Model):
	user = db.UserProperty(auto_current_user_add=True)
	nickname = db.StringProperty()
	question = db.ReferenceProperty(Question)
	
	@staticmethod
	def createAuthor(question, nickname=None):
		if nickname is None:
			user = users.get_current_user()
			nickname = user.nickname()		
		author = Author()
		author.nickname = nickname
		author.question = question
		return author
		
	@staticmethod
	def getAuthor(question, nickname=None):
		author = None
		user = users.get_current_user()
		if nickname is not None:
			author = Author.all().filter("question = ", question).filter("nickname =", nickname).get()
		elif user is not None:
			author = Author.all().filter("question = ", question).filter("user =", user).get()
		return author
	
	@staticmethod
	def addNickname(questionId, nickname):
		question = Question.getQuestionById(questionId)
		author = Author.getAuthor(question)
		if not author:
			author = Author.createAuthor(question, nickname)
		else:
			author.nickname = nickname
		author.put()
	
	@staticmethod
	def changeNickname(questionId, nickname=None):
        # TUESDAY: add support for non-authenticated users
        # TUESDAY: display nicknames in gui (send authenticated user info to instructor)
		# xx only good when authenticated user exists for Author
		question = Question.getQuestionById(questionId)
		author = Author.getAuthor(question)
        
		if author:
			# reset nickname to authenticated user if no nickname provided
			author.nickname = nickname if nickname is not None else (author.user.nickname() if author.user else "Unknown")
			author.put()
			
	@staticmethod
	def nicknameAlreadyExists(questionId, nickname):
		question = Question.getQuestionById(questionId)
		author = Author.all().filter("question =", question).filter("nickname =", nickname).get()
		return author is not None
				
	@staticmethod
	def getNickname(questionId):
		# xx only good when authenticated user exists for Author
		question = Question.getQuestionById(questionId)
		author = Author.getAuthor(question)
		return author.nickname if author is not None else None
	
###################
##### CLUSTER #####
###################
class Cluster(db.Model):
	text = db.StringProperty()
	question = db.ReferenceProperty(Question)
	rand = db.FloatProperty()
	date = db.DateTimeProperty(auto_now=True)

	@staticmethod
	def createCluster(text, index, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			clusterObj = Cluster()
			clusterObj.text = text
			clusterObj.index = index
			clusterObj.question = questionObj
			if Cluster.all().filter("question =", questionObj).count() == 0:
				clusterObj.rand = 1.0
			else:
				clusterObj.rand = random.random()
			clusterObj.put()
			return clusterObj
		else:
			return None

	@staticmethod
	def getRandomCluster(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			rand = random.random()
			return Cluster.all().filter("question =", questionObj).order("rand").filter("rand >", rand).get()
		else:
			return None

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
			ClusterAssignment.deleteAllClusterAssignments(questionIdStr)
			clusters = Cluster.all().filter("question =", questionObj)
			for clusterObj in clusters:
				for idea in Idea.all().filter("cluster =", clusterObj):
					idea.cluster = None
					idea.put()
			db.delete(clusters)

################
##### IDEA #####
################
class Idea(db.Model):
	author = db.ReferenceProperty(Author)
	date = db.DateTimeProperty(auto_now=True)
	text = db.StringProperty()
	cluster = db.ReferenceProperty(Cluster)
	question = db.ReferenceProperty(Question)
	rand = db.FloatProperty()

	@staticmethod
	def getIdeaById(ideaIdStr):
		ideaObj = Idea.get_by_id(int(ideaIdStr))
		return ideaObj

	@staticmethod
	def createIdea(idea, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			if len(idea) > 500:
				idea = idea[:500]
			idea = idea.replace("\n", "")
			ideaObj = Idea()
			ideaObj.author = Author.createAuthor(questionObj)
			ideaObj.text = idea
			ideaObj.question = questionObj
			if Idea.all().filter("question =", questionObj).count() == 0:
				ideaObj.rand = 1.0
			else:
				ideaObj.rand = random.random()
			ideaObj.put()

	@staticmethod
	def numIdeas(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			return Idea.all().filter("question =", questionObj).count()
		else:
			return 0

	@staticmethod
	def getRandomIdea(questionObj):
		rand = random.random()
		return Idea.all().filter("question =", questionObj).order("rand").filter("rand >", rand).get()

	@staticmethod
	def assignCluster(id, clusterObj):
		"""Assigns specified cluster to the specified idea"""
		ideaObj = Idea.get_by_id(id)
		if ideaObj:
			ideaObj.cluster = clusterObj
			ideaObj.put()

	@staticmethod
	def deleteAllIdeas(questionIdStr):
		IdeaTag.deleteAllIdeas(questionIdStr)
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			IdeaAssignment.deleteAllIdeaAssignments(questionIdStr)
			db.delete(Idea.all().filter("question =", questionObj))

#############################
##### CLUSTERASSIGNMENT #####
#############################
class ClusterAssignment(db.Model):
	author = db.ReferenceProperty(Author)
	cluster = db.ReferenceProperty(Cluster)
	question = db.ReferenceProperty(Question)

	@staticmethod
	def getAssignmentId(questionIdStr):
		"""Determines the cluster assigned to this author"""
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			ca = ClusterAssignment.all()
			# need to pass nickname
			ca = ca.filter("author =", Author.getAuthor(questionObj))
			ca = ca.filter("question =", questionObj)
			if ca.count() == 0:
				cluster = Cluster.getRandomCluster(questionIdStr)
				if cluster:
					caObj = ClusterAssignment()
					caObj.author = Author.createAuthor(questionObj)
					caObj.cluster = cluster
					caObj.question = questionObj
					caObj.put()
					return cluster.key().id()
				else:
					return -1
			else:
				caObj = ca.get()
				return ca.get().cluster.key().id()
		else:
			return -1

	@staticmethod
	def deleteAllClusterAssignments(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			db.delete(ClusterAssignment.all().filter("question =", questionObj))

#############################
##### IDEAASSIGNMENT #####
#############################
class IdeaAssignment(db.Model):
	author = db.ReferenceProperty(Author)
	idea = db.ReferenceProperty(Idea)
	question = db.ReferenceProperty(Question)
	current = db.BooleanProperty(default=False)

	@staticmethod
	def getCurrentAssignmentId(questionIdStr):
		"""Gets the current assignment (or a new one if there isn't a current one)"""
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			# need to pass nickname
			ia = IdeaAssignment.all().filter("author =", Author.getAuthor(questionObj)).filter("question =", questionObj).filter("current =", True).get()
			if ia:
				return ia.idea.key().id()
			else:
				return IdeaAssignment.getNewAssignmentId(questionIdStr)
		else:
			return -1
		
	@staticmethod
	def getNewAssignmentId(questionIdStr):
		"""Get a new random idea assignent for this author"""
		ia = None
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			# First deselect any existing "current" assignment
			currents = IdeaAssignment.all().filter("author =", Author.getAuthor(questionObj)).filter("question =", questionObj).filter("current =", True)
			for currentObj in currents:
				currentObj.current = False
				currentObj.put()
			
			numIdeas = Idea.all().filter("question =", questionObj).count()
			# need to pass nickname
			numAssignments = IdeaAssignment.all().filter("author =", Author.getAuthor(questionObj)).filter("question =", questionObj).count()
			assignmentNeeded = True
			# Randomly select ideas, but keep trying if we've already assigned this one.
			# This is a BAD algorithm if there are a lot of ideas AND individuals get a lot of assignments
			# but that seems unlikely to happen
			MAX_TRIES = 10
			num_tries = 0
			while assignmentNeeded and (numIdeas > numAssignments) and (num_tries < MAX_TRIES):
				num_tries += 1
				idea = Idea.getRandomIdea(questionObj)
				if idea:
					# need to pass nickname
					assigned = (IdeaAssignment.all().filter("author =", Author.getAuthor(questionObj)).filter("idea =", idea).count() > 0)
					if assigned:
						pass	# Whoops - already seen this idea, look for another
					else:
						ia = IdeaAssignment()
						ia.author = Author.createAuthor(questionObj)
						ia.idea = idea
						ia.question = questionObj
						ia.current = True
						ia.put()
						assignmentNeeded = False
				else:
					return -1
		if ia:
			return ia.idea.key().id()
		else:
			return -1

	@staticmethod
	def deleteAllIdeaAssignments(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			db.delete(IdeaAssignment.all().filter("question =", questionObj))

######################
##### CLUSTERTAG #####
######################
class ClusterTag(db.Model):
	tag = db.StringProperty()
	question = db.ReferenceProperty(Question)
	cluster = db.ReferenceProperty(Cluster)
	author = db.ReferenceProperty(Author)
	date = db.DateTimeProperty(auto_now=True)

	@staticmethod
	def createClusterTag(tagStr, cluster_id, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		clusterObj = Cluster.get_by_id(cluster_id)
		if clusterObj and questionObj:
			tagObj = ClusterTag()
			tagObj.tag = tagStr
			tagObj.question = questionObj
			tagObj.cluster = clusterObj
			tagObj.author = Author.createAuthor(questionObj)
			tagObj.put()

	@staticmethod
	def getTags(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			tags = ClusterTag.all().filter("question =", questionObj)
			return tags
		else:
			return None

	@staticmethod
	def getTagsByUser(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			# need to pass nickname
			tags = ClusterTag.all().filter("question =", questionObj).filter("author = ", Author.getAuthor(questionObj))
			return tags
		else:
			return None

	@staticmethod
	def deleteAllTags(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			tags = ClusterTag.all().filter("question =", questionObj)
			db.delete(tags)

######################
##### IDEATAG #####
######################
class IdeaTag(db.Model):
	tag = db.StringProperty()
	question = db.ReferenceProperty(Question)
	idea = db.ReferenceProperty(Idea)
	author = db.ReferenceProperty(Author)
	date = db.DateTimeProperty(auto_now=True)

	@staticmethod
	def createIdeaTag(tagStr, idea_id, questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		ideaObj = Idea.get_by_id(idea_id)
		if ideaObj and questionObj:
			tagObj = IdeaTag()
			tagObj.tag = tagStr
			tagObj.question = questionObj
			tagObj.idea = ideaObj
			tagObj.author = Author.createAuthor(questionObj)
			tagObj.put()

	@staticmethod
	def getTags(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			tags = IdeaTag.all().filter("question =", questionObj)
			return tags
		else:
			return None

	@staticmethod
	def getTagsByUser(ideaIdStr):
		ideaObj = Idea.getIdeaById(ideaIdStr)
		if ideaObj:
			# need to pass nickname
			tags = IdeaTag.all().filter("idea =", ideaObj).filter("author = ", Author.getAuthor(ideaObj.question))
			return tags
		else:
			return None

	@staticmethod
	def deleteAllTags(questionIdStr):
		questionObj = Question.getQuestionById(questionIdStr)
		if questionObj:
			tags = IdeaTag.all().filter("question =", questionObj)
			db.delete(tags)

######################
##### CONNECTION #####
######################
class Connection(db.Model):
	client_id = db.StringProperty()
	question = db.ReferenceProperty(Question)