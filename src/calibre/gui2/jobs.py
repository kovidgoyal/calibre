__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import traceback, logging, collections, time

from PyQt4.QtCore import QAbstractTableModel, QMutex, QObject, SIGNAL, Qt, \
                         QVariant, QThread
from PyQt4.QtGui import QIcon, QDialog

from calibre import detect_ncpus, Settings
from calibre.gui2 import NONE, error_dialog
from calibre.parallel import Server
from calibre.gui2.dialogs.job_view_ui import Ui_Dialog

class JobException(Exception):
    pass

class Job(QThread):
    ''' Class to run a function in a separate thread with optional mutex based locking.'''
    def __init__(self, id, description, slot, priority, func, *args, **kwargs):
        '''        
        @param id: Number. Id of this thread.
        @param description: String. Description of this job.
        @param slot: The callable that should be called when the job is done.
        @param priority: The priority with which this thread should be run
        @param func: A callable that should be executed in this thread.
        '''
        QThread.__init__(self)
        self.id = id
        self.func = func
        self.description = description if description else 'Job #' + str(self.id)
        self.args = args
        self.kwargs = kwargs
        self.slot, self._priority = slot, priority
        self.result = None
        self.percent_done = 0
        self.logger = logging.getLogger('Job #'+str(id))
        self.logger.setLevel(logging.DEBUG)
        self.is_locked = False
        self.log = self.exception = self.last_traceback = None
        self.connect_done_signal()
        self.start_time = None
        
        
    def start(self):
        self.start_time = time.time()
        QThread.start(self, self._priority)
    
    def progress_update(self, val):
        self.percent_done = val
        self.emit(SIGNAL('status_update(int, int)'), self.id, int(val))
        
    def formatted_log(self):
        if self.log is None:
            return ''
        return '<h2>Log:</h2><pre>%s</pre>'%self.log
        
    
class DeviceJob(Job):
    ''' Jobs that involve communication with the device. '''
    def run(self):
        last_traceback, exception = None, None
        
        try:
            self.result = self.func(self.progress_update, *self.args, **self.kwargs)
        except Exception, err:
            exception = err
            last_traceback = traceback.format_exc()            
        
        self.exception, self.last_traceback = exception, last_traceback
        
    def formatted_error(self):
        if self.exception is None:
            return ''
        ans = u'<p><b>%s</b>: %s</p>'%(self.exception.__class__.__name__, self.exception)
        ans += '<h2>Traceback:</h2><pre>%s</pre>'%self.last_traceback
        return ans
        
    def notify(self):
        self.emit(SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'), 
                  self.id, self.description, self.result, self.exception, self.last_traceback)
    
    def connect_done_signal(self):
        if self.slot is not None:
            self.connect(self, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                            self.slot, Qt.QueuedConnection)
        
