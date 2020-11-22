#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


import os
import shutil
import sys
from itertools import count
from PyQt5.Qt import (
    QT_VERSION, QApplication, QBuffer, QByteArray, QFontDatabase, QFontInfo,
    QHBoxLayout, QMimeData, QSize, Qt, QTimer, QUrl, QWidget, pyqtSignal
)
from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineWidgets import (
    QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineView
)

from calibre import as_unicode, prints
from calibre.constants import (
    FAKE_HOST, FAKE_PROTOCOL, __version__, in_develop_mode, is_running_from_develop,
    ismacos, iswindows
)
from calibre.ebooks.metadata.book.base import field_metadata
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.gui2 import choose_images, error_dialog, safe_open_url
from calibre.gui2.viewer.config import viewer_config_dir, vprefs
from calibre.gui2.webengine import (
    Bridge, RestartingWebEngineView, create_script, from_js, insert_scripts,
    secure_webengine, to_js
)
from calibre.srv.code import get_translations_data
from calibre.utils.serialize import json_loads
from calibre.utils.shared_file import share_open
from polyglot.builtins import as_bytes, iteritems, unicode_type
from polyglot.functools import lru_cache

try:
    from PyQt5 import sip
except ImportError:
    import sip

SANDBOX_HOST = FAKE_HOST.rpartition('.')[0] + '.sandbox'

# Override network access to load data from the book {{{


def set_book_path(path, pathtoebook):
    set_book_path.pathtoebook = pathtoebook
    set_book_path.path = os.path.abspath(path)
    set_book_path.metadata = get_data('calibre-book-metadata.json')[0]
    set_book_path.manifest, set_book_path.manifest_mime = get_data('calibre-book-manifest.json')
    set_book_path.parsed_metadata = json_loads(set_book_path.metadata)
    set_book_path.parsed_manifest = json_loads(set_book_path.manifest)


def get_manifest():
    return getattr(set_book_path, 'parsed_manifest', None)


def get_path_for_name(name):
    bdir = getattr(set_book_path, 'path', None)
    if bdir is None:
        return
    path = os.path.abspath(os.path.join(bdir, name))
    if path.startswith(bdir):
        return path


def get_data(name):
    path = get_path_for_name(name)
    if path is None:
        return None, None
    try:
        with share_open(path, 'rb') as f:
            return f.read(), guess_type(name)
    except EnvironmentError as err:
        prints('Failed to read from book file: {} with error: {}'.format(name, as_unicode(err)))
    return None, None


def background_image():
    ans = getattr(background_image, 'ans', None)
    if ans is None:
        img_path = os.path.join(viewer_config_dir, 'bg-image.data')
        if os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                data = f.read()
                mt, data = data.split(b'|', 1)
        else:
            ans = b'image/jpeg', b''
        ans = background_image.ans = mt.decode('utf-8'), data
    return ans


def send_reply(rq, mime_type, data):
    if sip.isdeleted(rq):
        return
    # make the buf a child of rq so that it is automatically deleted when
    # rq is deleted
    buf = QBuffer(parent=rq)
    buf.open(QBuffer.WriteOnly)
    # we have to copy data into buf as it will be garbage
    # collected by python
    buf.write(data)
    buf.seek(0)
    buf.close()
    rq.reply(mime_type.encode('ascii'), buf)


@lru_cache(maxsize=2)
def get_mathjax_dir():
    return P('mathjax', allow_user_override=False)


def handle_mathjax_request(rq, name):
    mathjax_dir = get_mathjax_dir()
    path = os.path.abspath(os.path.join(mathjax_dir, '..', name))
    if path.startswith(mathjax_dir):
        mt = guess_type(name)
        try:
            with lopen(path, 'rb') as f:
                raw = f.read()
        except EnvironmentError as err:
            prints("Failed to get mathjax file: {} with error: {}".format(name, err), file=sys.stderr)
            rq.fail(rq.RequestFailed)
            return
        if name.endswith('/startup.js'):
            raw = P('pdf-mathjax-loader.js', data=True, allow_user_override=False) + raw
        send_reply(rq, mt, raw)
    else:
        prints("Failed to get mathjax file: {} outside mathjax directory".format(name), file=sys.stderr)
        rq.fail(rq.RequestFailed)


