#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from threading import Thread
from Queue import Empty
import os, time, sys

from calibre.utils.ipc.job import ParallelJob
from calibre.utils.ipc.server import Server
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre import prints


def debug(*args):
    prints(*args)
    sys.stdout.flush()

def read_metadata_(task, tdir, notification=lambda x,y:x):
    from calibre.ebooks.metadata.meta import metadata_from_formats
    from calibre.ebooks.metadata.opf2 import OPFCreator
    for x in task:
        id, formats = x
        if isinstance(formats, basestring): formats = [formats]
        mi = metadata_from_formats(formats)
        mi.cover = None
        cdata = None
        if mi.cover_data:
            cdata = mi.cover_data[-1]
        mi.cover_data = None
        opf = OPFCreator(tdir, mi)
        with open(os.path.join(tdir, '%s.opf'%id), 'wb') as f:
            opf.render(f)
        if cdata:
            with open(os.path.join(tdir, str(id)), 'wb') as f:
                f.write(cdata)
        notification(0.5, id)

class Progress(object):

    def __init__(self, result_queue, tdir):
        self.result_queue = result_queue
        self.tdir = tdir

    def __call__(self, id):
        cover = os.path.join(self.tdir, str(id))
        if not os.path.exists(cover): cover = None
        self.result_queue.put((id, os.path.join(self.tdir, '%s.opf'%id), cover))

class ReadMetadata(Thread):

    def __init__(self, tasks, result_queue):
        self.tasks, self.result_queue = tasks, result_queue
        self.canceled = False
        Thread.__init__(self)
        self.daemon = True
        self.tdir = PersistentTemporaryDirectory('_rm_worker')


    def run(self):
        jobs, ids = set([]), set([])
        for t in self.tasks:
            for b in t:
                ids.add(b[0])
        progress = Progress(self.result_queue, self.tdir)
        server = Server()
        for i, task in enumerate(self.tasks):
            job = ParallelJob('read_metadata',
                'Read metadata (%d of %d)'%(i, len(self.tasks)),
                lambda x,y:x,  args=[task, self.tdir])
            jobs.add(job)
            server.add_job(job)

        while not self.canceled:
            time.sleep(0.2)
            running = False
            for job in jobs:
                while True:
                    try:
                        id = job.notifications.get_nowait()[-1]
                        if id in ids:
                            progress(id)
                            ids.remove(id)
                    except Empty:
                        break
                job.update(consume_notifications=False)
                if not job.is_finished:
                    running = True

            if not running:
                break

        server.close()
        time.sleep(1)

        if self.canceled:
            return

        for id in ids:
            progress(id)

        for job in jobs:
            if job.failed:
                prints(job.details)
            if os.path.exists(job.log_path):
                os.remove(job.log_path)


def read_metadata(paths, result_queue, chunk=50):
    tasks = []
    pos = 0
    while pos < len(paths):
        tasks.append(paths[pos:pos+chunk])
        pos += chunk
    t = ReadMetadata(tasks, result_queue)
    t.start()
    return t

class SaveWorker(Thread):

    def __init__(self, result_queue, db, ids, path, by_author=False,
            single_dir=False,  single_format=None):
        Thread.__init__(self)
        self.daemon = True
        self.path, self.by_author = path, by_author
        self.single_dir, self.single_format = single_dir, single_format
        self.ids = ids
        self.library_path = db.library_path
        self.canceled = False
        self.result_queue = result_queue
        self.error = None
        self.start()

    def run(self):
        server = Server()
        ids = set(self.ids)
        tasks = server.split(list(ids))
        jobs = set([])
        for i, task in enumerate(tasks):
            tids = [x[-1] for x in task]
            job = ParallelJob('save_book',
                    'Save books (%d of %d)'%(i, len(tasks)),
                    lambda x,y:x,
                    args=[tids, self.library_path, self.path, self.single_dir,
                        self.single_format, self.by_author])
            jobs.add(job)
            server.add_job(job)


        while not self.canceled:
            time.sleep(0.2)
            running = False
            for job in jobs:
                job.update(consume_notifications=False)
                while True:
                    try:
                        id, title, ok = job.notifications.get_nowait()[0]
                        if id in ids:
                            self.result_queue.put((id, title, ok))
                            ids.remove(id)
                    except Empty:
                        break
                if not job.is_finished:
                    running = True

            if not running:
                break

        server.close()
        time.sleep(1)

        if self.canceled:
            return

        for job in jobs:
            if job.failed:
                prints(job.details)
                self.error = job.details
            if os.path.exists(job.log_path):
                os.remove(job.log_path)


def save_book(task, library_path, path, single_dir, single_format,
        by_author, notification=lambda x,y:x):
    from calibre.library.database2 import LibraryDatabase2
    db = LibraryDatabase2(library_path)

    def callback(id, title):
        notification((id, title, True))
        return True

    if single_format is None:
        failures = []
        db.export_to_dir(path, task, index_is_id=True, byauthor=by_author,
                callback=callback, single_dir=single_dir)
    else:
        failures = db.export_single_format_to_dir(path, task, single_format,
                index_is_id=True, callback=callback)

    for id, title in failures:
        notification((id, title, False))

