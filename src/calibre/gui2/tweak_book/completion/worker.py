#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys
from threading import Thread, Event, RLock
from contextlib import closing
from collections import namedtuple

from calibre.constants import iswindows
from calibre.gui2.tweak_book.completion.basic import Request
from calibre.gui2.tweak_book.completion.utils import DataError
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.serialize import msgpack_loads, msgpack_dumps
from polyglot.queue import Queue

COMPLETION_REQUEST = 'completion request'
CLEAR_REQUEST = 'clear request'


class CompletionWorker(Thread):

    daemon = True

    def __init__(self, result_callback=lambda x:x, worker_entry_point='main'):
        Thread.__init__(self)
        self.worker_entry_point = worker_entry_point
        self.start()
        self.main_queue = Queue()
        self.result_callback = result_callback
        self.reap_thread = None
        self.shutting_down = False
        self.connected = Event()
        self.current_completion_request = None
        self.latest_completion_request_id = None
        self.request_count = 0
        self.lock = RLock()

    def launch_worker_process(self):
        from calibre.utils.ipc.server import create_listener
        from calibre.utils.ipc.pool import start_worker
        self.worker_process = p = start_worker(
            'from {0} import run_main, {1}; run_main({1})'.format(self.__class__.__module__, self.worker_entry_point))
        auth_key = os.urandom(32)
        address, self.listener = create_listener(auth_key)
        eintr_retry_call(p.stdin.write, msgpack_dumps((address, auth_key)))
        p.stdin.flush(), p.stdin.close()
        self.control_conn = eintr_retry_call(self.listener.accept)
        self.data_conn = eintr_retry_call(self.listener.accept)
        self.data_thread = t = Thread(name='CWData', target=self.handle_data_requests)
        t.daemon = True
        t.start()
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

    def handle_data_requests(self):
        from calibre.gui2.tweak_book.completion.basic import handle_data_request
        while True:
            try:
                req = self.recv(self.data_conn)
            except EOFError:
                break
            except Exception:
                import traceback
                traceback.print_exc()
                break
            if req is None or self.shutting_down:
                break
            result, tb = handle_data_request(req)
            try:
                self.send((result, tb), self.data_conn)
            except EOFError:
                break
            except Exception:
                import traceback
                traceback.print_exc()
                break

    def run(self):
        self.launch_worker_process()
        while True:
            obj = self.main_queue.get()
            if obj is None:
                break
            req_type, req_data = obj
            try:
                if req_type is COMPLETION_REQUEST:
                    with self.lock:
                        if self.current_completion_request is not None:
                            ccr, self.current_completion_request = self.current_completion_request, None
                            self.send_completion_request(ccr)
                elif req_type is CLEAR_REQUEST:
                    self.send(req_data)
            except EOFError:
                break
            except Exception:
                import traceback
                traceback.print_exc()

    def send_completion_request(self, request):
        self.send(request)
        result = self.recv()
        if result.request_id == self.latest_completion_request_id:
            try:
                self.result_callback(result)
            except Exception:
                import traceback
                traceback.print_exc()

    def clear_caches(self, cache_type=None):
        self.main_queue.put((CLEAR_REQUEST, Request(None, 'clear_caches', cache_type, None)))

    def queue_completion(self, request_id, completion_type, completion_data, query=None):
        with self.lock:
            self.current_completion_request = Request(request_id, completion_type, completion_data, query)
            self.latest_completion_request_id = self.current_completion_request.id
        self.main_queue.put((COMPLETION_REQUEST, None))

    def shutdown(self):
        self.shutting_down = True
        self.main_queue.put(None)
        for conn in (getattr(self, 'control_conn', None), getattr(self, 'data_conn', None)):
            try:
                conn.close()
            except Exception:
                pass
        p = self.worker_process
        if p.poll() is None:
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
    stdin = getattr(sys.stdin, 'buffer', sys.stdin)
    address, key = msgpack_loads(eintr_retry_call(stdin.read))
    with closing(Client(address, authkey=key)) as control_conn, closing(Client(address, authkey=key)) as data_conn:
        func(control_conn, data_conn)


Result = namedtuple('Result', 'request_id ans traceback query')


def main(control_conn, data_conn):
    from calibre.gui2.tweak_book.completion.basic import handle_control_request
    while True:
        try:
            request = eintr_retry_call(control_conn.recv)
        except (KeyboardInterrupt, EOFError):
            break
        if request is None:
            break
        try:
            ans, tb = handle_control_request(request, data_conn), None
        except DataError as err:
            ans, tb = None, err.traceback()
        except Exception:
            import traceback
            ans, tb = None, traceback.format_exc()
        if request.id is not None:
            result = Result(request.id, ans, tb, request.query)
            try:
                eintr_retry_call(control_conn.send, result)
            except EOFError:
                break


def test_main(control_conn, data_conn):
    obj = control_conn.recv()
    control_conn.send(obj)


def test():
    w = CompletionWorker(worker_entry_point='test_main')
    w.wait_for_connection()
    w.send('Hello World!')
    print(w.recv())
    w.shutdown(), w.join()
