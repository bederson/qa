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

# Functions that query the datastore may not include a newly put() object
# if called immediately after the object is created (ok if updated).  
# Use an object's key id if you need to retrieve an object immediately after 
# stored. This behavior was noticed when Question.getQuestionById(code) was 
# called immediately after a new question was created.  Same behavior
# noticed when Person created for the first time.

import helpers    
import logging
import random
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
    date = db.DateTimeProperty(auto_now=True)
    numNotesToTagPerPerson = db.IntegerProperty(default=5)
    numNotesToComparePerPerson = db.IntegerProperty(default=5)
    numNotesForComparison = db.IntegerProperty(default=5)
    nicknameAuthentication = db.BooleanProperty(default=False)

    @staticmethod
    def getQuestionById(code):
        # this function retrieves question by question code, not datastore id
        return Question.all().filter("code = ", code).get() if code is not None else None

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

    @staticmethod
    def editQuestion(questionIdStr, title, question, nicknameAuthentication=False):
        questionObj = Question.getQuestionById(questionIdStr)
        if questionObj:
            questionObj.title = title
            questionObj.question = question
            questionObj.nicknameAuthentication = nicknameAuthentication
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
            db.delete(Person.all().filter("question =", questionObj))
            db.delete(questionObj)
            
    @staticmethod
    def getPhase(questionObj):
        return questionObj.phase if questionObj else None

    @staticmethod
    def setPhase(phase, questionObj):
        if questionObj:
            questionObj.phase = phase
            questionObj.put()

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
            "phase": self.phase,
            "num_tags_by_cluster": self.getNumTagsByCluster(),
            "num_tags_by_idea": self.getNumTagsByIdea(),
            "num_similar_ideas": self.getNumSimilarIdeas()
        } 

######################
##### Person #####
######################
class Person(db.Model):
    client_ids = db.StringListProperty(default=[])
    user = db.UserProperty(auto_current_user_add=True)
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
        # person user added automatically
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
        userIdentity = Person.cleanNickname(person.user) if user else ""
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
    def deleteAllClusterAssignments(questionIdStr):
        questionObj = Question.getQuestionById(questionIdStr)
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