#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from functools import partial
from threading import Thread, Event
import os, stat

from PyQt5.Qt import (
    QSize, QStackedLayout, QWidget, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QIcon, Qt, pyqtSignal, QGridLayout,
    QProgressBar, QDialog, QDialogButtonBox
)

from calibre import human_readable
from calibre.gui2 import choose_dir, error_dialog
from calibre.gui2.widgets2 import Dialog
from calibre.utils.exim import all_known_libraries, export
from calibre.utils.icu import numeric_sort_key

def disk_usage(path_to_dir, abort=None):
    stack = [path_to_dir]
    ans = 0
    while stack:
        bdir = stack.pop()
        try:
            for child in os.listdir(bdir):
                cpath = os.path.join(bdir, child)
                if abort is not None and abort.is_set():
                    return -1
                r = os.lstat(cpath)
                if stat.S_ISDIR(r.st_mode):
                    stack.append(cpath)
                ans += r.st_size
        except EnvironmentError:
            pass
    return ans

class RunAction(QDialog):

    update_current_signal = pyqtSignal(object, object, object)
    update_overall_signal = pyqtSignal(object, object, object)
    finish_signal = pyqtSignal()

    def __init__(self, title, err_msg, action, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Working please wait...'))
        self.title, self.action, self.tb, self.err_msg = title, action, None, err_msg
        self.abort = Event()
        self.setup_ui()
        t = Thread(name='ExImWorker', target=self.run_action)
        t.daemon = True
        t.start()

    def setup_ui(self):
        self.l = l = QGridLayout(self)
        self.bb = QDialogButtonBox(self)
        self.bb.setStandardButtons(self.bb.Cancel)
        self.bb.rejected.connect(self.reject)

        self.la1 = la = QLabel('<h2>' + self.title)
        l.addWidget(la, 0, 0, 1, -1)
        self.la2 = la = QLabel(_('Total:'))
        l.addWidget(la, l.rowCount(), 0)
        self.overall = p = QProgressBar(self)
        p.setMinimum(0), p.setValue(0), p.setMaximum(0)
        p.setMinimumWidth(450)
        l.addWidget(p, l.rowCount()-1, 1)
        self.omsg = la = QLabel(self)
        la.setMaximumWidth(450)
        l.addWidget(la, l.rowCount(), 1)
        self.la3 = la = QLabel(_('Current:'))
        l.addWidget(la, l.rowCount(), 0)
        self.current = p = QProgressBar(self)
        p.setMinimum(0), p.setValue(0), p.setMaximum(0)
        l.addWidget(p, l.rowCount()-1, 1)
        self.cmsg = la = QLabel(self)
        la.setMaximumWidth(450)
        l.addWidget(la, l.rowCount(), 1)
        l.addWidget(self.bb, l.rowCount(), 0, 1, -1)
        self.update_current_signal.connect(self.update_current, type=Qt.QueuedConnection)
        self.update_overall_signal.connect(self.update_overall, type=Qt.QueuedConnection)
        self.finish_signal.connect(self.finish_processing, type=Qt.QueuedConnection)

    def update_overall(self, msg, count, total):
        self.overall.setMaximum(total), self.overall.setValue(count)
        self.omsg.setText(msg)

    def update_current(self, msg, count, total):
        self.current.setMaximum(total), self.current.setValue(count)
        self.cmsg.setText(msg)

    def reject(self):
        self.abort.set()
        self.bb.button(self.bb.Cancel).setEnabled(False)

    def finish_processing(self):
        if self.abort.is_set():
            return QDialog.reject(self)
        if self.tb is not None:
            error_dialog(self, _('Failed'), self.err_msg + ' ' + _('Click "Show Details" for more information.'),
                            det_msg=self.tb, show=True)
        self.accept()

    def run_action(self):
        try:
            self.action(abort=self.abort, progress1=self.update_overall_signal.emit, progress2=self.update_current_signal.emit)
        except Exception:
            import traceback
            self.tb = traceback.format_exc()
        self.finish_signal.emit()

class EximDialog(Dialog):

    update_disk_usage = pyqtSignal(object, object)

    def __init__(self, parent=None, initial_panel=None):
        self.initial_panel = initial_panel
        self.abort_disk_usage = Event()
        Dialog.__init__(self, _('Export/Import all calibre data'), 'exim-calibre', parent=parent)

    def sizeHint(self):
        return QSize(800, 600)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.stack = s = QStackedLayout()
        l.addLayout(s)
        l.addWidget(self.bb)
        self.welcome = w = QWidget(self)
        s.addWidget(w)
        w.l = l = QVBoxLayout(w)
        w.la = la = QLabel('<p>' + _(
            'You can export all calibre data, including your books, settings and plugins'
            ' into a single directory. Then, you can use this tool to re-import all that'
            ' data into a different calibre install, for example, on another computer.') + '<p>' +
        _(
            'This is a simple way to move your calibre installation with all its data to'
            ' a new computer, or to replicate your current setup on a second computer.'
        ))
        la.setWordWrap(True)
        l.addWidget(la)
        l.addSpacing(20)
        self.exp_button = b = QPushButton(_('&Export all your calibre data'))
        b.clicked.connect(partial(self.show_panel, 'export'))
        l.addWidget(b), l.addSpacing(20)
        self.imp_button = b = QPushButton(_('&Import previously exported data'))
        b.clicked.connect(partial(self.show_panel, 'import'))
        l.addWidget(b), l.addStretch(20)

        self.setup_export_panel()
        self.show_panel(self.initial_panel)

    def export_lib_text(self, lpath, size=None):
        return _('{0} [Size: {1}]\nin {2}').format(
            os.path.basename(lpath), ('' if size < 0 else human_readable(size))
            if size is not None else _('Calculating...'), os.path.dirname(lpath))

    def setup_export_panel(self):
        self.export_panel = w = QWidget(self)
        self.stack.addWidget(w)
        w.l = l = QVBoxLayout(w)
        w.la = la = QLabel(_('Select which libraries you want to export below'))
        la.setWordWrap(True), l.addWidget(la)
        self.lib_list = ll = QListWidget(self)
        l.addWidget(ll)
        ll.setSelectionMode(ll.ExtendedSelection)
        ll.setStyleSheet('QListView::item { padding: 5px }')
        ll.setAlternatingRowColors(True)
        lpaths = all_known_libraries()
        for lpath in sorted(lpaths, key=lambda x:numeric_sort_key(os.path.basename(x))):
            i = QListWidgetItem(self.export_lib_text(lpath), ll)
            i.setData(Qt.UserRole, lpath)
            i.setData(Qt.UserRole+1, lpaths[lpath])
            i.setIcon(QIcon(I('lt.png')))
            i.setSelected(True)
        self.update_disk_usage.connect((
            lambda i, sz: self.lib_list.item(i).setText(self.export_lib_text(self.lib_list.item(i).data(Qt.UserRole), sz))), type=Qt.QueuedConnection)
        t = Thread(name='GetLibSizes', target=self.get_lib_sizes)
        t.daemon = True
        t.start()

    def get_lib_sizes(self):
        for i in xrange(self.lib_list.count()):
            path = self.lib_list.item(i).data(Qt.UserRole)
            try:
                sz = disk_usage(path, abort=self.abort_disk_usage)
            except Exception:
                import traceback
                traceback.print_exc()
            self.update_disk_usage.emit(i, sz)

    def show_panel(self, which):
        self.validate = self.run_action = lambda : True
        if which is None:
            self.bb.setStandardButtons(self.bb.Cancel)
        else:
            if which == 'export':
                self.validate = self.validate_export
                self.run_action = self.run_export_action
            self.bb.setStandardButtons(self.bb.Ok | self.bb.Cancel)
        self.stack.setCurrentIndex({'export':1, 'import':2}.get(which, 0))

    def validate_export(self):
        path = choose_dir(self, 'export-calibre-dir', _('Choose a directory to export to'))
        if not path:
            return False
        if os.listdir(path):
            error_dialog(self, _('Export dir not empty'), _(
                'The directory you choose to export the data to must be empty.'), show=True)
            return False
        self.export_dir = path
        return True

    def run_export_action(self):
        from calibre.gui2.ui import get_gui
        library_paths = {i.data(Qt.UserRole):i.data(Qt.UserRole+1) for i in self.lib_list.selectedItems()}
        dbmap = {}
        gui = get_gui()
        if gui is not None:
            db = gui.current_db.new_api
            dbmap[db.library_path] = db
        return RunAction(_('Exporting all calibre data...'), _(
            'Failed to export data.'), partial(export, self.export_dir, library_paths=library_paths, dbmap=dbmap),
                      parent=self).exec_() == Dialog.Accepted

    def accept(self):
        if not self.validate():
            return
        self.abort_disk_usage.set()
        if self.run_action():
            Dialog.accept(self)

    def reject(self):
        self.abort_disk_usage.set()
        Dialog.reject(self)

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = EximDialog(initial_panel='export')
    d.exec_()
    del app
