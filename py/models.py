#!/usr/bin/env python
#
# Copyright 2013 Ben Bederson - http://www.cs.umd.edu/~bederson
# Anne Rose - http://www.cs.umd.edu/hcil/members/arose
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

# Functions that query the datastore may not include a newly put() object
# if called immediately after the object is created (ok if updated).  
# Use an object's key id if you need to retrieve an object immediately after 
# stored. This behavior was noticed when Question.getQuestionById(code) was 
# called immediately after a new question was created.  Same behavior
# noticed when Person created for the first time.

import helpers    
import logging
import random
from constants import *
from lib import gaesessions
from google.appengine.ext import db
from google.appengine.api import users
              
####################
##### QUESTION #####
####################
class Question(db.Model):
    title = db.StringProperty()
    question = db.StringProperty()
    author = db.UserProperty(auto_current_user_add=True)
    code = db.StringProperty()
    phase = db.IntegerProperty(default=0)
    nicknameAuthentication = db.BooleanProperty(default=False)
    date = db.DateTimeProperty(auto_now=True)
    numNotesToTagPerPerson = db.IntegerProperty(default=5)
    numNotesToComparePerPerson = db.IntegerProperty(default=10)
    numNotesForComparison = db.IntegerProperty(default=2)
        
    @staticmethod
    def getQuestionById(code):
        # this function retrieves question by question code, not datastore id
        return Question.all().filter("code = ", code).get() if code else None

    @staticmethod
    def getQuestionsByUser():
        return Question.all().filter("author = ", users.get_current_user()).order("-date")

    @staticmethod
    def createQuestion(title, question, nicknameAuthentication=False):
        questionObj = None
        if users.get_current_user():
            codeNeeded = True
            while codeNeeded:
                code = str(random.randint(10000, 99999))
                q = Question.all().filter("code = ", code).get()
                if not q:
                    codeNeeded = False

            questionObj = Question()
            questionObj.title = title
            questionObj.question = question
            questionObj.nicknameAuthentication = nicknameAuthentication
            questionObj.code = code
            questionObj.put()
        return questionObj

    def editQuestion(self, title, question, nicknameAuthentication=False):
        self.title = title
        self.question = question
        self.nicknameAuthentication = nicknameAuthentication
        self.put()
        return self
       
    @staticmethod
    def delete(questionId):
        question = Question.getQuestionById(questionId)
        if question:
            Cluster.deleteAllClusters(question)
            Idea.deleteAllIdeas(questionId)
            db.delete(Person.all().filter("question =", question))
            db.delete(question)
            db.delete(Cascade.all().filter("question =", question))
            Cascade.deleteJobs(question)
            
    @staticmethod
    def getPhase(question):
        return question.phase if question else None

    @staticmethod
    def setPhase(phase, question):
        if question:
            question.phase = phase
            if phase == PHASE_CASCADE:
                Cascade.init(question)
            question.put()

    def getNumNotesToTagPerPerson(self):
        return self.numNotesToTagPerPerson

    def setNumNotesToTagPerPerson(self, numNotesToTagPerPerson):
        self.numNotesToTagPerPerson = numNotesToTagPerPerson
        self.put()

    def getNumNotesTaggedByUser(self, person):
        return IdeaAssignment.all().filter("author =", person).filter("question =", self).count()

    def getNumNotesToComparePerPerson(self):
        return self.numNotesToComparePerPerson
    
    def getNumNotesForComparison(self):
        return self.numNotesForComparison

    def setCompareNotesOptions(self, numNotesToComparePerPerson, numNotesForComparison):
        self.numNotesToComparePerPerson = numNotesToComparePerPerson
        self.numNotesForComparison = numNotesForComparison
        self.put()

    def getNumNotesComparedByUser(self, person):
        return SimilarIdeaAssignment.all().filter("author =", person).filter("question =", self).count()
            
    def getNumTagsByCluster(self):
        return ClusterTag.all().filter("question =", self).count()

    def getNumTagsByIdea(self):
        return IdeaTag.all().filter("question =", self).count()
    
    def getNumSimilarIdeas(self):
        return SimilarIdea.all().filter("question = ", self).count()
    
    def toDict(self):
        return {
            "question_id": self.code,
            "title": self.title,
            "question": self.question,
            "nickname_authentication": self.nicknameAuthentication,
            "phase": self.phase
        } 

