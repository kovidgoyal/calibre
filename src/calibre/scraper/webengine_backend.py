#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import base64
import html
import json
import os
import secrets
import sys
from contextlib import suppress
from time import monotonic

from qt.core import QApplication, QNetworkCookie, QObject, Qt, QTimer, QUrl, pyqtSignal
from qt.webengine import QWebEnginePage, QWebEngineScript

from calibre.scraper.qt_backend import Request
from calibre.scraper.qt_backend import worker as qt_worker
from calibre.scraper.simple_backend import create_base_profile
from calibre.utils.resources import get_path as P
from calibre.utils.webengine import create_script, insert_scripts

default_timeout: float = 60.  # seconds


def qurl_to_string(url: QUrl | str) -> str:
    return bytes(QUrl(url).toEncoded()).decode()


def qurl_to_key(url: QUrl | str) -> str:
    return qurl_to_string(url).rstrip('/')


Headers = list[tuple[str, str]]


class DownloadRequest(QObject):

    worth_retry: bool = False
    response_received = pyqtSignal(object)

    def __init__(self, url: str, output_path: str, timeout: float, req_id: int, parent: 'FetchBackend'):
        super().__init__(parent)
        self.url, self.filename = url, os.path.basename(output_path)
        self.output_path = output_path
        self.req_id: int = req_id
        self.created_at = self.last_activity_at = monotonic()
        self.timeout = timeout

    def handle_response(self, r: dict) -> None:
        result = {
            'action': 'finished', 'id': self.req_id, 'url': self.url, 'output': self.output_path,
            'final_url': r['url'], 'headers': r.get('headers', []), 'worth_retry': self.worth_retry,
        }
        if 'error' in r:
            result['error'] = r['error']
        else:
            if r['type'] != 'basic':
                print(f'WARNING: response type for {self.url} indicates headers are restrcited: {r["type"]}')
            with open(self.output_path, 'wb') as f:
                f.write(memoryview(r['data']))


class Worker(QWebEnginePage):
    working_on_request: DownloadRequest | None = None

    def javaScriptAlert(self, url, msg):
        pass

    def javaScriptConfirm(self, url, msg):
        return True

    def javaScriptPrompt(self, url, msg, defval):
        return True, defval

    def javaScriptConsoleMessage(self, level: QWebEnginePage.JavaScriptConsoleMessageLevel, message: str, line_num: int, source_id: str) -> None:
        if source_id == 'userscript:scraper.js':
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel and message.startswith(self.token):
                msg = json.loads(message.partition(' ')[2])
                t = msg.get('type')
                if t == 'print':
                    print(msg['text'])
                elif t == 'messages_available':
                    self.runjs('window.get_messages()', self.on_messages)
            else:
                print(f'{source_id}:{line_num}:{message}')
            return

    def runjs(self, js: str, callback) -> None:
        self.runJavaScript(js, QWebEngineScript.ScriptWorldId.ApplicationWorld, callback)

    def start_download(self, output_dir: str, req: Request, data: str) -> DownloadRequest:
        filename = os.path.basename(req['filename'])
        # TODO: Implement POST requests with data
        # TODO: Implement timeout
        payload = json.dumps({'req': req, 'data': data})
        content = f'''<!DOCTYPE html>
        <html><head></head></body><div id="payload">{html.escape(payload)}</div></body></html>
        '''
        self.setContent(content.encode(), 'text/html;charset=utf-8', QUrl(req['url']))
        self.working_on_request = DownloadRequest(req['url'], os.path.join(output_dir, filename), req['timeout'], req['id'], self.parent())
        return self.working_on_request

    def on_messages(self, messages: list[dict]) -> None:
        for m in messages:
            if m['type'] == 'finished':
                self.working_on_request.handle_response(m)
                self.working_on_request = None


