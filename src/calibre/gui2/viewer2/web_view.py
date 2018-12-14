#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from PyQt5.Qt import (
    QApplication, QBuffer, QByteArray, QHBoxLayout, QSize, QTimer, QUrl, QWidget
)
from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineWidgets import (
    QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineView
)

from calibre import as_unicode, prints
from calibre.constants import (
    FAKE_HOST, FAKE_PROTOCOL, __version__, is_running_from_develop
)
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.gui2 import error_dialog, open_url
from calibre.gui2.webengine import (
    Bridge, RestartingWebEngineView, create_script, from_js, insert_scripts,
    secure_webengine, to_js
)
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.config import JSONConfig

try:
    from PyQt5 import sip
except ImportError:
    import sip

vprefs = JSONConfig('viewer-webengine')
vprefs.defaults['session_data'] = {}


# Override network access to load data from the book {{{


def set_book_path(path=None):
    set_book_path.path = os.path.abspath(path)


def get_data(name):
    bdir = getattr(set_book_path, 'path', None)
    if bdir is None:
        return None, None
    path = os.path.abspath(os.path.join(bdir, name))
    if not path.startswith(bdir):
        return None, None
    try:
        with lopen(path, 'rb') as f:
            return f.read(), guess_type(name)
    except EnvironmentError as err:
        prints('Failed to read from book file: {} with error: {}'.format(name, as_unicode(err)))
    return None, None


class UrlSchemeHandler(QWebEngineUrlSchemeHandler):

    def __init__(self, parent=None):
        QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.mathjax_tdir = self.mathjax_manifest = None

    def requestStarted(self, rq):
        if bytes(rq.requestMethod()) != b'GET':
            rq.fail(rq.RequestDenied)
            return
        url = rq.requestUrl()
        if url.host() != FAKE_HOST or url.scheme() != FAKE_PROTOCOL:
            rq.fail(rq.UrlNotFound)
            return
        name = url.path()[1:]
        if name.startswith('book/'):
            name = name.partition('/')[2]
            try:
                data, mime_type = get_data(name)
                if data is None:
                    rq.fail(rq.UrlNotFound)
                    return
                if isinstance(data, type('')):
                    data = data.encode('utf-8')
                mime_type = {
                    # Prevent warning in console about mimetype of fonts
                    'application/vnd.ms-opentype':'application/x-font-ttf',
                    'application/x-font-truetype':'application/x-font-ttf',
                    'application/font-sfnt': 'application/x-font-ttf',
                }.get(mime_type, mime_type)
                self.send_reply(rq, mime_type, data)
            except Exception:
                import traceback
                traceback.print_exc()
                rq.fail(rq.RequestFailed)
        elif name == 'manifest':
            manifest, mime_type = get_data('calibre-book-manifest.json')
            metadata = get_data('calibre-book-metadata.json')[0]
            data = b'[' + manifest + b',' + metadata + b']'
            self.send_reply(rq, mime_type, data)
        elif name.startswith('mathjax/'):
            from calibre.gui2.viewer2.mathjax import monkeypatch_mathjax
            if name == 'mathjax/manifest.json':
                if self.mathjax_tdir is None:
                    import json
                    from calibre.srv.books import get_mathjax_manifest
                    self.mathjax_tdir = PersistentTemporaryDirectory(prefix='v2mjx-')
                    self.mathjax_manifest = json.dumps(get_mathjax_manifest(self.mathjax_tdir)['files'])
                    self.send_reply(rq, 'application/json', self.mathjax_manifest)
                    return
            path = os.path.abspath(os.path.join(self.mathjax_tdir, name))
            if path.startswith(self.mathjax_tdir):
                mt = guess_type(name)
                try:
                    with lopen(path, 'rb') as f:
                        raw = f.read()
                except EnvironmentError as err:
                    prints("Failed to get mathjax file: {} with error: {}".format(name, err))
                    rq.fail(rq.RequestFailed)
                    return
                if 'MathJax.js' in name:
                    # raw = open(os.path.expanduser('~/work/mathjax/unpacked/MathJax.js')).read()
                    raw = monkeypatch_mathjax(raw.decode('utf-8')).encode('utf-8')

                self.send_reply(rq, mt, raw)

    def send_reply(self, rq, mime_type, data):
        if sip.isdeleted(rq):
            return
        buf = QBuffer(parent=rq)
        buf.open(QBuffer.WriteOnly)
        # we have to copy data into buf as it will be garbage
        # collected by python
        buf.write(data)
        buf.seek(0)
        buf.close()
        buf.aboutToClose.connect(buf.deleteLater)
        rq.reply(mime_type.encode('ascii'), buf)

# }}}


def create_profile():
    ans = getattr(create_profile, 'ans', None)
    if ans is None:
        ans = QWebEngineProfile(QApplication.instance())
        ua = 'calibre-viewer ' + __version__
        ans.setHttpUserAgent(ua)
        if is_running_from_develop:
            from calibre.utils.rapydscript import compile_viewer
            compile_viewer()
        js = P('viewer.js', data=True, allow_user_override=False)
        insert_scripts(ans, create_script('viewer.js', js))
        url_handler = UrlSchemeHandler(ans)
        ans.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), url_handler)
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        s.setAttribute(s.LinksIncludedInFocusChain, False)
        create_profile.ans = ans
    return ans


