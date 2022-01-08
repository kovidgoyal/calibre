#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import json
import time
from collections import defaultdict
from functools import partial
from qt.core import (
    QAction, QApplication, QByteArray, QHBoxLayout, QIcon, QLabel, QMenu, QSize,
    QSizePolicy, QStackedLayout, Qt, QTimer, QToolBar, QUrl, QVBoxLayout, QWidget,
    pyqtSignal
)
from qt.webengine import (
    QWebEngineContextMenuRequest, QWebEnginePage, QWebEngineProfile,
    QWebEngineScript, QWebEngineSettings, QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler, QWebEngineView
)
from threading import Thread

from calibre import prints
from calibre.constants import (
    FAKE_HOST, FAKE_PROTOCOL, __version__, is_running_from_develop, ismacos,
    iswindows
)
from calibre.ebooks.oeb.base import OEB_DOCS, XHTML_MIME, serialize
from calibre.ebooks.oeb.polish.parsing import parse
from calibre.gui2 import (
    NO_URL_FORMATTING, QT_HIDDEN_CLEAR_ACTION, error_dialog, is_dark_theme,
    safe_open_url
)
from calibre.gui2.palette import dark_color, dark_link_color, dark_text_color
from calibre.gui2.tweak_book import TOP, actions, current_container, editors, tprefs
from calibre.gui2.tweak_book.file_list import OpenWithHandler
from calibre.gui2.viewer.web_view import handle_mathjax_request, send_reply
from calibre.gui2.webengine import RestartingWebEngineView
from calibre.gui2.widgets2 import HistoryLineEdit2
from calibre.utils.ipc.simple_worker import offload_worker
from calibre.utils.webengine import (
    Bridge, create_script, from_js, insert_scripts, secure_webengine, to_js
)
from polyglot.builtins import iteritems
from polyglot.queue import Empty, Queue
from polyglot.urllib import urlparse

shutdown = object()


def get_data(name):
    'Get the data for name. Returns a unicode string if name is a text document/stylesheet'
    if name in editors:
        return editors[name].get_raw_data()
    return current_container().raw_data(name)

# Parsing of html to add linenumbers {{{


def parse_html(raw):
    root = parse(raw, decoder=lambda x:x.decode('utf-8'), line_numbers=True, linenumber_attribute='data-lnum')
    ans = serialize(root, 'text/html')
    if not isinstance(ans, bytes):
        ans = ans.encode('utf-8')
    return ans


