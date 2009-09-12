#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Job management.
'''

from Queue import Empty, Queue

from PyQt4.Qt import QAbstractTableModel, QVariant, QModelIndex, Qt, \
    QTimer, SIGNAL, QIcon, QDialog, QAbstractItemDelegate, QApplication, \
    QSize, QStyleOptionProgressBarV2, QString, QStyle

from calibre.utils.ipc.server import Server
from calibre.utils.ipc.job import ParallelJob
from calibre.gui2 import Dispatcher, error_dialog, NONE, config
from calibre.gui2.device import DeviceJob
from calibre.gui2.dialogs.jobs_ui import Ui_JobsDialog
from calibre import __appname__

class JobManager(QAbstractTableModel):

    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.wait_icon     = QVariant(QIcon(I('jobs.svg')))
        self.running_icon  = QVariant(QIcon(I('exec.svg')))
        self.error_icon    = QVariant(QIcon(I('dialog_error.svg')))
        self.done_icon     = QVariant(QIcon(I('ok.svg')))

        self.jobs          = []
        self.add_job       = Dispatcher(self._add_job)
        self.server        = Server(limit=int(config['worker_limit']/2.0))
        self.changed_queue = Queue()

        self.timer         = QTimer(self)
        self.connect(self.timer, SIGNAL('timeout()'), self.update,
                Qt.QueuedConnection)
        self.timer.start(1000)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def rowCount(self, parent=QModelIndex()):
        return len(self.jobs)

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        if orientation == Qt.Horizontal:
            if   section == 0: text = _('Job')
            elif section == 1: text = _('Status')
            elif section == 2: text = _('Progress')
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
                    return QVariant(job.status_text)
                if col == 2:
                    p = 100. if job.is_finished else job.percent
                    return QVariant(p)
                if col == 3:
                    rtime = job.running_time
                    if rtime is None:
                        return NONE
                    return QVariant('%dm %ds'%(int(rtime)//60, int(rtime)%60))
            if role == Qt.DecorationRole and col == 0:
                state = job.run_state
                if state == job.WAITING:
                    return self.wait_icon
                if state == job.RUNNING:
                    return self.running_icon
                if job.killed or job.failed:
                    return self.error_icon
                return self.done_icon
        except:
            import traceback
            traceback.print_exc()
        return NONE

    def update(self):
        try:
            self._update()
        except BaseException:
            import traceback
            traceback.print_exc()

    def _update(self):
        # Update running time
        rows = set([])
        for i, j in enumerate(self.jobs):
            if j.run_state == j.RUNNING:
                idx = self.index(i, 3)
                self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                        idx, idx)

        # Update parallel jobs
        jobs = set([])
        while True:
            try:
                jobs.add(self.server.changed_jobs_queue.get_nowait())
            except Empty:
                break
        while True:
            try:
                jobs.add(self.changed_queue.get_nowait())
            except Empty:
                break

        if jobs:
            needs_reset = False
            for job in jobs:
                orig_state = job.run_state
                job.update()
                if orig_state != job.run_state:
                    needs_reset = True
            if needs_reset:
                self.jobs.sort()
                self.reset()
                if job.is_finished:
                    self.emit(SIGNAL('job_done(int)'), len(self.unfinished_jobs()))
            else:
                for job in jobs:
                    idx = self.jobs.index(job)
                    self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                        self.index(idx, 0), self.index(idx, 3))


    def _add_job(self, job):
        self.emit(SIGNAL('layoutAboutToBeChanged()'))
        self.jobs.append(job)
        self.jobs.sort()
        self.emit(SIGNAL('job_added(int)'), len(self.unfinished_jobs()))
        self.emit(SIGNAL('layoutChanged()'))

    def done_jobs(self):
        return [j for j in self.jobs if j.is_finished]

    def unfinished_jobs(self):
        return [j for j in self.jobs if not j.is_finished]

    def row_to_job(self, row):
        return self.jobs[row]

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

    def run_job(self, done, name, args=[], kwargs={},
                           description=''):
        job = ParallelJob(name, description, done, args=args, kwargs=kwargs)
        self.add_job(job)
        self.server.add_job(job)
        return job

    def launch_gui_app(self, name, args=[], kwargs={}, description=''):
        job = ParallelJob(name, description, lambda x: x,
                args=args, kwargs=kwargs)
        self.server.run_job(job, gui=True, redirect_output=False)


    def kill_job(self, row, view):
        job = self.jobs[row]
        if isinstance(job, DeviceJob):
            return error_dialog(view, _('Cannot kill job'),
                         _('Cannot kill jobs that communicate with the device')).exec_()
        if job.duration is not None:
            return error_dialog(view, _('Cannot kill job'),
                         _('Job has already run')).exec_()
        self.server.kill_job(job)

    def kill_all_jobs(self):
        for job in self.jobs:
            if isinstance(job, DeviceJob) or job.duration is not None:
                continue
            self.server.kill_job(job)

    def terminate_all_jobs(self):
        self.server.killall()


class ProgressBarDelegate(QAbstractItemDelegate):

    def sizeHint(self, option, index):
        return QSize(120, 30)

    def paint(self, painter, option, index):
        opts = QStyleOptionProgressBarV2()
        opts.rect = option.rect
        opts.minimum = 1
        opts.maximum = 100
        opts.textVisible = True
        percent, ok = index.model().data(index, Qt.DisplayRole).toInt()
        if not ok:
            percent = 0
        opts.progress = percent
        opts.text = QString(_('Unavailable') if percent == 0 else '%d%%'%percent)
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opts, painter)

class JobsDialog(QDialog, Ui_JobsDialog):
    def __init__(self, window, model):
        QDialog.__init__(self, window)
        Ui_JobsDialog.__init__(self)
        self.setupUi(self)
        self.jobs_view.setModel(model)
        self.model = model
        self.setWindowModality(Qt.NonModal)
        self.setWindowTitle(__appname__ + _(' - Jobs'))
        self.connect(self.jobs_view.model(), SIGNAL('modelReset()'),
                        self.jobs_view.resizeColumnsToContents)
        self.connect(self.kill_button, SIGNAL('clicked()'),
                        self.kill_job)
        self.connect(self.details_button, SIGNAL('clicked()'),
                        self.show_details)
        self.connect(self.stop_all_jobs_button, SIGNAL('clicked()'),
                self.kill_all_jobs)
        self.connect(self, SIGNAL('kill_job(int, PyQt_PyObject)'),
                        self.jobs_view.model().kill_job)
        self.pb_delegate = ProgressBarDelegate(self)
        self.jobs_view.setItemDelegateForColumn(2, self.pb_delegate)


    def kill_job(self):
        for index in self.jobs_view.selectedIndexes():
            row = index.row()
            self.model.kill_job(row, self)
            return

    def show_details(self):
        for index in self.jobs_view.selectedIndexes():
            self.jobs_view.show_details(index)
            return

    def kill_all_jobs(self):
        self.model.kill_all_jobs()

    def closeEvent(self, e):
        self.jobs_view.write_settings()
        e.accept()
