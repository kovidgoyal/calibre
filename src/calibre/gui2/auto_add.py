#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, shutil, time
from threading import Thread, Event

from PyQt4.Qt import (QFileSystemWatcher, QObject, Qt, pyqtSignal, QTimer)

from calibre import prints
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import gprefs
from calibre.gui2.dialogs.duplicates import DuplicatesQuestion

AUTO_ADDED = frozenset(BOOK_EXTENSIONS) - {'pdr', 'mbp', 'tan'}

class Worker(Thread):

    def __init__(self, path, callback):
        Thread.__init__(self)
        self.daemon = True
        self.keep_running = True
        self.wake_up = Event()
        self.path, self.callback = path, callback
        self.staging = set()
        self.allowed = AUTO_ADDED - frozenset(gprefs['blocked_auto_formats'])

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
        from calibre.utils.ipc.simple_worker import fork_job, WorkerError
        from calibre.ebooks.metadata.opf2 import metadata_to_opf
        from calibre.ebooks.metadata.meta import metadata_from_filename

        files = [x for x in os.listdir(self.path) if
                    # Must not be in the process of being added to the db
                    x not in self.staging
                    # Firefox creates 0 byte placeholder files when downloading
                    and os.stat(os.path.join(self.path, x)).st_size > 0
                    # Must be a file
                    and os.path.isfile(os.path.join(self.path, x))
                    # Must have read and write permissions
                    and os.access(os.path.join(self.path, x), os.R_OK|os.W_OK)
                    # Must be a known ebook file type
                    and os.path.splitext(x)[1][1:].lower() in self.allowed
                ]
        data = {}
        # Give any in progress copies time to complete
        time.sleep(2)

        for fname in files:
            f = os.path.join(self.path, fname)

            # Try opening the file for reading, if the OS prevents us, then at
            # least on windows, it means the file is open in another
            # application for writing. We will get notified by
            # QFileSystemWatcher when writing is completed, so ignore for now.
            try:
                open(f, 'rb').close()
            except:
                continue
            tdir = tempfile.mkdtemp(dir=self.tdir)
            try:
                fork_job('calibre.ebooks.metadata.meta',
                        'forked_read_metadata', (f, tdir), no_output=True)
            except WorkerError as e:
                prints('Failed to read metadata from:', fname)
                prints(e.orig_tb)
            except:
                import traceback
                traceback.print_exc()

            # Ensure that the pre-metadata file size is present. If it isn't,
            # write 0 so that the file is rescanned
            szpath = os.path.join(tdir, 'size.txt')
            try:
                with open(szpath, 'rb') as f:
                    int(f.read())
            except:
                with open(szpath, 'wb') as f:
                    f.write(b'0')

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
    auto_convert = pyqtSignal(object)

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
            self.auto_convert.connect(self.do_auto_convert,
                    type=Qt.QueuedConnection)
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

        needs_rescan = False
        duplicates = []
        added_ids = set()

        for fname, tdir in data.iteritems():
            paths = [os.path.join(self.worker.path, fname)]
            sz = os.path.join(tdir, 'size.txt')
            try:
                with open(sz, 'rb') as f:
                    sz = int(f.read())
                if sz != os.stat(paths[0]).st_size:
                    raise Exception('Looks like the file was written to after'
                            ' we tried to read metadata')
            except:
                needs_rescan = True
                try:
                    self.worker.staging.remove(fname)
                except KeyError:
                    pass

                continue

            mi = os.path.join(tdir, 'metadata.opf')
            if not os.access(mi, os.R_OK):
                continue
            mi = [OPF(open(mi, 'rb'), tdir,
                    populate_spine=False).to_book_metadata()]
            dups, ids = m.add_books(paths,
                    [os.path.splitext(fname)[1][1:].upper()], mi,
                    add_duplicates=not gprefs['auto_add_check_for_duplicates'],
                    return_ids=True)
            added_ids |= set(ids)
            num = len(ids)
            if dups:
                path = dups[0][0]
                with open(os.path.join(tdir, 'dup_cache.'+dups[1][0].lower()),
                        'wb') as dest, open(path, 'rb') as src:
                    shutil.copyfileobj(src, dest)
                    dups[0][0] = dest.name
                duplicates.append(dups)

            try:
                os.remove(paths[0])
                self.worker.staging.remove(fname)
            except:
                pass
            count += num

        if duplicates:
            paths, formats, metadata = [], [], []
            for p, f, mis in duplicates:
                paths.extend(p)
                formats.extend(f)
                metadata.extend(mis)
            dups = [(mi, mi.cover, [p]) for mi, p in zip(metadata, paths)]
            d = DuplicatesQuestion(m.db, dups, parent=gui)
            dups = tuple(d.duplicates)
            if dups:
                paths, formats, metadata = [], [], []
                for mi, cover, book_paths in dups:
                    paths.extend(book_paths)
                    formats.extend([p.rpartition('.')[-1] for p in book_paths])
                    metadata.extend([mi for i in book_paths])
                ids = m.add_books(paths, formats, metadata,
                        add_duplicates=True, return_ids=True)[1]
                added_ids |= set(ids)
                num = len(ids)
                count += num

        for tdir in data.itervalues():
            try:
                shutil.rmtree(tdir)
            except:
                pass

        if added_ids and gprefs['auto_add_auto_convert']:
            self.auto_convert.emit(added_ids)

        if count > 0:
            m.books_added(count)
            gui.status_bar.show_message(_(
                'Added %(num)d book(s) automatically from %(src)s') %
                dict(num=count, src=self.worker.path), 2000)
            if hasattr(gui, 'db_images'):
                gui.db_images.reset()

        if needs_rescan:
            QTimer.singleShot(2000, self.dir_changed)

    def do_auto_convert(self, added_ids):
        gui = self.parent()
        gui.iactions['Convert Books'].auto_convert_auto_add(added_ids)