######################
##### Person #####
######################
class Person(db.Model):
    client_ids = db.StringListProperty(default=[])
    user = db.UserProperty()
    nickname = db.StringProperty()    
    question = db.ReferenceProperty(Question)

    def setNickname(self, nickname=None):
        # reset nickname to authenticated user if no nickname provided
        self.nickname = nickname if nickname else (Person.cleanNickname(self.user) if self.user else None)
        self.put()
            
    def addClientId(self, client_id):    
        if client_id is not None and client_id not in self.client_ids:
            self.client_ids.append(client_id)
            self.put()
        return len(self.client_ids)
    
    def removeClientId(self, client_id):
        if client_id is not None and client_id in self.client_ids:
            self.client_ids.remove(client_id)  
            self.put()
        return len(self.client_ids)
                
    @staticmethod
    def createPerson(question=None, nickname=None):   
        person = Person()
        person.user = users.get_current_user() if not question or not question.nicknameAuthentication else None
        person.nickname = nickname if nickname else (Person.cleanNickname(person.user) if person.user else None)
        person.question = question
        person.put()
        
        # save to session since this person
        # may not be immediately retrievable from datastore
        session = gaesessions.get_current_session()
        session["new_person_id"] = person.key().id()
        
        return person
    
    @staticmethod
    def getPerson(question=None, nickname=None):
        person = None
        
        # check if person id stored in session
        # if so use to retrieve logged in user 
        session = gaesessions.get_current_session()
        person_id = session.pop("new_person_id") if session.has_key("new_person_id") else None
        if person_id:
            person = Person.get_by_id(person_id)
            # check if person id stored in session corresponds to inputs
            if not person:
                person = None
                helpers.log("WARNING: Person not found by id {0}".format(person_id))
            elif question and question != person.question:
                person = None
            elif nickname and nickname != person.nickname:
                person = None
        
        if not person:
            user = users.get_current_user()
            if question:
                if question.nicknameAuthentication:
                    # if no nickname provided, check session
                    if not nickname:
                        questionSessionValues = session.get(question.code)
                        nickname = questionSessionValues["nickname"] if questionSessionValues else None
                    if nickname:
                        person = Person.all().filter("question =", question).filter("nickname =", nickname).get()
                elif user is not None:
                    person = Person.all().filter("question =", question).filter("user =", user).get()
            elif user:
                person = Person.all().filter("question =", None).filter("user =", user).get()
        return person
                
    @staticmethod
    def getPersonFromClientId(client_id):
        person = None
        tokens = client_id.split("_")
        if len(tokens) > 1:
            person_id = tokens[1]
            person = Person.get_by_id(long(person_id))
        return person
                                        
    @staticmethod
    def cleanNickname(user):
        if user:
            nickname = user.nickname()
            if nickname.count("@") == 0:
                return nickname
            else:
                return nickname[:nickname.index("@")]
        else:
            return "none"
    
    @staticmethod
    def nicknameAlreadyExists(questionId, nickname):
        question = Question.getQuestionById(questionId)
        person = Person.all().filter("question =", question).filter("nickname =", nickname).get()
        return person is not None
        
    @staticmethod
    def isAdmin(requestHandler):
        return users.is_current_user_admin()
    
    @staticmethod
    def toDict(person):
        user = users.get_current_user()
        userIdentity = Person.cleanNickname(person.user) if person.user else ""
        isQuestionAuthor = user == person.question.author if user and person and person.question else False
        return {
            "nickname": person.nickname,
            "user_identity":  userIdentity if isQuestionAuthor else ""
        } 
    
    @staticmethod
    def equals(person1, person2):        
        usersMatch = person1.user == person2.user
        nicknamesMatch = person1.nickname == person2.nickname
        questionsMatch = (person1.question == None and person2.question == None) or (person1.question.code == person2.question.code)        
        return usersMatch and nicknamesMatch and questionsMatch     
                