class UrlSchemeHandler(QWebEngineUrlSchemeHandler):

    def __init__(self, parent=None):
        QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.allowed_hosts = (FAKE_HOST, SANDBOX_HOST)

    def requestStarted(self, rq):
        if bytes(rq.requestMethod()) != b'GET':
            return self.fail_request(rq, rq.RequestDenied)
        url = rq.requestUrl()
        host = url.host()
        if host not in self.allowed_hosts or url.scheme() != FAKE_PROTOCOL:
            return self.fail_request(rq)
        name = url.path()[1:]
        if host == SANDBOX_HOST and name.partition('/')[0] not in ('book', 'mathjax'):
            return self.fail_request(rq)
        if name.startswith('book/'):
            name = name.partition('/')[2]
            if name == '__index__':
                send_reply(rq, 'text/html', b'<div>\xa0</div>')
                return
            elif name == '__popup__':
                send_reply(rq, 'text/html', b'<div id="calibre-viewer-footnote-iframe">\xa0</div>')
                return
            try:
                data, mime_type = get_data(name)
                if data is None:
                    rq.fail(rq.UrlNotFound)
                    return
                data = as_bytes(data)
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
                return self.fail_request(rq, rq.RequestFailed)
        elif name == 'manifest':
            data = b'[' + set_book_path.manifest + b',' + set_book_path.metadata + b']'
            send_reply(rq, set_book_path.manifest_mime, data)
        elif name == 'reader-background':
            mt, data = background_image()
            if data:
                send_reply(rq, mt, data)
            else:
                rq.fail(rq.UrlNotFound)
        elif name.startswith('mathjax/'):
            handle_mathjax_request(rq, name)
        elif not name:
            send_reply(rq, 'text/html', viewer_html())
        else:
            return self.fail_request(rq)

    def fail_request(self, rq, fail_code=None):
        if fail_code is None:
            fail_code = rq.UrlNotFound
        rq.fail(fail_code)
        prints("Blocking FAKE_PROTOCOL request: {}".format(rq.requestUrl().toString()))

# }}}


def create_profile():
    ans = getattr(create_profile, 'ans', None)
    if ans is None:
        ans = QWebEngineProfile(QApplication.instance())
        osname = 'windows' if iswindows else ('macos' if ismacos else 'linux')
        # DO NOT change the user agent as it is used to workaround
        # Qt bugs see workaround_qt_bug() in ajax.pyj
        ua = 'calibre-viewer {} {}'.format(__version__, osname)
        ans.setHttpUserAgent(ua)
        if is_running_from_develop:
            from calibre.utils.rapydscript import compile_viewer
            prints('Compiling viewer code...')
            compile_viewer()
        js = P('viewer.js', data=True, allow_user_override=False)
        translations_json = get_translations_data() or b'null'
        js = js.replace(b'__TRANSLATIONS_DATA__', translations_json, 1)
        if in_develop_mode:
            js = js.replace(b'__IN_DEVELOP_MODE__', b'1')
        insert_scripts(ans, create_script('viewer.js', js))
        url_handler = UrlSchemeHandler(ans)
        ans.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), url_handler)
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        s.setAttribute(s.LinksIncludedInFocusChain, False)
        create_profile.ans = ans
    return ans