class ViewerBridge(Bridge):

    set_session_data = from_js(object, object)

    start_book_load = to_js()


class WebPage(QWebEnginePage):

    def __init__(self, parent):
        profile = create_profile()
        QWebEnginePage.__init__(self, profile, parent)
        profile.setParent(self)
        secure_webengine(self, for_viewer=True)
        self.bridge = ViewerBridge(self)

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        if level >= QWebEnginePage.ErrorMessageLevel and source_id == 'userscript:viewer.js':
            error_dialog(self.parent(), _('Unhandled error'), _(
                'There was an unhandled error: {} at line: {} of {}').format(
                    msg, linenumber, source_id.partition(':')[2]), show=True)
        prefix = {QWebEnginePage.InfoMessageLevel: 'INFO', QWebEnginePage.WarningMessageLevel: 'WARNING'}.get(
                level, 'ERROR')
        prints('%s: %s:%s: %s' % (prefix, source_id, linenumber, msg))

    def acceptNavigationRequest(self, url, req_type, is_main_frame):
        if req_type == self.NavigationTypeReload:
            return True
        if url.scheme() in (FAKE_PROTOCOL, 'data'):
            return True
        open_url(url)
        return False

    def go_to_anchor(self, anchor):
        self.bridge.go_to_anchor.emit(anchor or '')

    def runjs(self, src, callback=None):
        if callback is None:
            self.runJavaScript(src, QWebEngineScript.ApplicationWorld)
        else:
            self.runJavaScript(src, QWebEngineScript.ApplicationWorld, callback)


def viewer_html():
    ans = getattr(viewer_html, 'ans', None)
    if ans is None:
        ans = viewer_html.ans = P('viewer.html', data=True, allow_user_override=False).decode('utf-8')
    return ans


class Inspector(QWidget):

    def __init__(self, dock_action, parent=None):
        QWidget.__init__(self, parent=parent)
        self.view_to_debug = parent
        self.view = None
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.dock_action = dock_action
        QTimer.singleShot(0, self.connect_to_dock)

    def connect_to_dock(self):
        ac = self.dock_action
        ac.toggled.connect(self.visibility_changed)
        if ac.isChecked():
            self.visibility_changed(True)

    def visibility_changed(self, visible):
        if visible and self.view is None:
            self.view = QWebEngineView(self.view_to_debug)
            self.view_to_debug.page().setDevToolsPage(self.view.page())
            self.layout.addWidget(self.view)


class WebView(RestartingWebEngineView):

    def __init__(self, parent=None):
        self._host_widget = None
        RestartingWebEngineView.__init__(self, parent)
        self.dead_renderer_error_shown = False
        self.render_process_failed.connect(self.render_process_died)
        w = QApplication.instance().desktop().availableGeometry(self).width()
        self._size_hint = QSize(int(w/3), int(w/2))
        self._page = WebPage(self)
        self.bridge.bridge_ready.connect(self.on_bridge_ready)
        self.bridge.set_session_data.connect(self.set_session_data)
        self.pending_bridge_ready_actions = {}
        self.setPage(self._page)
        self.setAcceptDrops(False)
        self.clear()
        if parent is not None:
            self.inspector = Inspector(parent.inspector_dock.toggleViewAction(), self)
            parent.inspector_dock.setWidget(self.inspector)
            # QTimer.singleShot(300, lambda: (parent.inspector_dock.setVisible(True), parent.inspector_dock.setMinimumWidth(650)))

    @property
    def host_widget(self):
        ans = self._host_widget
        if ans is not None and not sip.isdeleted(ans):
            return ans

    def render_process_died(self):
        if self.dead_renderer_error_shown:
            return
        self.dead_renderer_error_shown = True
        error_dialog(self, _('Render process crashed'), _(
            'The Qt WebEngine Render process has crashed.'
            ' You should try restarting the viewer.') , show=True)

    def event(self, event):
        if event.type() == event.ChildPolished:
            child = event.child()
            if 'HostView' in child.metaObject().className():
                self._host_widget = child
        return QWebEngineView.event(self, event)

    def sizeHint(self):
        return self._size_hint

    def refresh(self):
        self.pageAction(QWebEnginePage.Reload).trigger()

    def clear(self):
        self.setHtml(viewer_html(), QUrl('{}://{}/'.format(FAKE_PROTOCOL, FAKE_HOST)))

    @property
    def bridge(self):
        return self._page.bridge

    def on_bridge_ready(self):
        for func, args in self.pending_bridge_ready_actions.iteritems():
            getattr(self.bridge, func)(*args)

    def start_book_load(self):
        key = (set_book_path.path,)
        if self.bridge.ready:
            self.bridge.start_book_load(key, vprefs['session_data'])
        else:
            self.pending_bridge_ready_actions['start_book_load'] = key, vprefs['session_data']

    def set_session_data(self, key, val):
        if key == '*' and val is None:
            vprefs['session_data'] = {}
        else:
            sd = vprefs['session_data']
            sd[key] = val
            vprefs['session_data'] = sd
