#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys
from threading import Thread
from collections import namedtuple
from multiprocessing.connection import Pipe

from calibre import detect_ncpus, as_unicode, prints
from calibre.constants import iswindows, DEBUG
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils import join_with_timeout
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.serialize import pickle_dumps, pickle_loads
from polyglot.builtins import iteritems, itervalues
from polyglot.queue import Queue

Job = namedtuple('Job', 'id module func args kwargs')
Result = namedtuple('Result', 'value err traceback')
WorkerResult = namedtuple('WorkerResult', 'id result is_terminal_failure worker')
TerminalFailure = namedtuple('TerminalFailure', 'message tb job_id')
File = namedtuple('File', 'name')

MAX_SIZE = 30 * 1024 * 1024  # max size of data to send over the connection (old versions of windows cannot handle arbitrary data lengths)

worker_kwargs = {'stdout':None}
get_stdout_from_child = False

if iswindows:
    # The windows console cannot show output from child processes
    # created with CREATE_NO_WINDOW, so the stdout/stderr file handles
    # the child process inherits will be broken. Similarly, windows GUI apps
    # have no usable stdout/stderr file handles. In both these cases, redirect
    # the child's stdout/stderr to NUL. If we are running in calibre-debug -g,
    # then redirect to PIPE and read from PIPE and print to our stdout.
    # Note that when running via the "Restart in debug mode" action, stdout is
    # not a console (its already redirected to a log file), so no redirection
    # is required.
    if getattr(sys, 'gui_app', False) or getattr(sys.stdout, 'isatty', lambda : False)():
        if DEBUG:
            # We are running in a windows console with calibre-debug -g
            import subprocess
            get_stdout_from_child = True
            worker_kwargs['stdout'] = subprocess.PIPE
            worker_kwargs['stderr'] = subprocess.STDOUT
        else:
            from calibre.utils.ipc.launch import windows_null_file
            worker_kwargs['stdout'] = worker_kwargs['stderr'] = windows_null_file


def get_stdout(process):
    import time
    while process.poll() is None:
        try:
            raw = process.stdout.read(1)
            if raw:
                try:
                    sys.stdout.buffer.write(raw)
                except OSError:
                    pass
            else:
                time.sleep(0.1)
        except (EOFError, OSError):
            break


def start_worker(code, pass_fds, name=''):
    from calibre.utils.ipc.simple_worker import start_pipe_worker
    if name:
        name = '-' + name
    p = start_pipe_worker(code, pass_fds=pass_fds, **worker_kwargs)
    if get_stdout_from_child:
        t = Thread(target=get_stdout, name='PoolWorkerGetStdout' + name, args=(p,))
        t.daemon = True
        t.start()
    return p


class Failure(Exception):

    def __init__(self, tf):
        Exception.__init__(self, tf.message)
        self.details = tf.tb
        self.job_id = tf.job_id
        self.failure_message = tf.message


class Worker:

    def __init__(self, p, conn, events, name):
        self.process, self.conn = p, conn
        self.events = events
        self.name = name or ''

    def __call__(self, job):
        eintr_retry_call(self.conn.send_bytes, pickle_dumps(job))
        if job is not None:
            self.job_id = job.id
            t = Thread(target=self.recv, name='PoolWorker-'+self.name)
            t.daemon = True
            t.start()

    def recv(self):
        try:
            result = pickle_loads(eintr_retry_call(self.conn.recv_bytes))
            wr = WorkerResult(self.job_id, result, False, self)
        except Exception as err:
            import traceback
            result = Result(None, as_unicode(err), traceback.format_exc())
            wr = WorkerResult(self.job_id, result, True, self)
        self.events.put(wr)

    def set_common_data(self, data):
        eintr_retry_call(self.conn.send_bytes, data)