class ViewerBridge(Bridge):

    view_created = from_js(object)
    content_file_changed = from_js(object)
    set_session_data = from_js(object, object)
    set_local_storage = from_js(object, object)
    reload_book = from_js()
    toggle_toc = from_js()
    toggle_bookmarks = from_js()
    toggle_highlights = from_js()
    new_bookmark = from_js(object)
    toggle_inspector = from_js()
    toggle_lookup = from_js(object)
    show_search = from_js(object, object)
    search_result_not_found = from_js(object)
    find_next = from_js(object)
    quit = from_js()
    update_current_toc_nodes = from_js(object, object)
    toggle_full_screen = from_js()
    report_cfi = from_js(object, object)
    ask_for_open = from_js(object)
    selection_changed = from_js(object, object)
    autoscroll_state_changed = from_js(object)
    copy_selection = from_js(object, object)
    view_image = from_js(object)
    copy_image = from_js(object)
    change_background_image = from_js(object)
    overlay_visibility_changed = from_js(object)
    reference_mode_changed = from_js(object)
    show_loading_message = from_js(object)
    show_error = from_js(object, object, object)
    export_shortcut_map = from_js(object)
    print_book = from_js()
    clear_history = from_js()
    reset_interface = from_js()
    quit = from_js()
    customize_toolbar = from_js()
    scrollbar_context_menu = from_js(object, object, object)
    close_prep_finished = from_js(object)
    highlights_changed = from_js(object)
    open_url = from_js(object)
    speak_simple_text = from_js(object)

    create_view = to_js()
    start_book_load = to_js()
    goto_toc_node = to_js()
    goto_cfi = to_js()
    full_screen_state_changed = to_js()
    get_current_cfi = to_js()
    show_home_page = to_js()
    background_image_changed = to_js()
    goto_frac = to_js()
    trigger_shortcut = to_js()
    set_system_palette = to_js()
    highlight_action = to_js()
    generic_action = to_js()
    show_search_result = to_js()
    prepare_for_close = to_js()
    viewer_font_size_changed = to_js()


def apply_font_settings(page_or_view):
    s = page_or_view.settings()
    sd = vprefs['session_data']
    fs = sd.get('standalone_font_settings', {})
    if fs.get('serif_family'):
        s.setFontFamily(s.SerifFont, fs.get('serif_family'))
    else:
        s.resetFontFamily(s.SerifFont)
    if fs.get('sans_family'):
        s.setFontFamily(s.SansSerifFont, fs.get('sans_family'))
    else:
        s.resetFontFamily(s.SansSerifFont)
    if fs.get('mono_family'):
        s.setFontFamily(s.FixedFont, fs.get('mono_family'))
    else:
        s.resetFontFamily(s.SansSerifFont)
    sf = fs.get('standard_font') or 'serif'
    sf = getattr(s, {'serif': 'SerifFont', 'sans': 'SansSerifFont', 'mono': 'FixedFont'}[sf])
    s.setFontFamily(s.StandardFont, s.fontFamily(sf))
    old_minimum = s.fontSize(s.MinimumFontSize)
    old_base = s.fontSize(s.DefaultFontSize)
    old_fixed_base = s.fontSize(s.DefaultFixedFontSize)
    mfs = fs.get('minimum_font_size')
    if mfs is None:
        s.resetFontSize(s.MinimumFontSize)
    else:
        s.setFontSize(s.MinimumFontSize, mfs)
    bfs = sd.get('base_font_size')
    if bfs is not None:
        s.setFontSize(s.DefaultFontSize, bfs)
        s.setFontSize(s.DefaultFixedFontSize, int(bfs * 13 / 16))

    font_size_changed = (old_minimum, old_base, old_fixed_base) != (
            s.fontSize(s.MinimumFontSize), s.fontSize(s.DefaultFontSize), s.fontSize(s.DefaultFixedFontSize))
    if font_size_changed and hasattr(page_or_view, 'execute_when_ready'):
        page_or_view.execute_when_ready('viewer_font_size_changed')

    return s


class WebPage(QWebEnginePage):

    def __init__(self, parent):
        profile = create_profile()
        QWebEnginePage.__init__(self, profile, parent)
        profile.setParent(self)
        secure_webengine(self, for_viewer=True)
        apply_font_settings(self)
        self.bridge = ViewerBridge(self)
        self.bridge.copy_selection.connect(self.trigger_copy)

    def trigger_copy(self, text, html):
        if text:
            md = QMimeData()
            md.setText(text)
            if html:
                md.setHtml(html)
            QApplication.instance().clipboard().setMimeData(md)

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        prefix = {QWebEnginePage.InfoMessageLevel: 'INFO', QWebEnginePage.WarningMessageLevel: 'WARNING'}.get(
                level, 'ERROR')
        prints('%s: %s:%s: %s' % (prefix, source_id, linenumber, msg), file=sys.stderr)
        try:
            sys.stderr.flush()
        except EnvironmentError:
            pass

    def acceptNavigationRequest(self, url, req_type, is_main_frame):
        if req_type == self.NavigationTypeReload:
            return True
        if req_type == self.NavigationTypeBackForward:
            return True
        if url.scheme() in (FAKE_PROTOCOL, 'data'):
            return True
        if url.scheme() in ('http', 'https'):
            safe_open_url(url)
        prints('Blocking navigation request to:', url.toString())
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
        ans = viewer_html.ans = P('viewer.html', data=True, allow_user_override=False)
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

    def sizeHint(self):
        return QSize(600, 1200)