###################
##### CLUSTER #####
###################
class Cluster(db.Model):
    text = db.StringProperty()
    question = db.ReferenceProperty(Question)
    rand = db.FloatProperty()
    date = db.DateTimeProperty(auto_now=True)
    clusterType = db.StringProperty()

    def getClusterType(self):
        return self.clusterType if self.clusterType else "words"
    
    @staticmethod
    def createCluster(text, index, questionObj, clusterType):
        if questionObj:
            clusterObj = Cluster()
            clusterObj.text = text
            clusterObj.index = index
            clusterObj.question = questionObj
            clusterObj.clusterType = clusterType
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
    def numClusters(question):
        if question:
            return Cluster.all().filter("question =", question).count()
        else:
            return 0

    @staticmethod
    def deleteAllClusters(questionObj):
        if questionObj:
            ClusterAssignment.deleteAllClusterAssignments(questionObj)
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
    author = db.ReferenceProperty(Person)
    date = db.DateTimeProperty(auto_now=True)
    text = db.StringProperty()
    cluster = db.ReferenceProperty(Cluster)
    question = db.ReferenceProperty(Question)
    rand = db.FloatProperty()

    def toDict(self):
        return {
            "id" : self.key().id(),
            "author" : Person.toDict(self.author),
            "date" : self.date,
            "text" : self.text,
            "question_code" : self.question.code
        }
    
    @staticmethod
    def getNumIdeas(question):
        return Idea.all().filter("question =", question).count() if question else 0
            
    @staticmethod
    def getIdeaById(ideaIdStr):
        ideaObj = Idea.get_by_id(int(ideaIdStr))
        return ideaObj

    @staticmethod
    def createIdea(idea, questionIdStr, person):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            if len(idea) > 500:
                idea = idea[:500]
            idea = idea.replace("\n", "")
            ideaObj = Idea()
            ideaObj.author = person
            ideaObj.text = idea
            ideaObj.question = questionObj
            if Idea.all().filter("question =", questionObj).count() == 0:
                ideaObj.rand = 1.0
            else:
                ideaObj.rand = random.random()
            ideaObj.put()
            return ideaObj

    @staticmethod
    def getRandomIdea(questionObj):
        rand = random.random()
        return Idea.all().filter("question =", questionObj).order("rand").filter("rand >", rand).get()

    @staticmethod
    def getRandomIdeas(questionObj, ideas, size=5):
        numIdeas = len(ideas) if ideas else 0
        if numIdeas >= size:
            return random.sample(ideas, size)
        else:
            helpers.log("WARNING: Cannot return {0} random ideas since only {1} ideas available".format(size, numIdeas))
            return []
    
    @staticmethod
    def assignCluster(id, clusterObj):
        """Assigns specified cluster to the specified idea"""
        ideaObj = Idea.get_by_id(id)
        if ideaObj:
            ideaObj.cluster = clusterObj
            ideaObj.put()
        return ideaObj

    @staticmethod
    def deleteAllIdeas(questionIdStr):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            IdeaTag.deleteAllTags(questionIdStr)
            IdeaAssignment.deleteAllIdeaAssignments(questionIdStr)
            SimilarIdea.deleteAllSimilarIdeas(questionIdStr)
            SimilarIdeaAssignment.deleteAllAssignments(questionIdStr)
            db.delete(Idea.all().filter("question =", questionObj))
                    
    @staticmethod
    def contains(ideas, match):
        found = False
        for idea in ideas:
            if Idea.equals(idea, match):
                found = True
                break
        return found
    
    @staticmethod
    def equals(idea1, idea2):
        textsMatch = idea1.text == idea2.text
        questionsMatch = (idea1.question == None and idea2.question == None) or (idea1.question.code == idea2.question.code)
        authorsMatch = Person.equals(idea1.author, idea2.author)
        datesMatch = idea1.date == idea2.date
        return textsMatch and questionsMatch and authorsMatch and datesMatch

#############################
##### CLUSTERASSIGNMENT #####
#############################
class ClusterAssignment(db.Model):
    author = db.ReferenceProperty(Person)
    cluster = db.ReferenceProperty(Cluster)
    question = db.ReferenceProperty(Question)

    @staticmethod
    def getAssignmentId(questionIdStr, person):
        """Determines the cluster assigned to this author"""
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            author = person
            ca = ClusterAssignment.all()
            ca = ca.filter("author =", author)
            ca = ca.filter("question =", questionObj)
            if ca.count() == 0:
                cluster = Cluster.getRandomCluster(questionIdStr)
                if cluster:
                    caObj = ClusterAssignment()
                    caObj.author = author
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
    def deleteAllClusterAssignments(questionObj):
        if questionObj:
            db.delete(ClusterAssignment.all().filter("question =", questionObj))

