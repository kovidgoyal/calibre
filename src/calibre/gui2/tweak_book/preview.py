#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import time
from threading import Thread
from Queue import Queue, Empty

from PyQt4.Qt import (
    QWidget, QVBoxLayout, QApplication, QSize, QNetworkAccessManager,
    QNetworkReply, QTimer, QNetworkRequest, QUrl)
from PyQt4.QtWebKit import QWebView

from calibre import prints
from calibre.constants import iswindows
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.base import serialize
from calibre.gui2 import Dispatcher
from calibre.gui2.tweak_book import current_container, editors
from calibre.gui2.viewer.documentview import apply_settings
from calibre.gui2.viewer.config import config
from calibre.utils.ipc.simple_worker import offload_worker

shutdown = object()

def parse_html(raw):
    root = parse(raw, decoder=lambda x:x.decode('utf-8'), replace_entities=False, line_numbers=True, linenumber_attribute='lnum')
    return serialize(root, 'text/html').decode('utf-8')

class ParseWorker(Thread):

    daemon = True
    SLEEP_TIME = 1

    def __init__(self, callback=lambda x, y: None):
        Thread.__init__(self)
        self.worker = offload_worker(priority='low')
        self.requests = Queue()
        self.request_count = 0
        self.start()
        self.cache = {}
        self.callback = callback

    def run(self):
        mod, func = 'calibre.gui2.tweak_book.preview', 'parse_html'
        try:
            # Connect to the worker and send a dummy job to initialize it
            self.worker(mod, func, b'<p></p>')
        except:
            import traceback
            traceback.print_exc()
            return

        while True:
            time.sleep(self.SLEEP_TIME)
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
            name, data = request[1:]
            old_len, old_fp, old_parsed = self.cache.get(name, (None, None, None))
            length, fp = len(data), hash(data)
            if length == old_len and fp == old_fp:
                self.done(name, old_parsed)
                continue
            try:
                res = self.worker(mod, func, data)
            except:
                import traceback
                traceback.print_exc()
            else:
                parsed_data = res['result']
                if res['tb']:
                    prints("Parser error:")
                    prints(res['tb'])
                else:
                    self.cache[name] = (length, fp, parsed_data)
                    self.done(name, parsed_data)

    def done(self, name, data):
        try:
            self.callback(name, data)
        except Exception:
            import traceback
            traceback.print_exc()

    def add_request(self, name):
        data = get_data(name)
        self.requests.put((self.request_count, name, data))
        self.request_count += 1

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
        self.page().setLinkDelegationPolicy(self.page().DelegateAllLinks)

    def sizeHint(self):
        return self._size_hint

class Preview(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        self.parse_worker = ParseWorker(callback=Dispatcher(self.parsing_done))
        self.view = WebView(self)
        l.addWidget(self.view)

        self.current_name = None
        self.parse_pending = False
        self.last_sync_request = None

    def show(self, name):
        self.current_name, self.parse_pending = name, True
        self.parse_worker.add_request(name)

    def parsing_done(self, name, data):
        if name == self.current_name:
            c = current_container()
            self.view.setHtml(data, QUrl.fromLocalFile(c.name_to_abspath(name)))
            self.parse_pending = False

