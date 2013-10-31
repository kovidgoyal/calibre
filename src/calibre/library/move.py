#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, os
from threading import Thread
from Queue import Empty

from calibre.utils.ipc.server import Server
from calibre.utils.ipc.job import ParallelJob


def move_library(from_, to, notification=lambda x:x):
    from calibre.db.legacy import LibraryDatabase
    time.sleep(1)
    old = LibraryDatabase(from_)
    old.move_library_to(to, notification)
    return True

class MoveLibrary(Thread):

    def __init__(self, from_, to, count, result_queue):
        Thread.__init__(self)
        self.total = count
        self.result_queue = result_queue
        self.from_ = from_
        self.to = to
        self.count = 0
        self.failed = False
        self.details = None

    def run(self):
        job = ParallelJob('move_library',
                'Move library from %s to %s'%(self.from_, self.to),
                lambda x,y:x,
                args=[self.from_, self.to])
        server = Server(pool_size=1)
        server.add_job(job)

        while not job.is_finished:
            time.sleep(0.2)
            job.update(consume_notifications=False)
            while True:
                try:
                    title = job.notifications.get_nowait()[0]
                    self.count += 1
                    self.result_queue.put((float(self.count)/self.total, title))
                except Empty:
                    break

        job.update()
        server.close()
        if not job.result:
            self.failed = True
            self.details = job.details

        if os.path.exists(job.log_path):
            os.remove(job.log_path)

