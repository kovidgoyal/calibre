#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, cPickle, sys
from threading import Thread, RLock
from collections import namedtuple
from Queue import Queue

from calibre import detect_ncpus, as_unicode, prints
from calibre.utils import join_with_timeout
from calibre.utils.ipc import eintr_retry_call

Job = namedtuple('Job', 'id module func args kwargs')
Result = namedtuple('Result', 'value err traceback')
WorkerResult = namedtuple('WorkerResult', 'id result is_terminal_failure worker')
TerminalFailure = namedtuple('TerminalFailure', 'message tb job_id')

class Failure(Exception):

    def __init__(self, tf):
        Exception.__init__(self, tf.message)
        self.details = tf.tb
        self.job_id = tf.job_id

class Worker(object):

    def __init__(self, p, conn, events, name):
        self.process, self.conn = p, conn
        self.events = events
        self.name = name or ''

    def __call__(self, job):
        eintr_retry_call(self.conn.send, job)
        if job is not None:
            self.job_id = job.id
            t = Thread(target=self.recv, name='PoolWorker-'+self.name)
            t.daemon = True
            t.start()

    def recv(self):
        try:
            result = eintr_retry_call(self.conn.recv)
            wr = WorkerResult(self.job_id, result, False, self)
        except Exception as err:
            import traceback
            result = Result(None, as_unicode(err), traceback.format_exc())
            wr = WorkerResult(self.job_id, result, True, self)
        self.events.put(wr)

class Pool(Thread):

    daemon = True

    def __init__(self, max_workers=None, name=None):
        Thread.__init__(self, name=name)
        self.lock = RLock()
        self.max_workers = max_workers or detect_ncpus()
        self.available_workers = []
        self.busy_workers = {}
        self.pending_jobs = []
        self.events = Queue()
        self.results = Queue()
        self.tracker = Queue()
        self.terminal_failure = None

        self.start()

    def create_worker(self):
        from calibre.utils.ipc.simple_worker import start_pipe_worker
        p = start_pipe_worker(
            'from {0} import run_main, {1}; run_main({1})'.format(self.__class__.__module__, 'worker_main'), stdout=None)
        sys.stdout.flush()
        eintr_retry_call(p.stdin.write, cPickle.dumps((self.address, self.auth_key), -1))
        p.stdin.flush(), p.stdin.close()
        conn = eintr_retry_call(self.listener.accept)
        return Worker(p, conn, self.events, self.name)

    def start_worker(self):
        try:
            self.available_workers.append(self.create_worker())
        except Exception:
            import traceback
            self.terminal_failure = TerminalFailure('Failed to start worker process', traceback.format_exc(), None)
            self.terminal_error()
            return False

    def run(self):
        from calibre.utils.ipc.server import create_listener
        self.auth_key = os.urandom(32)
        self.address, self.listener = create_listener(self.auth_key)
        with self.lock:
            if self.start_worker() is False:
                return

        while True:
            event = self.events.get()
            with self.lock:
                if event is None:
                    break
                if self.handle_event(event) is False:
                    break
        with self.lock:
            self.shutdown_workers()

    def handle_event(self, event):
        if isinstance(event, Job):
            job = event
            if not self.available_workers:
                if len(self.busy_workers) >= self.max_workers:
                    self.pending_jobs.append(job)
                    return
                if self.start_worker() is False:
                    return False
            return self.run_job(job)
        else:
            worker_result = event
            self.busy_workers.pop(worker_result.worker, None)
            self.available_workers.append(worker_result.worker)
            self.tracker.task_done()
            if worker_result.is_terminal_failure:
                self.terminal_failure = TerminalFailure('Worker process crashed while executing job', worker_result.result.traceback, worker_result.id)
                self.terminal_error()
                return False
            self.results.put(worker_result)

        while self.pending_jobs and self.available_workers:
            if self.run_job(self.pending_jobs.pop()) is False:
                return False

    def run_job(self, job):
        worker = self.available_workers.pop()
        try:
            worker(job)
        except Exception:
            import traceback
            self.terminal_failure = TerminalFailure('Worker process crashed while sending job', traceback.format_exc(), job.id)
            self.terminal_error()
            return False
        self.busy_workers[worker] = job

    @property
    def failed(self):
        return self.terminal_failure is not None

    def __call__(self, job_id, module, func, *args, **kwargs):
        '''
        Schedule a job. The job will be run in a worker process, with the
        result placed in self.results. If a terminal failure has occurred
        previously, this method will raise the :class:`Failure` exception.

        :param job_id: A unique id for the job. The result will have this id.
        :param module: Either a fully qualified python module name or python
                       source code which will be executed as a module.
                       Source code is detected by the presence of newlines in module.
        :param func: Name of the function from ``module`` that will be
                     executed. ``args`` and ``kwargs`` will be passed to the function.
        '''
        job = Job(job_id, module, func, args, kwargs)
        with self.lock:
            if self.failed:
                raise Failure(self.terminal_failure)
            self.tracker.put(None)
            self.events.put(job)

    def wait_for_tasks(self, timeout=None):
        ''' Wait for all queued jobs to be completed, if timeout is not None,
        will raise a RuntimeError if jobs are not completed in the specified
        time. Will raise a :class:`Failure` exception if a terminal failure has
        occurred previously. '''
        if self.failed:
            raise Failure(self.terminal_failure)
        if timeout is None:
            self.tracker.join()
        else:
            join_with_timeout(self.tracker, timeout)

    def terminal_error(self):
        for worker, job in self.busy_workers.iteritems():
            self.results.put(WorkerResult(job.id, Result(None, None, None), True, worker))
            self.tracker.task_done()
        while self.pending_jobs:
            job = self.pending_jobs.pop()
            self.results.put(WorkerResult(job.id, Result(None, None, None), True, worker))
            self.tracker.task_done()
        self.shutdown_workers()
        self.events.put(None)

    def shutdown(self):
        with self.lock:
            self.events.put(None)
            self.shutdown_workers()

    def shutdown_workers(self, wait_time=0.1):
        for worker in self.available_workers:
            try:
                worker(None)
            except Exception:
                pass
        for worker in self.busy_workers:
            worker.process.terminate()
        workers = [w.process for w in self.available_workers + list(self.busy_workers)]
        def join():
            for w in workers:
                w.wait()
        reaper = Thread(target=join, name='ReapPoolWorkers')
        reaper.daemon = True
        reaper.start()
        reaper.join(wait_time)
        for w in self.available_workers:
            if w.process.poll() is None:
                w.process.kill()
        del self.available_workers[:]
        self.busy_workers.clear()