class ParseItem:

    __slots__ = ('name', 'length', 'fingerprint', 'parsing_done', 'parsed_data')

    def __init__(self, name):
        self.name = name
        self.length, self.fingerprint = 0, None
        self.parsed_data = None
        self.parsing_done = False

    def __repr__(self):
        return 'ParsedItem(name={!r}, length={!r}, fingerprint={!r}, parsing_done={!r}, parsed_data_is_None={!r})'.format(
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


class UrlSchemeHandler(QWebEngineUrlSchemeHandler):

    def __init__(self, parent=None):
        QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.requests = defaultdict(list)

    def requestStarted(self, rq):
        if bytes(rq.requestMethod()) != b'GET':
            rq.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return
        url = rq.requestUrl()
        if url.host() != FAKE_HOST or url.scheme() != FAKE_PROTOCOL:
            rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        name = url.path()[1:]
        try:
            if name.startswith('calibre_internal-mathjax/'):
                handle_mathjax_request(rq, name.partition('-')[-1])
                return
            c = current_container()
            if not c.has_name(name):
                rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            mime_type = c.mime_map.get(name, 'application/octet-stream')
            if mime_type in OEB_DOCS:
                mime_type = XHTML_MIME
                self.requests[name].append((mime_type, rq))
                QTimer.singleShot(0, self.check_for_parse)
            else:
                data = get_data(name)
                if isinstance(data, str):
                    data = data.encode('utf-8')
                mime_type = {
                    # Prevent warning in console about mimetype of fonts
                    'application/vnd.ms-opentype':'application/x-font-ttf',
                    'application/x-font-truetype':'application/x-font-ttf',
                    'application/font-sfnt': 'application/x-font-ttf',
                }.get(mime_type, mime_type)
                send_reply(rq, mime_type, data)
        except Exception:
            import traceback
            traceback.print_exc()
            rq.fail(QWebEngineUrlRequestJob.Error.RequestFailed)

    def check_for_parse(self):
        remove = []
        for name, requests in iteritems(self.requests):
            data = parse_worker.get_data(name)
            if data is not None:
                if not isinstance(data, bytes):
                    data = data.encode('utf-8')
                for mime_type, rq in requests:
                    send_reply(rq, mime_type, data)
                remove.append(name)
        for name in remove:
            del self.requests[name]

        if self.requests:
            return QTimer.singleShot(10, self.check_for_parse)


# }}}


def uniq(vals):
    ''' Remove all duplicates from vals, while preserving order.  '''
    vals = vals or ()
    seen = set()
    seen_add = seen.add
    return tuple(x for x in vals if x not in seen and not seen_add(x))


def get_editor_settings(tprefs):
    dark = is_dark_theme()

    def get_color(name, dark_val):
        ans = tprefs[name]
        if ans == 'auto' and dark:
            ans = dark_val.name()
        if ans in ('auto', 'unset'):
            return None
        return ans

    return {
        'is_dark_theme': dark,
        'bg': get_color('preview_background', dark_color),
        'fg': get_color('preview_foreground', dark_text_color),
        'link': get_color('preview_link_color', dark_link_color),
        'os': 'windows' if iswindows else ('macos' if ismacos else 'linux'),
    }


def create_dark_mode_script():
    return create_script('dark-mode.js', '''
    (function() {
        var settings = JSON.parse(navigator.userAgent.split('|')[1]);

        function apply_body_colors(event) {
            if (document.documentElement) {
                if (settings.bg) document.documentElement.style.backgroundColor = settings.bg;
                if (settings.fg) document.documentElement.style.color = settings.fg;
            }
            if (document.body) {
                if (settings.bg) document.body.style.backgroundColor = settings.bg;
                if (settings.fg) document.body.style.color = settings.fg;
            }
        }

        function apply_css() {
            var css = '';
            if (settings.link) css += 'html > body :link, html > body :link * { color: ' + settings.link + ' !important; }';
            if (settings.is_dark_theme) { css = ':root { color-scheme: dark; }' + css; }
            var style = document.createElement('style');
            style.textContent = css;
            document.documentElement.appendChild(style);
            apply_body_colors();
        }

        apply_body_colors();
        document.addEventListener("DOMContentLoaded", apply_css);
    })();
    ''',
    injection_point=QWebEngineScript.InjectionPoint.DocumentCreation)


def create_profile():
    ans = getattr(create_profile, 'ans', None)
    if ans is None:
        ans = QWebEngineProfile(QApplication.instance())
        ua = 'calibre-editor-preview ' + __version__
        ans.setHttpUserAgent(ua)
        if is_running_from_develop:
            from calibre.utils.rapydscript import compile_editor
            compile_editor()
        js = P('editor.js', data=True, allow_user_override=False)
        cparser = P('csscolorparser.js', data=True, allow_user_override=False)

        insert_scripts(ans,
            create_script('csscolorparser.js', cparser),
            create_script('editor.js', js),
            create_dark_mode_script(),
        )
        url_handler = UrlSchemeHandler(ans)
        ans.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), url_handler)
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LinksIncludedInFocusChain, False)
        create_profile.ans = ans
    return ans


class PreviewBridge(Bridge):

    request_sync = from_js(object, object, object)
    request_split = from_js(object, object)
    live_css_data = from_js(object)

    go_to_sourceline_address = to_js()
    go_to_anchor = to_js()
    set_split_mode = to_js()
    live_css = to_js()


