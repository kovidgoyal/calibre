#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os, time
from itertools import count
from collections import namedtuple, deque
from functools import partial
from threading import RLock, Thread, Event

from calibre import detect_ncpus, force_unicode
from calibre.utils.monotonic import monotonic
from calibre.utils.ipc.simple_worker import fork_job, WorkerError
from polyglot.queue import Queue, Empty
from polyglot.builtins import iteritems, itervalues

StartEvent = namedtuple('StartEvent', 'job_id name module function args kwargs callback data')
DoneEvent = namedtuple('DoneEvent', 'job_id')


class Job(Thread):

    daemon = True

    def __init__(self, start_event, events_queue):
        Thread.__init__(self, name='JobsMonitor%s' % start_event.job_id)
        self.abort_event = Event()
        self.events_queue = events_queue
        self.job_name = start_event.name
        self.job_id = start_event.job_id
        self.func = partial(fork_job, start_event.module, start_event.function, start_event.args, start_event.kwargs, abort=self.abort_event)
        self.data, self.callback = start_event.data, start_event.callback
        self.result = self.traceback = None
        self.done = False
        self.start_time = monotonic()
        self.end_time = self.log_path = None
        self.wait_for_end = Event()
        self.start()

    def run(self):
        func, self.func = self.func, None
        try:
            result = func()
        except WorkerError as err:
            import traceback
            self.traceback = err.orig_tb or traceback.format_exc()
            self.log_path = getattr(err, 'log_path', None)
        else:
            self.result, self.log_path = result['result'], result['stdout_stderr']
        self.done = True
        self.end_time = monotonic()
        self.wait_for_end.set()
        self.events_queue.put(DoneEvent(self.job_id))

    @property
    def was_aborted(self):
        return self.done and self.result is None and self.abort_event.is_set()

    @property
    def failed(self):
        return bool(self.traceback) or self.was_aborted

    def remove_log(self):
        lp, self.log_path = self.log_path, None
        if lp:
            try:
                os.remove(lp)
            except EnvironmentError:
                pass

    def read_log(self):
        ans = ''
        if self.log_path is not None:
            try:
                with lopen(self.log_path, 'rb') as f:
                    ans = f.read()
            except EnvironmentError:
                pass
        if isinstance(ans, bytes):
            ans = force_unicode(ans, 'utf-8')
        return ans


class JobsManager(object):

    def __init__(self, opts, log):
        mj = opts.max_jobs
        if mj < 1:
            mj = detect_ncpus()
        self.log = log
        self.max_jobs = max(1, mj)
        self.max_job_time = max(0, opts.max_job_time * 60)
        self.lock = RLock()
        self.jobs = {}
        self.finished_jobs = {}
        self.events = Queue()
        self.job_id = count()
        self.waiting_job_ids = set()
        self.waiting_jobs = deque()
        self.max_block = None
        self.shutting_down = False
        self.event_loop = None

    def start_job(self, name, module, func, args=(), kwargs=None, job_done_callback=None, job_data=None):
        with self.lock:
            if self.shutting_down:
                return None
            if self.event_loop is None:
                self.event_loop = t = Thread(name='JobsEventLoop', target=self.run)
                t.daemon = True
                t.start()
            job_id = next(self.job_id)
            self.events.put(StartEvent(job_id, name, module, func, args, kwargs or {}, job_done_callback, job_data))
            self.waiting_job_ids.add(job_id)
            return job_id

    def job_status(self, job_id):
        with self.lock:
            if not self.shutting_down:
                if job_id in self.finished_jobs:
                    job = self.finished_jobs[job_id]
                    return 'finished', job.result, job.traceback, job.was_aborted
                if job_id in self.jobs:
                    return 'running', None, None, None
                if job_id in self.waiting_job_ids:
                    return 'waiting', None, None, None
        return None, None, None, None

    def abort_job(self, job_id):
        job = self.jobs.get(job_id)
        if job is not None:
            job.abort_event.set()

    def wait_for_running_job(self, job_id, timeout=None):
        job = self.jobs.get(job_id)
        if job is not None:
            job.wait_for_end.wait(timeout)
            if not job.done:
                return False
            while job_id not in self.finished_jobs:
                time.sleep(0.001)
            return True

    def shutdown(self, timeout=5.0):
        with self.lock:
            self.shutting_down = True
            for job in itervalues(self.jobs):
                job.abort_event.set()
            self.events.put(False)

    def wait_for_shutdown(self, wait_till):
        for job in itervalues(self.jobs):
            delta = wait_till - monotonic()
            if delta > 0:
                job.join(delta)
        if self.event_loop is not None:
            delta = wait_till - monotonic()
            if delta > 0:
                self.event_loop.join(delta)

    # Internal API {{{

    def run(self):
        while not self.shutting_down:
            if self.max_block is None:
                ev = self.events.get()
            else:
                try:
                    ev = self.events.get(block=True, timeout=self.max_block)
                except Empty:
                    ev = None
            if self.shutting_down:
                break
            if ev is None:
                self.abort_hanging_jobs()
            elif isinstance(ev, StartEvent):
                self.waiting_jobs.append(ev)
                self.start_waiting_jobs()
            elif isinstance(ev, DoneEvent):
                self.job_finished(ev.job_id)
            elif ev is False:
                break

    def start_waiting_jobs(self):
        with self.lock:
            while self.waiting_jobs and len(self.jobs) < self.max_jobs:
                ev = self.waiting_jobs.popleft()
                self.jobs[ev.job_id] = Job(ev, self.events)
                self.waiting_job_ids.discard(ev.job_id)
        self.update_max_block()

    def update_max_block(self):
        with self.lock:
            mb = None
            now = monotonic()
            for job in itervalues(self.jobs):
                if not job.done and not job.abort_event.is_set():
                    delta = self.max_job_time - (now - job.start_time)
                    if delta <= 0:
                        self.max_block = 0
                        return
                    if mb is None:
                        mb = delta
                    else:
                        mb = min(mb, delta)
            self.max_block = mb

    def abort_hanging_jobs(self):
        now = monotonic()
        found = False
        for job in itervalues(self.jobs):
            if not job.done and not job.abort_event.is_set():
                delta = self.max_job_time - (now - job.start_time)
                if delta <= 0:
                    job.abort_event.set()
                    found = True
        if found:
            self.update_max_block()

    def job_finished(self, job_id):
        with self.lock:
            self.finished_jobs[job_id] = job = self.jobs.pop(job_id)
            if job.callback is not None:
                try:
                    job.callback(job)
                except Exception:
                    import traceback
                    self.log.error('Error running callback for job: %s:\n%s' % (job.name, traceback.format_exc()))
        self.prune_finished_jobs()
        if job.traceback and not job.was_aborted:
            logdata = job.read_log()
            self.log.error('The job: %s failed:\n%s\n%s' % (job.job_name, logdata, job.traceback))
        job.remove_log()
        self.start_waiting_jobs()

    def prune_finished_jobs(self):
        with self.lock:
            remove = []
            now = monotonic()
            for job_id, job in iteritems(self.finished_jobs):
                if now - job.end_time > 3600:
                    remove.append(job_id)
            for job_id in remove:
                del self.finished_jobs[job_id]
    # }}}


def sleep_test(x):
    time.sleep(x)
    return x


def error_test():
    raise Exception('a testing error')