class ConversionJob(Job):
    ''' Jobs that involve conversion of content.'''
    def run(self):
        last_traceback, exception = None, None
        try:
            self.result, exception, last_traceback, self.log = \
                self.server.run(self.id, self.func, self.args, self.kwargs)
        except Exception, err:
            last_traceback = traceback.format_exc()
            exception = (exception.__class__.__name__, unicode(str(err), 'utf8', 'replace'))
            
        self.last_traceback, self.exception = last_traceback, exception
        
    def notify(self):
        self.emit(SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'), 
                  self.id, self.description, self.result, self.exception, self.last_traceback, self.log)
        
    def connect_done_signal(self):
        if self.slot is not None:
            self.connect(self, SIGNAL('jobdone(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                            self.slot, Qt.QueuedConnection)
    
    def formatted_error(self):
        if self.exception is None:
            return ''
        ans = u'<p><b>%s</b>: %s</p>'%self.exception
        ans += '<h2>Traceback:</h2><pre>%s</pre>'%self.last_traceback
        return ans
        
class JobManager(QAbstractTableModel):
    
    PRIORITY = {'Idle'  : QThread.IdlePriority,
                'Lowest': QThread.LowestPriority,
                'Low'   : QThread.LowPriority,
                'Normal': QThread.NormalPriority 
                }
    
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.waiting_jobs  = collections.deque()
        self.running_jobs  = collections.deque()
        self.finished_jobs = collections.deque()
        self.add_queue     = collections.deque()
        self.update_lock   = QMutex() # Protects write access to the above dequeues
        self.next_id       = 0
        self.wait_icon     = QVariant(QIcon(':/images/jobs.svg'))
        self.running_icon  = QVariant(QIcon(':/images/exec.svg'))
        self.error_icon    = QVariant(QIcon(':/images/dialog_error.svg'))
        self.done_icon     = QVariant(QIcon(':/images/ok.svg'))
        
        self.process_server  = Server()
                
        self.ncpus = detect_ncpus()
        self.timer_id = self.startTimer(500)
        
    def terminate_device_jobs(self):
        for job in self.running_jobs:
            if isinstance(job, DeviceJob):
                job.terminate()
                
    def terminate_all_jobs(self):
        for job in self.running_jobs:
            try:
                if isinstance(job, DeviceJob):
                    job.terminate()
                self.process_server.kill(job.id)
            except:
                continue
    
    def timerEvent(self, event):
        if event.timerId() == self.timer_id:
            self.update_lock.lock()
            try:
                refresh = False
                
                while self.add_queue:
                    job = self.add_queue.pop()
                    self.waiting_jobs.append(job)
                    self.emit(SIGNAL('job_added(int)'), job.id, Qt.QueuedConnection)
                    
                
                for job in [job for job in self.running_jobs if job.isFinished()]:
                    self.running_jobs.remove(job)
                    self.finished_jobs.appendleft(job)
                    if job.result != self.process_server.KILL_RESULT:
                        job.notify()
                    job.running_time = time.time() - job.start_time
                    self.emit(SIGNAL('job_done(int)'), job.id)
                    refresh = True
                
                cjs = list(self.running_conversion_jobs())
                if len(cjs) < self.ncpus:
                    cj = None
                    for job in self.waiting_jobs:
                        if isinstance(job, ConversionJob):
                            cj = job
                            break
                    if cj is not None:
                        self.waiting_jobs.remove(cj)
                        cj.start()
                        self.running_jobs.append(cj)
                        refresh = True
                    
                djs = list(self.running_device_jobs())
                if len(djs) == 0:
                    dj = None
                    for job in self.waiting_jobs:
                        if isinstance(job, DeviceJob):
                            dj = job
                            break
                    if dj is not None:
                        self.waiting_jobs.remove(dj)
                        dj.start()
                        self.running_jobs.append(dj)
                        refresh = True
                if refresh:
                    self.reset()
                    if len(self.running_jobs) == 0:
                        self.emit(SIGNAL('no_more_jobs()'))
                for i in range(len(self.running_jobs)):
                    self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), self.index(i, 3), self.index(i, 3))
            finally:
                self.update_lock.unlock()
        
    def has_jobs(self):
        return len(self.waiting_jobs) + len(self.running_jobs) > 0
    
    def has_device_jobs(self):
        return len(tuple(self.running_device_jobs())) > 0
    
    def running_device_jobs(self):
        for job in self.running_jobs:
            if isinstance(job, DeviceJob):
                yield job
    
    def running_conversion_jobs(self):
        for job in self.running_jobs:
            if isinstance(job, ConversionJob):
                yield job
                
    def update_progress(self, id, percent):
        row = -1
        for collection in (self.running_jobs, self.waiting_jobs, self.finished_jobs):
            for job in collection:
                row += 1
                if job.id == id:
                    job.percent_done = percent
                    index = self.index(row, 2)
                    self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), index, index)
                    return
            
                
    def create_job(self, job_class, description, slot, priority, *args, **kwargs):
        self.next_id += 1
        id = self.next_id
        job = job_class(id, description, slot, priority, *args, **kwargs)
        job.server = self.process_server
        QObject.connect(job, SIGNAL('status_update(int, int)'), self.status_update, Qt.QueuedConnection)
        self.update_lock.lock()
        self.add_queue.append(job)
        self.update_lock.unlock()            
        return job
    
    def run_conversion_job(self, slot, callable, args=[], **kwargs):
        '''
        Run a conversion job.
        @param slot: The function to call with the job result. 
        @param callable: The function to call to communicate with the device.
        @param args: The arguments to pass to callable
        @param kwargs: The keyword arguments to pass to callable
        '''
        desc = kwargs.pop('job_description', '')
        if args and hasattr(args[0], 'append') and '--verbose' not in args[0]:
            args[0].append('--verbose')
        priority = self.PRIORITY[str(Settings().value('conversion job priority', 
                            QVariant('Normal')).toString())]
        job = self.create_job(ConversionJob, desc, slot, priority,
                              callable, *args, **kwargs)
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
        job = self.create_job(DeviceJob, desc, slot, QThread.NormalPriority, 
                              callable, *args, **kwargs)        
        return job.id
    
    def rowCount(self, parent):
        return len(self.running_jobs) + len(self.waiting_jobs) + len(self.finished_jobs)    
    
    def columnCount(self, parent):
        return 4
    
    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        if orientation == Qt.Horizontal:      
            if   section == 0: text = _("Job")
            elif section == 1: text = _("Status")
            elif section == 2: text = _("Progress")
            elif section == 3: text = _('Running time')
            return QVariant(text)
        else: 
            return QVariant(section+1)
        
    def row_to_job(self, row):
        if row < len(self.running_jobs):
            return self.running_jobs[row], 0
        row -= len(self.running_jobs)
        if row < len(self.waiting_jobs):
            return self.waiting_jobs[row], 1
        row -= len(self.running_jobs)
        return self.finished_jobs[row], 2
    
    def data(self, index, role):
        if role not in (Qt.DisplayRole, Qt.DecorationRole):
            return NONE
        row, col = index.row(), index.column()
        try:
            job, status = self.row_to_job(row)
        except IndexError:
            return NONE
        
        if role == Qt.DisplayRole:            
            if col == 0:
                return QVariant(job.description)
            if col == 1:
                if status == 2:
                    st = _('Finished') if job.exception is None else _('Error')
                else:
                    st = [_('Working'), _('Waiting')][status] 
                return QVariant(st)
            if col == 2:
                return QVariant(int(100*job.percent_done))
            if col == 3:
                if job.start_time is None:
                    return NONE
                rtime = job.running_time if hasattr(job, 'running_time') else time.time() - job.start_time
                return QVariant('%dm %ds'%(int(rtime)//60, int(rtime)%60))
        if role == Qt.DecorationRole and col == 0:
            if status == 1:
                return self.wait_icon
            if status == 0:
                return self.running_icon
            if status == 2:
                if job.exception or job.result == self.process_server.KILL_RESULT:
                    return self.error_icon
                return self.done_icon 
        return NONE
    
    def status_update(self, id, progress):
        for i in range(len(self.running_jobs)):
            job = self.running_jobs[i]
            if job.id == id:
                self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'), self.index(i, 2), self.index(i, 3))
                break
            
    def kill_job(self, row, gui_parent):
        job, status = self.row_to_job(row)
        if isinstance(job, DeviceJob):
            error_dialog(gui_parent, _('Cannot kill job'), 
                _('Cannot kill jobs that are communicating with the device as this may cause data corruption.')).exec_()
            return
        if status == 2:
            error_dialog(gui_parent, _('Cannot kill job'), 
                _('Cannot kill already completed jobs.')).exec_()
            return
        if status == 1:
            error_dialog(gui_parent, _('Cannot kill job'), 
                _('Cannot kill waiting jobs.')).exec_()
            return
        self.process_server.kill(job.id)

class DetailView(QDialog, Ui_Dialog):
    
    def __init__(self, parent, job):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle(job.description)
        self.job = job
        txt = self.job.formatted_error() + self.job.formatted_log()
        
        if not txt:
            txt = 'No details available'
            
        self.log.setHtml(txt)
            
        
