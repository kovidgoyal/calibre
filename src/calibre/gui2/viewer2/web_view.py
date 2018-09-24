#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from PyQt5.Qt import QApplication, QBuffer, QByteArray, QSize, QUrl
from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineWidgets import (
    QWebEnginePage, QWebEngineProfile, QWebEngineScript
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
        QWebEnginePage.__init__(self, create_profile(), parent)
        secure_webengine(self, for_viewer=True)
        self.bridge = ViewerBridge(self)

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        prints('%s:%s: %s' % (source_id, linenumber, msg))

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


class WebView(RestartingWebEngineView):

    def __init__(self, parent=None):
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

    def render_process_died(self):
        if self.dead_renderer_error_shown:
            return
        self.dead_renderer_error_shown = True
        error_dialog(self, _('Render process crashed'), _(
            'The Qt WebEngine Render process has crashed.'
            ' You should try restarting the viewer.') , show=True)

    def sizeHint(self):
        return self._size_hint

    def refresh(self):
        self.pageAction(QWebEnginePage.Reload).trigger()

    def clear(self):
        self.setHtml('<p>&nbsp;', QUrl('{}://{}/'.format(FAKE_PROTOCOL, FAKE_HOST)))

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