#############################
##### IDEAASSIGNMENT #####
#############################
class IdeaAssignment(db.Model):
    author = db.ReferenceProperty(Person)
    idea = db.ReferenceProperty(Idea)
    question = db.ReferenceProperty(Question)
    current = db.BooleanProperty(default=False)

    @staticmethod
    def getCurrentAssignment(questionObj, person):
        """Gets the current assignment (or a new one if there isn't a current one)"""
        if questionObj and person:
            ia = IdeaAssignment.all().filter("author =", person).filter("question =", questionObj).filter("current =", True).get()
            if ia:
                return ia
            else:
                return IdeaAssignment.createNewAssignment(questionObj, person)
        else:
            return None
        
    @staticmethod
    def createNewAssignment(questionObj, person):
        """Get a new random idea assignment for this author"""
        ia = None
        if questionObj:
            # First deselect any existing "current" assignment
            currents = IdeaAssignment.all().filter("author =", person).filter("question =", questionObj).filter("current =", True)
            for currentObj in currents:
                currentObj.current = False
                currentObj.put()
            
            numIdeas = Idea.all().filter("question =", questionObj).count()
            numAssignments = IdeaAssignment.all().filter("author =", person).filter("question =", questionObj).count()
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
                    assigned = (IdeaAssignment.all().filter("author =", person).filter("idea =", idea).count() > 0)
                    if assigned:
                        pass    # Whoops - already seen this idea, look for another
                    else:
                        ia = IdeaAssignment()
                        ia.author = person
                        ia.idea = idea
                        ia.question = questionObj
                        ia.current = True
                        ia.put()
                        assignmentNeeded = False
                        
            if assignmentNeeded and num_tries >= MAX_TRIES:
                helpers.log("WARNING: Random idea assignment not found. Tried {0} times.".format(MAX_TRIES))
                
        return ia if ia else None

    @staticmethod
    def deleteAllIdeaAssignments(questionIdStr):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            db.delete(IdeaAssignment.all().filter("question =", questionObj))

#############################
##### SimilarIdeaAssignment #####
#############################
class SimilarIdeaAssignment(db.Model):
    author = db.ReferenceProperty(Person)
    idea = db.ReferenceProperty(Idea)
    compareToKeys = db.ListProperty(db.Key)
    question = db.ReferenceProperty(Question)
    current = db.BooleanProperty(default=False)
    
    @property
    def compareToIdeas(self):
        return [db.get(key) for key in self.compareToKeys]

    def toDict(self):
        return {
            "author": Person.toDict(self.author),
            "idea": self.idea.toDict(),    
            "question_code": self.question.code,
            "compare_to": [idea.toDict() for idea in self.compareToIdeas],
            "current": self.current
        }
        
    @staticmethod
    def getCurrentAssignment(questionObj, person):
        """Gets the current assignment (or a new one if there isn't a current one)"""
        assignment = None
        if questionObj and person:
                assignment = SimilarIdeaAssignment.all().filter("author =", person).filter("question =", questionObj).filter("current =", True).get()
                if not assignment:
                    assignment = SimilarIdeaAssignment.createNewAssignment(questionObj, person)

        return assignment if assignment else None
            
    @staticmethod
    def createNewAssignment(questionObj, person):
        """Get a new random assignment for this author"""
        assignment = None
        if questionObj:
            # First deselect any existing "current" assignment
            SimilarIdeaAssignment.unselectAllAssignments(questionObj, person)
            
            # Get list of ideas already assigned to user (don't want to show duplicates)
            numIdeas = Idea.all().filter("question =", questionObj).count()
            userAssignments = SimilarIdeaAssignment.all().filter("author =", person).filter("question =", questionObj)
            numUserAssignments = userAssignments.count()
            
            assignmentNeeded = True
            # Randomly select ideas, but keep trying if we've already assigned this one.
            # This is a BAD algorithm if there are a lot of ideas AND individuals get a lot of assignments
            # but that seems unlikely to happen
            MAX_TRIES = 10
            num_tries = 0
            while assignmentNeeded and (numIdeas > numUserAssignments) and (num_tries < MAX_TRIES):
                num_tries += 1
                idea = Idea.getRandomIdea(questionObj)
                if idea:
                    ideasAssigned = [ userAssignment.idea for userAssignment in userAssignments ]
                    alreadyAssigned = Idea.contains(ideasAssigned, idea)
                    if alreadyAssigned:
                        pass    # Whoops - already seen this idea, look for another
                    else: 
                        otherIdeas = Idea.all().filter("question =", questionObj).filter("__key__ !=", idea.key())
                        compareToIdeas = Idea.getRandomIdeas(questionObj, list(otherIdeas), size=questionObj.numNotesForComparison)
                        if len(compareToIdeas) < questionObj.numNotesForComparison:
                            # skip if cannot find enough ideas to compare to
                            assignmentNeeded = False
                        else:                          
                            assignment = SimilarIdeaAssignment()
                            assignment.author = person
                            assignment.idea = idea
                            assignment.compareToKeys = [ idea.key() for idea in compareToIdeas ]
                            assignment.question = questionObj
                            assignment.current = True
                            assignment.put()
                            assignmentNeeded = False
                else:
                    return None
                
            if assignmentNeeded and num_tries >= MAX_TRIES:
                helpers.log("WARNING: Random idea not found. Tried {0} times.".format(MAX_TRIES))
                
        return assignment if assignment else None
        
    @staticmethod
    def unselectAllAssignments(questionObj, person):
        currents = SimilarIdeaAssignment.all().filter("author =", person).filter("question =", questionObj).filter("current =", True)
        for currentObj in currents:
            currentObj.current = False
            currentObj.put()
                
    @staticmethod
    def deleteAllAssignments(questionIdStr):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            db.delete(SimilarIdeaAssignment.all().filter("question =", questionObj))
        