def worker_main(conn):
    from importlib import import_module
    while True:
        try:
            job = eintr_retry_call(conn.recv)
        except EOFError:
            break
        except Exception:
            prints('recv() failed in worker, terminating worker', file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
        if job is None:
            break
        try:
            if '\n' in job.module:
                import_module('calibre.customize.ui')  # Load plugins
                from calibre.utils.ipc.simple_worker import compile_code
                mod = compile_code(job.module)
                func = mod[job.func]
            else:
                func = getattr(import_module(job.module), job.func)
            result = func(*job.args, **job.kwargs)
            result = Result(result, None, None)
        except Exception as err:
            import traceback
            result = Result(None, as_unicode(err), traceback.format_exc())
        try:
            eintr_retry_call(conn.send, result)
        except EOFError:
            break
        except Exception:
            prints('send() failed in worker, terminating worker', file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
    return 0

def run_main(func):
    from multiprocessing.connection import Client
    from contextlib import closing
    address, key = cPickle.loads(eintr_retry_call(sys.stdin.read))
    with closing(Client(address, authkey=key)) as conn:
        raise SystemExit(func(conn))

def test():
    def get_results(pool, ignore_fail=False):
        ans = {}
        while not p.results.empty():
            r = p.results.get()
            if not ignore_fail and r.is_terminal_failure:
                print (r.result.err)
                print (r.result.traceback)
                raise SystemExit(1)
            ans[r.id] = r.result
        return ans

    # Test normal execution
    p = Pool(name='Test')
    expected_results = {}
    for i in range(1000):
        p(i, 'def x(i):\n return 2*i', 'x', i)
        expected_results[i] = 2 * i
    p.wait_for_tasks(30)
    results = {k:v.value for k, v in get_results(p).iteritems()}
    if results != expected_results:
        raise SystemExit('%r != %r' % (expected_results, results))
    p.shutdown(), p.join()

    # Test exceptions in jobs
    p = Pool(name='Test')
    for i in range(1000):
        p(i, 'def x(i):\n return 1/0', 'x', i)
    p.wait_for_tasks(30)
    c = 0
    for r in get_results(p).itervalues():
        c += 1
        if not r.traceback or 'ZeroDivisionError' not in r.traceback:
            raise SystemExit('Unexpected result: %s' % r)
    if c != 1000:
        raise SystemExit('Incorrect number of results')
    p.shutdown(), p.join()

    # Test worker crash
    p = Pool(name='Test')
    for i in range(1000):
        try:
            p(i, 'def x(i):\n os._exit(1)', 'x', i)
        except Failure:
            break
    try:
        p.wait_for_tasks(30)
    except Failure:
        pass
    results = get_results(p, ignore_fail=True)
    if not p.failed:
        raise SystemExit('No expected terminal failure')
    p.shutdown(), p.join()
