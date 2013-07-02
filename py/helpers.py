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
import constants

def log(msg):
    import logging
    if constants.ENABLE_DEBUG_LOGGING:
        logging.getLogger().info(msg)

def isRunningLocally():
    import os
    return not os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine')

def toJson(data):        
    import json
    return json.dumps(data, default=_jsonHandler)

def fromJson(data):
    import json
    return json.loads(data) if data else None
  
def _jsonHandler(o):
    from datetime import datetime
    if isinstance(o, datetime):
        return o.strftime("%B %d, %Y %H:%M:%S")
    else:
        raise TypeError(repr(o))
    
def cleanWord(word):
    word = word.lower()
    word = word.strip("`~!@#$%^&*()-_=+|;:',<.>/?")
    if isStopWord(word):
        word = ""
    return word
    
def isStopWord(word):
    return (word in constants.STOP_WORDS)