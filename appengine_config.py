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

# Key generated with os.urandom(64).encode('hex')
COOKIE_KEY = '64b4587b7e70ca6f43592bbf5dd0870534e4b17d473cc5bc1aa8bb31f6333090cb60ca7482dbf8283ccff80a8ae0645d70adec72add7e0f38bbb4aedaef514bc'

def webapp_add_wsgi_middleware(app):
	from lib.gaesessions import SessionMiddleware
	#from google.appengine.ext.appstats import recording
	app = SessionMiddleware(app, cookie_key=COOKIE_KEY)
	#app = recording.appstats_wsgi_middleware(app)
	return app
