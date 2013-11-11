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
import StringIO
from google.appengine.api import memcache

def log(msg):
    import logging
    if constants.ENABLE_DEBUG_LOGGING:
        logging.getLogger().info(msg)

def isRunningLocally():
    import os
    return not os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine')

def allowDuplicateJobs():
    return constants.ALLOW_DUPLICATE_TASKS_WHEN_RUNNING_LOCALLY and isRunningLocally();
    
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
    # characters only stripped from ends
    word = word.strip("`~!@#$%^&*()-_=+|;:',<.>/?")
    if isStopWord(word):
        word = ""
    return word
    
def isStopWord(word):
    return (word in constants.STOP_WORDS)

def intersect(a, b):
    return list(set(a) & set(b))

def union(a, b):
    return list(set(a) | set(b))

def saveToMemcache(key, value):
    client = memcache.Client()
    MAX_RETRIES = 10    
    i = 0
    while i <= MAX_RETRIES: # Retry loop
        keyValue = client.gets(key)
        if keyValue is None:
            client.add(key, value)
            break
        else:
            if client.cas(key, value):
                break
        i += 1
        if i > MAX_RETRIES:
            log("WARNING: Unable to save value to memcache")
        
# UnicodeWriter class was taken directly from Python documentation for the csv module.
# (c) Copyright 1990-2011, Python Software Foundation
# Licensed under same license as Python itself.
# Slightly modified by Alex Quinn on 12-12-2011.
class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """
    import csv

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        import codecs, csv
        # Redirect output to a queue
        self.queue = StringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([unicode(s).encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)