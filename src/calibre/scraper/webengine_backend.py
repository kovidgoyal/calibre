#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import base64
import html
import json
import os
import secrets
import sys
from collections import deque
from contextlib import suppress
from http import HTTPStatus
from time import monotonic

from qt.core import QApplication, QByteArray, QNetworkCookie, QObject, Qt, QTimer, QUrl, pyqtSignal, sip
from qt.webengine import QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineSettings

from calibre.scraper.qt_backend import Request, too_slow_or_timed_out
from calibre.scraper.qt_backend import worker as qt_worker
from calibre.utils.resources import get_path as P
from calibre.utils.webengine import create_script, insert_scripts, setup_profile


def create_base_profile(cache_name='', allow_js=False):
    from calibre.utils.random_ua import random_common_chrome_user_agent
    if cache_name:
        ans = QWebEngineProfile(cache_name, QApplication.instance())
    else:
        ans = QWebEngineProfile(QApplication.instance())
    setup_profile(ans)
    ans.setHttpUserAgent(random_common_chrome_user_agent())
    ans.setHttpCacheMaximumSize(0)  # managed by webengine
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
    return ans



class DownloadRequest(QObject):

    aborted_on_timeout: bool = False
    response_received = pyqtSignal(object)

    def __init__(self, url: str, output_path: str, timeout: float, req_id: int, parent: 'FetchBackend'):
        super().__init__(parent)
        self.url, self.filename = url, os.path.basename(output_path)
        self.output_path = output_path
        self.req_id: int = req_id
        self.created_at = self.last_activity_at = monotonic()
        self.timeout = timeout
        self.bytes_received = 0
        self.result = {
            'action': 'finished', 'id': self.req_id, 'url': self.url, 'output': self.output_path,
            'headers': [], 'final_url': self.url, 'worth_retry': False,
        }

    def metadata_received(self, r: dict) -> None:
        if r['response_type'] != 'basic':
            print(f'WARNING: response type for {self.url} indicates headers are restrcited: {r["type"]}')
        self.result['worth_retry'] = r['status_code'] in (
            HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.GATEWAY_TIMEOUT)
        self.result['final_url'] = r['url']
        self.result['headers'] = r['headers']
        self.result['http_code'] = r['status_code']
        self.result['http_status_message'] = r['status_msg']

    def chunk_received(self, chunk: QByteArray) -> None:
        mv = memoryview(chunk)
        self.bytes_received += len(mv)
        with open(self.output_path, 'ab') as f:
            f.write(mv)

    def as_result(self, r: dict | None = {}) -> dict:
        if self.aborted_on_timeout:
            self.result['error'] = 'Timed out'
            self.result['worth_retry'] = True
        else:
            if r:
                self.result['error'] = r['error']
                self.result['worth_retry'] = True  # usually some kind of network error
        return self.result

    def too_slow_or_timed_out(self, now: float) -> bool:
        return too_slow_or_timed_out(self.timeout, self.last_activity_at, self.created_at, self.bytes_received, now)


class Worker(QWebEnginePage):
    working_on_request: DownloadRequest | None = None
    messages_dispatch = pyqtSignal(object)
    result_received = pyqtSignal(object)

    def __init__(self, profile, parent):
        super().__init__(profile, parent)
        self.messages_dispatch.connect(self.on_messages)

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
                if t == 'messages_available':
                    self.runjs('window.get_messages()', self.dispatch_messages)
            else:
                print(f'{source_id}:{line_num}:{message}')
            return

    def dispatch_messages(self, messages: list) -> None:
        if not sip.isdeleted(self):
            self.messages_dispatch.emit(messages)

    def runjs(self, js: str, callback = None) -> None:
        if callback is None:
            self.runJavaScript(js, QWebEngineScript.ScriptWorldId.ApplicationWorld)
        else:
            self.runJavaScript(js, QWebEngineScript.ScriptWorldId.ApplicationWorld, callback)

    def start_download(self, output_dir: str, req: Request, data: str) -> DownloadRequest:
        filename = os.path.basename(req['filename'])
        payload = json.dumps({'req': req, 'data': data})
        content = f'''<!DOCTYPE html>
        <html><head></head></body><div id="payload">{html.escape(payload)}</div></body></html>
        '''
        self.setContent(content.encode(), 'text/html;charset=utf-8', QUrl(req['url']))
        self.working_on_request = DownloadRequest(req['url'], os.path.join(output_dir, filename), req['timeout'], req['id'], self.parent())
        return self.working_on_request

    def abort_on_timeout(self) -> None:
        if self.working_on_request is not None:
            self.working_on_request.aborted_on_timeout = True
            self.runjs(f'window.abort_download({self.working_on_request.req_id})')

    def on_messages(self, messages: list[dict]) -> None:
        if not messages:
            return
        if self.working_on_request is None:
            print('Got messages without request:', messages)
            return
        self.working_on_request.last_activity_at = monotonic()
        for m in messages:
            t = m['type']
            if t == 'metadata_received':
                self.working_on_request.metadata_received(m)
            elif t == 'chunk_received':
                self.working_on_request.chunk_received(m['chunk'])
            elif t == 'finished':
                result = self.working_on_request.as_result()
                self.working_on_request = None
                self.result_received.emit(result)
            elif t == 'error':
                result = self.working_on_request.as_result(m)
                self.working_on_request = None
                self.result_received.emit(result)


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
        self.pending_requests: deque[tuple[Request, str]] = deque()
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
        now = monotonic()
        has_workers = False
        for w in self.workers:
            if w.working_on_request is not None:
                if w.working_on_request.too_slow_or_timed_out(now):
                    w.abort_on_timeout()
                else:
                    has_workers = True
        if not has_workers:
            self.timeout_timer.stop()

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
                self.timeout_timer.start()
                return
        if len(self.workers) < 5:
            self.workers.append(self.create_worker())
            self.workers[-1].start_download(self.output_dir, req, data)
            self.timeout_timer.start()
            return
        self.pending_requests.append((req, data))

    def create_worker(self) -> Worker:
        ans = Worker(self.profile, self)
        ans.token = self.token + ' '
        ans.result_received.connect(self.result_received)
        return ans

    def result_received(self, result: dict) -> None:
        self.send_response(result)
        self.download_finished.emit(result)
        if self.pending_requests:
            w = self.sender()
            req, data = self.pending_requests.popleft()
            w.start_download(self.output_dir, req, data)
            self.timeout_timer.start()

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


def develop(*urls: str) -> None:
    from calibre.scraper.qt import WebEngineBrowser
    br = WebEngineBrowser()
    for url in urls:
        print(url)
        res = br.open(url)
        print(f'{res.code} {res.reason}')
        print(res.headers)
        print(len(res.read()))


if __name__ == '__main__':
    develop(*sys.argv[1:])