class FetchBackend(QObject):

    request_download = pyqtSignal(object)
    input_finished = pyqtSignal(str)
    set_cookies = pyqtSignal(object)
    set_user_agent_signal = pyqtSignal(str)
    download_finished = pyqtSignal(object)

    def __init__(self, output_dir: str = '', cache_name: str = '', parent: QObject = None, user_agent: str = '', verify_ssl_certificates: bool = True) -> None:
        profile = create_base_profile(cache_name)
        self.token = secrets.token_hex()
        js = P('scraper.js', allow_user_override=False, data=True).decode('utf-8').replace('TOKEN', self.token)
        insert_scripts(profile, create_script('scraper.js', js))
        if user_agent:
            profile.setHttpUserAgent(user_agent)
        self.output_dir = output_dir or os.getcwd()
        self.profile = profile
        super().__init__(parent)
        self.workers: list[Worker] = []
        self.pending_requests: list[tuple[Request, str]] = []
        sys.excepthook = self.excepthook
        self.request_download.connect(self.download, type=Qt.ConnectionType.QueuedConnection)
        self.set_cookies.connect(self._set_cookies, type=Qt.ConnectionType.QueuedConnection)
        self.set_user_agent_signal.connect(self.set_user_agent, type=Qt.ConnectionType.QueuedConnection)
        self.input_finished.connect(self.on_input_finished, type=Qt.ConnectionType.QueuedConnection)
        self.all_request_cookies: list[QNetworkCookie] = []
        self.timeout_timer = t = QTimer(self)
        t.setInterval(50)
        t.timeout.connect(self.enforce_timeouts)

    def excepthook(self, cls: type, exc: Exception, tb) -> None:
        if not isinstance(exc, KeyboardInterrupt):
            sys.__excepthook__(cls, exc, tb)
        QApplication.instance().exit(1)

    def on_input_finished(self, error_msg: str) -> None:
        if error_msg:
            self.send_response({'action': 'input_error', 'error': error_msg})
        QApplication.instance().exit(1)

    def enforce_timeouts(self):
        # TODO: Start timer on download and port this method
        now = monotonic()
        timed_out = tuple(dr for dr in self.live_requests if dr.too_slow_or_timed_out(now))
        for dr in timed_out:
            if dr.webengine_download_request is None:
                dr.cancel_on_start = True
            else:
                dr.webengine_download_request.cancel()
            self.live_requests.discard(dr)
        if self.live_requests:
            self.timeout_timer.start()

    def download(self, req: Request) -> None:
        qurl = QUrl(req['url'])
        cs = self.profile.cookieStore()
        for c in self.all_request_cookies:
            c = QNetworkCookie(c)
            c.normalize(qurl)
            cs.setCookie(c)
        data_path = req['data_path']
        data = ''
        if data_path:
            with open(data_path, 'rb') as f:
                data = base64.standard_b64encode(f.read()).decode()
        if not self.workers:
            self.workers.append(self.create_worker())
        for w in self.workers:
            if w.working_on_request is None:
                w.start_download(self.output_dir, req, data)
                return
        if len(self.workers) < 5:
            self.workers.append(self.create_worker)
            self.workers[-1].start_download(self.output_dir, req, data)
            return
        # TODO: Drain pending requests on finish
        self.pending_requests.append((req, data))

    def create_worker(self) -> Worker:
        ans = Worker(self.profile, self)
        ans.token = self.token + ' '
        return ans

    def send_response(self, r: dict[str, str]) -> None:
        with suppress(OSError):
            print(json.dumps(r), flush=True, file=sys.__stdout__)

    def set_user_agent(self, new_val: str) -> None:
        self.profile.setHttpUserAgent(new_val)

    def add_cookie(self, c: QNetworkCookie) -> None:
        cs = self.profile.cookieStore()
        if c.domain():
            cs.setCookie(c)
        else:
            self.all_request_cookies.append(c)

    def _set_cookie_from_header(self, cookie_string: str) -> None:
        for c in QNetworkCookie.parseCookies(cookie_string.encode()):
            self.add_cookie(c)

    def _set_cookies(self, cookies: list[dict[str, str]]) -> None:
        for c in cookies:
            if 'header' in c:
                self._set_cookie_from_header(c['header'])
            else:
                self.set_simple_cookie(c['name'], c['value'], c.get('domain'), c.get('path'))

    def set_simple_cookie(self, name: str, value: str, domain: str | None = None, path: str | None = '/'):
        c = QNetworkCookie()
        c.setName(name.encode())
        c.setValue(value.encode())
        if domain is not None:
            c.setDomain(domain)
        if path is not None:
            c.setPath(path)
        self.add_cookie(c)


def worker(tdir: str, user_agent: str, verify_ssl_certificates: bool) -> None:
    return qt_worker(tdir, user_agent, verify_ssl_certificates, FetchBackend)


def develop(url: str) -> None:
    from calibre.scraper.qt import WebEngineBrowser
    br = WebEngineBrowser()
    raw = br.open(url).read()
    print(len(raw))


if __name__ == '__main__':
    develop(sys.argv[-1])
