##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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

from PyQt4.QtCore import QAbstractTableModel, QMutex, QObject, SIGNAL

from libprs500.gui2.device import DeviceJob

class JobException(Exception):
    pass

class JobManager(QAbstractTableModel):
    
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.jobs = {}
        self.next_id = 0
        self.job_create_lock = QMutex()
        self.job_remove_lock = QMutex()
        self.device_lock = QMutex()
        self.cleanup_lock = QMutex()
        self.cleanup = {}
        
    def create_job(self, job_class, lock, *args, **kwargs):
        self.job_create_lock.lock()
        try:
            self.next_id += 1
            job = job_class(self.next_id, lock, *args, **kwargs)
            QObject.connect(job, SIGNAL('finished()'), self.cleanup_jobs)
            self.jobs[self.next_id] = job
            self.emit(SIGNAL('job_added(int)'), self.next_id)
            return job
        finally:
            self.job_create_lock.unlock()
    
    def run_device_job(self, slot, callable, *args, **kwargs):
        '''
        Run a job to communicate with the device.
        @param slot: The function to call with the job result. It is called with
        the parameters id, result, exception, formatted_traceback
        @param callable: The function to call to communicate with the device.
        @param args: The arguments to pass to callable
        @param kwargs: The keyword arguments to pass to callable
        '''
        job = self.create_job(DeviceJob, self.device_lock, callable, *args, **kwargs)        
        QObject.connect(job, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                        self.job_done)
        if slot:
            QObject.connect(job, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                            slot)
        job.start()
        return job.id
        
    def job_done(self, id, *args, **kwargs):
        '''
        Slot that is called when a job is completed.
        '''
        self.job_remove_lock.lock()
        try:
            job = self.jobs.pop(id)
            self.cleanup_lock.lock()
            self.cleanup[id] = job            
            self.cleanup_lock.unlock()
            if len(self.jobs.keys()) == 0:
                self.emit(SIGNAL('no_more_jobs()'))
        finally:
            self.job_remove_lock.unlock()
        
    def cleanup_jobs(self):
        self.cleanup_lock.lock()
        toast = []
        for id in self.cleanup.keys():
            if not self.cleanup[id].isRunning():
                toast.append(id)
        for id in toast:
            self.cleanup.pop(id)
        self.cleanup_lock.unlock()
        