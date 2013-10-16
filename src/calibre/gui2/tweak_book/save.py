#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import shutil, os
from threading import Thread
from Queue import LifoQueue, Empty

from PyQt4.Qt import (QObject, pyqtSignal, QLabel, QWidget, QHBoxLayout, Qt)

from calibre.constants import iswindows
from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils import join_with_timeout
from calibre.utils.filenames import atomic_rename

class SaveWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        self.setLayout(l)
        self.label = QLabel('')
        self.pi = ProgressIndicator(self, 24)
        l.addWidget(self.label)
        l.addWidget(self.pi)
        l.setContentsMargins(0, 0, 0, 0)
        self.pi.setVisible(False)
        self.stop()

    def start(self):
        self.pi.setVisible(True)
        self.pi.startAnimation()
        self.label.setText(_('Saving...'))

    def stop(self):
        self.pi.setVisible(False)
        self.pi.stopAnimation()
        self.label.setText(_('Saved'))

class SaveManager(QObject):

    start_save = pyqtSignal()
    report_error = pyqtSignal(object)
    save_done = pyqtSignal()

    def __init__(self, parent):
        QObject.__init__(self, parent)
        self.count = 0
        self.last_saved = -1
        self.requests = LifoQueue()
        t = Thread(name='save-thread', target=self.run)
        t.daemon = True
        t.start()
        self.status_widget = w = SaveWidget(parent)
        self.start_save.connect(w.start, type=Qt.QueuedConnection)
        self.save_done.connect(w.stop, type=Qt.QueuedConnection)

    def schedule(self, tdir, container):
        self.count += 1
        self.requests.put((self.count, tdir, container))

    def run(self):
        while True:
            x = self.requests.get()
            if x is None:
                self.requests.task_done()
                self.__empty_queue()
                break
            try:
                count, tdir, container = x
                self.process_save(count, tdir, container)
            except:
                import traceback
                traceback.print_exc()
            finally:
                self.requests.task_done()

    def __empty_queue(self):
        ' Only to be used during shutdown '
        while True:
            try:
                self.requests.get_nowait()
            except Empty:
                break
            else:
                self.requests.task_done()

    def process_save(self, count, tdir, container):
        if count <= self.last_saved:
            shutil.rmtree(tdir, ignore_errors=True)
            return
        self.last_saved = count
        self.start_save.emit()
        try:
            self.do_save(tdir, container)
        except:
            import traceback
            self.report_error.emit(traceback.format_exc())
        self.save_done.emit()

    def do_save(self, tdir, container):
        temp = None
        try:
            path = container.path_to_ebook
            temp = PersistentTemporaryFile(
                prefix=('_' if iswindows else '.'), suffix=os.path.splitext(path)[1], dir=os.path.dirname(path))
            temp.close()
            temp = temp.name
            container.commit(temp)
            atomic_rename(temp, path)
        finally:
            if temp and os.path.exists(temp):
                os.remove(temp)
            shutil.rmtree(tdir, ignore_errors=True)

    @property
    def has_tasks(self):
        return bool(self.requests.unfinished_tasks)

    def wait(self, timeout=30):
        if timeout is None:
            self.requests.join()
        else:
            try:
                join_with_timeout(self.requests, timeout)
            except RuntimeError:
                return False
        return True

    def shutdown(self):
        self.requests.put(None)