######################
##### CLUSTERTAG #####
######################
class ClusterTag(db.Model):
    tag = db.StringProperty()
    question = db.ReferenceProperty(Question)
    cluster = db.ReferenceProperty(Cluster)
    author = db.ReferenceProperty(Person)
    date = db.DateTimeProperty(auto_now=True)

    @staticmethod
    def createClusterTag(tagStr, cluster_id, questionIdStr, person):
        questionObj = Question.getQuestionById(questionIdStr)
        clusterObj = Cluster.get_by_id(cluster_id)
        tagObj = None
        if clusterObj and questionObj:
            tagObj = ClusterTag()
            tagObj.tag = tagStr
            tagObj.question = questionObj
            tagObj.cluster = clusterObj
            tagObj.author = person
            tagObj.put()
        return tagObj

    @staticmethod
    def getTags(questionIdStr):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            tags = ClusterTag.all().filter("question =", questionObj)
            return tags
        else:
            return None

    @staticmethod
    def getTagsByUser(questionIdStr, person):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            tags = ClusterTag.all().filter("question =", questionObj).filter("author = ", person)
            return tags
        else:
            return None

    @staticmethod
    def deleteAllTags(questionObj):
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
    author = db.ReferenceProperty(Person)
    date = db.DateTimeProperty(auto_now=True)

    @staticmethod
    def createIdeaTag(tagStr, idea_id, questionIdStr, person):
        questionObj = Question.getQuestionById(questionIdStr)
        ideaObj = Idea.get_by_id(idea_id)
        if ideaObj and questionObj:
            tagObj = IdeaTag()
            tagObj.tag = tagStr
            tagObj.question = questionObj
            tagObj.idea = ideaObj
            tagObj.author = person
            tagObj.put()
        return tagObj

    @staticmethod
    def getTags(questionIdStr):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            tags = IdeaTag.all().filter("question =", questionObj)
            return tags
        else:
            return None

    @staticmethod
    def getTagsByUser(ideaIdStr, person):
        ideaObj = Idea.getIdeaById(ideaIdStr)
        if ideaObj:
            tags = IdeaTag.all().filter("idea =", ideaObj).filter("author = ", person)
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
##### SIMILARIDEA #####
######################
class SimilarIdea(db.Model):
    question = db.ReferenceProperty(Question)
    idea = db.ReferenceProperty(Idea, collection_name='idea_similaridea_set')
    similar = db.ReferenceProperty(Idea, collection_name='similar_similaridea_set')
    author = db.ReferenceProperty(Person)
    date = db.DateTimeProperty(auto_now=True)
 
    def toDict(self):
        return {
            "idea" : self.idea.toDict(),
            "similar" : self.similar.toDict(),
            "author" : Person.toDict(self.author),
            "date" : self.date,
            "question_code" : self.question.code
        }
        
    @staticmethod
    def createSimilarIdea(idea_id, similar_idea_id, question, person):
        idea = Idea.get_by_id(idea_id)
        similarIdea = Idea.get_by_id(similar_idea_id)
        similarObj = None
        if idea and similarIdea and question:
            similarObj = SimilarIdea()
            similarObj.question = question
            similarObj.idea = idea
            similarObj.similar = similarIdea
            similarObj.author = person
            similarObj.put()
        return similarObj
 
    @staticmethod
    def getAllSimilarIdeas(question):
        return SimilarIdea.all().filter("question =", question) if question else None
        
    @staticmethod
    def getSimilarIdeasByUser(ideaIdStr, person):
        ideaObj = Idea.getIdeaById(ideaIdStr)
        if ideaObj:
            similarIdeas = SimilarIdea.all().filter("idea =", ideaObj).filter("author = ", person)
            return similarIdeas
        else:
            return None
 
    @staticmethod
    def deleteAllSimilarIdeas(questionIdStr):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            similarIdeas = SimilarIdea.all().filter("question =", questionObj)
            db.delete(similarIdeas)
            