def system_colors():
    app = QApplication.instance()
    is_dark_theme = app.is_dark_theme
    pal = app.palette()
    ans = {
        'background': pal.color(pal.Base).name(),
        'foreground': pal.color(pal.Text).name(),
    }
    if is_dark_theme:
        # only override link colors for dark themes
        # since if the book specifies its own link colors
        # they will likely work well with light themes
        ans['link'] = pal.color(pal.Link).name()
    return ans


class WebView(RestartingWebEngineView):

    cfi_changed = pyqtSignal(object)
    reload_book = pyqtSignal()
    toggle_toc = pyqtSignal()
    show_search = pyqtSignal(object, object)
    search_result_not_found = pyqtSignal(object)
    find_next = pyqtSignal(object)
    toggle_bookmarks = pyqtSignal()
    toggle_highlights = pyqtSignal()
    new_bookmark = pyqtSignal(object)
    toggle_inspector = pyqtSignal()
    toggle_lookup = pyqtSignal(object)
    quit = pyqtSignal()
    update_current_toc_nodes = pyqtSignal(object, object)
    toggle_full_screen = pyqtSignal()
    ask_for_open = pyqtSignal(object)
    selection_changed = pyqtSignal(object, object)
    autoscroll_state_changed = pyqtSignal(object)
    view_image = pyqtSignal(object)
    copy_image = pyqtSignal(object)
    overlay_visibility_changed = pyqtSignal(object)
    reference_mode_changed = pyqtSignal(object)
    show_loading_message = pyqtSignal(object)
    show_error = pyqtSignal(object, object, object)
    print_book = pyqtSignal()
    reset_interface = pyqtSignal()
    quit = pyqtSignal()
    customize_toolbar = pyqtSignal()
    scrollbar_context_menu = pyqtSignal(object, object, object)
    close_prep_finished = pyqtSignal(object)
    highlights_changed = pyqtSignal(object)
    shortcuts_changed = pyqtSignal(object)
    paged_mode_changed = pyqtSignal()
    standalone_misc_settings_changed = pyqtSignal(object)
    view_created = pyqtSignal(object)
    dispatch_on_main_thread_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        self._host_widget = None
        self._tts_client = None
        self.callback_id_counter = count()
        self.callback_map = {}
        self.current_cfi = self.current_content_file = None
        RestartingWebEngineView.__init__(self, parent)
        self.dead_renderer_error_shown = False
        self.render_process_failed.connect(self.render_process_died)
        self.dispatch_on_main_thread_signal.connect(self.dispatch_on_main_thread)
        w = QApplication.instance().desktop().availableGeometry(self).width()
        QApplication.instance().palette_changed.connect(self.palette_changed)
        self.show_home_page_on_ready = True
        self._size_hint = QSize(int(w/3), int(w/2))
        self._page = WebPage(self)
        self.view_is_ready = False
        self.bridge.bridge_ready.connect(self.on_bridge_ready)
        self.bridge.view_created.connect(self.on_view_created)
        self.bridge.content_file_changed.connect(self.on_content_file_changed)
        self.bridge.set_session_data.connect(self.set_session_data)
        self.bridge.set_local_storage.connect(self.set_local_storage)
        self.bridge.reload_book.connect(self.reload_book)
        self.bridge.toggle_toc.connect(self.toggle_toc)
        self.bridge.show_search.connect(self.show_search)
        self.bridge.search_result_not_found.connect(self.search_result_not_found)
        self.bridge.find_next.connect(self.find_next)
        self.bridge.toggle_bookmarks.connect(self.toggle_bookmarks)
        self.bridge.toggle_highlights.connect(self.toggle_highlights)
        self.bridge.new_bookmark.connect(self.new_bookmark)
        self.bridge.toggle_inspector.connect(self.toggle_inspector)
        self.bridge.toggle_lookup.connect(self.toggle_lookup)
        self.bridge.quit.connect(self.quit)
        self.bridge.update_current_toc_nodes.connect(self.update_current_toc_nodes)
        self.bridge.toggle_full_screen.connect(self.toggle_full_screen)
        self.bridge.ask_for_open.connect(self.ask_for_open)
        self.bridge.selection_changed.connect(self.selection_changed)
        self.bridge.autoscroll_state_changed.connect(self.autoscroll_state_changed)
        self.bridge.view_image.connect(self.view_image)
        self.bridge.copy_image.connect(self.copy_image)
        self.bridge.overlay_visibility_changed.connect(self.overlay_visibility_changed)
        self.bridge.reference_mode_changed.connect(self.reference_mode_changed)
        self.bridge.show_loading_message.connect(self.show_loading_message)
        self.bridge.show_error.connect(self.show_error)
        self.bridge.print_book.connect(self.print_book)
        self.bridge.clear_history.connect(self.clear_history)
        self.bridge.reset_interface.connect(self.reset_interface)
        self.bridge.quit.connect(self.quit)
        self.bridge.customize_toolbar.connect(self.customize_toolbar)
        self.bridge.scrollbar_context_menu.connect(self.scrollbar_context_menu)
        self.bridge.close_prep_finished.connect(self.close_prep_finished)
        self.bridge.highlights_changed.connect(self.highlights_changed)
        self.bridge.open_url.connect(safe_open_url)
        self.bridge.speak_simple_text.connect(self.speak_simple_text)
        self.bridge.export_shortcut_map.connect(self.set_shortcut_map)
        self.shortcut_map = {}
        self.bridge.report_cfi.connect(self.call_callback)
        self.bridge.change_background_image.connect(self.change_background_image)
        self.pending_bridge_ready_actions = {}
        self.setPage(self._page)
        self.setAcceptDrops(False)
        self.setUrl(QUrl('{}://{}/'.format(FAKE_PROTOCOL, FAKE_HOST)))
        self.urlChanged.connect(self.url_changed)
        if parent is not None:
            self.inspector = Inspector(parent.inspector_dock.toggleViewAction(), self)
            parent.inspector_dock.setWidget(self.inspector)

    @property
    def tts_client(self):
        if self._tts_client is None:
            from calibre.gui2.tts.implementation import Client
            self._tts_client = Client(self.dispatch_on_main_thread_signal.emit)
        return self._tts_client

    def dispatch_on_main_thread(self, func):
        try:
            func()
        except Exception:
            import traceback
            traceback.print_exc()

    def speak_simple_text(self, text):
        from calibre.gui2.tts.errors import TTSSystemUnavailable
        try:
            self.tts_client.speak_simple_text(text)
        except TTSSystemUnavailable as err:
            return error_dialog(self, _('Text-to-Speech unavailable'), str(err), show=True)

    def shutdown(self):
        if self._tts_client is not None:
            self._tts_client.shutdown()
            self._tts_client = None

    def set_shortcut_map(self, smap):
        self.shortcut_map = smap
        self.shortcuts_changed.emit(smap)

    def url_changed(self, url):
        if url.hasFragment():
            frag = url.fragment(url.FullyDecoded)
            if frag and frag.startswith('bookpos='):
                cfi = frag[len('bookpos='):]
                if cfi:
                    self.current_cfi = cfi
                    self.cfi_changed.emit(cfi)

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
                self._host_widget.setFocus(Qt.OtherFocusReason)
        return QWebEngineView.event(self, event)

    def sizeHint(self):
        return self._size_hint

    def refresh(self):
        self.pageAction(QWebEnginePage.ReloadAndBypassCache).trigger()

    @property
    def bridge(self):
        return self._page.bridge

    def on_bridge_ready(self):
        f = QApplication.instance().font()
        fi = QFontInfo(f)
        family = f.family()
        if family in ('.AppleSystemUIFont', 'MS Shell Dlg 2'):
            family = 'system-ui'
        ui_data = {
            'all_font_families': QFontDatabase().families(),
            'ui_font_family': family,
            'ui_font_sz': '{}px'.format(fi.pixelSize()),
            'show_home_page_on_ready': self.show_home_page_on_ready,
            'system_colors': system_colors(),
            'QT_VERSION': QT_VERSION,
        }
        self.bridge.create_view(
            vprefs['session_data'], vprefs['local_storage'], field_metadata.all_metadata(), ui_data)
        for func, args in iteritems(self.pending_bridge_ready_actions):
            getattr(self.bridge, func)(*args)

    def on_view_created(self, data):
        self.view_created.emit(data)
        self.view_is_ready = True

    def on_content_file_changed(self, data):
        self.current_content_file = data

    def start_book_load(self, initial_position=None, highlights=None, current_book_data=None):
        key = (set_book_path.path,)
        cbd = current_book_data or {}
        book_url = None
        if 'calibre_library_id' in cbd:
            lid = cbd['calibre_library_id'].encode('utf-8').hex()
            book_url = f'calibre://view-book/_hex_-{lid}/{cbd["calibre_book_id"]}/{cbd["calibre_book_fmt"]}'
        self.execute_when_ready('start_book_load', key, initial_position, set_book_path.pathtoebook, highlights or [], book_url)

    def execute_when_ready(self, action, *args):
        if self.bridge.ready:
            getattr(self.bridge, action)(*args)
        else:
            self.pending_bridge_ready_actions[action] = args

    def goto_toc_node(self, node_id):
        self.execute_when_ready('goto_toc_node', node_id)

    def goto_cfi(self, cfi):
        self.execute_when_ready('goto_cfi', cfi)

    def notify_full_screen_state_change(self, in_fullscreen_mode):
        self.execute_when_ready('full_screen_state_changed', in_fullscreen_mode)

    def set_session_data(self, key, val):
        if key == '*' and val is None:
            vprefs['session_data'] = {}
            apply_font_settings(self)
            self.paged_mode_changed.emit()
            self.standalone_misc_settings_changed.emit()
        elif key != '*':
            sd = vprefs['session_data']
            sd[key] = val
            vprefs['session_data'] = sd
            if key in ('standalone_font_settings', 'base_font_size'):
                apply_font_settings(self)
            elif key == 'read_mode':
                self.paged_mode_changed.emit()
            elif key == 'standalone_misc_settings':
                self.standalone_misc_settings_changed.emit(val)

    def set_local_storage(self, key, val):
        if key == '*' and val is None:
            vprefs['local_storage'] = {}
        elif key != '*':
            sd = vprefs['local_storage']
            sd[key] = val
            vprefs['local_storage'] = sd

    def do_callback(self, func_name, callback):
        cid = unicode_type(next(self.callback_id_counter))
        self.callback_map[cid] = callback
        self.execute_when_ready('get_current_cfi', cid)

    def call_callback(self, request_id, data):
        callback = self.callback_map.pop(request_id, None)
        if callback is not None:
            callback(data)

    def get_current_cfi(self, callback):
        self.do_callback('get_current_cfi', callback)

    def show_home_page(self):
        self.execute_when_ready('show_home_page')

    def change_background_image(self, img_id):
        files = choose_images(self, 'viewer-background-image', _('Choose background image'), formats=['png', 'gif', 'jpg', 'jpeg'])
        if files:
            img = files[0]
            with open(img, 'rb') as src, open(os.path.join(viewer_config_dir, 'bg-image.data'), 'wb') as dest:
                dest.write(as_bytes(guess_type(img)[0] or 'image/jpeg') + b'|')
                shutil.copyfileobj(src, dest)
            background_image.ans = None
            self.execute_when_ready('background_image_changed', img_id)

    def goto_frac(self, frac):
        self.execute_when_ready('goto_frac', frac)

    def clear_history(self):
        self._page.history().clear()

    def clear_caches(self):
        self._page.profile().clearHttpCache()

    def trigger_shortcut(self, which):
        self.execute_when_ready('trigger_shortcut', which)

    def show_search_result(self, sr):
        self.execute_when_ready('show_search_result', sr)

    def palette_changed(self):
        self.execute_when_ready('set_system_palette', system_colors())

    def prepare_for_close(self):
        self.execute_when_ready('prepare_for_close')

    def highlight_action(self, uuid, which):
        self.execute_when_ready('highlight_action', uuid, which)
        self.setFocus(Qt.OtherFocusReason)

    def generic_action(self, which, data):
        self.execute_when_ready('generic_action', which, data)