class Pool(Thread):

    daemon = True

    def __init__(self, max_workers=None, name=None):
        Thread.__init__(self, name=name)
        self.max_workers = max_workers or detect_ncpus()
        self.available_workers = []
        self.busy_workers = {}
        self.pending_jobs = []
        self.events = Queue()
        self.results = Queue()
        self.tracker = Queue()
        self.terminal_failure = None
        self.common_data = pickle_dumps(None)
        self.shutting_down = False

        self.start()

    def set_common_data(self, data=None):
        ''' Set some data that will be passed to all subsequent jobs without
        needing to be transmitted every time. You must call this method before
        queueing any jobs, otherwise the behavior is undefined. You can call it
        after all jobs are done, then it will be used for the new round of
        jobs. Can raise the :class:`Failure` exception is data could not be
        sent to workers.'''
        if self.failed:
            raise Failure(self.terminal_failure)
        self.events.put(data)

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
        if self.failed:
            raise Failure(self.terminal_failure)
        job = Job(job_id, module, func, args, kwargs)
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

    def shutdown(self, wait_time=0.1):
        ''' Shutdown this pool, terminating all worker process. The pool cannot
        be used after a shutdown. '''
        self.shutting_down = True
        self.events.put(None)
        self.shutdown_workers(wait_time=wait_time)

    def create_worker(self):
        a, b = Pipe()
        with a:
            cmd = 'from {0} import run_main, {1}; run_main({2!r}, {1})'.format(
                self.__class__.__module__, 'worker_main', a.fileno())
            p = start_worker(cmd, (a.fileno(),))
        sys.stdout.flush()
        p.stdin.close()
        w = Worker(p, b, self.events, self.name)
        if self.common_data != pickle_dumps(None):
            w.set_common_data(self.common_data)
        return w

    def start_worker(self):
        try:
            w = self.create_worker()
            if not self.shutting_down:
                self.available_workers.append(w)
        except Exception:
            import traceback
            self.terminal_failure = TerminalFailure('Failed to start worker process', traceback.format_exc(), None)
            self.terminal_error()
            return False

    def run(self):
        if self.start_worker() is False:
            return

        while True:
            event = self.events.get()
            if event is None or self.shutting_down:
                break
            if self.handle_event(event) is False:
                break

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
        elif isinstance(event, WorkerResult):
            worker_result = event
            self.busy_workers.pop(worker_result.worker, None)
            self.available_workers.append(worker_result.worker)
            self.tracker.task_done()
            if worker_result.is_terminal_failure:
                self.terminal_failure = TerminalFailure('Worker process crashed while executing job', worker_result.result.traceback, worker_result.id)
                self.terminal_error()
                return False
            self.results.put(worker_result)
        else:
            self.common_data = pickle_dumps(event)
            if len(self.common_data) > MAX_SIZE:
                self.cd_file = PersistentTemporaryFile('pool_common_data')
                with self.cd_file as f:
                    f.write(self.common_data)
                self.common_data = pickle_dumps(File(f.name))
            for worker in self.available_workers:
                try:
                    worker.set_common_data(self.common_data)
                except Exception:
                    import traceback
                    self.terminal_failure = TerminalFailure('Worker process crashed while sending common data', traceback.format_exc(), None)
                    self.terminal_error()
                    return False

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

    def terminal_error(self):
        if self.shutting_down:
            return
        for worker, job in iteritems(self.busy_workers):
            self.results.put(WorkerResult(job.id, Result(None, None, None), True, worker))
            self.tracker.task_done()
        while self.pending_jobs:
            job = self.pending_jobs.pop()
            self.results.put(WorkerResult(job.id, Result(None, None, None), True, None))
            self.tracker.task_done()
        self.shutdown()

    def shutdown_workers(self, wait_time=0.1):
        self.worker_data = self.common_data = None
        for worker in self.busy_workers:
            if worker.process.poll() is None:
                try:
                    worker.process.terminate()
                except OSError:
                    pass  # If the process has already been killed
        workers = [w.process for w in self.available_workers + list(self.busy_workers)]
        aw = list(self.available_workers)

        def join():
            for w in aw:
                try:
                    w(None)
                except Exception:
                    pass
            for w in workers:
                try:
                    w.wait()
                except Exception:
                    pass
        reaper = Thread(target=join, name='ReapPoolWorkers')
        reaper.daemon = True
        reaper.start()
        reaper.join(wait_time)
        for w in self.available_workers + list(self.busy_workers):
            try:
                w.conn.close()
            except Exception:
                pass
        for w in workers:
            if w.poll() is None:
                try:
                    w.kill()
                except OSError:
                    pass
        del self.available_workers[:]
        self.busy_workers.clear()
        if hasattr(self, 'cd_file'):
            try:
                os.remove(self.cd_file.name)
            except OSError:
                pass


