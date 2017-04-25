#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import time, textwrap, json
from bisect import bisect_right
from base64 import b64encode
from future_builtins import map
from threading import Thread
from Queue import Queue, Empty
from functools import partial
from urlparse import urlparse

from PyQt5.Qt import (
    QWidget, QVBoxLayout, QApplication, QSize, QNetworkAccessManager, QMenu, QIcon,
    QNetworkReply, QTimer, QNetworkRequest, QUrl, Qt, QToolBar,
    pyqtSlot, pyqtSignal)
from PyQt5.QtWebKitWidgets import QWebView, QWebInspector, QWebPage

from calibre import prints
from calibre.constants import FAKE_PROTOCOL, FAKE_HOST
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.ebooks.oeb.base import serialize, OEB_DOCS
from calibre.gui2 import error_dialog, open_url, NO_URL_FORMATTING, secure_web_page
from calibre.gui2.tweak_book import current_container, editors, tprefs, actions, TOP
from calibre.gui2.viewer.documentview import apply_settings
from calibre.gui2.viewer.config import config
from calibre.gui2.widgets2 import HistoryLineEdit2
from calibre.utils.ipc.simple_worker import offload_worker

shutdown = object()


def get_data(name):
    'Get the data for name. Returns a unicode string if name is a text document/stylesheet'
    if name in editors:
        return editors[name].get_raw_data()
    return current_container().raw_data(name)

# Parsing of html to add linenumbers {{{


def parse_html(raw):
    root = parse(raw, decoder=lambda x:x.decode('utf-8'), line_numbers=True, linenumber_attribute='data-lnum')
    return serialize(root, 'text/html').encode('utf-8')


class ParseItem(object):

    __slots__ = ('name', 'length', 'fingerprint', 'parsing_done', 'parsed_data')

    def __init__(self, name):
        self.name = name
        self.length, self.fingerprint = 0, None
        self.parsed_data = None
        self.parsing_done = False

    def __repr__(self):
        return 'ParsedItem(name=%r, length=%r, fingerprint=%r, parsing_done=%r, parsed_data_is_None=%r)' % (
            self.name, self.length, self.fingerprint, self.parsing_done, self.parsed_data is None)


class ParseWorker(Thread):

    daemon = True
    SLEEP_TIME = 1

    def __init__(self):
        Thread.__init__(self)
        self.requests = Queue()
        self.request_count = 0
        self.parse_items = {}
        self.launch_error = None

    def run(self):
        mod, func = 'calibre.gui2.tweak_book.preview', 'parse_html'
        try:
            # Connect to the worker and send a dummy job to initialize it
            self.worker = offload_worker(priority='low')
            self.worker(mod, func, '<p></p>')
        except:
            import traceback
            traceback.print_exc()
            self.launch_error = traceback.format_exc()
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
                pi.parsing_done = True
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
            if pi.parsing_done and pi.length == ldata and pi.fingerprint == hdata:
                return
            pi.parsed_data = None
            pi.parsing_done = False
        pi.length, pi.fingerprint = ldata, hdata
        self.requests.put((self.request_count, pi, data))
        self.request_count += 1

    def shutdown(self):
        self.requests.put(shutdown)

    def get_data(self, name):
        return getattr(self.parse_items.get(name, None), 'parsed_data', None)

    def clear(self):
        self.parse_items.clear()

    def is_alive(self):
        return Thread.is_alive(self) or (hasattr(self, 'worker') and self.worker.is_alive())


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
            mime_type = {
                # Prevent warning in console about mimetype of fonts
                'application/vnd.ms-opentype':'application/x-font-ttf',
                'application/x-font-truetype':'application/x-font-ttf',
                'application/font-sfnt': 'application/x-font-ttf',
            }.get(mime_type, mime_type)
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
        self.setHeader(QNetworkRequest.ContentTypeHeader, 'application/xhtml+xml; charset=utf-8')
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

    def createRequest(self, operation, request, data):
        qurl = request.url()
        if operation == self.GetOperation and qurl.host() == FAKE_HOST:
            name = qurl.path()[1:]
            c = current_container()
            if c.has_name(name):
                try:
                    return NetworkReply(self, request, c.mime_map.get(name, 'application/octet-stream'), name)
                except Exception:
                    import traceback
                    traceback.print_exc()
        return QNetworkAccessManager.createRequest(self, operation, request, data)

# }}}


def uniq(vals):
    ''' Remove all duplicates from vals, while preserving order.  '''
    vals = vals or ()
    seen = set()
    seen_add = seen.add
    return tuple(x for x in vals if x not in seen and not seen_add(x))


