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
#	  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import webapp2

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

from py.handlers import *

app = webapp2.WSGIApplication([
	('/', MainPageHandler),
    ('/admin', AdminPageHandler),
    ('/idea', IdeaPageHandler),
    ('/loginpage', LoginPageHandler),
	('/results', ResultsPageHandler),
	('/tag', TagPageHandler),
    ('/similar', SimilarPageHandler),
    ('/cascade', CascadePageHandler),

	('/login', LoginHandler),
    ('/logout', LogoutHandler),
    ('/nickname', NicknameHandler),
	('/query', QueryHandler),
	('/newquestion', NewQuestionHandler),
	('/editquestion', EditQuestionHandler),
	('/newidea', NewIdeaHandler),
	('/newclustertag', NewClusterTagHandler),
	('/newideatag', NewIdeaTagHandler),
	('/delete', DeleteHandler),
	('/cluster', ClusterHandler),
	('/getideaassignment', IdeaAssignmentHandler),
    ('/similar_idea', SimilarIdeaHandler),
	('/set_phase', PhaseHandler),
	('/set_num_notes_to_tag_per_person', NumNotesToTagPerPersonHandler),
    ('/set_compare_notes_options', CompareNotesOptionsHandler),
    ('/set_cascade_options', CascadeOptionsHandler),
	
	('/migrate', MigrateHandler),

	('/_ah/channel/connected/', ConnectedHandler),
	('/_ah/channel/disconnected/', DisconnectedHandler)
    ],
    debug=True)
