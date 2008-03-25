__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


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