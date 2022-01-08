#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, tempfile, json
from threading import Thread, RLock, Event

from calibre.utils.ipc.job import BaseJob
from calibre.utils.logging import GUILog
from calibre.ptempfile import base_dir
from polyglot.queue import Queue


class ThreadedJob(BaseJob):

    def __init__(self,
            type_, description,

            func, args, kwargs,

            callback,

            max_concurrent_count=1,
            killable=True,
            log=None):
        '''
        A job that is run in its own thread in the calibre main process

        :param type_: The type of this job (a string). The type is used in
        conjunction with max_concurrent_count to prevent too many jobs of the
        same type from running

        :param description: A user viewable job description

        :func: The function that actually does the work. This function *must*
        accept at least three keyword arguments: abort, log and notifications. abort is
        An Event object. func should periodically check abort.is_set() and if
        it is True, it should stop processing as soon as possible. notifications
        is a Queue. func should put progress notifications into it in the form
        of a tuple (frac, msg). frac is a number between 0 and 1 indicating
        progress and msg is a string describing the progress. log is a Log
        object which func should use for all debugging output. func should
        raise an Exception to indicate failure. This exception is stored in
        job.exception and can thus be used to pass arbitrary information to
        callback.

        :param args,kwargs: These are passed to func when it is called

        :param callback: A callable that is called on completion of this job.
        Note that it is not called if the user kills the job. Check job.failed
        to see if the job succeeded or not. And use job.log to get the job log.

        :param killable: If False the GUI won't let the user kill this job

        :param log: Must be a subclass of GUILog or None. If None a default
        GUILog is created.
        '''
        BaseJob.__init__(self, description)

        self.type = type_
        self.max_concurrent_count = max_concurrent_count
        self.killable = killable
        self.callback = callback
        self.abort = Event()
        self.exception = None

        kwargs['notifications'] = self.notifications
        kwargs['abort'] = self.abort
        self.log = GUILog() if log is None else log
        kwargs['log'] = self.log

        self.func, self.args, self.kwargs = func, args, kwargs
        self.consolidated_log = None

    def start_work(self):
        self.start_time = time.time()
        self.log('Starting job:', self.description)
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.exception = e
            self.failed = True
            self.log.exception('Job: "%s" failed with error:'%self.description)
            self.log.debug('Called with args:', self.args, self.kwargs)

        self.duration = time.time() - self.start_time
        try:
            self.callback(self)
        except:
            import traceback
            traceback.print_exc()
        self._cleanup()

    def _cleanup(self):

        try:
            self.consolidate_log()
        except:
            if self.log is not None:
                self.log.exception('Log consolidation failed')

        # No need to keep references to these around anymore
        self.func = self.args = self.kwargs = self.notifications = None
        # We can't delete self.callback as it might be a Dispatch object and if
        # it is garbage collected it won't work

    def kill(self):
        if self.start_time is None:
            self.start_time = time.time()
            self.duration = 0.0001
        else:
            self.duration = time.time() - self.start_time
            self.abort.set()

        self.log('Aborted job:', self.description)
        self.killed = True
        self.failed = True
        self._cleanup()

    def consolidate_log(self):
        logs = [self.log.html, self.log.plain_text]
        bdir = base_dir()
        log_dir = os.path.join(bdir, 'threaded_job_logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        fd, path = tempfile.mkstemp(suffix='.json', prefix='log-', dir=log_dir)
        data = json.dumps(logs, ensure_ascii=False, indent=2)
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        self.consolidated_log = path
        self.log = None

    def read_consolidated_log(self):
        with open(self.consolidated_log, 'rb') as f:
            return json.loads(f.read().decode('utf-8'))

    @property
    def details(self):
        if self.consolidated_log is None:
            return self.log.plain_text
        return self.read_consolidated_log()[1]

    @property
    def html_details(self):
        if self.consolidated_log is None:
            return self.log.html
        return self.read_consolidated_log()[0]


class ThreadedJobWorker(Thread):

    def __init__(self, job):
        Thread.__init__(self)
        self.daemon = True
        self.job = job

    def run(self):
        try:
            self.job.start_work()
        except:
            import traceback
            from calibre import prints
            prints('Job had unhandled exception:', self.job.description)
            traceback.print_exc()


class ThreadedJobServer(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.lock = RLock()

        self.queued_jobs = []
        self.running_jobs = set()
        self.changed_jobs = Queue()
        self.keep_going = True

    def close(self):
        self.keep_going = False

    def add_job(self, job):
        with self.lock:
            self.queued_jobs.append(job)

        if not self.is_alive():
            self.start()

    def run(self):
        while self.keep_going:
            try:
                self.run_once()
            except:
                import traceback
                traceback.print_exc()
            time.sleep(0.1)

    def run_once(self):
        with self.lock:
            remove = set()
            for worker in self.running_jobs:
                if worker.is_alive():
                    # Get progress notifications
                    if worker.job.consume_notifications():
                        self.changed_jobs.put(worker.job)
                else:
                    remove.add(worker)
                    self.changed_jobs.put(worker.job)

            for worker in remove:
                self.running_jobs.remove(worker)

            jobs = self.get_startable_jobs()
            for job in jobs:
                w = ThreadedJobWorker(job)
                w.start()
                self.running_jobs.add(w)
                self.changed_jobs.put(job)
                self.queued_jobs.remove(job)

    def kill_job(self, job):
        with self.lock:
            if job in self.queued_jobs:
                self.queued_jobs.remove(job)
            elif job in self.running_jobs:
                self.running_jobs.remove(job)
        job.kill()
        self.changed_jobs.put(job)

    def running_jobs_of_type(self, type_):
        return len([w for w in self.running_jobs if w.job.type == type_])

    def get_startable_jobs(self):
        queued_types = []
        ans = []
        for job in self.queued_jobs:
            num = self.running_jobs_of_type(job.type)
            num += queued_types.count(job.type)
            if num < job.max_concurrent_count:
                queued_types.append(job.type)
                ans.append(job)
        return ans
