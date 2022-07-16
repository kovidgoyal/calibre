#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import sys
import weakref
from functools import lru_cache
from qt.core import (
    QApplication, QByteArray, QFrame, QGridLayout, QIcon, QLabel, QLineEdit,
    QListWidget, QPushButton, QSize, QSplitter, Qt, QUrl, QVBoxLayout, QWidget,
    pyqtSignal
)
from qt.webengine import (
    QWebEnginePage, QWebEngineProfile, QWebEngineScript,
    QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler, QWebEngineView
)

from calibre.constants import FAKE_HOST, FAKE_PROTOCOL
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.gui2 import error_dialog, gprefs, is_dark_theme, question_dialog
from calibre.gui2.palette import dark_color, dark_link_color, dark_text_color
from calibre.utils.logging import default_log
from calibre.utils.short_uuid import uuid4
from calibre.utils.webengine import secure_webengine, send_reply, setup_profile
from polyglot.builtins import as_bytes


class RequestInterceptor(QWebEngineUrlRequestInterceptor):

    def interceptRequest(self, request_info):
        method = bytes(request_info.requestMethod())
        if method not in (b'GET', b'HEAD'):
            default_log.warn(f'Blocking URL request with method: {method}')
            request_info.block(True)
            return
        qurl = request_info.requestUrl()
        if qurl.scheme() not in (FAKE_PROTOCOL,):
            default_log.warn(f'Blocking URL request {qurl.toString()} as it is not for a resource in the book')
            request_info.block(True)
            return


def current_container():
    return getattr(current_container, 'ans', lambda: None)()


@lru_cache(maxsize=2)
def mathjax_dir():
    return P('mathjax', allow_user_override=False)


class UrlSchemeHandler(QWebEngineUrlSchemeHandler):

    def __init__(self, parent=None):
        QWebEngineUrlSchemeHandler.__init__(self, parent)
        self.allowed_hosts = (FAKE_HOST,)

    def requestStarted(self, rq):
        if bytes(rq.requestMethod()) != b'GET':
            return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestDenied)
        c = current_container()
        if c is None:
            return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestDenied)
        url = rq.requestUrl()
        host = url.host()
        if host not in self.allowed_hosts or url.scheme() != FAKE_PROTOCOL:
            return self.fail_request(rq)
        path = url.path()
        if path.startswith('/book/'):
            name = path[len('/book/'):]
            try:
                mime_type = c.mime_map.get(name) or guess_type(name)
                try:
                    with c.open(name) as f:
                        q = os.path.abspath(f.name)
                        if not q.startswith(c.root):
                            raise FileNotFoundError('Attempt to leave sandbox')
                        data = f.read()
                except FileNotFoundError:
                    print(f'Could not find file {name} in book', file=sys.stderr)
                    rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
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
                return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestFailed)
        elif path.startswith('/mathjax/'):
            try:
                ignore, ignore, base, rest = path.split('/', 3)
            except ValueError:
                print(f'Could not find file {path} in mathjax', file=sys.stderr)
                rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            try:
                mime_type = guess_type(rest)
                if base == 'loader' and '/' not in rest and '\\' not in rest:
                    data = P(rest, allow_user_override=False, data=True)
                elif base == 'data':
                    q = os.path.abspath(os.path.join(mathjax_dir(), rest))
                    if not q.startswith(mathjax_dir()):
                        raise FileNotFoundError('')
                    with open(q, 'rb') as f:
                        data = f.read()
                else:
                    raise FileNotFoundError('')
                send_reply(rq, mime_type, data)
            except FileNotFoundError:
                print(f'Could not find file {path} in mathjax', file=sys.stderr)
                rq.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            except Exception:
                import traceback
                traceback.print_exc()
                return self.fail_request(rq, QWebEngineUrlRequestJob.Error.RequestFailed)
        else:
            return self.fail_request(rq)

    def fail_request(self, rq, fail_code=None):
        if fail_code is None:
            fail_code = QWebEngineUrlRequestJob.Error.UrlNotFound
        rq.fail(fail_code)
        print(f"Blocking FAKE_PROTOCOL request: {rq.requestUrl().toString()} with code: {fail_code}", file=sys.stderr)


