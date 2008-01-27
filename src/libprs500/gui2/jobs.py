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
import traceback, logging

from PyQt4.QtCore import QAbstractTableModel, QMutex, QObject, SIGNAL, Qt, \
                         QVariant, QThread, QModelIndex, QSettings
from PyQt4.QtGui import QIcon

from libprs500.gui2 import NONE
from libprs500.parallel import Server

class JobException(Exception):
    pass

class Job(QThread):
    ''' Class to run a function in a separate thread with optional mutex based locking.'''
    def __init__(self, id, description, mutex, func, *args, **kwargs):
        '''        
        @param id: Number. Id of this thread.
        @param description: String. Description of this job.
        @param mutex: A QMutex or None. Is locked before function is run.
        @param func: A callable that should be executed in this thread.
        '''
        QThread.__init__(self)
        self.id = id
        self.func = func
        self.description = description if description else 'Device Job #' + str(self.id)
        self.args = args
        self.kwargs = kwargs
        self.mutex = mutex
        self.result = None
        self.percent_done = 0
        self.logger = logging.getLogger('Job #'+str(id))
        self.logger.setLevel(logging.DEBUG)
        self.is_locked = False
        self.log = None
        
        
    def lock(self):
        if self.mutex is not None:
            self.is_locked = True
            self.mutex.lock()
            self.is_locked = False
            
            
    def unlock(self):
        if self.mutex is not None:
            self.mutex.unlock()
            self.is_locked = False
    
    def progress_update(self, val):
        self.percent_done = val
        self.emit(SIGNAL('status_update(int, int)'), self.id, int(val))

class DeviceJob(Job):
    '''
    Jobs that involve communication with the device. Synchronous.
    '''
    def run(self):
        self.lock()
        last_traceback, exception = None, None
        try:
            try:
                self.result = self.func(self.progress_update, *self.args, **self.kwargs)
            except Exception, err:
                exception = err
                last_traceback = traceback.format_exc()            
        finally:
            self.unlock()
            self.emit(SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'), 
                      self.id, self.description, self.result, exception, last_traceback)
        
MPServer = None
class ConversionJob(Job):
    ''' Jobs that involve conversion of content. Synchronous. '''
    def run(self):
        self.lock()
        last_traceback, exception = None, None
        try:
            try:
                self.result, exception, last_traceback, self.log = \
                    MPServer.run(self.id, self.func, self.args, self.kwargs)
            except Exception, err:
                last_traceback = traceback.format_exc()
                exception = (exception.__class__.__name__, unicode(str(err), 'utf8', 'replace'))                        
        finally:
            self.unlock()
            self.emit(SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'), 
                      self.id, self.description, self.result, exception, last_traceback, self.log)
            
        