class WebPage(QWebEnginePage):

    def __init__(self, parent):
        QWebEnginePage.__init__(self, create_profile(), parent)
        secure_webengine(self, for_viewer=True)
        self.bridge = PreviewBridge(self)

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        prints(f'{source_id}:{linenumber}: {msg}')

    def acceptNavigationRequest(self, url, req_type, is_main_frame):
        if req_type in (QWebEnginePage.NavigationType.NavigationTypeReload, QWebEnginePage.NavigationType.NavigationTypeBackForward):
            return True
        if url.scheme() in (FAKE_PROTOCOL, 'data'):
            return True
        if url.scheme() in ('http', 'https') and req_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            safe_open_url(url)
        prints('Blocking navigation request to:', url.toString())
        return False

    def go_to_anchor(self, anchor):
        if anchor is TOP:
            anchor = ''
        self.bridge.go_to_anchor.emit(anchor or '')

    def runjs(self, src, callback=None):
        if callback is None:
            self.runJavaScript(src, QWebEngineScript.ScriptWorldId.ApplicationWorld)
        else:
            self.runJavaScript(src, QWebEngineScript.ScriptWorldId.ApplicationWorld, callback)

    def go_to_sourceline_address(self, sourceline_address):
        if self.bridge.ready:
            lnum, tags = sourceline_address
            if lnum is None:
                return
            tags = [x.lower() for x in tags]
            self.bridge.go_to_sourceline_address.emit(lnum, tags, tprefs['preview_sync_context'])

    def split_mode(self, enabled):
        if self.bridge.ready:
            self.bridge.set_split_mode.emit(1 if enabled else 0)


