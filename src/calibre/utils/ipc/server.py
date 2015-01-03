#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, cPickle, time, tempfile, errno
from math import ceil
from threading import Thread, RLock
from Queue import Queue, Empty
from multiprocessing.connection import Listener, arbitrary_address
from collections import deque
from binascii import hexlify

from calibre.utils.ipc import eintr_retry_call
from calibre.utils.ipc.launch import Worker
from calibre.utils.ipc.worker import PARALLEL_FUNCS
from calibre import detect_ncpus as cpu_count
from calibre.constants import iswindows, DEBUG, islinux
from calibre.ptempfile import base_dir

_counter = 0

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

_name_counter = 0

if islinux:
    import fcntl
    class LinuxListener(Listener):

        def __init__(self, *args, **kwargs):
            Listener.__init__(self, *args, **kwargs)
            # multiprocessing tries to call unlink even on abstract
            # named sockets, prevent it from doing so.
            self._listener._unlink.cancel()
            # Prevent child processes from inheriting this socket
            # If we dont do this child processes not created by calibre, will
            # inherit this socket, preventing the calibre GUI from being restarted.
            # Examples of such processes are external viewers launched by Qt
            # using openUrl().
            fd = self._listener._socket.fileno()
            old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)

        def close(self):
            # To ensure that the socket is released, we have to call
            # shutdown() not close(). This is needed to allow calibre to
            # restart using the same socket address.
            import socket
            self._listener._socket.shutdown(socket.SHUT_RDWR)
            self._listener._socket.close()

        def accept(self, *args, **kwargs):
            ans = Listener.accept(self, *args, **kwargs)
            fd = ans.fileno()
            old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)
            return ans

    def create_listener(authkey, backlog=4):
        # Use abstract named sockets on linux to avoid creating unnecessary temp files
        global _name_counter
        prefix = u'\0calibre-ipc-listener-%d-%%d' % os.getpid()
        while True:
            _name_counter += 1
            address = (prefix % _name_counter).encode('ascii')
            try:
                l = LinuxListener(address=address, authkey=authkey, backlog=backlog)
                return address, l
            except EnvironmentError as err:
                if err.errno == errno.EADDRINUSE:
                    continue
                raise
else:
    def create_listener(authkey, backlog=4):
        address = arbitrary_address('AF_PIPE' if iswindows else 'AF_UNIX')
        if iswindows and address[1] == ':':
            address = address[2:]
        listener = Listener(address=address, authkey=authkey, backlog=backlog)
        return address, listener

class Server(Thread):

    def __init__(self, notify_on_job_done=lambda x: x, pool_size=None,
            limit=sys.maxint, enforce_cpu_limit=True):
        Thread.__init__(self)
        self.daemon = True
        global _counter
        self.id = _counter+1
        _counter += 1

        if enforce_cpu_limit:
            limit = min(limit, cpu_count())
        self.pool_size = limit if pool_size is None else pool_size
        self.notify_on_job_done = notify_on_job_done
        self.auth_key = os.urandom(32)
        self.address, self.listener = create_listener(self.auth_key, backlog=4)
        self.add_jobs_queue, self.changed_jobs_queue = Queue(), Queue()
        self.kill_queue = Queue()
        self.waiting_jobs = []
        self.workers = deque()
        self.launched_worker_count = 0
        self._worker_launch_lock = RLock()

        self.start()

    def launch_worker(self, gui=False, redirect_output=None, job_name=None):
        start = time.time()
        with self._worker_launch_lock:
            self.launched_worker_count += 1
            id = self.launched_worker_count
        fd, rfile = tempfile.mkstemp(prefix=u'ipc_result_%d_%d_'%(self.id, id),
                dir=base_dir(), suffix=u'.pickle')
        os.close(fd)
        if redirect_output is None:
            redirect_output = not gui

        env = {
                'CALIBRE_WORKER_ADDRESS' : hexlify(cPickle.dumps(self.listener.address, -1)),
                'CALIBRE_WORKER_KEY' : hexlify(self.auth_key),
                'CALIBRE_WORKER_RESULT' : hexlify(rfile.encode('utf-8')),
              }
        cw = self.do_launch(env, gui, redirect_output, rfile, job_name=job_name)
        if isinstance(cw, basestring):
            raise CriticalError('Failed to launch worker process:\n'+cw)
        if DEBUG:
            print 'Worker Launch took:', time.time() - start
        return cw

    def do_launch(self, env, gui, redirect_output, rfile, job_name=None):
        w = Worker(env, gui=gui, job_name=job_name)

        try:
            w(redirect_output=redirect_output)
            conn = eintr_retry_call(self.listener.accept)
            if conn is None:
                raise Exception('Failed to launch worker process')
        except BaseException:
            try:
                w.kill()
            except:
                pass
            import traceback
            return traceback.format_exc()
        return ConnectedWorker(w, conn, rfile)

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
                        job.result = cPickle.load(open(worker.rfile, 'rb'))
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