###################
##### CASCADE #####
###################

# BEHAVIOR: cascade jobs created when phase enabled
# BEHAVIOR: when cascade params are changed, cascade jobs are re-created
# BEHAVIOR: step 1 - displays up to t ideas at a time
# BEHAVIOR: step 1 - does not remove any ideas authored by person, skipped or *seen before*
# BEHAVIOR: step 1 - k jobs performed to create a category for an idea; should k categories be required for each idea? or ok to skip?
# BEHAVIOR: step 1 - user currently allowed to do as many jobs per step as they can

# TODO/BUG: datastore updates not always searchable in time for current user; how to fix?
# TODO/BUG: how to ensure updates available to all users in time; model blocking? transactions?
# TODO: warn admin that any previous cascade data will be lost when jobs re-created
# TODO: need to add timestamps to record how long each step takes
# TODO: when step changes, need to notify waiting users
# TODO: ask users to suggest category during idea creation
# TODO: would it be better to create task and then keep track of k responses (instead of repeating task)
# TODO: step 1 - remove any ideas user has authored, skipped, or already created categories for
# TODO: step 1 - need to release assignments after some period of inactivity
# TODO: step 1 - need to better randomize ideas presented in jobs 
# TODO: step 1 - should users be asked once more to create categories for any ideas with no categories
# TODO: step 2 - what if only one category suggested - still vote?
# TODO: step 2 - categories that only differ by case should be shown together
# TODO: step 2 - user should only vote once per idea
# TODO: step 2 - how should voting threshold be determined (based on k?)

###################

NONE_OF_THE_ABOVE = "None of the above"
DEFAULT_VOTING_THRESHOLD = 2

