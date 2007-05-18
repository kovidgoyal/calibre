##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


'''
Define a threaded interface for working with devices.
'''

import threading, Queue

from libprs500.devices.device import Device
from libprs500.devices.prs500.driver import PRS500

class DeviceManager(object):
    
    def __init__(self):
        self.devices = []
        self.device_jobs = Queue(0)


class Job(object):
    count = 0
    def __init__(self, func, args):
        self.completed = False
        self.exception = None
        

class Worker(threading.Thread):
    
    def __init__(self, jobs):        
        self.jobs = jobs
        self.results = []
        threading.Thread.__init__(self)
        self.setDaemon(True)
        
    def run(self):
        '''Thread loops taking jobs from the queue as they become available'''
        while True:
            job = self.jobs.get(True, None)
            # Do job
            self.jobs.task_done()