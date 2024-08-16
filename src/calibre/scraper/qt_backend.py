#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import sys
from contextlib import suppress
from threading import Thread
from time import monotonic
from typing import Any, TypedDict

from qt.core import (
    QApplication,
    QNetworkAccessManager,
    QNetworkCookie,
    QNetworkCookieJar,
    QNetworkReply,
    QNetworkRequest,
    QObject,
    QSslError,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
    sip,
)

from calibre.utils.random_ua import random_common_chrome_user_agent

default_timeout: float = 60.  # seconds


def qurl_to_string(url: QUrl | str) -> str:
    return bytes(QUrl(url).toEncoded()).decode()


def qurl_to_key(url: QUrl | str) -> str:
    return qurl_to_string(url).rstrip('/')


Headers = list[tuple[str, str]]

class Request(TypedDict):
    id: int
    url: str
    headers: Headers
    data_path: str
    method: str
    filename: str
    timeout: float


class CookieJar(QNetworkCookieJar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_request_cookies = []

    def add_cookie(self, c: QNetworkCookie) -> None:
        if c.domain():
            self.insertCookie(c)
        else:
            self.all_request_cookies.append(c)

    def cookiesForUrl(self, url: QUrl) -> list[QNetworkCookie]:
        ans = []
        for c in self.all_request_cookies:
            c = QNetworkCookie(c)
            c.normalize(url)
            ans.append(c)
        return super().cookiesForUrl(url) + ans


def too_slow_or_timed_out(timeout: float, last_activity_at: float, created_at: float, downloaded_bytes: int, now: float) -> bool:
    if timeout and last_activity_at + timeout < now:
        return True
    time_taken = now - created_at
    if time_taken > default_timeout:
        rate = downloaded_bytes / time_taken
        return rate < 10
    return False


class DownloadRequest(QObject):

    worth_retry: bool = False

    def __init__(self, url: str, output_path: str, reply: QNetworkReply, timeout: float, req_id: int, parent: 'FetchBackend'):
        super().__init__(parent)
        self.url, self.filename = url, os.path.basename(output_path)
        self.output_path = output_path
        self.reply = reply
        self.req_id: int = req_id
        self.created_at = self.last_activity_at = monotonic()
        self.timeout = timeout
        self.bytes_received = 0
        self.reply.downloadProgress.connect(self.on_download_progress, type=Qt.ConnectionType.QueuedConnection)
        self.reply.uploadProgress.connect(self.on_upload_progress, type=Qt.ConnectionType.QueuedConnection)
        # self.reply.readyRead.connect(self.on_data_available)

    def on_download_progress(self, bytes_received: int, bytes_total: int) -> None:
        self.bytes_received = bytes_received
        self.last_activity_at = monotonic()

    def on_upload_progress(self, bytes_received: int, bytes_total: int) -> None:
        self.bytes_received = bytes_received
        self.last_activity_at = monotonic()

    def save_data(self) -> None:
        with open(self.output_path, 'wb') as f:
            ba = self.reply.readAll()
            f.write(memoryview(ba))

    def on_ssl_errors(self, err) -> None:
        pass

    def as_result(self) -> dict[str, str]:
        self.save_data()
        e = self.reply.error()
        result = {
            'action': 'finished', 'id': self.req_id, 'url': self.url, 'output': self.output_path,
            'final_url': qurl_to_string(self.reply.url()), 'headers': []
        }
        h = result['headers']
        for (k, v) in self.reply.rawHeaderPairs():
            h.append((bytes(k).decode('utf-8', 'replace'), bytes(v).decode('utf-8', 'replace')))
        if code := self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute):
            result['http_code'] = code
        if msg := self.reply.attribute(QNetworkRequest.Attribute.HttpReasonPhraseAttribute):
            result['http_status_message'] = msg

        if e != QNetworkReply.NetworkError.NoError:
            if e in (
                QNetworkReply.NetworkError.TimeoutError,
                QNetworkReply.NetworkError.TemporaryNetworkFailureError,

                QNetworkReply.NetworkError.ConnectionRefusedError,
                QNetworkReply.NetworkError.RemoteHostClosedError,
                QNetworkReply.NetworkError.OperationCanceledError,  # abort() called in overall timeout check
                QNetworkReply.NetworkError.SslHandshakeFailedError,
            ):
                self.worth_retry = True
            es = f'{e}: {self.reply.errorString()}'
            result['error'], result['worth_retry'] = es, self.worth_retry
        return result

    def too_slow_or_timed_out(self, now: float) -> bool:
        return too_slow_or_timed_out(self.timeout, self.last_activity_at, self.created_at, self.bytes_received, now)


