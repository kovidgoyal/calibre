#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import sys
import weakref
from threading import Lock, Thread, get_ident

from calibre.constants import iswindows
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.filenames import retry_on_fail
from calibre.utils.ipc.simple_worker import start_pipe_worker


def worker_main(source):
    from qt.core import QUrl

    from calibre.gui2 import must_use_qt
    from calibre.gui_launch import setup_qt_logging
    setup_qt_logging()

    from .simple_backend import SimpleScraper
    must_use_qt()
    s = SimpleScraper(source)
    for line in sys.stdin.buffer:
        line = line.strip()
        if source == 'test':
            print(line.decode('utf-8'), file=sys.stderr)
        try:
            cmd, rest = line.split(b':', 1)
        except Exception:
            continue
        if cmd == b'EXIT':
            raise SystemExit(int(rest))
        if cmd == b'FETCH':
            try:
                d = json.loads(rest)
                html = s.fetch(QUrl.fromEncoded(d['url'].encode('utf-8')), timeout=float(d['timeout']))
            except Exception as e:
                import traceback
                result = {'ok': False, 'tb': traceback.format_exc(), 'err': str(e)}
            else:
                with PersistentTemporaryFile(suffix='-scraper-result.html') as t:
                    t.write(html.encode('utf-8'))
                result = {'ok': True, 'html_file': t.name}
            print(json.dumps(result), flush=True)


overseers = []


class Overseer:

    def __init__(self):
        self.lock = Lock()
        self.workers = {}
        overseers.append(weakref.ref(self))

    def safe_wait(self, w, timeout):
        try:
            return w.wait(timeout)
        except Exception:
            pass

    def worker_for_source(self, source):
        wname = f'{source}::{get_ident()}'
        with self.lock:
            ans = self.workers.get(wname)
            if ans is None:
                w = start_pipe_worker(f'from calibre.scraper.simple import worker_main; worker_main({source!r})')
                ans = self.workers[wname] = w
        return ans

    def fetch_url(self, url_or_qurl, source='', timeout=60):
        from qt.core import QUrl
        w = self.worker_for_source(source)
        if isinstance(url_or_qurl, str):
            url_or_qurl = QUrl(url_or_qurl)
        w.stdin.write(b'FETCH:')
        w.stdin.write(json.dumps({'url': bytes(url_or_qurl.toEncoded()).decode('utf-8'), 'timeout': timeout}).encode('utf-8'))
        w.stdin.write(b'\n')
        w.stdin.flush()
        output = json.loads(w.stdout.readline())
        if not output['ok']:
            raise ValueError(output['err'])
        with open(output['html_file'], 'rb') as f:
            html = f.read().decode('utf-8')
        retry_on_fail(os.remove, output['html_file'])
        return html

    def __del__(self):
        with self.lock:
            for w in self.workers.values():
                w.stdin.write(b'EXIT:0\n')
                w.stdin.flush()
                w.stdin.close()
                w.stdout.close()
            for w in self.workers.values():
                if self.safe_wait(w, 0.2) is None:
                    w.terminate()
                    if not iswindows:
                        if self.safe_wait(w, 0.1) is None:
                            w.kill()
            self.workers.clear()
    close = __del__


def cleanup_overseers():
    threads = []
    for x in overseers:
        o = x()
        if o is not None:
            t = Thread(target=o.close, name='CloseOverSeer')
            t.start()
            threads.append(t)
    del overseers[:]

    def join_all():
        for t in threads:
            t.join()
    return join_all


read_url_lock = Lock()


def read_url(storage, url, timeout=60):
    with read_url_lock:
        if not storage:
            storage.append(Overseer())
        scraper = storage[0]
    from calibre.ebooks.chardet import strip_encoding_declarations
    return strip_encoding_declarations(scraper.fetch_url(url, timeout=timeout))


if __name__ == '__main__':
    print(read_url([], sys.argv[-1]))
