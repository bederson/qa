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

import webapp2
from py.handlers import *

app = webapp2.WSGIApplication([
	('/', MainPageHandler),
    ('/idea', IdeaPageHandler),
	('/results', ResultsPageHandler),
	('/admin', AdminPageHandler),
	('/tag', TagPageHandler),

	('/query', QueryHandler),
	('/newquestion', NewQuestionHandler),
	('/editquestion', EditQuestionHandler),
	('/newidea', NewIdeaHandler),
	('/newclustertag', NewClusterTagHandler),
	('/newideatag', NewIdeaTagHandler),
	('/delete', DeleteHandler),
	('/cluster', ClusterHandler),
	('/getideaassignment', IdeaAssignmentHandler),
	('/set_phase', PhaseHandler),
	('/set_num_notes_to_tag_per_person', NumNotesToTagPerPersonHandler),
	
	('/migrate', MigrateHandler),

	('/_ah/channel/connected/', ConnectedHandler),
	('/_ah/channel/disconnected/', DisconnectedHandler)
], debug=True)
