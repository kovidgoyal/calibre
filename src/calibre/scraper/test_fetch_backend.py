#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import http.server
import json
import os
import re
import unittest
from threading import Event, Thread

from lxml.html import fromstring, tostring

from calibre.utils.resources import get_path as P

from .fetch import Browser
from .simple import Overseer

skip = ''
is_sanitized = 'libasan' in os.environ.get('LD_PRELOAD', '')
if is_sanitized:
    skip = 'Skipping Scraper tests as ASAN is enabled'
elif 'SKIP_QT_BUILD_TEST' in os.environ:
    skip = 'Skipping Scraper tests as it causes crashes in macOS VM'


@unittest.skipIf(skip, skip)
class TestSimpleWebEngineScraper(unittest.TestCase):

    def test_dom_load(self):
        from qt.core import QUrl
        overseer = Overseer()
        for f in ('book', 'nav'):
            path = P(f'templates/new_{f}.html', allow_user_override=False)
            url = QUrl.fromLocalFile(path)
            html = overseer.fetch_url(url, 'test')

            def c(a):
                ans = tostring(fromstring(a.encode('utf-8')), pretty_print=True, encoding='unicode')
                return re.sub(r'\s+', ' ', ans)
            with open(path, 'rb') as f:
                raw = f.read().decode('utf-8')
            self.assertEqual(c(html), c(raw))
        self.assertRaises(ValueError, overseer.fetch_url, 'file:///does-not-exist.html', 'test')
        w = overseer.workers
        self.assertEqual(len(w), 1)
        del overseer
        self.assertFalse(w)


class Handler(http.server.BaseHTTPRequestHandler):

    request_count = 0

    def do_GET(self):
        h = {}
        for k, v in self.headers.items():
            h.setdefault(k, []).append(v)
        ans = {
            'path': self.path,
            'headers': h,
            'request_count': self.request_count,
        }
        data = json.dumps(ans).encode()
        self.send_response(http.HTTPStatus.OK)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.flush_headers()
        self.wfile.write(data)

    def log_request(self, code='-', size='-'):
        self.request_count += 1


@unittest.skipIf(skip, skip)
class TestFetchBackend(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def setUp(self):
        self.server_started = Event()
        self.server_thread = Thread(target=self.run_server, daemon=True)
        self.server_thread.start()
        self.server_started.wait(5)
        self.request_count = 0

    def tearDown(self):
        self.server.shutdown()
        self.server_thread.join(5)

    def test_recipe_browser(self):
        def u(path=''):
            return f'http://localhost:{self.port}{path}'
        def get(path=''):
            raw = br.open(u(path)).read()
            return json.loads(raw)
        br = Browser(user_agent='test-ua', headers=(('th', '1'),), start_worker=True)
        try:
            r = get()
            self.ae(r['request_count'], 0)
            print(r)
            self.ae(r['headers']['th'], ['1'])
            self.ae(r['headers']['User-Agent'], ['test-ua'])
            self.assertIn('Accept-Encoding', r['headers'])
        finally:
            br.shutdown()

    def run_server(self):
        import socketserver

        def create_handler(*a):
            ans = Handler(*a)
            ans.backend = self
            return ans

        with socketserver.TCPServer(("", 0), create_handler) as httpd:
            self.server = httpd
            self.port = httpd.server_address[1]
            self.server_started.set()
            httpd.serve_forever()


def find_tests():
    ans = unittest.defaultTestLoader.loadTestsFromTestCase(TestSimpleWebEngineScraper)
    ans.addTests(iter(unittest.defaultTestLoader.loadTestsFromTestCase(TestFetchBackend)))
    return ans