class Inspector(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        self.view_to_debug = parent
        self.view = None
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

    def connect_to_dock(self):
        ac = actions['inspector-dock']
        ac.toggled.connect(self.visibility_changed)
        if ac.isChecked():
            self.visibility_changed(True)

    def visibility_changed(self, visible):
        if visible and self.view is None:
            self.view = QWebEngineView(self.view_to_debug)
            self.view_to_debug.page().setDevToolsPage(self.view.page())
            self.layout.addWidget(self.view)

    def sizeHint(self):
        return QSize(1280, 600)


class WebView(RestartingWebEngineView, OpenWithHandler):

    def __init__(self, parent=None):
        RestartingWebEngineView.__init__(self, parent)
        self.inspector = Inspector(self)
        w = self.screen().availableSize().width()
        self._size_hint = QSize(int(w/3), int(w/2))
        self._page = WebPage(self)
        self.setPage(self._page)
        self.clear()
        self.setAcceptDrops(False)
        self.dead_renderer_error_shown = False
        self.render_process_failed.connect(self.render_process_died)

    def render_process_died(self):
        if self.dead_renderer_error_shown:
            return
        self.dead_renderer_error_shown = True
        error_dialog(self, _('Render process crashed'), _(
            'The Qt WebEngine Render process has crashed so Preview/Live CSS will not work.'
            ' You should try restarting the editor.')
, show=True)

    def sizeHint(self):
        return self._size_hint

    def update_settings(self):
        settings = get_editor_settings(tprefs)
        p = self._page.profile()
        ua = p.httpUserAgent().split('|')[0] + '|' + json.dumps(settings)
        p.setHttpUserAgent(ua)

    def refresh(self):
        self.update_settings()
        self.pageAction(QWebEnginePage.WebAction.ReloadAndBypassCache).trigger()

    def set_url(self, qurl):
        self.update_settings()
        RestartingWebEngineView.setUrl(self, qurl)

    def clear(self):
        self.update_settings()
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
        self.pageAction(QWebEnginePage.WebAction.InspectElement).trigger()

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        data = self.lastContextMenuRequest()
        url = data.linkUrl()
        url = str(url.toString(NO_URL_FORMATTING)).strip()
        text = data.selectedText()
        if text:
            ca = self.pageAction(QWebEnginePage.WebAction.Copy)
            if ca.isEnabled():
                menu.addAction(ca)
        menu.addAction(actions['reload-preview'])
        menu.addAction(QIcon.ic('debug.png'), _('Inspect element'), self.inspect)
        if url.partition(':')[0].lower() in {'http', 'https'}:
            menu.addAction(_('Open link'), partial(safe_open_url, data.linkUrl()))
        if QWebEngineContextMenuRequest.MediaType.MediaTypeImage.value <= data.mediaType().value <= QWebEngineContextMenuRequest.MediaType.MediaTypeFile.value:
            url = data.mediaUrl()
            if url.scheme() == FAKE_PROTOCOL:
                href = url.path().lstrip('/')
                if href:
                    c = current_container()
                    resource_name = c.href_to_name(href)
                    if resource_name and c.exists(resource_name) and resource_name not in c.names_that_must_not_be_changed:
                        self.add_open_with_actions(menu, resource_name)
                        if data.mediaType() == QWebEngineContextMenuRequest.MediaType.MediaTypeImage:
                            mime = c.mime_map[resource_name]
                            if mime.startswith('image/'):
                                menu.addAction(_('Edit %s') % resource_name, partial(self.edit_image, resource_name))
        menu.exec(ev.globalPos())

    def open_with(self, file_name, fmt, entry):
        self.parent().open_file_with.emit(file_name, fmt, entry)

    def edit_image(self, resource_name):
        self.parent().edit_file.emit(resource_name)


class Preview(QWidget):

    sync_requested = pyqtSignal(object, object)
    split_requested = pyqtSignal(object, object, object)
    split_start_requested = pyqtSignal()
    link_clicked = pyqtSignal(object, object)
    refresh_starting = pyqtSignal()
    refreshed = pyqtSignal()
    live_css_data = pyqtSignal(object)
    render_process_restarted = pyqtSignal()
    open_file_with = pyqtSignal(object, object, object)
    edit_file = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedLayout(l)
        self.stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.current_sync_retry_count = 0
        self.view = WebView(self)
        self.view._page.bridge.request_sync.connect(self.request_sync)
        self.view._page.bridge.request_split.connect(self.request_split)
        self.view._page.bridge.live_css_data.connect(self.live_css_data)
        self.view._page.bridge.bridge_ready.connect(self.on_bridge_ready)
        self.view._page.loadFinished.connect(self.load_finished)
        self.view._page.loadStarted.connect(self.load_started)
        self.view.render_process_restarted.connect(self.render_process_restarted)
        self.pending_go_to_anchor = None
        self.inspector = self.view.inspector
        self.stack.addWidget(self.view)
        self.cover = c = QLabel(_('Loading preview, please wait...'))
        c.setWordWrap(True)
        c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        c.setStyleSheet('QLabel { background-color: palette(window); }')
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.cover)
        self.stack.setCurrentIndex(self.stack.indexOf(self.cover))
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
        self.search.setClearButtonEnabled(True)
        ac = self.search.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.clear_clicked)
        self.search.initialize('tweak_book_preview_search')
        self.search.setPlaceholderText(_('Search in preview'))
        self.search.returnPressed.connect(self.find_next)
        self.bar.addSeparator()
        self.bar.addWidget(self.search)
        for d in ('next', 'prev'):
            ac = actions['find-%s-preview' % d]
            ac.triggered.connect(getattr(self, 'find_' + d))
            self.bar.addAction(ac)

    def clear_clicked(self):
        self.view._page.findText('')

    def find(self, direction):
        text = str(self.search.text())
        self.view._page.findText(text, (
            QWebEnginePage.FindFlag.FindBackward if direction == 'prev' else QWebEnginePage.FindFlag(0)))

    def find_next(self):
        self.find('next')

    def find_prev(self):
        self.find('prev')

    def go_to_anchor(self, anchor):
        self.view._page.go_to_anchor(anchor)

    def request_sync(self, tagname, href, lnum):
        if self.current_name:
            c = current_container()
            if tagname == 'a' and href:
                if href and href.startswith('#'):
                    name = self.current_name
                else:
                    name = c.href_to_name(href, self.current_name) if href else None
                if name == self.current_name:
                    return self.go_to_anchor(urlparse(href).fragment)
                if name and c.exists(name) and c.mime_map[name] in OEB_DOCS:
                    return self.link_clicked.emit(name, urlparse(href).fragment or TOP)
            self.sync_requested.emit(self.current_name, lnum)

    def request_split(self, loc, totals):
        actions['split-in-preview'].setChecked(False)
        if not loc or not totals:
            return error_dialog(self, _('Invalid location'),
                                _('Cannot split on the body tag'), show=True)
        if self.current_name:
            self.split_requested.emit(self.current_name, loc, totals)

    @property
    def bridge_ready(self):
        return self.view._page.bridge.ready

    def sync_to_editor(self, name, sourceline_address):
        self.current_sync_request = (name, sourceline_address)
        self.current_sync_retry_count = 0
        QTimer.singleShot(100, self._sync_to_editor)

    def _sync_to_editor(self):
        if not actions['sync-preview-to-editor'].isChecked() or self.current_sync_retry_count >= 3000 or self.current_sync_request is None:
            return
        if self.refresh_timer.isActive() or not self.bridge_ready or self.current_sync_request[0] != self.current_name:
            self.current_sync_retry_count += 1
            return QTimer.singleShot(100, self._sync_to_editor)
        sourceline_address = self.current_sync_request[1]
        self.current_sync_request = None
        self.current_sync_retry_count = 0
        self.view._page.go_to_sourceline_address(sourceline_address)

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
            self.view.set_url(self.name_to_qurl())
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
                self.view.set_url(current_url)
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
        actions['split-in-preview'].setToolTip('<p>' + (_(
            'Abort file split') if checked else _(
                'Split this file at a specified location.<p>After clicking this button, click'
                ' inside the preview panel above at the location you want the file to be split.')))
        if checked:
            self.split_start_requested.emit()
        else:
            self.view._page.split_mode(False)

    def do_start_split(self):
        self.view._page.split_mode(True)

    def stop_split(self):
        actions['split-in-preview'].setChecked(False)

    def load_started(self):
        self.stack.setCurrentIndex(self.stack.indexOf(self.cover))

    def on_bridge_ready(self):
        self.stack.setCurrentIndex(self.stack.indexOf(self.view))

    def load_finished(self, ok):
        self.stack.setCurrentIndex(self.stack.indexOf(self.view))
        if self.pending_go_to_anchor:
            self.view._page.go_to_anchor(self.pending_go_to_anchor)
            self.pending_go_to_anchor = None
        if actions['split-in-preview'].isChecked():
            if ok:
                self.do_start_split()
            else:
                self.stop_split()

    def request_live_css_data(self, editor_name, sourceline, tags):
        if self.view._page.bridge.ready:
            self.view._page.bridge.live_css(editor_name, sourceline, tags)

    def apply_settings(self):
        s = self.view.settings()
        s.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, int(tprefs['preview_base_font_size']))
        s.setFontSize(QWebEngineSettings.FontSize.DefaultFixedFontSize, int(tprefs['preview_mono_font_size']))
        s.setFontSize(QWebEngineSettings.FontSize.MinimumLogicalFontSize, int(tprefs['preview_minimum_font_size']))
        s.setFontSize(QWebEngineSettings.FontSize.MinimumFontSize, int(tprefs['preview_minimum_font_size']))
        sf, ssf, mf = tprefs['engine_preview_serif_family'], tprefs['engine_preview_sans_family'], tprefs['engine_preview_mono_family']
        if sf:
            s.setFontFamily(QWebEngineSettings.FontFamily.SerifFont, sf)
        if ssf:
            s.setFontFamily(QWebEngineSettings.FontFamily.SansSerifFont, ssf)
        if mf:
            s.setFontFamily(QWebEngineSettings.FontFamily.FixedFont, mf)
        stdfnt = tprefs['preview_standard_font_family'] or 'serif'
        stdfnt = {
            'serif': QWebEngineSettings.FontFamily.SerifFont,
            'sans': QWebEngineSettings.FontFamily.SansSerifFont,
            'mono': QWebEngineSettings.FontFamily.FixedFont
        }[stdfnt]
        s.setFontFamily(QWebEngineSettings.FontFamily.StandardFont, s.fontFamily(stdfnt))
