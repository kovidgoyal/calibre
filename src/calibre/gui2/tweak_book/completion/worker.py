#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import cPickle, os, sys
from threading import Thread, Event
from Queue import Queue
from contextlib import closing

from calibre.constants import iswindows
from calibre.utils.ipc import eintr_retry_call

class CompletionWorker(Thread):

    daemon = True

    def __init__(self, worker_entry_point='main'):
        Thread.__init__(self)
        self.worker_entry_point = worker_entry_point
        self.start()
        self.main_queue = Queue()
        self.reap_thread = None
        self.shutting_down = False
        self.connected = Event()

    def launch_worker_process(self):
        from calibre.utils.ipc.server import create_listener
        from calibre.utils.ipc.simple_worker import start_pipe_worker
        self.worker_process = p = start_pipe_worker(
            'from {0} import run_main, {1}; run_main({1})'.format(self.__class__.__module__, self.worker_entry_point), stdout=None)
        auth_key = os.urandom(32)
        address, self.listener = create_listener(auth_key)
        eintr_retry_call(p.stdin.write, cPickle.dumps((address, auth_key), -1))
        p.stdin.flush(), p.stdin.close()
        self.control_conn = eintr_retry_call(self.listener.accept)
        self.data_conn = eintr_retry_call(self.listener.accept)
        self.connected.set()

    def send(self, data, conn=None):
        conn = conn or self.control_conn
        try:
            eintr_retry_call(conn.send, data)
        except:
            if not self.shutting_down:
                raise

    def recv(self, conn=None):
        conn = conn or self.control_conn
        try:
            return eintr_retry_call(conn.recv)
        except:
            if not self.shutting_down:
                raise

    def wait_for_connection(self, timeout=None):
        self.connected.wait(timeout)

    def run(self):
        self.launch_worker_process()
        while True:
            obj = self.main_queue.get()
            if obj is None:
                break

    def shutdown(self):
        self.shutting_down = True
        self.main_queue.put(None)
        p = self.worker_process
        if p.returncode is None:
            self.worker_process.terminate()
            t = self.reap_thread = Thread(target=p.wait)
            t.daemon = True
            t.start()

    def join(self, timeout=0.2):
        if self.reap_thread is not None:
            self.reap_thread.join(timeout)
        if not iswindows and self.worker_process.returncode is None:
            self.worker_process.kill()
        return self.worker_process.returncode

_completion_worker = None
def completion_worker():
    global _completion_worker
    if _completion_worker is None:
        _completion_worker = CompletionWorker()
    return _completion_worker

def run_main(func):
    from multiprocessing.connection import Client
    address, key = cPickle.loads(eintr_retry_call(sys.stdin.read))
    with closing(Client(address, authkey=key)) as control_conn, closing(Client(address, authkey=key)) as data_conn:
        func(control_conn, data_conn)

def test_main(control_conn, data_conn):
    obj = control_conn.recv()
    control_conn.send(obj)

def test():
    w = CompletionWorker(worker_entry_point='test_main')
    w.wait_for_connection()
    w.send('Hello World!')
    print (w.recv())
    w.shutdown(), w.join()
