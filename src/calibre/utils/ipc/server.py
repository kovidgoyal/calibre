#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import os
import sys
import tempfile
import time
from collections import deque
from itertools import count
from math import ceil
from multiprocessing import Pipe
from threading import Thread

from calibre import detect_ncpus as cpu_count, force_unicode
from calibre.constants import DEBUG
from calibre.ptempfile import base_dir
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.ipc.launch import Worker
from calibre.utils.ipc.worker import PARALLEL_FUNCS
from calibre.utils.serialize import pickle_loads
from polyglot.binary import as_hex_unicode
from polyglot.builtins import environ_item, string_or_bytes
from polyglot.queue import Empty, Queue


server_counter = count()
_name_counter = count()


class ConnectedWorker(Thread):

    def __init__(self, worker, conn, rfile):
        Thread.__init__(self)
        self.daemon = True
        self.conn = conn
        self.worker = worker
        self.notifications = Queue()
        self._returncode = 'dummy'
        self.killed = False
        self.log_path = worker.log_path
        self.rfile = rfile
        self.close_log_file = getattr(worker, 'close_log_file', None)

    def start_job(self, job):
        notification = PARALLEL_FUNCS[job.name][-1] is not None
        eintr_retry_call(self.conn.send, (job.name, job.args, job.kwargs, job.description))
        if notification:
            self.start()
        else:
            self.conn.close()
        self.job = job

    def run(self):
        while True:
            try:
                x = eintr_retry_call(self.conn.recv)
                self.notifications.put(x)
            except BaseException:
                break
        try:
            self.conn.close()
        except BaseException:
            pass

    def kill(self):
        self.killed = True
        try:
            self.worker.kill()
        except BaseException:
            pass

    @property
    def is_alive(self):
        return not self.killed and self.worker.is_alive

    @property
    def returncode(self):
        if self._returncode != 'dummy':
            return self._returncode
        r = self.worker.returncode
        if self.killed and r is None:
            self._returncode = 1
            return 1
        if r is not None:
            self._returncode = r
        return r


class CriticalError(Exception):
    pass


