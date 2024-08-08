#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import sys
from contextlib import suppress
from threading import Thread
from typing import Union

from qt.core import QApplication, QNetworkCookie, QObject, Qt, QUrl, pyqtSignal
from qt.webengine import QWebEngineDownloadRequest, QWebEnginePage, QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

from calibre.scraper.simple_backend import create_base_profile


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    def interceptRequest(self, req: QWebEngineUrlRequestInfo) -> None:
        fb: FetchBackend = self.parent()
        if fb:
            key = qurl_to_key(req.requestUrl())
            if dr := fb.download_requests[key]:
                for name, x in dr.headers.items():
                    if isinstance(x, str):
                        x = [x]
                    for val in x:
                        req.setHttpHeader(name.encode(), val.encode())


def qurl_to_string(url: QUrl | str) -> str:
    return bytes(QUrl(url).toEncoded()).decode()


qurl_to_key = qurl_to_string
Headers = dict[str, Union[str, list[str]]]


class DownloadRequest:

    def __init__(self, url: str, filename: str, headers: Headers | None = None):
        self.url, self.filename = url, filename
        self.url_key = qurl_to_key(url)
        self.headers: Headers = headers or {}
        self.num_of_responses_needed = 1
        self.finished = False
        self.error_message = ''
        self.webengine_download_request: QWebEngineDownloadRequest | None = None


class FetchBackend(QWebEnginePage):

    request_download = pyqtSignal(str, str)
    input_finished = pyqtSignal(str)
    download_finished = pyqtSignal(object)

    def __init__(self, output_dir: str = '', cache_name: str = '', parent: QObject = None) -> None:
        self.profile = create_base_profile(cache_name)
        self.profile.downloadRequested.connect(self._download_requested)
        self.output_dir = output_dir or os.getcwd()
        self.profile.setDownloadPath(self.output_dir)
        super().__init__(self.profile, parent)
        self.interceptor = RequestInterceptor(self)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.request_download.connect(self.download, type=Qt.ConnectionType.QueuedConnection)
        self.input_finished.connect(self.on_input_finished, type=Qt.ConnectionType.QueuedConnection)
        self.download_requests: dict[str, DownloadRequest] = {}
        self.pending_download_requests: dict[int, DownloadRequest] = {}
        self.download_requests_by_id: dict[int, DownloadRequest] = {}
        self.dr_identifier_count = 0

    def on_input_finished(self, error_msg: str) -> None:
        if error_msg:
            self.send_response({'action': 'input_error', 'error': error_msg})
        QApplication.instance().exit(1)

    def download(self, url: str, filename: str, extra_headers: Headers | None = None) -> None:
        filename = os.path.basename(filename)
        qurl = QUrl(url)
        key = qurl_to_key(qurl)
        dr = self.download_requests.get(key)
        if dr:
            dr.num_of_responses_needed += 1
        else:
            self.download_requests[key] = dr = DownloadRequest(url, filename, extra_headers)
            self.dr_identifier_count += 1
            self.pending_download_requests[self.dr_identifier_count] = dr
            super().download(qurl, str(self.dr_identifier_count))

    def _download_requested(self, wdr: QWebEngineDownloadRequest) -> None:
        try:
            idc = int(wdr.suggestedFileName())
            dr: DownloadRequest = self.pending_download_requests.pop(idc)
        except Exception:
            import traceback
            traceback.print_exc()
            return
        try:
            if dr.filename:
                wdr.setDownloadFileName(dr.filename)
            dr.webengine_download_request = wdr
            self.download_requests_by_id[wdr.id()] = dr
            wdr.isFinishedChanged.connect(self._download_finished)
            wdr.receivedBytesChanged.connect(self._bytes_received)
            wdr.accept()
        except Exception:
            import traceback
            traceback.print_exc()
            self.report_finish(wdr, dr)

    def _bytes_received(self) -> None:
        wdr: QWebEngineDownloadRequest = self.sender()
        wdr

    def _download_finished(self) -> None:
        wdr: QWebEngineDownloadRequest = self.sender()
        if dr := self.download_requests_by_id.get(wdr.id()):
            self.report_finish(wdr, dr)

    def report_finish(self, wdr: QWebEngineDownloadRequest, dr: DownloadRequest) -> None:
        s = wdr.state()
        output = os.path.join(wdr.downloadDirectory(), wdr.downloadFileName())
        result: dict[str, str] = {}
        if s == QWebEngineDownloadRequest.DownloadState.DownloadRequested:
            # Open of URL failed
            result = {'action': 'finished', 'error':'Open of URL failed', 'url': dr.url, 'output': output}
            dr.finished = True
        elif s == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            result = {'action': 'finished', 'error':'Timed out waiting for download', 'url': dr.url, 'output': output}
            dr.finished = True
        elif s == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            result = {'action': 'finished', 'error':wdr.interruptReasonString(), 'url': dr.url, 'output': output}
            dr.finished = True
        elif s == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            result = {'action': 'finished', 'url': dr.url, 'output': output, 'final_url': qurl_to_string(wdr.url())}
            dr.finished = True

        if result:
            self.download_finished.emit(result)
            while dr.num_of_responses_needed:
                dr.num_of_responses_needed -= 1
                self.send_response(result)

    def send_response(self, r: dict[str, str]) -> None:
        with suppress(OSError):
            print(json.dumps(r), flush=True)

    def set_user_agent(self, new_val: str) -> None:
        self.profile.setHttpUserAgent(new_val)

    def set_simple_cookie(self, name, value, domain, path='/'):
        cs = self.profile.cookieStore()
        cookie_string = f'{name}={value}; Domain={domain}; Path={path}'
        for c in QNetworkCookie.parseCookies(cookie_string):
            cs.setCookie(c)


def read_commands(backend: FetchBackend, tdir: str) -> None:
    file_counter = 0
    error_msg = ''
    try:
        for line in sys.stdin:
            cmd = json.loads(line)
            ac = cmd['action']
            if ac == 'download':
                file_counter += 1
                backend.request_download.emit(cmd['url'], os.path.join(tdir, str(file_counter)))
            elif ac == 'quit':
                break
    except Exception as err:
        import traceback
        traceback.print_exc()
        error_msg = str(err)
    backend.input_finished.emit(error_msg)


def worker(tdir):
    app = QApplication.instance()
    backend = FetchBackend(output_dir=tdir, parent=app)
    read_thread = Thread(target=read_commands, args=(backend, tdir), daemon=True)
    read_thread.start()
    app.exec()
    del backend
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
        backend.download(url, f'test-output-{i}')
        num_left += 1
    app.exec()


if __name__ == '__main__':
    develop(sys.argv[-1])