class Cascade(db.Model):
    question = db.ReferenceProperty(Question)
    step = db.IntegerProperty(default=1)
    k = db.IntegerProperty(default=5)
    m = db.IntegerProperty(default=32)
    t = db.IntegerProperty(default=8)

    def setOptions(self, k, m, t):
        optionsChanged = self.k != k or self.m != m or self.t != t
        if optionsChanged:
            self.k = k
            self.m = m
            self.t = t
            self.put()
            
            # TODO/BUG CHECK: need to verify new parameters are being used when jobs re-created
            Cascade.init(self.question)
        
    @staticmethod
    def init(question, step=1):        
        helpers.log("CascadeJob.init: step={0}".format(step))
        cascade = Cascade.getCascadeForQuestion(question)        
        if step == 1:
            Cascade.deleteJobs(question)
            if cascade.step != 1:
                cascade.step = 1
                cascade.put()
            cascade.createJobsForStep1()
        
        elif step == 2:
            cascade.createJobsForStep2()
            
        elif step == 3:
            cascade.createJobsForStep3()

        elif step == 4:
            # TODO
            pass
        
        elif step == 5:
            # TODO
            pass
        
    def createJobsForStep1(self):
        task_group = []
        idea_keys = Idea.all(keys_only=True).filter("question = ", self.question).order("rand")
        for i in range(self.k):
            for idea_key in idea_keys:
                if len(task_group) == self.t:
                    task = CascadeSuggestCategoryTask()
                    task.question = self.question
                    task.idea_keys = task_group
                    task.put()
                    
                    job = CascadeJob()
                    job.question = self.question
                    job.cascade = self
                    job.step = 1
                    job.task = task
                    job.worker = None
                    job.put()
                    
                    task_group = []
                
                task_group.append(idea_key)
        
        if len(task_group) > 0:
            task = CascadeSuggestCategoryTask()
            task.question = self.question
            task.idea_keys = task_group
            task.put()
                    
            job = CascadeJob()
            job.question = self.question
            job.cascade = self
            job.step = 1
            job.task = task
            job.worker = None
            job.put()
                                
    def createJobsForStep2(self):
        suggestedCategories = {}
        step1 = CascadeJob.all().filter("question =", self.question).filter("step =", 1)
        for job in step1:
            i = 0
            for idea in job.task.ideas:
                ideaId = idea.key().id()
                category = job.task.categories[i].strip()
                if category != "":
                    if ideaId not in suggestedCategories:
                        suggestedCategories[ideaId] = { "idea": idea, "categories": [] }
                        
                    if category not in suggestedCategories[ideaId]["categories"]:
                        suggestedCategories[ideaId]["categories"].append(category)
                i += 1
                
        # TODO: improve by saving only 1 version of task in datastore, but save result in job?
        for i in range(self.k):
            for ideaId in suggestedCategories:
                task = CascadeSelectBestTask()
                task.question = self.question
                task.idea = suggestedCategories[ideaId]["idea"]
                task.categories = suggestedCategories[ideaId]["categories"]
                if i==0: task.categories.append(NONE_OF_THE_ABOVE)
                task.put()
                    
                job = CascadeJob()
                job.question = self.question
                job.cascade = self
                job.step = 2
                job.task = task
                job.worker = None
                job.put()
      
    def createJobsForStep3(self):
        helpers.log("createJobsForStep3")
        groupedVotes = {}
        step2 = CascadeJob.all().filter("question =", self.question).filter("step =", 2)
        for job in step2:
            idea = job.task.idea
            ideaId = idea.key().id()
            category = job.task.categories[job.task.bestCategoryIndex] if job.task.bestCategoryIndex is not None else None
            if category:
                if ideaId not in groupedVotes:                    
                    groupedVotes[ideaId] = { "idea": idea, "votes": {} }
                     
                if category not in groupedVotes[ideaId]["votes"]:
                    groupedVotes[ideaId]["votes"][category] = 0
                groupedVotes[ideaId]["votes"][category] += 1
         
        # TODO: how should the voting threshold be calculated; k=5 and voting threshold=2 by default
        votingThreshold = DEFAULT_VOTING_THRESHOLD if self.k > 3 else 1

        bestCategories = []
        for ideaId in groupedVotes:
            for category in groupedVotes[ideaId]["votes"]:
                numVotesForCategory = groupedVotes[ideaId]["votes"][category]
                if numVotesForCategory >= votingThreshold:
                    if category not in bestCategories:
                        bestCategories.append(category)

        # TODO: currently using t for group size; should be separate variable?
        task_group = { "idea_keys": [], "categories": [] }
        idea_keys = Idea.all(keys_only=True).filter("question = ", self.question).order("rand")
        for i in range(self.k):
            for idea_key in idea_keys:
                for category in bestCategories:
                    if len(task_group["idea_keys"]) == self.t:
                        task = CascadeCategoryFitTask()
                        task.question = self.question
                        task.idea_keys = task_group["idea_keys"]
                        task.categories = task_group["categories"]
                        task.put()
                        
                        job = CascadeJob()
                        job.question = self.question
                        job.cascade = self
                        job.step = 3
                        job.task = task
                        job.worker = None
                        job.put()
                        
                        task_group = { "idea_keys": [], "categories": [] }

                    task_group["idea_keys"].append(idea_key)
                    task_group["categories"].append(category)
    
        # TODO: move to function?
        if len(task_group["idea_keys"]) > 0:
            task = CascadeSuggestCategoryTask()
            task.question = self.question
            task.idea_keys = task_group["idea_keys"]
            task.categories = task_group["categories"]
            task.put()
                    
            job = CascadeJob()
            job.question = self.question
            job.cascade = self
            job.step = 3
            job.task = task
            job.worker = None
            job.put()
                                                    
    @staticmethod
    def getCascadeForQuestion(question):
        cascade = Cascade.all().filter("question =", question).get()            
        if not cascade:
            cascade = Cascade()
            cascade.question = question
            cascade.put()
        return cascade
                       
    @staticmethod         
    def deleteJobs(question):
        db.delete(CascadeJob().all().filter("question =", question))
        db.delete(CascadeSuggestCategoryTask().all().filter("question =", question))
        db.delete(CascadeSelectBestTask().all().filter("question = ", question))
        db.delete(CascadeCategoryFitTask().all().filter("question = ", question))
        helpers.log("WARNING: Remember to delete cascade jobs for steps 3b-5")
                 
