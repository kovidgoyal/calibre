#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import secrets
import sys
import time
from functools import lru_cache
from qt.core import QApplication, QEventLoop, QLoggingCategory, QUrl
from qt.webengine import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from threading import Lock

from calibre.constants import cache_dir, iswindows
from calibre.gui2.webengine import create_script, insert_scripts
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.ipc.simple_worker import start_pipe_worker
from calibre.utils.filenames import retry_on_fail


def canonicalize_qurl(qurl):
    qurl = qurl.adjusted(QUrl.UrlFormattingOption.StripTrailingSlash | QUrl.UrlFormattingOption.NormalizePathSegments)
    if qurl.path() == '/':
        qurl = qurl.adjusted(QUrl.UrlFormattingOption.RemovePath)
    return qurl


@lru_cache(maxsize=None)
def create_profile(cache_name='simple', allow_js=False):
    from calibre.utils.random_ua import random_common_chrome_user_agent
    ans = QWebEngineProfile(cache_name, QApplication.instance())
    ans.setHttpUserAgent(random_common_chrome_user_agent())
    ans.setHttpCacheMaximumSize(0)  # managed by webengine
    ans.setCachePath(os.path.join(cache_dir(), 'scraper', cache_name))
    s = ans.settings()
    a = s.setAttribute
    a(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    a(QWebEngineSettings.WebAttribute.JavascriptEnabled, allow_js)
    s.setUnknownUrlSchemePolicy(QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes)
    a(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    a(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
    # ensure javascript cannot read from local files
    a(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    a(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, False)
    js = P('scraper.js', allow_user_override=False, data=True).decode('utf-8')
    ans.token = secrets.token_hex()
    js = js.replace('TOKEN', ans.token)
    insert_scripts(ans, create_script('scraper.js', js))
    return ans


class SimpleScraper(QWebEnginePage):

    def __init__(self, source, parent=None):
        profile = create_profile(source)
        self.token = profile.token
        super().__init__(profile, parent)
        self.setAudioMuted(True)
        self.loadStarted.connect(self.load_started)
        self.loadFinished.connect(self.load_finished)
        self.loadProgress.connect(self.load_progress)

    def load_started(self):
        if hasattr(self, 'current_fetch'):
            self.current_fetch['load_started'] = True

    def load_finished(self, ok):
        if hasattr(self, 'current_fetch'):
            self.current_fetch['load_finished'] = True
            self.current_fetch['load_was_ok'] = ok
            if not ok and self.is_current_url:
                self.current_fetch['working'] = False

    def load_progress(self, progress):
        if hasattr(self, 'current_fetch'):
            self.current_fetch['end_time'] = time.monotonic() + self.current_fetch['timeout']

    def javaScriptAlert(self, url, msg):
        pass

    def javaScriptConfirm(self, url, msg):
        return True

    def javaScriptPrompt(self, url, msg, defval):
        return True, defval

    @property
    def is_current_url(self):
        if not hasattr(self, 'current_fetch'):
            return False
        return canonicalize_qurl(self.url()) == self.current_fetch['fetching_url']

    def javaScriptConsoleMessage(self, level, message, line_num, source_id):
        parts = message.split(maxsplit=1)
        if len(parts) == 2 and parts[0] == self.token:
            msg = json.loads(parts[1])
            t = msg.get('type')
            if t == 'print':
                print(msg['text'], file=sys.stderr)
            elif t == 'domready':
                if self.is_current_url:
                    self.current_fetch['working'] = False
                    if not msg.get('failed'):
                        self.current_fetch['html'] = msg['html']

    def fetch(self, url_or_qurl, timeout=60):
        fetching_url = QUrl(url_or_qurl)
        self.current_fetch = {
            'timeout': timeout, 'end_time': time.monotonic() + timeout,
            'fetching_url': canonicalize_qurl(fetching_url), 'working': True,
            'load_started': False
        }
        self.load(fetching_url)
        try:
            app = QApplication.instance()
            while self.current_fetch['working'] and time.monotonic() < self.current_fetch['end_time']:
                app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            ans = self.current_fetch.get('html')
            if ans is None:
                eurl = fetching_url.toString()
                if self.current_fetch['working']:
                    raise TimeoutError(f'Timed out loading HTML from: {eurl}')
                raise ValueError(f'Failed to load HTML from: {eurl}')
            return ans
        finally:
            del self.current_fetch


def worker_main(source):
    QLoggingCategory.setFilterRules('''\
qt.webenginecontext.info=false
''')
    from calibre.gui2 import must_use_qt
    must_use_qt()
    s = SimpleScraper(source)
    for line in sys.stdin.buffer:
        line = line.strip()
        try:
            cmd, rest = line.split(b':', 1)
        except Exception:
            continue
        if cmd == b'EXIT':
            raise SystemExit(int(rest))
        if cmd == b'FETCH':
            try:
                html = s.fetch(QUrl.fromEncoded(json.loads(rest).encode('utf-8')))
            except Exception as e:
                import traceback
                result = {'ok': False, 'tb': traceback.format_exc(), 'err': str(e)}
            else:
                with PersistentTemporaryFile(suffix='-scraper-result.html') as t:
                    t.write(html.encode('utf-8'))
                result = {'ok': True, 'html_file': t.name}
            print(json.dumps(result), flush=True)


class Overseer:

    def __init__(self):
        self.lock = Lock()
        self.workers = {}

    def worker_for_source(self, source):
        with self.lock:
            ans = self.workers.get(source)
            if ans is None:
                w = start_pipe_worker(f'from calibre.scraper.simple import worker_main; worker_main({source!r})')
                ans = self.workers[source] = w
        return ans

    def fetch_url(self, source, url_or_qurl):
        w = self.worker_for_source(source)
        if isinstance(url_or_qurl, str):
            url_or_qurl = QUrl(url_or_qurl)
        w.stdin.write(b'FETCH:')
        w.stdin.write(json.dumps(bytes(url_or_qurl.toEncoded()).decode('utf-8')).encode('utf-8'))
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
            for w in self.workers.values():
                if w.wait(0.2) is None:
                    w.terminate()
                    if not iswindows:
                        if w.wait(0.1) is None:
                            w.kill()
            self.workers.clear()


def find_tests():
    import unittest
    from lxml.html import fromstring, tostring
    import re

    class TestSimpleWebEngineScraper(unittest.TestCase):

        def test_dom_load(self):
            overseer = Overseer()
            for f in ('book', 'nav'):
                path = P(f'templates/new_{f}.html', allow_user_override=False)
                url = QUrl.fromLocalFile(path)
                html = overseer.fetch_url('test', url)

                def c(a):
                    ans = tostring(fromstring(a.encode('utf-8')), pretty_print=True, encoding='unicode')
                    return re.sub(r'\s+', ' ', ans)
                self.assertEqual(c(html), c(open(path, 'rb').read().decode('utf-8')))
            self.assertRaises(ValueError, overseer.fetch_url, 'test', 'file:///does-not-exist.html')
            w = overseer.workers
            self.assertEqual(len(w), 1)
            del overseer
            self.assertFalse(w)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSimpleWebEngineScraper)


if __name__ == '__main__':
    app = QApplication([])
    s = SimpleScraper('test')
    s.fetch('file:///t/raw.html', timeout=5)
    del s
    del app