def worker_main(conn):
    from importlib import import_module
    common_data = None
    while True:
        try:
            job = pickle_loads(eintr_retry_call(conn.recv_bytes))
        except EOFError:
            break
        except KeyboardInterrupt:
            break
        except Exception:
            prints('recv() failed in worker, terminating worker', file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
        if job is None:
            break
        if not isinstance(job, Job):
            if isinstance(job, File):
                with lopen(job.name, 'rb') as f:
                    common_data = f.read()
                common_data = pickle_loads(common_data)
            else:
                common_data = job
            continue
        try:
            if '\n' in job.module:
                import_module('calibre.customize.ui')  # Load plugins
                from calibre.utils.ipc.simple_worker import compile_code
                mod = compile_code(job.module)
                func = mod[job.func]
            else:
                func = getattr(import_module(job.module), job.func)
            if common_data is not None:
                job.kwargs['common_data'] = common_data
            result = func(*job.args, **job.kwargs)
            result = Result(result, None, None)
        except Exception as err:
            import traceback
            result = Result(None, as_unicode(err), traceback.format_exc())
        try:
            eintr_retry_call(conn.send_bytes, pickle_dumps(result))
        except EOFError:
            break
        except Exception:
            prints('send() failed in worker, terminating worker', file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
    return 0


def run_main(client_fd, func):
    if iswindows:
        from multiprocessing.connection import PipeConnection as Connection
    else:
        from multiprocessing.connection import Connection
    with Connection(client_fd) as conn:
        raise SystemExit(func(conn))


def test_write():
    print('Printing to stdout in worker')


def test():
    def get_results(pool, ignore_fail=False):
        ans = {}
        while not p.results.empty():
            r = p.results.get()
            if not ignore_fail and r.is_terminal_failure:
                print(r.result.err)
                print(r.result.traceback)
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
    results = {k:v.value for k, v in iteritems(get_results(p))}
    if results != expected_results:
        raise SystemExit(f'{expected_results!r} != {results!r}')
    p.shutdown(), p.join()

    # Test common_data
    p = Pool(name='Test')
    expected_results = {}
    p.start_worker()
    p.set_common_data(7)
    for i in range(1000):
        p(i, 'def x(i, common_data=None):\n return common_data + i', 'x', i)
        expected_results[i] = 7 + i
    p.wait_for_tasks(30)
    results = {k:v.value for k, v in iteritems(get_results(p))}
    if results != expected_results:
        raise SystemExit(f'{expected_results!r} != {results!r}')
    p.shutdown(), p.join()

    # Test large common data
    p = Pool(name='Test')
    data = b'a' * (4 * MAX_SIZE)
    p.set_common_data(data)
    p(0, 'def x(i, common_data=None):\n return len(common_data)', 'x', 0)
    p.wait_for_tasks(30)
    results = get_results(p)
    if len(data) != results[0].value:
        raise SystemExit('Common data was not returned correctly')
    p.shutdown(), p.join()

    # Test exceptions in jobs
    p = Pool(name='Test')
    for i in range(1000):
        p(i, 'def x(i):\n return 1/0', 'x', i)
    p.wait_for_tasks(30)
    c = 0
    for r in itervalues(get_results(p)):
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

    # Test shutting down with busy workers
    p = Pool(name='Test')
    for i in range(1000):
        p(i, 'import time;\ndef x(i):\n time.sleep(10000)', 'x', i)
    p.shutdown(), p.join()

    print('Tests all passed!')