def find_le(a, x):
    'Find rightmost value in a less than or equal to x'
    try:
        return a[bisect_right(a, x)]
    except IndexError:
        return a[-1]


class WebPage(QWebPage):

    sync_requested = pyqtSignal(object, object, object)
    split_requested = pyqtSignal(object, object)

    def __init__(self, parent):
        QWebPage.__init__(self, parent)
        settings = self.settings()
        apply_settings(settings, config().parse())
        settings.setMaximumPagesInCache(0)
        secure_web_page(settings)
        settings.setAttribute(settings.PrivateBrowsingEnabled, True)
        settings.setAttribute(settings.LinksIncludedInFocusChain, False)
        settings.setAttribute(settings.DeveloperExtrasEnabled, True)
        settings.setDefaultTextEncoding('utf-8')
        data = 'data:text/css;charset=utf-8;base64,'
        css = '[data-in-split-mode="1"] [data-is-block="1"]:hover { cursor: pointer !important; border-top: solid 5px green !important }'
        data += b64encode(css.encode('utf-8'))
        settings.setUserStyleSheetUrl(QUrl(data))

        self.setNetworkAccessManager(NetworkAccessManager(self))
        self.setLinkDelegationPolicy(self.DelegateAllLinks)
        self.mainFrame().javaScriptWindowObjectCleared.connect(self.init_javascript)
        self.init_javascript()

    def javaScriptConsoleMessage(self, msg, lineno, source_id):
        prints('preview js:%s:%s:'%(unicode(source_id), lineno), unicode(msg))

    def init_javascript(self):
        if not hasattr(self, 'js'):
            from calibre.utils.resources import compiled_coffeescript
            self.js = compiled_coffeescript('ebooks.oeb.display.utils', dynamic=False)
            self.js += P('csscolorparser.js', data=True, allow_user_override=False)
            self.js += compiled_coffeescript('ebooks.oeb.polish.preview', dynamic=False)
        self._line_numbers = None
        mf = self.mainFrame()
        mf.addToJavaScriptWindowObject("py_bridge", self)
        mf.evaluateJavaScript(self.js)

    @pyqtSlot(str, str, str)
    def request_sync(self, tag_name, href, sourceline_address):
        try:
            self.sync_requested.emit(unicode(tag_name), unicode(href), json.loads(unicode(sourceline_address)))
        except (TypeError, ValueError, OverflowError, AttributeError):
            pass

    def go_to_anchor(self, anchor, lnum):
        self.mainFrame().evaluateJavaScript('window.calibre_preview_integration.go_to_anchor(%s, %s)' % (
            json.dumps(anchor), json.dumps(str(lnum))))

    @pyqtSlot(str, str)
    def request_split(self, loc, totals):
        actions['split-in-preview'].setChecked(False)
        loc, totals = json.loads(unicode(loc)), json.loads(unicode(totals))
        if not loc or not totals:
            return error_dialog(self.view(), _('Invalid location'),
                                _('Cannot split on the body tag'), show=True)
        self.split_requested.emit(loc, totals)

    @property
    def line_numbers(self):
        if self._line_numbers is None:
            def atoi(x):
                try:
                    ans = int(x)
                except (TypeError, ValueError):
                    ans = None
                return ans
            val = self.mainFrame().evaluateJavaScript('window.calibre_preview_integration.line_numbers()')
            self._line_numbers = sorted(uniq(filter(lambda x:x is not None, map(atoi, val))))
        return self._line_numbers

    def go_to_line(self, lnum):
        try:
            lnum = find_le(self.line_numbers, lnum)
        except IndexError:
            return
        self.mainFrame().evaluateJavaScript(
            'window.calibre_preview_integration.go_to_line(%d)' % lnum)

    def go_to_sourceline_address(self, sourceline_address):
        lnum, tags = sourceline_address
        if lnum is None:
            return
        tags = [x.lower() for x in tags]
        self.mainFrame().evaluateJavaScript(
            'window.calibre_preview_integration.go_to_sourceline_address(%d, %s)' % (lnum, json.dumps(tags)))

    def split_mode(self, enabled):
        self.mainFrame().evaluateJavaScript(
            'window.calibre_preview_integration.split_mode(%s)' % (
                'true' if enabled else 'false'))


