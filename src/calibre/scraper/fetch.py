#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import json
import time
from contextlib import suppress
from io import BytesIO
from queue import Queue
from threading import Lock, Thread
from urllib.error import URLError

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
        return self.data.read(*a, **kw)

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

    def __init__(self, user_agent: str = '', headers: tuple[tuple[str, str], ...] = (), start_worker: bool = False):
        self.tdir = ''
        self.worker = self.dispatcher = None
        self.dispatch_map = {}
        self.id_counter = 0
        self.addheaders: list[tuple[str, str]] = list(headers)
        self.user_agent = user_agent
        self.lock = Lock()
        self.shutting_down = False
        if start_worker:
            self._ensure_state()

    def open(self, url_or_request, data=None, timeout=None):
        if data is not None:
            raise TypeError('The scraper fetch browser does not support sending data with requests')
        headers = []
        if hasattr(url_or_request, 'get_method'):
            r = url_or_request
            if r.get_method() != 'GET':
                raise TypeError('The scraper fetch browser only supports GET requests')
            if r.data is not None:
                raise TypeError('The scraper fetch browser does not support sending data with requests')
            headers = r.header_items()
            url = r.full_url
        else:
            url = url_or_request
        self._ensure_state()

        with self.lock:
            self.id_counter += 1
            res = FakeResponse()
            self.dispatch_map[self.id_counter] = res.queue
            cmd = {'action': 'download', 'id': self.id_counter, 'url': url, 'timeout': timeout, 'headers': self.addheaders + headers}
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
        self.worker.stdin.write(json.dumps(cmd).encode())
        self.worker.stdin.write(b'\n')
        self.worker.stdin.flush()

    def _ensure_state(self):
        with self.lock:
            if not self.tdir:
                self.tdir = PersistentTemporaryDirectory()
                self.worker = run_worker(self.tdir, self.user_agent)
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


def run_worker(tdir: str, user_agent: str):
    from calibre.utils.ipc.simple_worker import start_pipe_worker
    return start_pipe_worker(f'from calibre.scraper.fetch import worker; worker({tdir!r}, {user_agent!r})')


def worker(*args):
    from calibre.gui2 import must_use_qt
    must_use_qt()
    from .fetch_backend import worker
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
