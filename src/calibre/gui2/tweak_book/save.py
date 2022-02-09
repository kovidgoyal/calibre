#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import shutil, os, errno, stat
from threading import Thread

from qt.core import (QObject, pyqtSignal, QLabel, QWidget, QHBoxLayout, Qt, QSize)

from calibre.constants import iswindows
from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils import join_with_timeout
from calibre.utils.filenames import atomic_rename, format_permissions
from polyglot.queue import LifoQueue, Empty


def save_dir_container(container, path):
    if not os.path.exists(path):
        os.makedirs(path)
    if not os.path.isdir(path):
        raise ValueError('%s is not a folder, cannot save a directory based container to it' % path)
    container.commit(path)


def save_container(container, path):
    if container.is_dir:
        return save_dir_container(container, path)
    temp = PersistentTemporaryFile(
        prefix=('_' if iswindows else '.'), suffix=os.path.splitext(path)[1], dir=os.path.dirname(path))
    if hasattr(os, 'fchmod'):
        # Ensure file permissions and owner information is preserved
        fno = temp.fileno()
        st = None
        try:
            st = os.stat(path)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
            # path may not exist if we are saving a copy, in which case we use
            # the metadata from the original book
            try:
                st = os.stat(container.path_to_ebook)
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
                # Somebody deleted the original file
        if st is not None:
            try:
                os.fchmod(fno, st.st_mode | stat.S_IWUSR)
            except OSError as err:
                if err.errno != errno.EPERM:
                    raise
                raise OSError('Failed to change permissions of {} to {} ({}), with error: {}. Most likely the {} directory has a restrictive umask'.format(
                    temp.name, oct(st.st_mode), format_permissions(st.st_mode), errno.errorcode[err.errno], os.path.dirname(temp.name)))
            try:
                os.fchown(fno, st.st_uid, st.st_gid)
            except OSError as err:
                if err.errno not in (errno.EPERM, errno.EACCES):
                    # ignore chown failure as user could be editing file belonging
                    # to a different user, in which case we really can't do anything
                    # about it short of making the file update non-atomic
                    raise

    temp.close()
    temp = temp.name
    try:
        container.commit(temp)
        atomic_rename(temp, path)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def send_message(msg=''):
    if msg:
        from calibre.gui2.listener import send_message_in_process
        send_message_in_process('bookedited:'+msg)


def find_first_existing_ancestor(path):
    while path and not os.path.exists(path):
        npath = os.path.dirname(path)
        if npath == path:
            break
        path = npath
    return path


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
        self.pi.setDisplaySize(QSize(self.label.height(), self.label.height()))
        self.pi.setVisible(True)
        self.pi.startAnimation()
        self.label.setText(_('Saving...'))

    def stop(self):
        self.pi.setVisible(False)
        self.pi.stopAnimation()
        self.label.setText('')


class SaveManager(QObject):

    start_save = pyqtSignal()
    report_error = pyqtSignal(object)
    save_done = pyqtSignal()
    check_for_completion = pyqtSignal()

    def __init__(self, parent, notify=None):
        QObject.__init__(self, parent)
        self.count = 0
        self.last_saved = -1
        self.requests = LifoQueue()
        self.notify_requests = LifoQueue()
        self.notify_data = notify
        t = Thread(name='save-thread', target=self.run)
        t.daemon = True
        t.start()
        t = Thread(name='notify-thread', target=self.notify_calibre)
        t.daemon = True
        t.start()
        self.status_widget = w = SaveWidget(parent)
        self.start_save.connect(w.start, type=Qt.ConnectionType.QueuedConnection)
        self.save_done.connect(w.stop, type=Qt.ConnectionType.QueuedConnection)

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
            error_occurred = True
            try:
                count, tdir, container = x
                error_occurred = self.process_save(count, tdir, container)
            except:
                import traceback
                traceback.print_exc()
            finally:
                self.requests.task_done()
            if not error_occurred:
                self.check_for_completion.emit()

    def notify_calibre(self):
        while True:
            if not self.notify_requests.get():
                break
            send_message(self.notify_data)

    def clear_notify_data(self):
        self.notify_data = None

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
        error_occurred = False
        try:
            self.do_save(tdir, container)
        except:
            import traceback
            self.report_error.emit(traceback.format_exc())
            error_occurred = True
        self.save_done.emit()
        if self.notify_data:
            self.notify_requests.put(True)
        return error_occurred

    def do_save(self, tdir, container):
        try:
            save_container(container, container.path_to_ebook)
        finally:
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
        self.notify_requests.put(None)