class JobManager(QAbstractTableModel):
    
    PRIORITY = {'Idle'  : QThread.IdlePriority,
                'Lowest': QThread.LowestPriority,
                'Low'   : QThread.LowPriority,
                'Normal': QThread.NormalPriority 
                }
    
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.jobs = {}
        self.next_id = 0
        self.job_create_lock = QMutex()
        self.job_remove_lock = QMutex()
        self.device_lock = QMutex()
        self.conversion_lock = QMutex()
        self.cleanup_lock = QMutex()
        self.cleanup = {}
        self.device_job_icon = QVariant(QIcon(':/images/reader.svg'))
        self.job_icon        = QVariant(QIcon(':/images/jobs.svg'))
        global MPServer
        MPServer = Server()
        
    def terminate_device_jobs(self):
        changed = False
        for key in self.jobs.keys():
            if isinstance(self.jobs[key], DeviceJob):
                changed = True
                job = self.jobs.pop(key)
                job.terminate()
                job.mutex.unlock()
                self.emit(SIGNAL('job_done(int)'), job.id)
        if changed:
            self.reset()
    
    def create_job(self, job_class, description, lock, *args, **kwargs):
        self.job_create_lock.lock()
        try:
            self.next_id += 1
            job = job_class(self.next_id, description, lock, *args, **kwargs)
            QObject.connect(job, SIGNAL('finished()'), self.cleanup_jobs, Qt.QueuedConnection)
            QObject.connect(job, SIGNAL('status_update(int, int)'), self.status_update, Qt.QueuedConnection)
            self.beginInsertRows(QModelIndex(), len(self.jobs), len(self.jobs))
            self.jobs[self.next_id] = job
            self.endInsertRows()
            self.emit(SIGNAL('job_added(int)'), self.next_id)
            return job
        finally:
            self.job_create_lock.unlock()
    
    def has_device_jobs(self):
        for job in self.jobs.values():
            if isinstance(job, DeviceJob):
                return True
        return False
    
    def has_jobs(self):
        return len(self.jobs.values()) > 0
    
    def run_conversion_job(self, slot, callable, args=[], **kwargs):
        '''
        Run a conversion job.
        @param slot: The function to call with the job result. 
        @param callable: The function to call to communicate with the device.
        @param args: The arguments to pass to callable
        @param kwargs: The keyword arguments to pass to callable
        '''
        desc = kwargs.pop('job_description', '')
        job = self.create_job(ConversionJob, desc, self.conversion_lock, 
                              callable, *args, **kwargs)
        QObject.connect(job, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                        self.job_done, Qt.QueuedConnection)
        if slot:
            QObject.connect(job, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                            slot, Qt.QueuedConnection)
        priority = self.PRIORITY[str(QSettings().value('conversion job priority', 
                            QVariant('Normal')).toString())]
        job.start(priority)
        return job.id
    
    def run_device_job(self, slot, callable, *args, **kwargs):
        '''
        Run a job to communicate with the device.
        @param slot: The function to call with the job result. 
        @param callable: The function to call to communicate with the device.
        @param args: The arguments to pass to callable
        @param kwargs: The keyword arguments to pass to callable
        '''
        desc = callable.__doc__ if callable.__doc__ else ''
        desc += kwargs.pop('job_extra_description', '')
        job = self.create_job(DeviceJob, desc, self.device_lock, callable, *args, **kwargs)        
        QObject.connect(job, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                        self.job_done, Qt.QueuedConnection)
        if slot:
            QObject.connect(job, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                            slot, Qt.QueuedConnection)
        job.start()
        return job.id
        
    def job_done(self, id, *args, **kwargs):
        '''
        Slot that is called when a job is completed.
        '''
        keys = self.jobs.keys()
        if not id in keys: # Terminated job
            return
        self.job_remove_lock.lock()
        try:
            keys.sort()
            idx = keys.index(id)
            self.beginRemoveRows(QModelIndex(), idx, idx)
            job = self.jobs.pop(id)
            self.endRemoveRows()
            self.cleanup_lock.lock()
            self.cleanup[id] = job            
            self.cleanup_lock.unlock()
            self.emit(SIGNAL('job_done(int)'), id)            
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
        
        
    def rowCount(self, parent):
        return len(self.jobs)    
    
    def columnCount(self, parent):
        return 3
    
    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        if orientation == Qt.Horizontal:      
            if   section == 0: text = _("Job")
            elif section == 1: text = _("Status")
            elif section == 2: text = _("Progress")
            return QVariant(text)
        else: 
            return QVariant(section+1)
        
    def data(self, index, role):
        if role not in (Qt.DisplayRole, Qt.DecorationRole):
            return NONE
        row, col = index.row(), index.column()
        keys = self.jobs.keys()
        keys.sort()
        job = self.jobs[keys[row]]
        if role == Qt.DisplayRole:            
            if col == 0:
                return QVariant(job.description)
            if col == 1:
                status = _('Waiting')
                if job.isRunning() and not job.is_locked:
                    status = _('Working')
                if job.isFinished():
                    status = _('Done')
                return QVariant(status)
            if col == 2:
                p = str(job.percent_done) + r'%' if job.percent_done > 0 else _('Unavailable')
                return QVariant(p)
        if role == Qt.DecorationRole and col == 0:
            return self.device_job_icon if isinstance(job, DeviceJob) else self.job_icon
        return NONE
    
    def status_update(self, id, progress):
        keys = self.jobs.keys()
        keys.sort()
        try:
            row = keys.index(id)
            index = self.index(row, 2)
            self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), index, index)
        except ValueError:
            pass
        
    def closeEvent(self, e):
        self.jobs_view.write_settings()
        e.accept()
            
        
        