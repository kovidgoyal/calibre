#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
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
    QTimeZone,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import human_readable
from calibre.gui2 import error_dialog
from calibre.utils.localization import ngettext


class ProgressBar(QWidget):

    done = pyqtSignal(str)

    def __init__(self, qurl: QUrl, path: str, nam: QNetworkAccessManager, text: str, parent: QWidget | None):
        super().__init__(parent)
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
        self.file_obj = tempfile.NamedTemporaryFile('wb', dir=os.path.dirname(self.path), delete=False)
        req = QNetworkRequest(qurl)
        fi = QFileInfo(self.path)
        if fi.exists():
            req.setHeader(QNetworkRequest.KnownHeaders.IfModifiedSinceHeader, fi.lastModified(QTimeZone(QTimeZone.Initialization.UTC)))

        self.reply = reply = nam.get(req)
        self.over_reported = False
        reply.downloadProgress.connect(self.on_download)
        reply.errorOccurred.connect(self.on_error)
        reply.finished.connect(self.finished)
        reply.readyRead.connect(self.data_received)

    def data_received(self):
        try:
            self.file_obj.write(self.reply.readAll())
        except Exception as e:
            self.on_over(_('Failed to write downloaded data with error: {}').format(e))

    def on_error(self, ec: QNetworkReply.NetworkError) -> None:
        self.on_over(_('Failed to write downloaded data with error: {}').format(self.reply.errorString()))

    def on_over(self, err_msg: str = '') -> None:
        if self.over_reported:
            return
        self.over_reported = True
        with suppress(Exception):
            self.file_obj.close()
        if err_msg:
            with suppress(OSError):
                os.remove(self.file_obj.name)
        else:
            code = self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if code == 200:
                os.replace(self.file_obj.name, self.path)
            else:
                with suppress(OSError):
                    os.remove(self.file_obj.name)
                if code != 304:  # 304 is Not modified
                    err_msg = _('Server replied with unknown HTTP status code: {}').format(code)
        self.done.emit(err_msg)

    def on_download(self, received: int, total: int) -> None:
        if total > 0:
            self.pb.setMaximum(total)
            self.pb.setValue(received)
            t = human_readable(total)
            r = human_readable(received)
            self.pb.setFormat(f'%p% {r} of {t}')

    def finished(self):
        self.pb.setMaximum(100)
        self.pb.setValue(100)
        self.pb.setFormat(_('Download finished'))
        self.on_over()


class DownloadResources(QDialog):

    def __init__(self, title: str, message: str, urls: dict[str, tuple[str, str]], parent: QWidget | None = None):
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
        central.l = QVBoxLayout(central)
        sa.setWidget(central)

        self.todo = set()
        self.bars = []
        self.failures = []
        self.nam = nam = QNetworkAccessManager(self)
        for url, (path, desc) in urls.items():
            qurl = QUrl(url)
            self.todo.add(qurl)
            pb = ProgressBar(qurl, path, nam, desc, self)
            pb.done.connect(self.on_done, type=Qt.ConnectionType.QueuedConnection)
            central.l.addWidget(pb)
            self.bars.append(pb)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Cancel, self)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)
        sz = self.sizeHint()
        sz.setWidth(max(500, sz.width()))
        self.resize(sz)

    def on_done(self, err_msg: str):
        pb = self.sender()
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
                        self, _('Download failed'), msg + ' ' + _('Click "Show details" for more information'),
                        det_msg='\n\n'.join(self.failures), show=True)
                self.reject()
            else:
                self.accept()

    def reject(self):
        for pb in self.bars:
            pb.blockSignals(True)
            pb.reply.abort()
        super().reject()


def download_resources(
    title: str, message: str, urls: dict[str, tuple[str, str]], parent: QWidget | None = None, headless: bool = False
) -> bool:
    if not headless:
        d = DownloadResources(title, message, urls, parent=parent)
        return d.exec() == QDialog.DialogCode.Accepted
    from calibre import browser
    print(title)
    print(message)
    for url, (path, name) in urls.items():
        print(_('Downloading {}...').format(name))
        br = browser()
        data = br.open_novisit(url).read()
        with open(path, 'wb') as f:
            f.write(data)
    return True


def develop():
    from calibre.gui2 import Application
    app = Application([])
    urls =  {
        'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx': (
            '/tmp/model', 'Voice neural network'),
        'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json': (
            '/tmp/config', 'Voice configuration'),
    }
    d = DownloadResources('Test download resources', 'Downloading voice data', urls)
    d.exec()
    del d
    del app


if __name__ == '__main__':
    develop()
