#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import hashlib
import os
import re
import tempfile
from contextlib import suppress

from qt.core import (
    QDialog,
    QDialogButtonBox,
    QFileInfo,
    QLabel,
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
    QProgressBar,
    QScrollArea,
    Qt,
    QTimer,
    QTimeZone,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import human_readable
from calibre.gui2 import error_dialog
from calibre.utils.localization import _, ngettext


class ProgressBar(QWidget):
    done = pyqtSignal(str)
    MAX_RETRIES = 3
    RETRY_DELAY_MS = 500

    def __init__(self, qurl: QUrl, path: str, nam: QNetworkAccessManager, text: str, parent: QWidget | None, sha256: str = '') -> None:
        super().__init__(parent)
        self.expected_sha256 = sha256.lower()
        self.hasher = hashlib.sha256()
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(text)
        la.setWordWrap(True)
        l.addWidget(la)
        self.pb = pb = QProgressBar(self)
        pb.setTextVisible(True)
        pb.setMinimum(0), pb.setMaximum(0)
        l.addWidget(pb)
        self.qurl = qurl
        self.desc = text
        self.path = path
        self.nam = nam
        self.file_obj = tempfile.NamedTemporaryFile('wb', dir=os.path.dirname(self.path), delete=False)  # ruff: ignore[open-file-with-context-handler]
        self.reply: QNetworkReply | None = None
        self.over_reported = False
        self.total_size: int | None = None
        self.response_end: int | None = None
        self.response_checked = False
        self.use_ranges = bool(sha256)
        self.request_start = 0
        self.request_ranged = False
        self.validator = b''
        self.retries = self.retry_progress = 0
        self.not_modified = False
        self.restarted_after_corruption = False
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self.start_request)
        self.start_request()

    def reset_partial_file(self) -> None:
        self.file_obj.seek(0)
        self.file_obj.truncate()
        self.hasher = hashlib.sha256()

    def start_request(self) -> None:
        if self.over_reported:
            return
        self.request_start = self.file_obj.tell()
        if self.total_size is not None and self.request_start == self.total_size:
            self.on_over()
            return
        self.response_checked = False
        self.response_end = None
        req = QNetworkRequest(self.qurl)
        req.setRawHeader(b'Accept-Encoding', b'identity')
        # Ranges are only used to resume an interrupted transfer, the rest of
        # the resource is requested at once to avoid a request per chunk.
        self.request_ranged = self.use_ranges and self.request_start > 0
        if self.request_ranged:
            req.setRawHeader(b'Range', f'bytes={self.request_start}-'.encode('ascii'))
            if self.validator:
                req.setRawHeader(b'If-Range', self.validator)
        fi = QFileInfo(self.path)
        if not self.request_start and fi.exists():
            req.setHeader(
                QNetworkRequest.KnownHeaders.IfModifiedSinceHeader,
                fi.lastModified(QTimeZone(QTimeZone.Initialization.UTC)),
            )

        self.reply = reply = self.nam.get(req)
        assert reply is not None
        reply.downloadProgress.connect(self.on_download)
        reply.finished.connect(self.finished)
        reply.readyRead.connect(self.data_received)

    def release_reply(self) -> None:
        reply, self.reply = self.reply, None
        if reply is not None:
            reply.downloadProgress.disconnect(self.on_download)
            reply.finished.disconnect(self.finished)
            reply.readyRead.disconnect(self.data_received)
            if reply.isRunning():
                reply.abort()
            reply.deleteLater()

    def prepare_response(self) -> bool:
        if self.response_checked:
            return True
        reply = self.reply
        assert reply is not None
        code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if code not in (200, 206):
            return False
        encoding = reply.rawHeader(b'Content-Encoding').data().strip().lower()
        identity = encoding in (b'', b'identity')
        length = reply.rawHeader(b'Content-Length').data()
        try:
            size = int(length) if length else None
        except ValueError:
            self.on_over(_('Server returned an invalid Content-Length'))
            return False
        if code == 206:
            match = re.fullmatch(rb'bytes (\d+)-(\d+)/(\d+)', reply.rawHeader(b'Content-Range').data())
            if match is None or not self.request_ranged or not identity:
                self.on_over(_('Server returned an invalid byte range'))
                return False
            start, end, total = map(int, match.groups())
            if (
                start != self.request_start
                or end < start
                or end >= total
                or (self.total_size is not None and self.total_size != total)
                or (size is not None and size != end - start + 1)
            ):
                self.on_over(_('Server returned an unexpected byte range'))
                return False
            self.total_size, self.response_end = total, end + 1
        else:
            # A server may ignore Range, or return a changed representation after If-Range.
            # The response then starts from the beginning, so request_start is
            # reset to 0 which also disables the validator check below.
            if self.request_start:
                self.reset_partial_file()
                self.request_start = 0
            self.total_size = size if identity else None
            self.response_end = self.total_size
        etag = reply.rawHeader(b'ETag').data()
        if code == 206 and not self.expected_sha256 and self.request_start and self.validator and etag != self.validator:
            self.on_over(_('Server changed the resource during download'))
            return False
        self.validator = etag if re.fullmatch(rb'"[\x21\x23-\x7e\x80-\xff]*"', etag) else b''
        self.use_ranges = identity and bool(self.expected_sha256 or self.validator)
        self.response_checked = True
        return True

    def data_received(self) -> None:
        if self.over_reported:
            return
        try:
            reply = self.reply
            assert reply is not None
            data = reply.readAll().data() if reply.isOpen() else b''
            if not self.prepare_response():
                return
            if self.response_end is not None and self.file_obj.tell() + len(data) > self.response_end:
                self.on_over(_('Server sent more data than requested'))
                return
            self.file_obj.write(data)
            self.hasher.update(data)
            self.on_download()
        except Exception as e:
            self.on_over(_('Failed to write downloaded data with error: {}').format(e))

    def retry(self, err_msg: str) -> None:
        position = self.file_obj.tell()
        # Bound failures at the same offset while allowing interrupted transfers to make progress.
        # Progress only counts when it is kept, transfers that restart from
        # the beginning have a fixed number of retries.
        if self.use_ranges and position > self.retry_progress:
            self.retries = 0
            self.retry_progress = position
        if self.retries >= self.MAX_RETRIES:
            self.on_over(err_msg)
            return
        self.retries += 1
        if not self.use_ranges:
            self.reset_partial_file()
            self.total_size = None
        self.pb.setFormat(_('Retrying download...'))
        self.retry_timer.start(self.RETRY_DELAY_MS * 2 ** (self.retries - 1))

    def on_over(self, err_msg: str = '') -> None:
        if self.over_reported:
            return
        self.over_reported = True
        self.retry_timer.stop()
        self.release_reply()
        try:
            self.file_obj.close()
        except OSError as e:
            err_msg = err_msg or _('Failed to write downloaded data with error: {}').format(e)
        if err_msg:
            with suppress(OSError):
                os.remove(self.file_obj.name)
        elif self.not_modified:
            with suppress(OSError):
                os.remove(self.file_obj.name)
        elif self.expected_sha256 and self.hasher.hexdigest() != self.expected_sha256:
            with suppress(OSError):
                os.remove(self.file_obj.name)
            err_msg = _('The downloaded data is corrupted, its checksum does not match')
        else:
            try:
                os.replace(self.file_obj.name, self.path)
            except OSError as e:
                with suppress(OSError):
                    os.remove(self.file_obj.name)
                err_msg = _('Failed to write downloaded data with error: {}').format(e)
        self.pb.setMaximum(100)
        self.pb.setValue(0 if err_msg else 100)
        self.pb.setFormat(_('Download failed') if err_msg else _('Download finished'))
        self.done.emit(err_msg)

    def on_download(self, received: int = 0, total: int = 0) -> None:
        if not self.over_reported and self.total_size:
            position = self.file_obj.tell()
            self.pb.setMaximum(1000)
            self.pb.setValue(min(1000, position * 1000 // self.total_size))
            t = human_readable(self.total_size)
            r = human_readable(position)
            self.pb.setFormat(f'%p% {r} of {t}')

    def response_is_complete(self, code: object, ok: bool) -> bool:
        if code not in (200, 206) or not self.response_checked:
            return False
        if self.total_size is not None:
            return self.total_size == self.file_obj.tell()
        if self.expected_sha256 and self.hasher.hexdigest() == self.expected_sha256:
            # The data is complete even if the server does not end the response
            return True
        return code == 200 and ok

    def restart_after_corruption(self) -> bool:
        # Data assembled from several responses can be corrupted by any of
        # them, so download it again from the beginning once before giving up.
        if not self.expected_sha256 or self.restarted_after_corruption or self.hasher.hexdigest() == self.expected_sha256:
            return False
        self.restarted_after_corruption = True
        self.reset_partial_file()
        self.total_size = None
        self.validator = b''
        self.retries = self.retry_progress = 0
        self.pb.setFormat(_('Retrying download...'))
        self.retry_timer.start(0)
        return True

    def finished(self) -> None:
        if self.over_reported:
            return
        self.data_received()
        if self.over_reported:
            return
        reply = self.reply
        assert reply is not None
        code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        error = reply.error()
        ok = error == QNetworkReply.NetworkError.NoError
        message = _('Failed to download data with error: {}').format(reply.errorString())
        self.release_reply()
        if code == 304 and not self.request_start:
            if os.path.exists(self.path):
                self.not_modified = True
                self.on_over()
            else:
                self.on_over(_('Server reported that the data is unchanged but there is no previously downloaded copy'))
        elif self.response_is_complete(code, ok):
            if not self.restart_after_corruption():
                self.on_over()
        elif code == 206 and ok and self.response_end == self.file_obj.tell():
            # The server returned less of the resource than requested, ask for the rest
            self.retries = 0
            self.retry_progress = self.file_obj.tell()
            self.retry_timer.start(0)
        elif code in (200, 206) and ok:
            # The response ended early without an error, treat it as interrupted
            self.retry(message)
        elif code in (408, 429, 500, 502, 503, 504) or error in {
            QNetworkReply.NetworkError.TimeoutError,
            QNetworkReply.NetworkError.RemoteHostClosedError,
            QNetworkReply.NetworkError.TemporaryNetworkFailureError,
            QNetworkReply.NetworkError.ProxyConnectionClosedError,
            QNetworkReply.NetworkError.ProxyTimeoutError,
            QNetworkReply.NetworkError.UnknownNetworkError,
        }:
            self.retry(message)
        else:
            self.on_over(message)

    def cancel(self) -> None:
        self.over_reported = True
        self.retry_timer.stop()
        self.release_reply()
        with suppress(OSError):
            self.file_obj.close()
        with suppress(OSError):
            os.remove(self.file_obj.name)


class DownloadResources(QDialog):
    def __init__(
        self,
        title: str,
        message: str,
        urls: dict[str, tuple[str, str]],
        parent: QWidget | None = None,
        hashes: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(message)
        la.setWordWrap(True)
        l.addWidget(la)
        self.scroll_area = sa = QScrollArea(self)
        sa.setWidgetResizable(True)
        l.addWidget(sa)
        self.central = central = QWidget(sa)
        central_l = QVBoxLayout(central)
        sa.setWidget(central)

        self.todo = set()
        self.bars = []
        self.failures = []
        self.nam = nam = QNetworkAccessManager(self)
        # An inactivity timeout allows large models to take as long as needed.
        nam.setTransferTimeout(15_000)
        for url, (path, desc) in urls.items():
            qurl = QUrl(url)
            self.todo.add(qurl)
            pb = ProgressBar(qurl, path, nam, desc, self, sha256=(hashes or {}).get(url, ''))
            pb.done.connect(self.on_done, type=Qt.ConnectionType.QueuedConnection)
            central_l.addWidget(pb)
            self.bars.append(pb)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)
        sz = self.sizeHint()
        sz.setWidth(max(500, sz.width()))
        self.resize(sz)

    def on_done(self, err_msg: str) -> None:
        pb = self.sender()
        assert pb is not None
        assert isinstance(pb, ProgressBar)
        self.todo.discard(pb.qurl)
        if err_msg:
            self.failures.append(_('Failed to download {0} with error: {1}').format(pb.desc, err_msg))
        if not self.todo:
            if self.failures:
                if len(self.failures) == len(self.bars):
                    msg = ngettext(_('Could not download {}.'), _('Could not download any of the resources.'), len(self.bars)).format(self.bars[0].desc)
                else:
                    msg = _('Could not download some resources.')
                error_dialog(
                    self,
                    _('Download failed'),
                    msg + ' ' + _('Click "Show details" for more information'),
                    det_msg='\n\n'.join(self.failures),
                    show=True,
                )
                self.reject()
            else:
                self.accept()

    def reject(self) -> None:
        for pb in self.bars:
            pb.blockSignals(True)
            pb.cancel()
        super().reject()


def download_resources(
    title: str,
    message: str,
    urls: dict[str, tuple[str, str]],
    parent: QWidget | None = None,
    headless: bool = False,
    hashes: dict[str, str] | None = None,
) -> bool:
    """
    Download the specified URLs. urls maps each URL to the path it is saved to and a
    description. hashes optionally maps URLs to the expected SHA-256 of their data,
    data that does not match is not saved.
    """
    hashes = hashes or {}
    if not headless:
        d = DownloadResources(title, message, urls, parent=parent, hashes=hashes)
        return d.exec() == QDialog.DialogCode.Accepted
    from calibre import browser

    print(title)
    print(message)
    br = browser()
    for url, (path, name) in urls.items():
        print(_('Downloading {}...').format(name))
        data = br.open_novisit(url).read()
        if (expected := hashes.get(url)) and hashlib.sha256(data).hexdigest() != expected.lower():
            raise ValueError(f'The data downloaded from {url} is corrupted, its checksum does not match')
        part_path = path + '.part'
        try:
            with open(part_path, 'wb') as f:
                f.write(data)
            os.replace(part_path, path)
        except BaseException:
            with suppress(OSError):
                os.remove(part_path)
            raise
    return True


def develop() -> None:
    from calibre.gui2 import Application

    app = Application([])
    urls = {
        'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx': (
            '/tmp/model',
            'Voice neural network',
        ),
        'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json': (
            '/tmp/config',
            'Voice configuration',
        ),
    }
    d = DownloadResources('Test download resources', 'Downloading voice data', urls)
    d.exec()
    del d
    del app


if __name__ == '__main__':
    develop()
