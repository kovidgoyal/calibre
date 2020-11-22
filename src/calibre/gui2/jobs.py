#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Job management.
'''

import time

from PyQt5.Qt import (QAbstractTableModel, QModelIndex, Qt, QPainter,
    QTimer, pyqtSignal, QIcon, QDialog, QAbstractItemDelegate, QApplication,
    QSize, QStyleOptionProgressBar, QStyle, QToolTip, QWidget, QStyleOption,
    QHBoxLayout, QVBoxLayout, QSizePolicy, QLabel, QCoreApplication, QAction,
    QByteArray, QSortFilterProxyModel, QTextBrowser, QPlainTextEdit)

from calibre import strftime
from calibre.constants import islinux, isbsd
from calibre.utils.ipc.server import Server
from calibre.utils.ipc.job import ParallelJob
from calibre.gui2 import (Dispatcher, error_dialog, question_dialog,
        config, gprefs)
from calibre.gui2.device import DeviceJob
from calibre.gui2.dialogs.jobs_ui import Ui_JobsDialog
from calibre import __appname__, as_unicode
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.threaded_jobs import ThreadedJobServer, ThreadedJob
from calibre.gui2.widgets2 import Dialog
from calibre.utils.search_query_parser import SearchQueryParser, ParseException
from calibre.utils.icu import lower
from polyglot.builtins import range
from polyglot.queue import Empty, Queue


class AdaptSQP(SearchQueryParser):

    def __init__(self, *args, **kwargs):
        pass


def human_readable_interval(secs):
    secs = int(secs)
    days = secs // 86400
    hours = secs // 3600 % 24
    minutes = secs // 60 % 60
    seconds = secs % 60
    parts = []
    if days > 0:
        parts.append('%dd' % days)
    if hours > 0:
        parts.append('%dh' % hours)
    if minutes > 0:
        parts.append('%dm' % minutes)
    if secs > 0:
        parts.append('%ds' % seconds)
    return ' '.join(parts)


class JobManager(QAbstractTableModel, AdaptSQP):  # {{{

    job_added = pyqtSignal(int)
    job_done  = pyqtSignal(int)

    def __init__(self):
        QAbstractTableModel.__init__(self)
        SearchQueryParser.__init__(self, ['all'])

        self.wait_icon     = (QIcon(I('jobs.png')))
        self.running_icon  = (QIcon(I('exec.png')))
        self.error_icon    = (QIcon(I('dialog_error.png')))
        self.done_icon     = (QIcon(I('ok.png')))

        self.jobs          = []
        self.add_job       = Dispatcher(self._add_job)
        self.server        = Server(limit=config['worker_limit']//2,
                                enforce_cpu_limit=config['enforce_cpu_limit'])
        self.threaded_server = ThreadedJobServer()
        self.changed_queue = Queue()

        self.timer         = QTimer(self)
        self.timer.timeout.connect(self.update, type=Qt.QueuedConnection)
        self.timer.start(1000)

    def columnCount(self, parent=QModelIndex()):
        return 5

    def rowCount(self, parent=QModelIndex()):
        return len(self.jobs)

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return ({
              0: _('Job'),
              1: _('Status'),
              2: _('Progress'),
              3: _('Running time'),
              4: _('Start time'),
            }.get(section, ''))
        else:
            return (section+1)

    def show_tooltip(self, arg):
        widget, pos = arg
        QToolTip.showText(pos, self.get_tooltip())

    def get_tooltip(self):
        running_jobs = [j for j in self.jobs if j.run_state == j.RUNNING]
        waiting_jobs = [j for j in self.jobs if j.run_state == j.WAITING]
        lines = [ngettext('There is a running job:', 'There are {} running jobs:', len(running_jobs)).format(len(running_jobs))]
        for job in running_jobs:
            desc = job.description
            if not desc:
                desc = _('Unknown job')
            p = 100. if job.is_finished else job.percent
            lines.append('%s:  %.0f%% done'%(desc, p))
        l = ngettext('There is a waiting job', 'There are {} waiting jobs', len(waiting_jobs)).format(len(waiting_jobs))
        lines.extend(['', l])
        for job in waiting_jobs:
            desc = job.description
            if not desc:
                desc = _('Unknown job')
            lines.append(desc)
        return '\n'.join(['calibre', '']+ lines)

    def data(self, index, role):
        try:
            if role not in (Qt.DisplayRole, Qt.DecorationRole):
                return None
            row, col = index.row(), index.column()
            job = self.jobs[row]

            if role == Qt.DisplayRole:
                if col == 0:
                    desc = job.description
                    if not desc:
                        desc = _('Unknown job')
                    return (desc)
                if col == 1:
                    return (job.status_text)
                if col == 2:
                    p = 100. if job.is_finished else job.percent
                    return (p)
                if col == 3:
                    rtime = job.running_time
                    if rtime is None:
                        return None
                    return human_readable_interval(rtime)
                if col == 4 and job.start_time is not None:
                    return (strftime('%H:%M -- %d %b', time.localtime(job.start_time)))
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
        return None

    def update(self):
        try:
            self._update()
        except BaseException:
            import traceback
            traceback.print_exc()

    def _update(self):
        # Update running time
        for i, j in enumerate(self.jobs):
            if j.run_state == j.RUNNING:
                idx = self.index(i, 3)
                self.dataChanged.emit(idx, idx)

        # Update parallel jobs
        jobs = set()
        while True:
            try:
                jobs.add(self.server.changed_jobs_queue.get_nowait())
            except Empty:
                break

        # Update device jobs
        while True:
            try:
                jobs.add(self.changed_queue.get_nowait())
            except Empty:
                break

        # Update threaded jobs
        while True:
            try:
                jobs.add(self.threaded_server.changed_jobs.get_nowait())
            except Empty:
                break

        if jobs:
            needs_reset = False
            for job in jobs:
                orig_state = job.run_state
                job.update()
                if orig_state != job.run_state:
                    needs_reset = True
                    if job.is_finished:
                        self.job_done.emit(len(self.unfinished_jobs()))
            if needs_reset:
                self.modelAboutToBeReset.emit()
                self.jobs.sort()
                self.modelReset.emit()
            else:
                for job in jobs:
                    idx = self.jobs.index(job)
                    self.dataChanged.emit(
                        self.index(idx, 0), self.index(idx, 3))

        # Kill parallel jobs that have gone on too long
        try:
            wmax_time = gprefs['worker_max_time'] * 60
        except:
            wmax_time = 0

        if wmax_time > 0:
            for job in self.jobs:
                if isinstance(job, ParallelJob):
                    rtime = job.running_time
                    if (rtime is not None and rtime > wmax_time and
                            job.duration is None):
                        job.timed_out = True
                        self.server.kill_job(job)

    def _add_job(self, job):
        self.modelAboutToBeReset.emit()
        self.jobs.append(job)
        self.jobs.sort()
        self.job_added.emit(len(self.unfinished_jobs()))
        self.modelReset.emit()

    def done_jobs(self):
        return [j for j in self.jobs if j.is_finished]

    def unfinished_jobs(self):
        return [j for j in self.jobs if not j.is_finished]

    def row_to_job(self, row):
        return self.jobs[row]

    def rows_to_jobs(self, rows):
        return [self.jobs[row] for row in rows]

    def has_device_jobs(self, queued_also=False):
        for job in self.jobs:
            if isinstance(job, DeviceJob):
                if job.duration is None:  # Running or waiting
                    if (job.is_running or queued_also):
                        return True
        return False

    def has_jobs(self):
        for job in self.jobs:
            if job.is_running:
                return True
        return False

    def run_job(self, done, name, args=[], kwargs={},
                           description='', core_usage=1):
        job = ParallelJob(name, description, done, args=args, kwargs=kwargs)
        job.core_usage = core_usage
        self.add_job(job)
        self.server.add_job(job)
        return job

    def run_threaded_job(self, job):
        self.add_job(job)
        self.threaded_server.add_job(job)

    def launch_gui_app(self, name, args=(), kwargs=None, description=''):
        job = ParallelJob(name, description, lambda x: x,
                args=list(args), kwargs=kwargs or {})
        self.server.run_job(job, gui=True, redirect_output=False)

    def _kill_job(self, job):
        if isinstance(job, ParallelJob):
            self.server.kill_job(job)
        elif isinstance(job, ThreadedJob):
            self.threaded_server.kill_job(job)
        else:
            job.kill_on_start = True

    def hide_jobs(self, rows):
        for r in rows:
            self.jobs[r].hidden_in_gui = True
        for r in rows:
            self.dataChanged.emit(self.index(r, 0), self.index(r, 0))

    def show_hidden_jobs(self):
        for j in self.jobs:
            j.hidden_in_gui = False
        for r in range(len(self.jobs)):
            self.dataChanged.emit(self.index(r, 0), self.index(r, 0))

    def kill_job(self, job, view):
        if isinstance(job, DeviceJob):
            return error_dialog(view, _('Cannot kill job'),
                         _('Cannot kill jobs that communicate with the device')).exec_()
        if job.duration is not None:
            return error_dialog(view, _('Cannot kill job'),
                         _('Job has already run')).exec_()
        if not getattr(job, 'killable', True):
            return error_dialog(view, _('Cannot kill job'),
                    _('This job cannot be stopped'), show=True)
        self._kill_job(job)

    def kill_multiple_jobs(self, jobs, view):
        devjobs = [j for j in jobs if isinstance(j, DeviceJob)]
        if devjobs:
            error_dialog(view, _('Cannot kill job'),
                         _('Cannot kill jobs that communicate with the device')).exec_()
            jobs = [j for j in jobs if not isinstance(j, DeviceJob)]
        jobs = [j for j in jobs if j.duration is None]
        unkillable = [j for j in jobs if not getattr(j, 'killable', True)]
        if unkillable:
            names = '\n'.join(as_unicode(j.description) for j in unkillable)
            error_dialog(view, _('Cannot kill job'),
                    _('Some of the jobs cannot be stopped. Click "Show details"'
                        ' to see the list of unstoppable jobs.'), det_msg=names,
                    show=True)
            jobs = [j for j in jobs if getattr(j, 'killable', True)]
        jobs = [j for j in jobs if j.duration is None]
        for j in jobs:
            self._kill_job(j)

    def kill_all_jobs(self):
        for job in self.jobs:
            if (isinstance(job, DeviceJob) or job.duration is not None or
                    not getattr(job, 'killable', True)):
                continue
            self._kill_job(job)

    def terminate_all_jobs(self):
        self.server.killall()
        for job in self.jobs:
            if (isinstance(job, DeviceJob) or job.duration is not None or
                    not getattr(job, 'killable', True)):
                continue
            if not isinstance(job, ParallelJob):
                self._kill_job(job)

    def universal_set(self):
        return {i for i, j in enumerate(self.jobs) if not getattr(j,
            'hidden_in_gui', False)}

    def get_matches(self, location, query, candidates=None):
        if candidates is None:
            candidates = self.universal_set()
        ans = set()
        if not query:
            return ans
        query = lower(query)
        for j in candidates:
            job = self.jobs[j]
            if job.description and query in lower(job.description):
                ans.add(j)
        return ans

    def find(self, query):
        query = query.strip()
        rows = self.parse(query)
        return rows

# }}}


class FilterModel(QSortFilterProxyModel):  # {{{

    search_done = pyqtSignal(object)

    def __init__(self, parent):
        QSortFilterProxyModel.__init__(self, parent)
        self.search_filter = None

    def filterAcceptsRow(self, source_row, source_parent):
        if (self.search_filter is not None and source_row not in
                self.search_filter):
            return False
        m = self.sourceModel()
        try:
            job = m.row_to_job(source_row)
        except:
            return False
        return not getattr(job, 'hidden_in_gui', False)

    def find(self, query):
        ok = True
        val = None
        if query:
            try:
                val = self.sourceModel().parse(query)
            except ParseException:
                ok = False
        self.search_filter = val
        self.beginResetModel()
        self.search_done.emit(ok)
        self.endResetModel()

# }}}

# Jobs UI {{{


class ProgressBarDelegate(QAbstractItemDelegate):  # {{{

    def sizeHint(self, option, index):
        return QSize(120, 30)

    def paint(self, painter, option, index):
        opts = QStyleOptionProgressBar()
        opts.rect = option.rect
        opts.minimum = 1
        opts.maximum = 100
        opts.textVisible = True
        try:
            percent = int(index.model().data(index, Qt.DisplayRole))
        except (TypeError, ValueError):
            percent = 0
        opts.progress = percent
        opts.text = (_('Unavailable') if percent == 0 else '%d%%'%percent)
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opts, painter)
# }}}


class DetailView(Dialog):  # {{{

    def __init__(self, parent, job):
        self.job = job
        self.html_view = hasattr(job, 'html_details') and not getattr(job, 'ignore_html_details', False)
        Dialog.__init__(self, job.description, 'job-detail-view-dialog', parent)

    def sizeHint(self):
        return QSize(700, 500)

    @property
    def plain_text(self):
        if self.html_view:
            return self.tb.toPlainText()
        return self.log.toPlainText()

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setText(self.plain_text)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        if self.html_view:
            self.tb = w = QTextBrowser(self)
        else:
            self.log = w = QPlainTextEdit(self)
            w.setReadOnly(True), w.setLineWrapMode(w.NoWrap)
        l.addWidget(w)
        l.addWidget(self.bb)
        self.bb.clear(), self.bb.setStandardButtons(self.bb.Close)
        self.copy_button = b = self.bb.addButton(_('&Copy to clipboard'), self.bb.ActionRole)
        b.setIcon(QIcon(I('edit-copy.png')))
        b.clicked.connect(self.copy_to_clipboard)
        self.next_pos = 0
        self.update()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)
        if not self.html_view:
            v = self.log.verticalScrollBar()
            v.setValue(v.maximum())

    def update(self):
        if self.html_view:
            html = self.job.html_details
            if len(html) > self.next_pos:
                self.next_pos = len(html)
                self.tb.setHtml(
                    '<pre style="font-family:monospace">%s</pre>'%html)
        else:
            f = self.job.log_file
            f.seek(self.next_pos)
            more = f.read()
            self.next_pos = f.tell()
            if more:
                self.log.appendPlainText(more.decode('utf-8', 'replace'))
# }}}


class JobsButton(QWidget):  # {{{

    tray_tooltip_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.num_jobs = 0
        self.mouse_over = False
        self.pi = ProgressIndicator(self, self.style().pixelMetric(QStyle.PM_ToolBarIconSize))
        self._jobs = QLabel('')
        self._jobs.mouseReleaseEvent = self.mouseReleaseEvent
        self.update_label()
        self.shortcut = 'Alt+Shift+J'

        self.l = l = QHBoxLayout(self)
        l.setSpacing(3)
        l.addWidget(self.pi)
        l.addWidget(self._jobs)
        m = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self.layout().setContentsMargins(m, m, m, m)
        self._jobs.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setCursor(Qt.PointingHandCursor)
        b = _('Click to see list of jobs')
        self.setToolTip(b + ' [%s]'%self.shortcut)
        self.action_toggle = QAction(b, parent)
        parent.addAction(self.action_toggle)
        self.action_toggle.triggered.connect(self.toggle)
        if hasattr(parent, 'keyboard'):
            parent.keyboard.register_shortcut('toggle jobs list', _('Show/hide the Jobs List'), default_keys=(self.shortcut,), action=self.action_toggle)

    def update_label(self):
        n = self.jobs()
        prefix = '<b>' if n > 0 else ''
        self._jobs.setText(prefix + _('Jobs:') + ' {} '.format(n))

    def event(self, ev):
        m = None
        et = ev.type()
        if et == ev.Enter:
            m = True
        elif et == ev.Leave:
            m = False
        if m is not None and m != self.mouse_over:
            self.mouse_over = m
            self.update()
        return QWidget.event(self, ev)

    def initialize(self, jobs_dialog, job_manager):
        self.jobs_dialog = jobs_dialog
        job_manager.job_added.connect(self.job_added)
        job_manager.job_done.connect(self.job_done)
        self.jobs_dialog.addAction(self.action_toggle)

    def mouseReleaseEvent(self, event):
        self.toggle()

    def toggle(self, *args):
        if self.jobs_dialog.isVisible():
            self.jobs_dialog.hide()
        else:
            self.jobs_dialog.show()

    @property
    def is_running(self):
        return self.pi.isAnimated()

    def start(self):
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()

    def jobs(self):
        return self.num_jobs

    def tray_tooltip(self, num=0):
        if num == 0:
            text = _('No running jobs')
        elif num == 1:
            text = _('One running job')
        else:
            text = _('%d running jobs') % num
        if not (islinux or isbsd):
            text = 'calibre: ' + text
        return text

    def job_added(self, nnum):
        self.num_jobs = nnum
        self.update_label()
        self.start()
        self.tray_tooltip_updated.emit(self.tray_tooltip(nnum))

    def job_done(self, nnum):
        self.num_jobs = nnum
        self.update_label()
        if nnum == 0:
            self.no_more_jobs()
        self.tray_tooltip_updated.emit(self.tray_tooltip(nnum))

    def no_more_jobs(self):
        if self.is_running:
            self.stop()
            QCoreApplication.instance().alert(self, 5000)

    def paintEvent(self, ev):
        if self.mouse_over:
            p = QPainter(self)
            tool = QStyleOption()
            tool.rect = self.rect()
            tool.state = QStyle.State_Raised | QStyle.State_Active | QStyle.State_MouseOver
            s = self.style()
            s.drawPrimitive(QStyle.PE_PanelButtonTool, tool, p, self)
            p.end()
        QWidget.paintEvent(self, ev)

# }}}


class JobsDialog(QDialog, Ui_JobsDialog):

    def __init__(self, window, model):
        QDialog.__init__(self, window)
        Ui_JobsDialog.__init__(self)
        self.setupUi(self)
        self.model = model
        self.proxy_model = FilterModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.search_done.connect(self.search.search_done)
        self.jobs_view.setModel(self.proxy_model)
        self.setWindowModality(Qt.NonModal)
        self.setWindowTitle(__appname__ + _(' - Jobs'))
        self.details_button.clicked.connect(self.show_details)
        self.kill_button.clicked.connect(self.kill_job)
        self.stop_all_jobs_button.clicked.connect(self.kill_all_jobs)
        self.pb_delegate = ProgressBarDelegate(self)
        self.jobs_view.setItemDelegateForColumn(2, self.pb_delegate)
        self.jobs_view.doubleClicked.connect(self.show_job_details)
        self.jobs_view.horizontalHeader().setSectionsMovable(True)
        self.hide_button.clicked.connect(self.hide_selected)
        self.hide_all_button.clicked.connect(self.hide_all)
        self.show_button.clicked.connect(self.show_hidden)
        self.search.initialize('jobs_search_history',
                help_text=_('Search for a job by name'))
        self.search.search.connect(self.find)
        connect_lambda(self.search_button.clicked, self, lambda self: self.find(self.search.current_text))
        self.restore_state()

    def restore_state(self):
        try:
            geom = gprefs.get('jobs_dialog_geometry', None)
            if geom:
                QApplication.instance().safe_restore_geometry(self, QByteArray(geom))
            state = gprefs.get('jobs view column layout3', None)
            if state is not None:
                self.jobs_view.horizontalHeader().restoreState(QByteArray(state))
        except:
            pass
        idx = self.jobs_view.model().index(0, 0)
        if idx.isValid():
            sm = self.jobs_view.selectionModel()
            sm.select(idx, sm.ClearAndSelect|sm.Rows)

    def save_state(self):
        try:
            state = bytearray(self.jobs_view.horizontalHeader().saveState())
            gprefs['jobs view column layout3'] = state
            geom = bytearray(self.saveGeometry())
            gprefs['jobs_dialog_geometry'] = geom
        except:
            pass

    def show_job_details(self, index):
        index = self.proxy_model.mapToSource(index)
        if index.isValid():
            row = index.row()
            job = self.model.row_to_job(row)
            d = DetailView(self, job)
            d.exec_()
            d.timer.stop()

    def show_details(self, *args):
        index = self.jobs_view.currentIndex()
        if index.isValid():
            self.show_job_details(index)

    def kill_job(self, *args):
        indices = [self.proxy_model.mapToSource(index) for index in
                self.jobs_view.selectionModel().selectedRows()]
        indices = [i for i in indices if i.isValid()]
        jobs = self.model.rows_to_jobs([index.row() for index in indices])
        if not jobs:
            return error_dialog(self, _('No job'),
                _('No job selected'), show=True)
        if question_dialog(self, _('Are you sure?'),
                ngettext('Do you really want to stop the selected job?',
                    'Do you really want to stop all the selected jobs?',
                    len(jobs))):
            if len(jobs) > 1:
                self.model.kill_multiple_jobs(jobs, self)
            else:
                self.model.kill_job(jobs[0], self)

    def kill_all_jobs(self, *args):
        if question_dialog(self, _('Are you sure?'),
                _('Do you really want to stop all non-device jobs?')):
            self.model.kill_all_jobs()

    def hide_selected(self, *args):
        indices = [self.proxy_model.mapToSource(index) for index in
                self.jobs_view.selectionModel().selectedRows()]
        indices = [i for i in indices if i.isValid()]
        rows = [index.row() for index in indices]
        if not rows:
            return error_dialog(self, _('No job'),
                _('No job selected'), show=True)
        self.model.hide_jobs(rows)
        self.proxy_model.beginResetModel(), self.proxy_model.endResetModel()

    def hide_all(self, *args):
        self.model.hide_jobs(list(range(0,
            self.model.rowCount(QModelIndex()))))
        self.proxy_model.beginResetModel(), self.proxy_model.endResetModel()

    def show_hidden(self, *args):
        self.model.show_hidden_jobs()
        self.find(self.search.current_text)

    def closeEvent(self, e):
        self.save_state()
        return QDialog.closeEvent(self, e)

    def show(self, *args):
        self.restore_state()
        return QDialog.show(self, *args)

    def hide(self, *args):
        self.save_state()
        return QDialog.hide(self, *args)

    def reject(self):
        self.save_state()
        QDialog.reject(self)

    def find(self, query):
        self.proxy_model.find(query)

# }}}
