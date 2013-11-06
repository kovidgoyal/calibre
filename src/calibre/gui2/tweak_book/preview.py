#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Thread
from Queue import Queue, Empty

from PyQt4.Qt import (
    QWidget, QVBoxLayout, QApplication, QSize, QNetworkAccessManager,
    QNetworkReply, QTimer, QNetworkRequest, QUrl)
from PyQt4.QtWebKit import QWebView

from calibre.constants import iswindows
from calibre.gui2.tweak_book import current_container, editors
from calibre.gui2.viewer.documentview import apply_settings
from calibre.gui2.viewer.config import config
from calibre.utils.ipc.simple_worker import offload_worker

shutdown = object()

class ParseWorker(Thread):

    daemon = True

    def __init__(self):
        Thread.__init__(self)
        self.worker = offload_worker(priority='low')
        self.requests = Queue()
        self.request_count = 0
        self.start()

    def run(self):
        try:
            # Connect to the worker and send a dummy job to initialize it
            self.worker(None, None, (), {})
        except:
            import traceback
            traceback.print_exc()
            return

        while True:
            x = self.requests.get()
            requests = [x]
            while True:
                try:
                    requests.append(self.requests.get_nowait())
                except Empty:
                    break
            if shutdown in requests:
                self.worker.shutdown()
                break
            request = sorted(requests, reverse=True)[0]
            del requests
            request

    def shutdown(self):
        self.requests.put(shutdown)


class LocalNetworkReply(QNetworkReply):

    def __init__(self, parent, request, mime_type, data):
        QNetworkReply.__init__(self, parent)
        self.setOpenMode(QNetworkReply.ReadOnly | QNetworkReply.Unbuffered)
        self.__data = data
        self.setRequest(request)
        self.setUrl(request.url())
        self.setHeader(QNetworkRequest.ContentTypeHeader, mime_type)
        self.setHeader(QNetworkRequest.ContentLengthHeader, len(self.__data))
        QTimer.singleShot(0, self.finalize_reply)

    def bytesAvailable(self):
        return len(self.__data)

    def isSequential(self):
        return True

    def abort(self):
        pass

    def readData(self, maxlen):
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

def get_data(name):
    if name in editors:
        return editors[name].data
    return current_container().open(name).read()

class NetworkAccessManager(QNetworkAccessManager):

    OPERATION_NAMES = {getattr(QNetworkAccessManager, '%sOperation'%x) :
            x.upper() for x in ('Head', 'Get', 'Put', 'Post', 'Delete',
                'Custom')
    }

    def createRequest(self, operation, request, data):
        url = unicode(request.url().toString())
        if url.startswith('file://'):
            path = url[7:]
            if iswindows and path.startswith('/'):
                path = path[1:]
            c = current_container()
            name = c.abspath_to_name(path)
            if c.has_name(name):
                try:
                    return LocalNetworkReply(self, request, c.mime_map.get(name, 'application/octet-stream'),
                                             get_data(name) if operation == self.GetOperation else b'')
                except Exception:
                    import traceback
                    traceback.print_stack()
        return QNetworkAccessManager.createRequest(self, operation, request,
                data)

class WebView(QWebView):

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)
        w = QApplication.instance().desktop().availableGeometry(self).width()
        self._size_hint = QSize(int(w/3), int(w/2))
        settings = self.page().settings()
        apply_settings(settings, config().parse())
        settings.setMaximumPagesInCache(0)
        settings.setAttribute(settings.JavaEnabled, False)
        settings.setAttribute(settings.PluginsEnabled, False)
        settings.setAttribute(settings.PrivateBrowsingEnabled, True)
        settings.setAttribute(settings.JavascriptCanOpenWindows, False)
        settings.setAttribute(settings.JavascriptCanAccessClipboard, False)
        settings.setAttribute(settings.LinksIncludedInFocusChain, False)
        settings.setAttribute(settings.DeveloperExtrasEnabled, True)
        settings.setDefaultTextEncoding('utf-8')

        self.setHtml('<p>')
        self.page().setNetworkAccessManager(NetworkAccessManager(self))

    def sizeHint(self):
        return self._size_hint

class Preview(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        self.parse_worker = ParseWorker()
        self.view = WebView(self)
        l.addWidget(self.view)

    def show(self, name):
        data = get_data(name)
        c = current_container()
        self.view.setHtml(data, QUrl.fromLocalFile(c.name_to_abspath(name)))

