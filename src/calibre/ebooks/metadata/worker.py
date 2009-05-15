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
                job.update()
                if not job.is_finished:
                    running = True

            if not running:
                break

        server.close()
        time.sleep(1)

        if self.canceled:
            return

        for id in ids:
            print 11111111, id
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
