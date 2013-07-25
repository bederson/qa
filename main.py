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


import os
import sys
import webapp2
from py.handlers import *

sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

app = webapp2.WSGIApplication([
	('/', MainPageHandler),
    ('/nickname_page', NicknameLoginPageHandler),
    ('/idea', IdeaPageHandler),
    ('/cascade', CascadePageHandler),
    ('/results', ResultsPageHandler),
    ('/admin', AdminPageHandler),

    ('/login', LoginHandler),
	('/nickname_login', NicknameLoginHandler),
	('/question_login', QuestionLoginHandler),
    ('/logout', LogoutHandler),
    ('/nickname', NicknameHandler),
	('/new_question', NewQuestionHandler),
	('/edit_question', EditQuestionHandler),
    ('/delete_question', DeleteQuestionHandler),
    ('/download_question', DownloadQuestionHandler),
    ('/set_active', ActiveHandler),
    ('/set_phase', PhaseHandler),
    ('/set_cascade_options', CascadeOptionsHandler),
    ('/cascade_init_step', CascadeInitStepHandler),
	('/cascade_job', CascadeJobHandler),
    ('/cancel_cascade_job', CancelCascadeJobHandler),
    ('/new_idea', NewIdeaHandler),
    ('/query', QueryHandler),
	
	('/_ah/channel/connected/', ChannelConnectedHandler),
	('/_ah/channel/disconnected/', ChannelDisconnectedHandler)
    ],
    debug=True)
