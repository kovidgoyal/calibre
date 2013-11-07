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
    QNetworkReply, QTimer, QNetworkRequest, QUrl, Qt, QNetworkDiskCache)
from PyQt4.QtWebKit import QWebView

from calibre import prints
from calibre.constants import iswindows
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.base import serialize, OEB_DOCS
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.gui2.tweak_book import current_container, editors
from calibre.gui2.viewer.documentview import apply_settings
from calibre.gui2.viewer.config import config
from calibre.utils.ipc.simple_worker import offload_worker

shutdown = object()

def get_data(name):
    'Get the data for name. Returns a unicode string if name is a text document/stylesheet'
    if name in editors:
        return editors[name].get_raw_data()
    return current_container().raw_data(name)

# Parsing of html to add linenumbers {{{
def parse_html(raw):
    root = parse(raw, decoder=lambda x:x.decode('utf-8'), line_numbers=True, linenumber_attribute='lnum')
    return serialize(root, 'text/html').encode('utf-8')

class ParseItem(object):

    __slots__ = ('name', 'length', 'fingerprint', 'parsed_data')

    def __init__(self, name):
        self.name = name
        self.length, self.fingerprint = 0, None
        self.parsed_data = None

class ParseWorker(Thread):

    daemon = True
    SLEEP_TIME = 1

    def __init__(self):
        Thread.__init__(self)
        self.requests = Queue()
        self.request_count = 0
        self.parse_items = {}

    def run(self):
        mod, func = 'calibre.gui2.tweak_book.preview', 'parse_html'
        try:
            # Connect to the worker and send a dummy job to initialize it
            self.worker = offload_worker(priority='low')
            self.worker(mod, func, '<p></p>')
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
            pi, data = request[1:]
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
                    pi.parsed_data = parsed_data

    def add_request(self, name):
        data = get_data(name)
        ldata, hdata = len(data), hash(data)
        pi = self.parse_items.get(name, None)
        if pi is None:
            self.parse_items[name] = pi = ParseItem(name)
        else:
            if pi.length == ldata and pi.fingerprint == hdata:
                return
            pi.parsed_data = None
        pi.length, pi.fingerprint = ldata, hdata
        self.requests.put((self.request_count, pi, data))
        self.request_count += 1

    def shutdown(self):
        self.requests.put(shutdown)

    def get_data(self, name):
        return getattr(self.parse_items.get(name, None), 'parsed_data', None)

    def clear(self):
        self.parse_items.clear()

parse_worker = ParseWorker()
# }}}

# Override network access to load data "live" from the editors {{{
class NetworkReply(QNetworkReply):

    def __init__(self, parent, request, mime_type, name):
        QNetworkReply.__init__(self, parent)
        self.setOpenMode(QNetworkReply.ReadOnly | QNetworkReply.Unbuffered)
        self.setRequest(request)
        self.setUrl(request.url())
        self._aborted = False
        if mime_type in OEB_DOCS:
            self.resource_name = name
            QTimer.singleShot(0, self.check_for_parse)
        else:
            data = get_data(name)
            if isinstance(data, type('')):
                data = data.encode('utf-8')
                mime_type += '; charset=utf-8'
            self.__data = data
            self.setHeader(QNetworkRequest.ContentTypeHeader, mime_type)
            self.setHeader(QNetworkRequest.ContentLengthHeader, len(self.__data))
            QTimer.singleShot(0, self.finalize_reply)

    def check_for_parse(self):
        if self._aborted:
            return
        data = parse_worker.get_data(self.resource_name)
        if data is None:
            return QTimer.singleShot(10, self.check_for_parse)
        self.__data = data
        self.setHeader(QNetworkRequest.ContentTypeHeader, 'text/html; charset=utf-8')
        self.setHeader(QNetworkRequest.ContentLengthHeader, len(self.__data))
        self.finalize_reply()

    def bytesAvailable(self):
        try:
            return len(self.__data)
        except AttributeError:
            return 0

    def isSequential(self):
        return True

    def abort(self):
        self._aborted = True

    def readData(self, maxlen):
        ans, self.__data = self.__data[:maxlen], self.__data[maxlen:]
        return ans
    read = readData

    def finalize_reply(self):
        if self._aborted:
            return
        self.setFinished(True)
        self.setAttribute(QNetworkRequest.HttpStatusCodeAttribute, 200)
        self.setAttribute(QNetworkRequest.HttpReasonPhraseAttribute, "Ok")
        self.metaDataChanged.emit()
        self.downloadProgress.emit(len(self.__data), len(self.__data))
        self.readyRead.emit()
        self.finished.emit()


class NetworkAccessManager(QNetworkAccessManager):

    OPERATION_NAMES = {getattr(QNetworkAccessManager, '%sOperation'%x) :
            x.upper() for x in ('Head', 'Get', 'Put', 'Post', 'Delete',
                'Custom')
    }

    def __init__(self, *args):
        QNetworkAccessManager.__init__(self, *args)
        self.cache = QNetworkDiskCache(self)
        self.setCache(self.cache)
        self.cache.setCacheDirectory(PersistentTemporaryDirectory(prefix='disk_cache_'))
        self.cache.setMaximumCacheSize(0)

    def createRequest(self, operation, request, data):
        url = unicode(request.url().toString())
        if operation == self.GetOperation and url.startswith('file://'):
            path = url[7:]
            if iswindows and path.startswith('/'):
                path = path[1:]
            c = current_container()
            name = c.abspath_to_name(path)
            if c.has_name(name):
                try:
                    return NetworkReply(self, request, c.mime_map.get(name, 'application/octet-stream'), name)
                except Exception:
                    import traceback
                    traceback.print_exc()
        return QNetworkAccessManager.createRequest(self, operation, request, data)

# }}}

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

        self.page().setNetworkAccessManager(NetworkAccessManager(self))
        self.page().setLinkDelegationPolicy(self.page().DelegateAllLinks)

        self.clear()

    def sizeHint(self):
        return self._size_hint

    def refresh(self):
        self.pageAction(self.page().Reload).trigger()

    @dynamic_property
    def scroll_pos(self):
        def fget(self):
            mf = self.page().mainFrame()
            return (mf.scrollBarValue(Qt.Horizontal), mf.scrollBarValue(Qt.Vertical))
        def fset(self, val):
            mf = self.page().mainFrame()
            mf.setScrollBarValue(Qt.Horizontal, val[0])
            mf.setScrollBarValue(Qt.Vertical, val[1])
        return property(fget=fget, fset=fset)

    def clear(self):
        self.setHtml('<p>')

class Preview(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        self.view = WebView(self)
        l.addWidget(self.view)

        self.current_name = None
        self.last_sync_request = None
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        parse_worker.start()

    def show(self, name):
        if name != self.current_name:
            self.refresh_timer.stop()
            self.current_name = name
            parse_worker.add_request(name)
            self.view.setUrl(QUrl.fromLocalFile(current_container().name_to_abspath(name)))

    def refresh(self):
        if self.current_name:
            # This will check if the current html has changed in its editor,
            # and re-parse it if so
            parse_worker.add_request(self.current_name)
            # Tell webkit to reload all html and associated resources
            self.view.refresh()

    def clear(self):
        self.view.clear()