class WebView(QWebView):

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)
        self.inspector = QWebInspector(self)
        w = QApplication.instance().desktop().availableGeometry(self).width()
        self._size_hint = QSize(int(w/3), int(w/2))
        self._page = WebPage(self)
        self.setPage(self._page)
        self.inspector.setPage(self._page)
        self.clear()
        self.setAcceptDrops(False)

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
        self.setHtml(_(
            '''
            <h3>Live preview</h3>

            <p>Here you will see a live preview of the HTML file you are currently editing.
            The preview will update automatically as you make changes.

            <p style="font-size:x-small; color: gray">Note that this is a quick preview
            only, it is not intended to simulate an actual e-book reader. Some
            aspects of your e-book will not work, such as page breaks and page margins.
            '''))

    def inspect(self):
        self.inspector.parent().show()
        self.inspector.parent().raise_()
        self.pageAction(self.page().InspectElement).trigger()

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        p = self.page()
        mf = p.mainFrame()
        r = mf.hitTestContent(ev.pos())
        url = unicode(r.linkUrl().toString(NO_URL_FORMATTING)).strip()
        ca = self.pageAction(QWebPage.Copy)
        if ca.isEnabled():
            menu.addAction(ca)
        menu.addAction(actions['reload-preview'])
        menu.addAction(QIcon(I('debug.png')), _('Inspect element'), self.inspect)
        if url.partition(':')[0].lower() in {'http', 'https'}:
            menu.addAction(_('Open link'), partial(open_url, r.linkUrl()))
        menu.exec_(ev.globalPos())


