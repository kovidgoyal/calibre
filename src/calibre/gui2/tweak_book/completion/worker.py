#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple
from multiprocessing.connection import Pipe
from threading import Event, RLock, Thread

from calibre.constants import iswindows
from calibre.gui2.tweak_book.completion.basic import Request
from calibre.gui2.tweak_book.completion.utils import DataError
from calibre.utils.ipc import eintr_retry_call
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
        self.latest_completion_request_id = None
        self.request_count = 0
        self.lock = RLock()

    def launch_worker_process(self):
        from calibre.utils.ipc.pool import start_worker
        control_a, control_b = Pipe()
        data_a, data_b = Pipe()
        with control_a, data_a:
            pass_fds = control_a.fileno(), data_a.fileno()
            self.worker_process = p = start_worker(
                'from {0} import run_main, {1}; run_main({2}, {3}, {1})'.format(
                    self.__class__.__module__, self.worker_entry_point, *pass_fds),
                pass_fds
            )
            p.stdin.close()
        self.control_conn = control_b
        self.data_conn = data_b
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
                    self.send_completion_request(req_data)
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
        latest_completion_request_id = self.latest_completion_request_id
        if result is not None and result.request_id == latest_completion_request_id:
            try:
                self.result_callback(result)
            except Exception:
                import traceback
                traceback.print_exc()

    def clear_caches(self, cache_type=None):
        self.main_queue.put((CLEAR_REQUEST, Request(None, 'clear_caches', cache_type, None)))

    def queue_completion(self, request_id, completion_type, completion_data, query=None):
        with self.lock:
            ccr = Request(request_id, completion_type, completion_data, query)
            self.latest_completion_request_id = ccr.id
        self.main_queue.put((COMPLETION_REQUEST, ccr))

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


def run_main(control_fd, data_fd, func):
    if iswindows:
        from multiprocessing.connection import PipeConnection as Connection
    else:
        from multiprocessing.connection import Connection
    with Connection(control_fd) as control_conn, Connection(data_fd) as data_conn:
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
    dobj = data_conn.recv()
    control_conn.send((obj, dobj))


def test():
    w = CompletionWorker(worker_entry_point='test_main')
    w.wait_for_connection()
    w.data_conn.send('got the data')
    w.send('Hello World!')
    print(w.recv())
    w.shutdown(), w.join()
