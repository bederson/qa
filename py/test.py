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
import MySQLdb
from multiprocessing import Process

dbConnection = MySQLdb.connect("localhost", constants.LOCAL_DB_USER, constants.LOCAL_DB_PWD, constants.DATABASE_NAME)
dbCursor = dbConnection.cursor(MySQLdb.cursors.DictCursor)

def updateTest1():
	for i in range(300):
		sql = "update users set nickname='test1-{0}' where id=107".format(i)
		dbCursor.execute(sql)
		dbConnection.commit()

def updateTest2():
	for i in range(300):
		sql = "update users set nickname='test2-{0}' where id=107".format(i)
		dbCursor.execute(sql)
		dbConnection.commit()

def updateTest3():
	for i in range(300):
		sql = "update users set nickname='test3-{0}' where id=107".format(i)
		dbCursor.execute(sql)
		dbConnection.commit()

def updateInParallel(*fns):
	proc = []
	for fn in fns:
		p = Process(target=fn)
		p.start()
		proc.append(p)
	for p in proc:
		p.join()

updateInParallel(updateTest1, updateTest2, updateTest3, updateTest1, updateTest2, updateTest3, updateTest1, updateTest2, updateTest3, updateTest1, updateTest2, updateTest3);
print("updates complete")
dbCursor.close()
dbConnection.close()
