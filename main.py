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
    ('/nickname_page/([0-9]+)', NicknameLoginPageHandler),
    ('/idea/([0-9]+)', IdeaPageHandler),
    ('/cascade/([0-9]+)', CascadePageHandler),
    ('/results/([0-9]+)', ResultsPageHandler),
    ('/results_test/([0-9]+)', ResultsTestPageHandler),
    ('/admin', AdminPageHandler),
    ('/admin/([0-9]+)', AdminPageHandler),
        
    ('/login', LoginHandler),
    ('/login/([0-9]+)', LoginHandler),
	('/nickname_login', NicknameLoginHandler),
	('/question_login', QuestionLoginHandler),
	('/logout', LogoutHandler),
    ('/logout/([0-9]+)', LogoutHandler),
    ('/nickname', NicknameHandler),
	('/new_question', NewQuestionHandler),
	('/edit_question', EditQuestionHandler),
    ('/copy_question', CopyQuestionHandler),
    ('/delete_question', DeleteQuestionHandler),
    ('/download_question', DownloadQuestionHandler),
    ('/set_active', ActiveHandler),
    ('/new_idea', NewIdeaHandler),
	('/cascade_job', CascadeJobHandler),
    ('/cascade_save_and_get_next_job', CascadeSaveAndGetNextJobHandler),
    ('/cancel_cascade_job', CancelCascadeJobHandler),
    ('/generate_categories', CategoryHandler),
    ('/generate_test_categories', TestCategoryHandler),
    ('/discuss_idea', DiscussIdeaHandler),
    ('/query', QueryHandler),
	
	('/_ah/channel/connected/', ChannelConnectedHandler),
	('/_ah/channel/disconnected/', ChannelDisconnectedHandler)
    ],
    debug=True)
