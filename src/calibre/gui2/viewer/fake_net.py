#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os

from PyQt5.Qt import QNetworkReply, QNetworkAccessManager, QUrl, QNetworkRequest, QTimer, pyqtSignal, QByteArray

from calibre import guess_type as _guess_type, prints
from calibre.constants import FAKE_HOST, FAKE_PROTOCOL, DEBUG
from calibre.ebooks.oeb.base import OEB_DOCS
from calibre.ebooks.oeb.display.webview import cleanup_html, load_as_html
from calibre.utils.short_uuid import uuid4


def guess_type(x):
    return _guess_type(x)[0] or 'application/octet-stream'


cc_header = QByteArray(b'Cache-Control'), QByteArray(b'max-age=864001')


class NetworkReply(QNetworkReply):

    def __init__(self, parent, request, mime_type, data):
        QNetworkReply.__init__(self, parent)
        self.setOpenMode(QNetworkReply.ReadOnly | QNetworkReply.Unbuffered)
        self.setRequest(request)
        self.setUrl(request.url())
        self._aborted = False
        self.__data = data
        self.setHeader(QNetworkRequest.ContentTypeHeader, mime_type)
        self.setHeader(QNetworkRequest.ContentLengthHeader, len(self.__data))
        self.setRawHeader(*cc_header)
        QTimer.singleShot(0, self.finalize_reply)

    def bytesAvailable(self):
        return len(self.__data)

    def isSequential(self):
        return True

    def abort(self):
        pass

    def readData(self, maxlen):
        if maxlen >= len(self.__data):
            ans, self.__data = self.__data, b''
            return ans
        ans, self.__data = self.__data[:maxlen], self.__data[maxlen:]
        return ans
    read = readData

    def finalize_reply(self):
        self.setFinished(True)
        self.setAttribute(QNetworkRequest.HttpStatusCodeAttribute, 200)
        self.setAttribute(QNetworkRequest.HttpReasonPhraseAttribute, "Ok")
        self.metaDataChanged.emit()
        self.downloadProgress.emit(len(self.__data), len(self.__data))
        self.readyRead.emit()
        self.finished.emit()


class NotFound(QNetworkReply):

    def __init__(self, parent, request):
        QNetworkReply.__init__(self, parent)
        self.setOpenMode(QNetworkReply.ReadOnly | QNetworkReply.Unbuffered)
        self.setHeader(QNetworkRequest.ContentTypeHeader, 'application/octet-stream')
        self.setHeader(QNetworkRequest.ContentLengthHeader, 0)
        self.setRequest(request)
        self.setUrl(request.url())
        QTimer.singleShot(0, self.finalize_reply)

    def bytesAvailable(self):
        return 0

    def isSequential(self):
        return True

    def abort(self):
        pass

    def readData(self, maxlen):
        return b''

    def finalize_reply(self):
        self.setAttribute(QNetworkRequest.HttpStatusCodeAttribute, 404)
        self.setAttribute(QNetworkRequest.HttpReasonPhraseAttribute, "Not Found")
        self.finished.emit()


def normpath(p):
    return os.path.normcase(os.path.abspath(p))


class NetworkAccessManager(QNetworkAccessManager):

    load_error = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QNetworkAccessManager.__init__(self, parent)
        self.mathjax_prefix = str(uuid4())
        self.mathjax_base = '%s://%s/%s/' % (FAKE_PROTOCOL, FAKE_HOST, self.mathjax_prefix)
        self.root = self.orig_root = os.path.dirname(P('viewer/blank.html', allow_user_override=False))
        self.mime_map, self.single_pages, self.codec_map = {}, set(), {}

    def set_book_data(self, root, spine):
        self.orig_root = root
        self.root = normpath(root)
        self.mime_map, self.single_pages, self.codec_map = {}, set(), {}
        for p in spine:
            mt = getattr(p, 'mime_type', None)
            key = normpath(p)
            if mt is not None:
                self.mime_map[key] = mt
            self.codec_map[key] = getattr(p, 'encoding', 'utf-8')
            if getattr(p, 'is_single_page', False):
                self.single_pages.add(key)

    def is_single_page(self, path):
        if not path:
            return False
        key = normpath(path)
        return key in self.single_pages

    def as_abspath(self, qurl):
        name = qurl.path()[1:]
        return os.path.join(self.orig_root, *name.split('/'))

    def as_url(self, abspath):
        name = os.path.relpath(abspath, self.root).replace('\\', '/')
        ans = QUrl()
        ans.setScheme(FAKE_PROTOCOL), ans.setAuthority(FAKE_HOST), ans.setPath('/' + name)
        return ans

    def guess_type(self, name):
        mime_type = guess_type(name)
        mime_type = {
            # Prevent warning in console about mimetype of fonts
            'application/vnd.ms-opentype':'application/x-font-ttf',
            'application/x-font-truetype':'application/x-font-ttf',
            'application/x-font-opentype':'application/x-font-ttf',
            'application/x-font-otf':'application/x-font-ttf',
            'application/font-sfnt': 'application/x-font-ttf',
        }.get(mime_type, mime_type)
        return mime_type

    def preprocess_data(self, data, path):
        mt = self.mime_map.get(path, self.guess_type(path))
        if mt.lower() in OEB_DOCS:
            enc = self.codec_map.get(path, 'utf-8')
            html = data.decode(enc, 'replace')
            html = cleanup_html(html)
            data = html.encode('utf-8')
            if load_as_html(html):
                mt = 'text/html; charset=utf-8'
            else:
                mt = 'application/xhtml+xml; charset=utf-8'
        return data, mt

    def createRequest(self, operation, request, data):
        qurl = request.url()
        if operation == QNetworkAccessManager.GetOperation and qurl.host() == FAKE_HOST:
            name = qurl.path()[1:]
            if name.startswith(self.mathjax_prefix):
                base = normpath(P('viewer/mathjax'))
                path = normpath(os.path.join(base, name.partition('/')[2]))
            else:
                base = self.root
                path = normpath(os.path.join(self.root, name))
            if path.startswith(base) and os.path.exists(path):
                try:
                    with lopen(path, 'rb') as f:
                        data = f.read()
                    data, mime_type = self.preprocess_data(data, path)
                    return NetworkReply(self, request, mime_type, data)
                except Exception:
                    import traceback
                    self.load_error.emit(name, traceback.format_exc())
            if DEBUG:
                prints('URL not found in book: %r' % qurl.toString())
            return NotFound(self, request)
        return QNetworkAccessManager.createRequest(self, operation, request)