class Preview(QWidget):

    sync_requested = pyqtSignal(object, object)
    split_requested = pyqtSignal(object, object, object)
    split_start_requested = pyqtSignal()
    link_clicked = pyqtSignal(object, object)
    refresh_starting = pyqtSignal()
    refreshed = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        self.view = WebView(self)
        self.view.page().sync_requested.connect(self.request_sync)
        self.view.page().split_requested.connect(self.request_split)
        self.view.page().loadFinished.connect(self.load_finished)
        self.inspector = self.view.inspector
        self.inspector.setPage(self.view.page())
        l.addWidget(self.view)
        self.bar = QToolBar(self)
        l.addWidget(self.bar)

        ac = actions['auto-reload-preview']
        ac.setCheckable(True)
        ac.setChecked(True)
        ac.toggled.connect(self.auto_reload_toggled)
        self.auto_reload_toggled(ac.isChecked())
        self.bar.addAction(ac)

        ac = actions['sync-preview-to-editor']
        ac.setCheckable(True)
        ac.setChecked(True)
        ac.toggled.connect(self.sync_toggled)
        self.sync_toggled(ac.isChecked())
        self.bar.addAction(ac)

        self.bar.addSeparator()

        ac = actions['split-in-preview']
        ac.setCheckable(True)
        ac.setChecked(False)
        ac.toggled.connect(self.split_toggled)
        self.split_toggled(ac.isChecked())
        self.bar.addAction(ac)

        ac = actions['reload-preview']
        ac.triggered.connect(self.refresh)
        self.bar.addAction(ac)

        actions['preview-dock'].toggled.connect(self.visibility_changed)

        self.current_name = None
        self.last_sync_request = None
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        parse_worker.start()
        self.current_sync_request = None

        self.search = HistoryLineEdit2(self)
        self.search.initialize('tweak_book_preview_search')
        self.search.setPlaceholderText(_('Search in preview'))
        self.search.returnPressed.connect(partial(self.find, 'next'))
        self.bar.addSeparator()
        self.bar.addWidget(self.search)
        for d in ('next', 'prev'):
            ac = actions['find-%s-preview' % d]
            ac.triggered.connect(partial(self.find, d))
            self.bar.addAction(ac)

    def find(self, direction):
        text = unicode(self.search.text())
        self.view.findText(text, QWebPage.FindWrapsAroundDocument | (
            QWebPage.FindBackward if direction == 'prev' else QWebPage.FindFlags(0)))

    def request_sync(self, tagname, href, lnum):
        if self.current_name:
            c = current_container()
            if tagname == 'a' and href:
                if href and href.startswith('#'):
                    name = self.current_name
                else:
                    name = c.href_to_name(href, self.current_name) if href else None
                if name == self.current_name:
                    return self.view.page().go_to_anchor(urlparse(href).fragment, lnum)
                if name and c.exists(name) and c.mime_map[name] in OEB_DOCS:
                    return self.link_clicked.emit(name, urlparse(href).fragment or TOP)
            self.sync_requested.emit(self.current_name, lnum)

    def request_split(self, loc, totals):
        if self.current_name:
            self.split_requested.emit(self.current_name, loc, totals)

    def sync_to_editor(self, name, sourceline_address):
        self.current_sync_request = (name, sourceline_address)
        QTimer.singleShot(100, self._sync_to_editor)

    def _sync_to_editor(self):
        if not actions['sync-preview-to-editor'].isChecked():
            return
        try:
            if self.refresh_timer.isActive() or self.current_sync_request[0] != self.current_name:
                return QTimer.singleShot(100, self._sync_to_editor)
        except TypeError:
            return  # Happens if current_sync_request is None
        sourceline_address = self.current_sync_request[1]
        self.current_sync_request = None
        self.view.page().go_to_sourceline_address(sourceline_address)

    def report_worker_launch_error(self):
        if parse_worker.launch_error is not None:
            tb, parse_worker.launch_error = parse_worker.launch_error, None
            error_dialog(self, _('Failed to launch worker'), _(
                'Failed to launch the worker process used for rendering the preview'), det_msg=tb, show=True)

    def name_to_qurl(self, name=None):
        name = name or self.current_name
        qurl = QUrl()
        qurl.setScheme(FAKE_PROTOCOL), qurl.setAuthority(FAKE_HOST), qurl.setPath('/' + name)
        return qurl

    def show(self, name):
        if name != self.current_name:
            self.refresh_timer.stop()
            self.current_name = name
            self.report_worker_launch_error()
            parse_worker.add_request(name)
            self.view.setUrl(self.name_to_qurl())
            return True

    def refresh(self):
        if self.current_name:
            self.refresh_timer.stop()
            # This will check if the current html has changed in its editor,
            # and re-parse it if so
            self.report_worker_launch_error()
            parse_worker.add_request(self.current_name)
            # Tell webkit to reload all html and associated resources
            current_url = self.name_to_qurl()
            self.refresh_starting.emit()
            if current_url != self.view.url():
                # The container was changed
                self.view.setUrl(current_url)
            else:
                self.view.refresh()
            self.refreshed.emit()

    def clear(self):
        self.view.clear()
        self.current_name = None

    @property
    def is_visible(self):
        return actions['preview-dock'].isChecked()

    @property
    def live_css_is_visible(self):
        try:
            return actions['live-css-dock'].isChecked()
        except KeyError:
            return False

    def start_refresh_timer(self):
        if self.live_css_is_visible or (self.is_visible and actions['auto-reload-preview'].isChecked()):
            self.refresh_timer.start(tprefs['preview_refresh_time'] * 1000)

    def stop_refresh_timer(self):
        self.refresh_timer.stop()

    def auto_reload_toggled(self, checked):
        if self.live_css_is_visible and not actions['auto-reload-preview'].isChecked():
            actions['auto-reload-preview'].setChecked(True)
            error_dialog(self, _('Cannot disable'), _(
                'Auto reloading of the preview panel cannot be disabled while the'
                ' Live CSS panel is open.'), show=True)
        actions['auto-reload-preview'].setToolTip(_(
            'Auto reload preview when text changes in editor') if not checked else _(
                'Disable auto reload of preview'))

    def sync_toggled(self, checked):
        actions['sync-preview-to-editor'].setToolTip(_(
            'Disable syncing of preview position to editor position') if checked else _(
                'Enable syncing of preview position to editor position'))

    def visibility_changed(self, is_visible):
        if is_visible:
            self.refresh()

    def split_toggled(self, checked):
        actions['split-in-preview'].setToolTip(textwrap.fill(_(
            'Abort file split') if checked else _(
                'Split this file at a specified location.\n\nAfter clicking this button, click'
                ' inside the preview panel above at the location you want the file to be split.')))
        if checked:
            self.split_start_requested.emit()
        else:
            self.view.page().split_mode(False)

    def do_start_split(self):
        self.view.page().split_mode(True)

    def stop_split(self):
        actions['split-in-preview'].setChecked(False)

    def load_finished(self, ok):
        if actions['split-in-preview'].isChecked():
            if ok:
                self.do_start_split()
            else:
                self.stop_split()

    def apply_settings(self):
        s = self.view.page().settings()
        s.setFontSize(s.DefaultFontSize, tprefs['preview_base_font_size'])
        s.setFontSize(s.DefaultFixedFontSize, tprefs['preview_mono_font_size'])
        s.setFontSize(s.MinimumLogicalFontSize, tprefs['preview_minimum_font_size'])
        s.setFontSize(s.MinimumFontSize, tprefs['preview_minimum_font_size'])
        sf, ssf, mf = tprefs['preview_serif_family'], tprefs['preview_sans_family'], tprefs['preview_mono_family']
        s.setFontFamily(s.StandardFont, {'serif':sf, 'sans':ssf, 'mono':mf, None:sf}[tprefs['preview_standard_font_family']])
        s.setFontFamily(s.SerifFont, sf)
        s.setFontFamily(s.SansSerifFont, ssf)
        s.setFontFamily(s.FixedFont, mf)
