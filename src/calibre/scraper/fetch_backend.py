#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from typing import Union

from qt.core import QNetworkCookie, QObject, Qt, QUrl, pyqtSignal
from qt.webengine import QWebEngineDownloadRequest, QWebEnginePage, QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

from .simple_backend import create_base_profile


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    def interceptRequest(self, req: QWebEngineUrlRequestInfo) -> None:
        pass


class FetchBackend(QWebEnginePage):

    request_download = pyqtSignal(object, str)

    def __init__(self, output_dir: str, cache_name: str = '', parent: QObject = None) -> None:
        self.profile = create_base_profile(cache_name)
        self.profile.downloadRequested.connect(self._download_requested)
        self.profile.setDownloadPath(output_dir)
        super().__init__(self.profile, parent)
        self.interceptor = RequestInterceptor(self)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.request_download.connect(self.download, type=Qt.ConnectionType.QueuedConnection)

    def download(self, url: Union[str, QUrl], filename_or_path: str = '') -> str:
        if isinstance(url, str):
            url = QUrl(url)
        super().download(url, filename_or_path)
        return bytes(url.toEncoded()).decode()

    def _download_requested(self, dr: QWebEngineDownloadRequest) -> None:
        dr.accept()
        dr.isFinishedChanged.connect(self._download_finished)

    def _download_finished(self) -> None:
        dr: QWebEngineDownloadRequest = self.sender()
        s = dr.state()
        url = bytes(dr.url().toEncoded()).decode()
        if s == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            print(99999999, url, dr.interruptReasonString())
        elif s == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            print(1111111, dr, url, dr.downloadFileName())

    def set_user_agent(self, new_val: str) -> None:
        self.profile.setHttpUserAgent(new_val)

    def set_simple_cookie(self, name, value, domain, path='/'):
        cs = self.profile.cookieStore()
        cookie_string = f'{name}={value}; Domain={domain}; Path={path}'
        for c in QNetworkCookie.parseCookies(cookie_string):
            cs.setCookie(c)
