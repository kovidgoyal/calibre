#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, shutil
from threading import Thread, Event

from PyQt4.Qt import (QFileSystemWatcher, QObject, Qt, pyqtSignal, QTimer)

from calibre import prints
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks import BOOK_EXTENSIONS

class Worker(Thread):

    def __init__(self, path, callback):
        Thread.__init__(self)
        self.daemon = True
        self.keep_running = True
        self.wake_up = Event()
        self.path, self.callback = path, callback
        self.staging = set()
        self.be = frozenset(BOOK_EXTENSIONS)

    def run(self):
        self.tdir = PersistentTemporaryDirectory('_auto_adder')
        while self.keep_running:
            self.wake_up.wait()
            self.wake_up.clear()
            if not self.keep_running:
                break
            try:
                self.auto_add()
            except:
                import traceback
                traceback.print_exc()

    def auto_add(self):
        from calibre.utils.ipc.simple_worker import fork_job
        from calibre.ebooks.metadata.opf2 import metadata_to_opf
        from calibre.ebooks.metadata.meta import metadata_from_filename

        files = [x for x in os.listdir(self.path) if x not in self.staging
                and os.path.isfile(os.path.join(self.path, x)) and
                os.access(os.path.join(self.path, x), os.R_OK|os.W_OK) and
                os.path.splitext(x)[1][1:].lower() in self.be]
        data = {}
        for fname in files:
            f = os.path.join(self.path, fname)
            tdir = tempfile.mkdtemp(dir=self.tdir)
            try:
                fork_job('calibre.ebooks.metadata.meta',
                        'forked_read_metadata', (f, tdir), no_output=True)
            except:
                import traceback
                traceback.print_exc()

            opfpath = os.path.join(tdir, 'metadata.opf')
            try:
                if os.stat(opfpath).st_size < 30:
                    raise Exception('metadata reading failed')
            except:
                mi = metadata_from_filename(fname)
                with open(opfpath, 'wb') as f:
                    f.write(metadata_to_opf(mi))
            self.staging.add(fname)
            data[fname] = tdir
        if data:
            self.callback(data)


class AutoAdder(QObject):

    metadata_read = pyqtSignal(object)

    def __init__(self, path, parent):
        QObject.__init__(self, parent)
        if path and os.path.isdir(path) and os.access(path, os.R_OK|os.W_OK):
            self.watcher = QFileSystemWatcher(self)
            self.worker = Worker(path, self.metadata_read.emit)
            self.watcher.directoryChanged.connect(self.dir_changed,
                    type=Qt.QueuedConnection)
            self.metadata_read.connect(self.add_to_db,
                    type=Qt.QueuedConnection)
            QTimer.singleShot(2000, self.initialize)
        elif path:
            prints(path,
                'is not a valid directory to watch for new ebooks, ignoring')

    def initialize(self):
        try:
            if os.listdir(self.worker.path):
                self.dir_changed()
        except:
            pass
        self.watcher.addPath(self.worker.path)

    def dir_changed(self, *args):
        if os.path.isdir(self.worker.path) and os.access(self.worker.path,
                os.R_OK|os.W_OK):
            if not self.worker.is_alive():
                self.worker.start()
            self.worker.wake_up.set()

    def stop(self):
        if hasattr(self, 'worker'):
            self.worker.keep_running = False
            self.worker.wake_up.set()

    def wait(self):
        if hasattr(self, 'worker'):
            self.worker.join()

    def add_to_db(self, data):
        from calibre.ebooks.metadata.opf2 import OPF

        gui = self.parent()
        if gui is None:
            return
        m = gui.library_view.model()
        count = 0

        for fname, tdir in data.iteritems():
            paths = [os.path.join(self.worker.path, fname)]
            mi = os.path.join(tdir, 'metadata.opf')
            if not os.access(mi, os.R_OK):
                continue
            mi = [OPF(open(mi, 'rb'), tdir,
                    populate_spine=False).to_book_metadata()]
            m.add_books(paths, [os.path.splitext(fname)[1][1:].upper()], mi,
                    add_duplicates=True)
            try:
                os.remove(os.path.join(self.worker.path, fname))
                try:
                    self.worker.staging.remove(fname)
                except KeyError:
                    pass
                shutil.rmtree(tdir)
            except:
                pass
            count += 1

        if count > 0:
            m.books_added(count)
            gui.status_bar.show_message(_(
                'Added %d book(s) automatically from %s') %
                (count, self.worker.path), 2000)
            if hasattr(gui, 'db_images'):
                gui.db_images.reset()


