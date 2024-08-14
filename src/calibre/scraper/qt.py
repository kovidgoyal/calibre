#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import shutil
import time
from contextlib import suppress
from io import BytesIO
from queue import Queue
from threading import RLock, Thread
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request

from calibre.ptempfile import PersistentTemporaryDirectory


class FakeResponse:

    def __init__(self):
        self.queue = Queue()
        self.done = False
        self.final_url = ''
        self.data = BytesIO()

    def _wait(self):
        if self.done:
            return
        self.done = True
        res = self.queue.get()
        if res['action'] == 'input_error':
            raise Exception(res['error'])
        self.final_url = res['final_url']
        if 'error' in res:
            ex = URLError(res['error'])
            ex.worth_retry = bool(res.get('worth_retry'))
            raise ex
        self.data = open(res['output'], 'rb')

    def read(self, *a, **kw):
        self._wait()
        ans = self.data.read(*a, **kw)
        return ans

    def seek(self, *a, **kw):
        self._wait()
        return self.data.seek(*a, **kw)

    def tell(self, *a, **kw):
        return self.data.tell(*a, **kw)

    def geturl(self):
        self._wait()
        return self.final_url

    def close(self):
        self.data.close()


class Browser:

    def __init__(self, user_agent: str = '', headers: tuple[tuple[str, str], ...] = (), verify_ssl_certificates: bool = True, start_worker: bool = False):
        self.tdir = ''
        self.worker = self.dispatcher = None
        self.dispatch_map = {}
        self.verify_ssl_certificates = verify_ssl_certificates
        self.id_counter = 0
        self.addheaders: list[tuple[str, str]] = list(headers)
        self.user_agent = user_agent
        self.lock = RLock()
        self.shutting_down = False
        if start_worker:
            self._ensure_state()

    def open(self, url_or_request: Request, data=None, timeout=None):
        method = 'POST' if data else 'GET'
        headers = []
        if hasattr(url_or_request, 'get_method'):
            r = url_or_request
            method = r.get_method()
            data = data or r.data
            headers = r.header_items()
            url = r.full_url
        else:
            url = url_or_request

        def has_header(x: str) -> bool:
            x = x.lower()
            for (h, v) in headers:
                if h.lower() == x:
                    return True
            return False

        if isinstance(data, dict):
            headers.append(('Content-Type', 'application/x-www-form-urlencoded'))
            data = urlencode(data)
        if isinstance(data, str):
            data = data.encode('utf-8')
            if not has_header('Content-Type'):
                headers.append(('Content-Type', 'text/plain'))

        with self.lock:
            self._ensure_state()
            self.id_counter += 1
            cmd = {
                'action': 'download', 'id': self.id_counter, 'url': url, 'method': method, 'timeout': timeout,
                'headers': self.addheaders + headers}
            if data:
                with open(os.path.join(self.tdir, f'i{self.id_counter}'), 'wb') as f:
                    if hasattr(data, 'read'):
                        shutil.copyfileobj(data, f)
                    else:
                        f.write(data)
                cmd['data_path'] = f.name
            res = FakeResponse()
            self.dispatch_map[self.id_counter] = res.queue
            self._send_command(cmd)
        return res

    open_novisit = open

    def set_simple_cookie(self, name: str, value: str, domain: str | None = None, path: str | None = '/'):
        '''
        Set a simple cookie using a name and value. If domain is specified, the cookie is only sent with requests
        to matching domains, otherwise it is sent with all requests. The leading dot in domain is optional.
        Similarly, by default all paths match, to restrict to certain path use the path parameter.
        '''
        c = {'name': name, 'value': value, 'domain': domain, 'path': path}
        self._send_command({'action': 'set_cookies', 'cookies':[c]})

    def set_user_agent(self, val: str = '') -> None:
        self.user_agent = val
        self._send_command({'action': 'set_user_agent', 'user_agent': val})

    def clone_browser(self):
        return self

    def _send_command(self, cmd):
        with self.lock:
            self.worker.stdin.write(json.dumps(cmd).encode())
            self.worker.stdin.write(b'\n')
            self.worker.stdin.flush()

    def _ensure_state(self):
        with self.lock:
            if not self.tdir:
                self.tdir = PersistentTemporaryDirectory()
                self.worker = run_worker(self.tdir, self.user_agent, self.verify_ssl_certificates)
                self.dispatcher = Thread(target=self._dispatch, daemon=True)
                self.dispatcher.start()

    def _dispatch(self):
        try:
            for line in self.worker.stdout:
                cmd = json.loads(line)
                if cmd.get('action') == 'finished':
                    with self.lock:
                        q = self.dispatch_map.pop(cmd['id'])
                    q.put(cmd)
                else:
                    raise Exception(f'Unexpected response from backend fetch worker process: {cmd}')
        except Exception:
            if not self.shutting_down:
                import traceback
                traceback.print_exc()

    def shutdown(self):
        self.shutting_down = True
        import shutil
        if self.worker:
            with suppress(OSError):
                self.worker.stdin.close()
            with suppress(OSError):
                self.worker.stdout.close()
            give_up_at = time.monotonic() + 1.5
            while time.monotonic() < give_up_at and self.worker.poll() is None:
                time.sleep(0.01)
            if self.worker.poll() is None:
                self.worker.kill()
        if self.tdir:
            with suppress(OSError):
                shutil.rmtree(self.tdir)
            self.tdir = ''
        if self.dispatcher:
            self.dispatcher.join()
            self.dispatcher = None

    def __del__(self):
        self.shutdown()


def run_worker(tdir: str, user_agent: str, verify_ssl_certificates: bool):
    from calibre.utils.ipc.simple_worker import start_pipe_worker
    return start_pipe_worker(f'from calibre.scraper.qt import worker; worker({tdir!r}, {user_agent!r}, {verify_ssl_certificates!r})')


def worker(*args):
    from calibre.gui2 import must_use_qt
    must_use_qt()
    from .qt_backend import worker
    worker(*args)


def develop():
    import sys
    br = Browser()
    try:
        for url in sys.argv[1:]:
            res = br.open(url)
            print(url, len(res.read()))
    finally:
        del br


if __name__ == '__main__':
    develop()
