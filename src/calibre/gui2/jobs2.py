#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Job management.
'''
import time
from PyQt4.QtCore import QAbstractTableModel, QVariant, QModelIndex, Qt, SIGNAL
from PyQt4.QtGui import QIcon, QDialog

from calibre.parallel import ParallelJob, Server
from calibre.gui2 import Dispatcher, error_dialog
from calibre.gui2.device import DeviceJob
from calibre.gui2.dialogs.job_view_ui import Ui_Dialog

NONE = QVariant()

class JobManager(QAbstractTableModel):
    
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.wait_icon     = QVariant(QIcon(':/images/jobs.svg'))
        self.running_icon  = QVariant(QIcon(':/images/exec.svg'))
        self.error_icon    = QVariant(QIcon(':/images/dialog_error.svg'))
        self.done_icon     = QVariant(QIcon(':/images/ok.svg'))
    
        self.jobs          = []
        self.server        = Server()
        self.add_job       = Dispatcher(self._add_job)
        self.status_update = Dispatcher(self._status_update)
        self.start_work    = Dispatcher(self._start_work)
        self.job_done      = Dispatcher(self._job_done)
        
    def columnCount(self, parent=QModelIndex()):
        return 4
    
    def rowCount(self, parent=QModelIndex()):
        return len(self.jobs)
    
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
        
    def data(self, index, role):
        try:
            if role not in (Qt.DisplayRole, Qt.DecorationRole):
                return NONE
            row, col = index.row(), index.column()
            job = self.jobs[row]
            
            if role == Qt.DisplayRole:
                if col == 0:
                    desc = job.description
                    if not desc:
                        desc = _('Unknown job')
                    return QVariant(desc)
                if col == 1:
                    status = job.status()
                    if status == 'DONE':
                        st = _('Finished')
                    elif status == 'ERROR':
                        st = _('Error')
                    elif status == 'WAITING':
                        st = _('Waiting')
                    else:
                        st = _('Working')
                    return QVariant(st)
                if col == 2:
                    pc = job.percent
                    if pc <=0:
                        percent = 0
                    else:
                        percent = int(100*pc)
                    return QVariant(percent)
                if col == 3:
                    if job.start_time is None:
                        return NONE
                    rtime = job.running_time if job.running_time is not None else \
                                time.time() - job.start_time
                    return QVariant('%dm %ds'%(int(rtime)//60, int(rtime)%60))
            if role == Qt.DecorationRole and col == 0:
                status = job.status()
                if status == 'WAITING':
                    return self.wait_icon
                if status == 'WORKING':
                    return self.running_icon
                if status == 'ERROR':
                    return self.error_icon
                if status == 'DONE':
                    return self.done_icon
        except:
            import traceback
            traceback.print_exc()
        return NONE
        
    def _add_job(self, job):
        self.emit(SIGNAL('layoutAboutToBeChanged()'))
        self.jobs.append(job)
        self.jobs.sort()
        self.emit(SIGNAL('job_added(int)'), self.rowCount())
        self.emit(SIGNAL('layoutChanged()'))
        
    def done_jobs(self):
        return [j for j in self.jobs if j.status() in ['DONE', 'ERROR']]
    
    def row_to_job(self, row):
        return self.jobs[row]
    
    def _start_work(self, job):
        self.emit(SIGNAL('layoutAboutToBeChanged()'))
        self.jobs.sort()
        self.emit(SIGNAL('layoutChanged()'))
    
    def _job_done(self, job):
        self.emit(SIGNAL('layoutAboutToBeChanged()'))
        self.jobs.sort()
        self.emit(SIGNAL('job_done(int)'), len(self.jobs) - len(self.done_jobs()))
        self.emit(SIGNAL('layoutChanged()'))
    
    def _status_update(self, job):
        row = self.jobs.index(job)
        self.emit(SIGNAL('dataChanged(QModelIndex, QModelIndex)'),
                  self.index(row, 0), self.index(row, 3))
        
            
    def has_device_jobs(self):
        for job in self.jobs:
            if job.is_running and isinstance(job, DeviceJob):
                return True
        return False
    
    def has_jobs(self):
        for job in self.jobs:
            if job.is_running:
                return True
        return False
    
    def run_job(self, done, func, args=[], kwargs={},
                           description=None):
        job = ParallelJob(func, done, self, args=args, kwargs=kwargs,
                          description=description)
        self.server.add_job(job)
        return job
        
    
    def output(self, job):
        self.emit(SIGNAL('output_received()'))
    
    def kill_job(self, row, view):
        job = self.jobs[row]
        if isinstance(job, DeviceJob):
            error_dialog(view, _('Cannot kill job'),
                         _('Cannot kill jobs that communicate with the device')).exec_()
            return
        if job.has_run:
            error_dialog(view, _('Cannot kill job'),
                         _('Job has already run')).exec_()
            return
        if not job.is_running:
            self.jobs.remove(job)
            self.reset()
            return


        self.server.kill(job)
    
    def terminate_all_jobs(self):
        pass
    
class DetailView(QDialog, Ui_Dialog):
    
    def __init__(self, parent, job):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle(job.description)
        self.job = job
        self.update()
        
            
    def update(self):
        self.log.setPlainText(self.job.console_text())
        vbar = self.log.verticalScrollBar()
        vbar.setValue(vbar.maximum())