class Page(QWebEnginePage):  # {{{

    elem_clicked = pyqtSignal(object, object, object, object, object)
    frag_shown = pyqtSignal(object)

    def __init__(self, parent, prefs):
        self.log = default_log
        self.current_frag = None
        self.com_id = str(uuid4())
        profile = QWebEngineProfile(QApplication.instance())
        setup_profile(profile)
        # store these globally as they need to be destructed after the QWebEnginePage
        current_container.url_handler = UrlSchemeHandler(parent=profile)
        current_container.interceptor = RequestInterceptor(profile)
        current_container.profile_memory = profile
        profile.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), current_container.url_handler)
        s = profile.settings()
        s.setDefaultTextEncoding('utf-8')
        profile.setUrlRequestInterceptor(current_container.interceptor)
        QWebEnginePage.__init__(self, profile, parent)
        secure_webengine(self, for_viewer=True)
        self.titleChanged.connect(self.title_changed)
        self.loadFinished.connect(self.show_frag)
        s = QWebEngineScript()
        s.setName('toc.js')
        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        s.setRunsOnSubFrames(True)
        s.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        js = P('toc.js', allow_user_override=False, data=True).decode('utf-8').replace('COM_ID', self.com_id, 1)
        if 'preview_background' in prefs.defaults and 'preview_foreground' in prefs.defaults:
            from calibre.gui2.tweak_book.preview import get_editor_settings
            settings = get_editor_settings(prefs)
        else:
            if is_dark_theme():
                settings = {
                    'is_dark_theme': True,
                    'bg': dark_color.name(),
                    'fg': dark_text_color.name(),
                    'link': dark_link_color.name(),
                }
            else:
                settings = {}
        js = js.replace('SETTINGS', json.dumps(settings), 1)
        s.setSourceCode(js)
        self.scripts().insert(s)

    def javaScriptConsoleMessage(self, level, msg, lineno, msgid):
        self.log('JS:', str(msg))

    def javaScriptAlert(self, origin, msg):
        self.log(str(msg))

    def title_changed(self, title):
        parts = title.split('-', 1)
        if len(parts) == 2 and parts[0] == self.com_id:
            self.runJavaScript(
                'JSON.stringify(window.calibre_toc_data)',
                QWebEngineScript.ScriptWorldId.ApplicationWorld, self.onclick)

    def onclick(self, data):
        try:
            tag, elem_id, loc, totals, frac = json.loads(data)
        except Exception:
            return
        elem_id = elem_id or None
        self.elem_clicked.emit(tag, frac, elem_id, loc, totals)

    def show_frag(self, ok):
        if ok and self.current_frag:
            self.runJavaScript('''
                document.location = '#non-existent-anchor';
                document.location = '#' + {};
            '''.format(json.dumps(self.current_frag)))
            self.current_frag = None
            self.runJavaScript('window.pageYOffset/document.body.scrollHeight', QWebEngineScript.ScriptWorldId.ApplicationWorld, self.frag_shown.emit)

# }}}


class WebView(QWebEngineView):  # {{{

    elem_clicked = pyqtSignal(object, object, object, object, object)
    frag_shown = pyqtSignal(object)

    def __init__(self, parent, prefs):
        QWebEngineView.__init__(self, parent)
        self._page = Page(self, prefs)
        self._page.elem_clicked.connect(self.elem_clicked)
        self._page.frag_shown.connect(self.frag_shown)
        self.setPage(self._page)

    def load_name(self, name, frag=None):
        self._page.current_frag = frag
        url = QUrl(f'{FAKE_PROTOCOL}://{FAKE_HOST}/')
        url.setPath(f'/book/{name}')
        self.setUrl(url)

    def sizeHint(self):
        return QSize(300, 300)

    def contextMenuEvent(self, ev):
        pass
# }}}


