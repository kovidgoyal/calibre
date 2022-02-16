#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


from threading import Thread
from queue import Queue


check_for_work = object()
quit = object()


class Worker(Thread):

    def __init__(self, jobs_queue, supervise_queue):
        super().__init__(name='FTSWorker', daemon=True)
        self.currently_working = False
        self.jobs_queue = jobs_queue
        self.supervise_queue = supervise_queue

    def run(self):
        while True:
            x = self.jobs_queue.get()
            if x is quit:
                break


class Pool:

    def __init__(self, dbref):
        self.max_workers = 1
        self.jobs_queue = Queue()
        self.supervise_queue = Queue()
        self.workers = []
        self.initialized = False
        self.dbref = dbref

    def initialize(self):
        if not self.initialized:
            self.supervisor_thread = Thread(name='FTSSupervisor', daemon=True, target=self.supervise)
            self.supervisor_thread.start()
            self.expand_workers()
            self.initialized = True

    def expand_workers(self):
        while len(self.workers) < self.max_workers:
            w = Worker(self.jobs_queue, self.supervise_queue)
            self.workers.append(w)
            w.start()

    def check_for_work(self):
        self.initialize()
        self.supervise_queue.put(check_for_work)

    def add_job(self, book_id, fmt, path, fmt_size, fmt_hash):
        self.initialize()
        job = Job(book_id, fmt, path, fmt_size, fmt_hash)
        self.jobs_queue.put(job)

    def supervise(self):
        while True:
            x = self.supervise_queue.get()
            if x is check_for_work:
                pass
            elif x is quit:
                break