class FetchBackend(QNetworkAccessManager):

    request_download = pyqtSignal(object)
    input_finished = pyqtSignal(str)
    set_cookies = pyqtSignal(object)
    set_user_agent_signal = pyqtSignal(str)
    download_finished = pyqtSignal(object)

    def __init__(self, output_dir: str = '', cache_name: str = '', parent: QObject = None, user_agent: str = '', verify_ssl_certificates: bool = True) -> None:
        super().__init__(parent)
        self.cookie_jar = CookieJar(self)
        self.verify_ssl_certificates = verify_ssl_certificates
        self.setCookieJar(self.cookie_jar)
        self.user_agent = user_agent or random_common_chrome_user_agent()
        self.setTransferTimeout(int(default_timeout * 1000))
        self.output_dir = output_dir or os.getcwd()
        sys.excepthook = self.excepthook
        self.request_download.connect(self.download, type=Qt.ConnectionType.QueuedConnection)
        self.set_cookies.connect(self._set_cookies, type=Qt.ConnectionType.QueuedConnection)
        self.set_user_agent_signal.connect(self.set_user_agent, type=Qt.ConnectionType.QueuedConnection)
        self.input_finished.connect(self.on_input_finished, type=Qt.ConnectionType.QueuedConnection)
        self.finished.connect(self.on_reply_finished, type=Qt.ConnectionType.QueuedConnection)
        self.sslErrors.connect(self.on_ssl_errors)
        self.live_requests: set[DownloadRequest] = set()
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
        timed_out = tuple(dr for dr in self.live_requests if dr.too_slow_or_timed_out(now))
        for dr in timed_out:
            dr.reply.abort()
        if not self.live_requests:
            self.timeout_timer.stop()

    def current_user_agent(self) -> str:
        return self.user_agent

    def download(self, req: Request) -> None:
        filename = os.path.basename(req['filename'])
        qurl = QUrl(req['url'])
        rq = QNetworkRequest(qurl)
        timeout = req['timeout']
        rq.setTransferTimeout(int(timeout * 1000))
        rq.setRawHeader(b'User-Agent', self.current_user_agent().encode())
        for (name, val) in req['headers']:
            ex = rq.rawHeader(name)
            if len(ex):
                val = bytes(ex).decode() + ', ' + val
            rq.setRawHeader(name.encode(), val.encode())
        qmethod = req['method'].lower()
        data_path = req['data_path']
        data = None
        if data_path:
            with open(data_path, 'rb') as f:
                data = f.read()
        if qmethod == 'get':
            reply = self.get(rq, data)
        elif qmethod == 'post':
            reply = self.post(rq, data)
        elif qmethod == 'put':
            reply = self.put(rq, data)
        elif qmethod == 'head':
            reply = self.head(rq, data)
        elif qmethod == 'delete':
            reply = self.deleteRequest(rq)
        else:
            reply = self.sendCustomRequest(rq, req['method'].encode(), data)
        dr = DownloadRequest(req['url'], os.path.join(self.output_dir, filename), reply, timeout, req['id'], self)
        self.live_requests.add(dr)
        if not self.timeout_timer.isActive():
            self.timeout_timer.start()

    def on_ssl_errors(self, reply: QNetworkReply, errors: list[QSslError]) -> None:
        if not self.verify_ssl_certificates:
            reply.ignoreSslErrors()

    def on_reply_finished(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        for x in tuple(self.live_requests):
            if x.reply is reply:
                self.live_requests.discard(x)
                self.report_finish(x)
                x.reply = None
                break

    def report_finish(self, dr: DownloadRequest) -> None:
        result = dr.as_result()
        self.download_finished.emit(result)
        self.send_response(result)

    def send_response(self, r: dict[str, str]) -> None:
        with suppress(OSError):
            print(json.dumps(r), flush=True, file=sys.__stdout__)

    def set_user_agent(self, new_val: str) -> None:
        self.user_agent = new_val

    def _set_cookie_from_header(self, cookie_string: str) -> None:
        for c in QNetworkCookie.parseCookies(cookie_string.encode()):
            self.cookie_jar.add_cookie(c)

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
        self.cookie_jar.add_cookie(c)


def request_from_cmd(cmd: dict[str, Any], filename: str) -> Request:
    timeout = cmd.get('timeout')
    if timeout is None:
        timeout = default_timeout
    req: Request = {
        'id': int(cmd['id']),
        'url': cmd['url'],
        'headers': cmd.get('headers') or [],
        'data_path': cmd.get('data_path') or '',
        'method': cmd.get('method') or 'get',
        'filename': filename,
        'timeout': float(timeout),
    }
    return req


def read_commands(backend: FetchBackend, tdir: str) -> None:
    error_msg = ''
    try:
        for line in sys.stdin:
            cmd = json.loads(line)
            ac = cmd['action']
            if ac == 'download':
                backend.request_download.emit(request_from_cmd(cmd, f'o{cmd["id"]}'))
            elif ac == 'set_cookies':
                backend.set_cookies.emit(cmd['cookies'])
            elif ac == 'set_user_agent':
                backend.set_user_agent_signal.emit(cmd['user_agent'])
            elif ac == 'quit':
                break
    except Exception as err:
        import traceback
        traceback.print_exc()
        error_msg = str(err)
    backend.input_finished.emit(error_msg)


def worker(tdir: str, user_agent: str, verify_ssl_certificates: bool, backend_class: type = FetchBackend) -> None:
    app = QApplication.instance()
    sys.stdout = sys.stderr
    backend = backend_class(parent=app, user_agent=user_agent, output_dir=tdir, verify_ssl_certificates=verify_ssl_certificates)
    try:
        read_thread = Thread(target=read_commands, args=(backend, tdir), daemon=True)
        read_thread.start()
        app.exec()
    finally:
        sip.delete(backend)
    del app


def develop(url: str) -> None:
    from calibre.gui2 import must_use_qt, setup_unix_signals
    must_use_qt()
    app = QApplication.instance()
    app.signal_received = lambda : app.exit(1)
    setup_unix_signals(app)
    backend = FetchBackend()
    num_left = 0

    def download_finished(dr: DownloadRequest):
        nonlocal num_left
        num_left -= 1
        if not num_left:
            backend.input_finished.emit('')

    backend.download_finished.connect(download_finished)
    for i, url in enumerate(sys.argv[1:]):
        backend.download(request_from_cmd({'url':url, 'id': i}, f'test-output-{i}'))
        num_left += 1
    app.exec()


if __name__ == '__main__':
    develop(sys.argv[-1])