class ItemEdit(QWidget):

    def __init__(self, parent, prefs=None):
        QWidget.__init__(self, parent)
        self.prefs = prefs or gprefs
        self.pending_search = None
        self.current_frag = None
        self.setLayout(QVBoxLayout())

        self.la = la = QLabel('<b>'+_(
            'Select a destination for the Table of Contents entry'))
        self.layout().addWidget(la)
        self.splitter = sp = QSplitter(self)
        self.layout().addWidget(sp)
        self.layout().setStretch(1, 10)
        sp.setOpaqueResize(False)
        sp.setChildrenCollapsible(False)

        self.dest_list = dl = QListWidget(self)
        dl.setMinimumWidth(250)
        dl.currentItemChanged.connect(self.current_changed)
        sp.addWidget(dl)

        w = self.w = QWidget(self)
        l = w.l = QGridLayout()
        w.setLayout(l)
        self.view = WebView(self, self.prefs)
        self.view.elem_clicked.connect(self.elem_clicked)
        self.view.frag_shown.connect(self.update_dest_label, type=Qt.ConnectionType.QueuedConnection)
        self.view.loadFinished.connect(self.load_finished, type=Qt.ConnectionType.QueuedConnection)
        l.addWidget(self.view, 0, 0, 1, 3)
        sp.addWidget(w)

        self.search_text = s = QLineEdit(self)
        s.setPlaceholderText(_('Search for text...'))
        s.returnPressed.connect(self.find_next)
        l.addWidget(s, 1, 0)
        self.ns_button = b = QPushButton(QIcon.ic('arrow-down.png'), _('Find &next'), self)
        b.clicked.connect(self.find_next)
        l.addWidget(b, 1, 1)
        self.ps_button = b = QPushButton(QIcon.ic('arrow-up.png'), _('Find &previous'), self)
        l.addWidget(b, 1, 2)
        b.clicked.connect(self.find_previous)

        self.f = f = QFrame()
        f.setFrameShape(QFrame.Shape.StyledPanel)
        f.setMinimumWidth(250)
        l = f.l = QVBoxLayout()
        f.setLayout(l)
        sp.addWidget(f)

        f.la = la = QLabel('<p>'+_(
            'Here you can choose a destination for the Table of Contents\' entry'
            ' to point to. First choose a file from the book in the left-most panel. The'
            ' file will open in the central panel.<p>'

            'Then choose a location inside the file. To do so, simply click on'
            ' the place in the central panel that you want to use as the'
            ' destination. As you move the mouse around the central panel, a'
            ' thick green line appears, indicating the precise location'
            ' that will be selected when you click.'))
        la.setStyleSheet('QLabel { margin-bottom: 20px }')
        la.setWordWrap(True)
        l.addWidget(la)

        f.la2 = la = QLabel('<b>'+_('Na&me of the ToC entry:'))
        l.addWidget(la)
        self.name = QLineEdit(self)
        self.name.setPlaceholderText(_('(Untitled)'))
        la.setBuddy(self.name)
        l.addWidget(self.name)

        self.base_msg = '<b>'+_('Currently selected destination:')+'</b>'
        self.dest_label = la = QLabel(self.base_msg)
        la.setWordWrap(True)
        la.setStyleSheet('QLabel { margin-top: 20px }')
        l.addWidget(la)

        l.addStretch()

        state = self.prefs.get('toc_edit_splitter_state', None)
        if state is not None:
            sp.restoreState(state)

    def load_finished(self, ok):
        if self.pending_search:
            self.pending_search()
        self.pending_search = None

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.search_text.hasFocus():
            # Prevent pressing enter in the search box from triggering the dialog's accept() method
            ev.accept()
            return
        return super().keyPressEvent(ev)

    def find(self, forwards=True):
        text = str(self.search_text.text()).strip()
        flags = QWebEnginePage.FindFlag(0) if forwards else QWebEnginePage.FindFlag.FindBackward
        self.find_data = text, flags, forwards
        self.view.findText(text, flags, self.find_callback)

    def find_callback(self, found):
        d = self.dest_list
        text, flags, forwards = self.find_data
        if not found and text:
            if d.count() == 1:
                return error_dialog(self, _('No match found'),
                    _('No match found for: %s')%text, show=True)

            delta = 1 if forwards else -1
            current = str(d.currentItem().data(Qt.ItemDataRole.DisplayRole) or '')
            next_index = (d.currentRow() + delta)%d.count()
            next = str(d.item(next_index).data(Qt.ItemDataRole.DisplayRole) or '')
            msg = '<p>'+_('No matches for %(text)s found in the current file [%(current)s].'
                          ' Do you want to search in the %(which)s file [%(next)s]?')
            msg = msg%dict(text=text, current=current, next=next,
                           which=_('next') if forwards else _('previous'))
            if question_dialog(self, _('No match found'), msg):
                self.pending_search = self.find_next if forwards else self.find_previous
                d.setCurrentRow(next_index)

    def find_next(self):
        return self.find()

    def find_previous(self):
        return self.find(forwards=False)

    def load(self, container):
        self.container = container
        current_container.ans = weakref.ref(container)
        spine_names = [container.abspath_to_name(p) for p in
                       container.spine_items]
        spine_names = [n for n in spine_names if container.has_name(n)]
        self.dest_list.addItems(spine_names)

    def current_changed(self, item):
        name = self.current_name = str(item.data(Qt.ItemDataRole.DisplayRole) or '')
        # Ensure encoding map is populated
        root = self.container.parsed(name)
        nasty = root.xpath('//*[local-name()="head"]/*[local-name()="p"]')
        if nasty:
            body = root.xpath('//*[local-name()="body"]')
            if not body:
                return error_dialog(self, _('Bad markup'),
                             _('This book has severely broken markup, its ToC cannot be edited.'), show=True)
            for x in reversed(nasty):
                body[0].insert(0, x)
            self.container.commit_item(name, keep_parsed=True)
        self.view.load_name(name, self.current_frag)
        self.current_frag = None
        self.dest_label.setText(self.base_msg + '<br>' + _('File:') + ' ' +
                                name + '<br>' + _('Top of the file'))

    def __call__(self, item, where):
        self.current_item, self.current_where = item, where
        self.current_name = None
        self.current_frag = None
        self.name.setText('')
        dest_index, frag = 0, None
        if item is not None:
            if where is None:
                self.name.setText(item.data(0, Qt.ItemDataRole.DisplayRole) or '')
                self.name.setCursorPosition(0)
            toc = item.data(0, Qt.ItemDataRole.UserRole)
            if toc.dest:
                for i in range(self.dest_list.count()):
                    litem = self.dest_list.item(i)
                    if str(litem.data(Qt.ItemDataRole.DisplayRole) or '') == toc.dest:
                        dest_index = i
                        frag = toc.frag
                        break

        self.dest_list.blockSignals(True)
        self.dest_list.setCurrentRow(dest_index)
        self.dest_list.blockSignals(False)
        item = self.dest_list.item(dest_index)
        if frag:
            self.current_frag = frag
        self.current_changed(item)

    def get_loctext(self, frac):
        frac = int(round(frac * 100))
        if frac == 0:
            loctext = _('Top of the file')
        else:
            loctext =  _('Approximately %d%% from the top')%frac
        return loctext

    def elem_clicked(self, tag, frac, elem_id, loc, totals):
        self.current_frag = elem_id or (loc, totals)
        base = _('Location: A &lt;%s&gt; tag inside the file')%tag
        loctext = base + ' [%s]'%self.get_loctext(frac)
        self.dest_label.setText(self.base_msg + '<br>' +
                    _('File:') + ' ' + self.current_name + '<br>' + loctext)

    def update_dest_label(self, val):
        self.dest_label.setText(self.base_msg + '<br>' +
                    _('File:') + ' ' + self.current_name + '<br>' +
                                self.get_loctext(val))

    @property
    def result(self):
        return (self.current_item, self.current_where, self.current_name,
                self.current_frag, self.name.text().strip() or _('(Untitled)'))