class CascadeTask(db.Model): 
    question = db.ReferenceProperty(Question)
   
    def toDict(self):
        return {
            "question_id" : self.question.code
        }
    
class CascadeSuggestCategoryTask(CascadeTask):
    idea_keys = db.ListProperty(db.Key)
    categories = db.StringListProperty(default=[])
    
    @property
    def ideas(self):
        return db.get(self.idea_keys)
    
    def completed(self, data):
        self.categories = data["categories"]
        self.put()
        
    def toDict(self): 
        dict = CascadeTask.toDict(self)
        dict["ideas"] = [ idea.toDict() for idea in self.ideas ]
        dict["categories"] = self.categories
        return dict
        
class CascadeSelectBestTask(CascadeTask):
    idea = db.ReferenceProperty(Idea)
    categories = db.StringListProperty(default=[])
    bestCategoryIndex = db.IntegerProperty(default=None)
    
    def completed(self, data):
        bestCategoryIndex = int(data["best_category_index"])
        if bestCategoryIndex != -1 and self.categories[bestCategoryIndex] != NONE_OF_THE_ABOVE:
            self.bestCategoryIndex = bestCategoryIndex
            self.put()
        
    def toDict(self): 
        dict = CascadeTask.toDict(self)
        dict["idea"] = self.idea.toDict()
        dict["categories"] = self.categories
        dict["best_category_index"] = self.bestCategoryIndex
        return dict

# TODO: improve by separating out class that just contains single idea, category, and fit vote; same for CascadeSuggestCategoryTask
class CascadeCategoryFitTask(CascadeTask):
    idea_keys = db.ListProperty(db.Key)
    categories = db.StringListProperty(default=[])
    categoryFits = db.ListProperty(bool)
    
    @property
    def ideas(self):
        return db.get(self.idea_keys)
    
    def completed(self, data):
        self.categoryFits = data["category_fits"]
        self.put()
        
    def toDict(self): 
        dict = CascadeTask.toDict(self)
        dict["ideas"] = [ idea.toDict() for idea in self.ideas ]
        dict["categories"] = self.categories
        dict["category_fits"] = self.categoryFits
        return dict
            
class CascadeJob(db.Model):
    question = db.ReferenceProperty(Question)
    cascade = db.ReferenceProperty(Cascade)
    step = db.IntegerProperty() # step for this job, current step in progress stored in Cascade class
    task = db.ReferenceProperty(CascadeTask)
    worker = db.ReferenceProperty(Person)
    status = db.IntegerProperty(default=0)

    @staticmethod
    def getJob(question, step, worker):  
                        
        # check if job already assigned
        job = CascadeJob.all().filter("question =", question).filter("step =", step).filter("worker =", worker).filter("status =", 0).get()

        # if not, get new assignment
        if not job:  
            job = CascadeJob.all().filter("question =", question).filter("step =", step).filter("worker =", None).get()
            if job:
                job.worker = worker
                jobKey = job.put()
                
                # TODO/HACK - need to guarantee datastore updated and searchable before next job requested
                job = CascadeJob.get_by_id(jobKey.id()) 
            
            # check if all jobs completed for this step, and if so, advance to next step
            if not job and step < 5:
                numJobsRemaining = CascadeJob.all().filter("question =", question).filter("step =", step).filter("status =", 0).count()
                isStepComplete = numJobsRemaining == 0
                if isStepComplete:
                    helpers.log("Step {0} complete".format(step))
                    cascade = Cascade.getCascadeForQuestion(question)
                    cascade.step += 1
                    cascade.put()
                                            
                    # TODO: check if jobs created and searchable before getJob called
                    # TODO: need to notify waiting users that new jobs available
                    # create jobs for this step
                    cascade.init(question, step+1)
                    
                    job = CascadeJob.getJob(question, step+1, worker)
        
        helpers.log("job={0}".format(job.toDict() if job else None))
        return job

    def completed(self, data):
        self.task.completed(data)
        self.status = 1
        key = self.put()
                    
        # TODO/HACK - seems to increase odds of updated values being in datastore before CascadeJob.getJob called
        # otherwise, job only changing every other time submit pressed (at least on localhost)
        job = CascadeJob.get_by_id(key.id())
        
    def toDict(self):
        return {
            "id" : self.key().id(),
            "question_code": self.question.code,
            "step": self.step,
            "task": self.task.toDict(),    
            "worker": Person.toDict(self.worker),
            "status": self.status
        }