#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Thread
from Queue import Queue, Empty

from PyQt4.Qt import (QWidget, QVBoxLayout, QApplication, QSize, QNetworkAccessManager)
from PyQt4.QtWebKit import QWebView

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

class NetworkAccessManager(QNetworkAccessManager):

    OPERATION_NAMES = {getattr(QNetworkAccessManager, '%sOperation'%x) :
            x.upper() for x in ('Head', 'Get', 'Put', 'Post', 'Delete',
                'Custom')
    }

    def createRequest(self, operation, request, data):
        url = unicode(request.url().toString())
        print (url)
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
        self.setHtml('<p>')
        self.nam = NetworkAccessManager(self)
        self.page().setNetworkAccessManager(self.nam)

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