class Server(Thread):

    def __init__(self, notify_on_job_done=lambda x: x, pool_size=None,
            limit=sys.maxsize, enforce_cpu_limit=True):
        Thread.__init__(self)
        self.daemon = True
        self.id = next(server_counter) + 1

        if enforce_cpu_limit:
            limit = min(limit, cpu_count())
        self.pool_size = limit if pool_size is None else pool_size
        self.notify_on_job_done = notify_on_job_done
        self.add_jobs_queue, self.changed_jobs_queue = Queue(), Queue()
        self.kill_queue = Queue()
        self.waiting_jobs = []
        self.workers = deque()
        self.launched_worker_counter = count()
        next(self.launched_worker_counter)
        self.start()

    def launch_worker(self, gui=False, redirect_output=None, job_name=None):
        start = time.monotonic()
        id = next(self.launched_worker_counter)
        fd, rfile = tempfile.mkstemp(prefix='ipc_result_%d_%d_'%(self.id, id),
                dir=base_dir(), suffix='.pickle')
        os.close(fd)
        if redirect_output is None:
            redirect_output = not gui

        cw = self.do_launch(gui, redirect_output, rfile, job_name=job_name)
        if isinstance(cw, string_or_bytes):
            raise CriticalError('Failed to launch worker process:\n'+force_unicode(cw))
        if DEBUG:
            print(f'Worker Launch took: {time.monotonic() - start:.2f} seconds')
        return cw

    def do_launch(self, gui, redirect_output, rfile, job_name=None):
        a, b = Pipe()
        with a:
            env = {
                'CALIBRE_WORKER_FD': str(a.fileno()),
                'CALIBRE_WORKER_RESULT' : environ_item(as_hex_unicode(rfile))
            }
            w = Worker(env, gui=gui, job_name=job_name)

            try:
                w(pass_fds=(a.fileno(),), redirect_output=redirect_output)
            except BaseException:
                try:
                    w.kill()
                except:
                    pass
                b.close()
                import traceback
                return traceback.format_exc()
        return ConnectedWorker(w, b, rfile)

    def add_job(self, job):
        job.done2 = self.notify_on_job_done
        self.add_jobs_queue.put(job)

    def run_job(self, job, gui=True, redirect_output=False):
        w = self.launch_worker(gui=gui, redirect_output=redirect_output, job_name=getattr(job, 'name', None))
        w.start_job(job)

    def run(self):
        while True:
            try:
                job = self.add_jobs_queue.get(True, 0.2)
                if job is None:
                    break
                self.waiting_jobs.insert(0, job)
            except Empty:
                pass

            # Get notifications from worker process
            for worker in self.workers:
                while True:
                    try:
                        n = worker.notifications.get_nowait()
                        worker.job.notifications.put(n)
                        self.changed_jobs_queue.put(worker.job)
                    except Empty:
                        break

            # Remove finished jobs
            for worker in [w for w in self.workers if not w.is_alive]:
                try:
                    worker.close_log_file()
                except:
                    pass
                self.workers.remove(worker)
                job = worker.job
                if worker.returncode != 0:
                    job.failed   = True
                    job.returncode = worker.returncode
                elif os.path.exists(worker.rfile):
                    try:
                        with lopen(worker.rfile, 'rb') as f:
                            job.result = pickle_loads(f.read())
                        os.remove(worker.rfile)
                    except:
                        pass
                job.duration = time.time() - job.start_time
                self.changed_jobs_queue.put(job)

            # Start waiting jobs
            sj = self.suitable_waiting_job()
            if sj is not None:
                job = self.waiting_jobs.pop(sj)
                job.start_time = time.time()
                if job.kill_on_start:
                    job.duration = 0.0
                    job.returncode = 1
                    job.killed = job.failed = True
                    job.result = None
                else:
                    worker = self.launch_worker()
                    worker.start_job(job)
                    self.workers.append(worker)
                    job.log_path = worker.log_path
                self.changed_jobs_queue.put(job)

            while True:
                try:
                    j = self.kill_queue.get_nowait()
                    self._kill_job(j)
                except Empty:
                    break

    def suitable_waiting_job(self):
        available_workers = self.pool_size - len(self.workers)
        for worker in self.workers:
            job = worker.job
            if job.core_usage == -1:
                available_workers = 0
            elif job.core_usage > 1:
                available_workers -= job.core_usage - 1
            if available_workers < 1:
                return None

        for i, job in enumerate(self.waiting_jobs):
            if job.core_usage == -1:
                if available_workers >= self.pool_size:
                    return i
            elif job.core_usage <= available_workers:
                return i

    def kill_job(self, job):
        self.kill_queue.put(job)

    def killall(self):
        for worker in self.workers:
            self.kill_queue.put(worker.job)

    def _kill_job(self, job):
        if job.start_time is None:
            job.kill_on_start = True
            return
        for worker in self.workers:
            if job is worker.job:
                worker.kill()
                job.killed = True
                break

    def split(self, tasks):
        '''
        Split a list into a list of sub lists, with the number of sub lists being
        no more than the number of workers this server supports. Each sublist contains
        2-tuples of the form (i, x) where x is an element from the original list
        and i is the index of the element x in the original list.
        '''
        ans, count, pos = [], 0, 0
        delta = int(ceil(len(tasks)/float(self.pool_size)))
        while count < len(tasks):
            section = []
            for t in tasks[pos:pos+delta]:
                section.append((count, t))
                count += 1
            ans.append(section)
            pos += delta
        return ans

    def close(self):
        try:
            self.add_jobs_queue.put(None)
        except:
            pass
        try:
            self.listener.close()
        except:
            pass
        time.sleep(0.2)
        for worker in list(self.workers):
            try:
                worker.kill()
            except:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
