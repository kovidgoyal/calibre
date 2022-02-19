#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os, sys
import traceback, subprocess
from contextlib import suppress
from queue import Queue
from threading import Thread

from calibre.utils.ipc.simple_worker import start_pipe_worker

check_for_work = object()
quit = object()


class Job:

    def __init__(self, book_id, fmt, path, fmt_size, fmt_hash):
        self.book_id = book_id
        self.fmt = fmt
        self.fmt_size = fmt_size
        self.fmt_hash = fmt_hash
        self.path = path


class Result:

    def __init__(self, job, err_msg=''):
        self.book_id = job.book_id
        self.fmt = job.fmt
        self.fmt_size = job.fmt_size
        self.fmt_hash = job.fmt_hash
        self.ok = not bool(err_msg)
        if self.ok:
            with open(job.path + '.txt', 'rb') as src:
                try:
                    self.text = src.read().decode('utf-8', 'replace')
                except Exception:
                    self.ok = False
                    self.text = traceback.format_exc()
        else:
            self.text = err_msg


class Worker(Thread):

    def __init__(self, jobs_queue, supervise_queue):
        super().__init__(name='FTSWorker', daemon=True)
        self.currently_working = False
        self.jobs_queue = jobs_queue
        self.supervise_queue = supervise_queue
        self.keep_going = True
        self.working = False

    def run(self):
        while self.keep_going:
            x = self.jobs_queue.get()
            if x is quit:
                break
            self.working = True
            try:
                res = self.run_job(x)
                if res is not None and self.keep_going:
                    self.supervise_queue.put(res)
            except Exception:
                tb = traceback.format_exc()
                traceback.print_exc()
                if self.keep_going:
                    self.supervise_queue.put(Result(x, tb))
            finally:
                self.working = False

    def run_job(self, job):
        txtpath = job.path + '.txt'
        errpath = job.path + '.error'
        try:
            with open(errpath, 'wb') as error:
                p = start_pipe_worker(
                    f'from calibre.db.fts.text import main; main({job.path!r})',
                    stdout=subprocess.DEVNULL, stderr=error, stdin=subprocess.DEVNULL, priority='low',
                )
                while self.keep_going:
                    with suppress(subprocess.TimeoutExpired):
                        p.wait(0.1)
                        break
                if p.returncode is None:
                    p.kill()
                    return
                if os.path.exists(txtpath):
                    return Result(job)
            with open(errpath, 'rb') as f:
                err = f.read().decode('utf-8', 'replace')
                return Result(job, err)
        finally:
            with suppress(OSError):
                os.remove(job.path)
            with suppress(OSError):
                os.remove(txtpath)
            with suppress(OSError):
                os.remove(errpath)


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

    def shutdown(self):
        if self.initialized:
            self.initialized = False
            self.supervise_queue.put(quit)
            for w in self.workers:
                w.keep_going = False
                self.jobs_queue.put(quit)
            self.supervisor_thread.join()
            for w in self.workers:
                w.join()

    def prune_dead_workers(self):
        self.workers = [w for w in self.workers if w.is_alive()]

    def expand_workers(self):
        self.prune_dead_workers()
        while len(self.workers) < self.max_workers:
            self.workers.append(self.create_worker())

    def create_worker(self):
        w = Worker(self.jobs_queue, self.supervise_queue)
        w.start()
        while not w.is_alive():
            w.join(0.01)
        return w

    def shrink_workers(self):
        self.prune_dead_workers()
        extra = len(self.workers) - self.max_workers
        while extra > 0:
            self.jobs_queue.put(quit)
            extra -= 1

    # external API {{{
    @property
    def num_of_workers(self):
        return len(self.workers)

    @num_of_workers.setter
    def num_of_workers(self, num):
        self.initialize()
        self.prune_dead_workers()
        num = max(1, num)
        self.max_workers = num
        if num > len(self.workers):
            self.expand_workers()
        elif num < self.workers:
            self.shrink_workers()

    @property
    def num_of_idle_workers(self):
        return sum(1 if w.working else 0 for w in self.workers)

    def check_for_work(self):
        self.initialize()
        self.supervise_queue.put(check_for_work)

    def add_job(self, book_id, fmt, path, fmt_size, fmt_hash):
        self.initialize()
        job = Job(book_id, fmt, path, fmt_size, fmt_hash)
        self.jobs_queue.put(job)

    def commit_result(self, result):
        text = result.text
        if not result.ok:
            print(f'Failed to get text from book_id: {result.book_id} format: {result.fmt}', file=sys.stderr)
            print(text, file=sys.stderr)
            text = ''
        db = self.dbref()
        if db is not None:
            db.commit_fts_result(result.book_id, result.fmt, result.fmt_size, result.fmt_hash, text)
    # }}}

    def do_check_for_work(self):
        db = self.dbref()
        if db is not None:
            db.queue_next_fts_job()

    def supervise(self):
        while True:
            x = self.supervise_queue.get()
            try:
                if x is check_for_work:
                    self.do_check_for_work()
                elif x is quit:
                    break
                elif isinstance(x, Result):
                    self.commit_result(x)
                    self.do_check_for_work()
            except Exception:
                traceback.print_exc()
