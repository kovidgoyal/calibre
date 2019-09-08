#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import absolute_import, division, print_function, unicode_literals

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

from PyQt5.Qt import (QWidget, QGridLayout, QListWidget, QSize, Qt, QUrl,
                      pyqtSlot, pyqtSignal, QVBoxLayout, QFrame, QLabel,
                      QLineEdit, QTimer, QPushButton, QIcon, QSplitter)
from PyQt5.QtWebKitWidgets import QWebView, QWebPage
from PyQt5.QtWebKit import QWebElement

from calibre.ebooks.oeb.display.webview import load_html
from calibre.gui2 import error_dialog, question_dialog, gprefs, secure_web_page
from calibre.utils.logging import default_log
from polyglot.builtins import native_string_type, range, unicode_type
from polyglot.binary import as_base64_unicode


class Page(QWebPage):  # {{{

    elem_clicked = pyqtSignal(object, object, object, object, object)

    def __init__(self):
        self.log = default_log
        QWebPage.__init__(self)
        secure_web_page(self.settings())
        self.js = None
        self.evaljs = self.mainFrame().evaluateJavaScript
        nam = self.networkAccessManager()
        nam.setNetworkAccessible(nam.NotAccessible)
        self.setLinkDelegationPolicy(self.DelegateAllLinks)

    def javaScriptConsoleMessage(self, msg, lineno, msgid):
        self.log('JS:', unicode_type(msg))

    def javaScriptAlert(self, frame, msg):
        self.log(unicode_type(msg))

    @pyqtSlot(result=bool)
    def shouldInterruptJavaScript(self):
        return True

    @pyqtSlot(QWebElement, native_string_type, native_string_type, float)
    def onclick(self, elem, loc, totals, frac):
        elem_id = unicode_type(elem.attribute('id')) or None
        tag = unicode_type(elem.tagName()).lower()
        self.elem_clicked.emit(tag, frac, elem_id, json.loads(unicode_type(loc)), json.loads(unicode_type(totals)))

    def load_js(self):
        if self.js is None:
            from calibre.utils.resources import compiled_coffeescript
            self.js = compiled_coffeescript('ebooks.oeb.display.utils')
            self.js += compiled_coffeescript('ebooks.oeb.polish.choose')
            if isinstance(self.js, bytes):
                self.js = self.js.decode('utf-8')
        self.mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        self.evaljs(self.js)
# }}}


class WebView(QWebView):  # {{{

    elem_clicked = pyqtSignal(object, object, object, object, object)

    def __init__(self, parent):
        QWebView.__init__(self, parent)
        self._page = Page()
        self._page.elem_clicked.connect(self.elem_clicked)
        self.setPage(self._page)
        raw = '''
        body { background-color: white  }
        .calibre_toc_hover:hover { cursor: pointer !important; border-top: solid 5px green !important }
        '''
        raw = '::selection {background:#ffff00; color:#000;}\n'+raw
        data = 'data:text/css;charset=utf-8;base64,'
        data += as_base64_unicode(raw)
        self.settings().setUserStyleSheetUrl(QUrl(data))

    def load_js(self):
        self.page().load_js()

    def sizeHint(self):
        return QSize(1500, 300)

    def show_frag(self, frag):
        self.page().mainFrame().scrollToAnchor(frag)

    @property
    def scroll_frac(self):
        try:
            val = float(self.page().evaljs('window.pageYOffset/document.body.scrollHeight'))
        except (TypeError, ValueError):
            val = 0
        return val
# }}}


class ItemEdit(QWidget):

    def __init__(self, parent, prefs=None):
        QWidget.__init__(self, parent)
        self.prefs = prefs or gprefs
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
        self.view = WebView(self)
        self.view.elem_clicked.connect(self.elem_clicked)
        l.addWidget(self.view, 0, 0, 1, 3)
        sp.addWidget(w)

        self.search_text = s = QLineEdit(self)
        s.setPlaceholderText(_('Search for text...'))
        l.addWidget(s, 1, 0)
        self.ns_button = b = QPushButton(QIcon(I('arrow-down.png')), _('Find &next'), self)
        b.clicked.connect(self.find_next)
        l.addWidget(b, 1, 1)
        self.ps_button = b = QPushButton(QIcon(I('arrow-up.png')), _('Find &previous'), self)
        l.addWidget(b, 1, 2)
        b.clicked.connect(self.find_previous)

        self.f = f = QFrame()
        f.setFrameShape(f.StyledPanel)
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

        f.la2 = la = QLabel('<b>'+_('&Name of the ToC entry:'))
        l.addWidget(la)
        self.name = QLineEdit(self)
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

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and self.search_text.hasFocus():
            # Prevent pressing enter in the search box from triggering the dialog's accept() method
            ev.accept()
            return
        return super(ItemEdit, self).keyPressEvent(ev)

    def find(self, forwards=True):
        text = unicode_type(self.search_text.text()).strip()
        flags = QWebPage.FindFlags(0) if forwards else QWebPage.FindBackward
        d = self.dest_list
        if d.count() == 1:
            flags |= QWebPage.FindWrapsAroundDocument
        if not self.view.findText(text, flags) and text:
            if d.count() == 1:
                return error_dialog(self, _('No match found'),
                    _('No match found for: %s')%text, show=True)

            delta = 1 if forwards else -1
            current = unicode_type(d.currentItem().data(Qt.DisplayRole) or '')
            next_index = (d.currentRow() + delta)%d.count()
            next = unicode_type(d.item(next_index).data(Qt.DisplayRole) or '')
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
        spine_names = [container.abspath_to_name(p) for p in
                       container.spine_items]
        spine_names = [n for n in spine_names if container.has_name(n)]
        self.dest_list.addItems(spine_names)

    def current_changed(self, item):
        name = self.current_name = unicode_type(item.data(Qt.DisplayRole) or '')
        self.current_frag = None
        path = self.container.name_to_abspath(name)
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
        encoding = self.container.encoding_map.get(name, None) or 'utf-8'

        load_html(path, self.view, codec=encoding,
                  mime_type=self.container.mime_map[name])
        self.view.load_js()
        self.dest_label.setText(self.base_msg + '<br>' + _('File:') + ' ' +
                                name + '<br>' + _('Top of the file'))
        if hasattr(self, 'pending_search'):
            f = self.pending_search
            del self.pending_search
            f()

    def __call__(self, item, where):
        self.current_item, self.current_where = item, where
        self.current_name = None
        self.current_frag = None
        self.name.setText(_('(Untitled)'))
        dest_index, frag = 0, None
        if item is not None:
            if where is None:
                self.name.setText(item.data(0, Qt.DisplayRole) or '')
                self.name.setCursorPosition(0)
            toc = item.data(0, Qt.UserRole)
            if toc.dest:
                for i in range(self.dest_list.count()):
                    litem = self.dest_list.item(i)
                    if unicode_type(litem.data(Qt.DisplayRole) or '') == toc.dest:
                        dest_index = i
                        frag = toc.frag
                        break

        self.dest_list.blockSignals(True)
        self.dest_list.setCurrentRow(dest_index)
        self.dest_list.blockSignals(False)
        item = self.dest_list.item(dest_index)
        self.current_changed(item)
        if frag:
            self.current_frag = frag
            QTimer.singleShot(1, self.show_frag)

    def show_frag(self):
        self.view.show_frag(self.current_frag)
        QTimer.singleShot(1, self.check_frag)

    def check_frag(self):
        pos = self.view.scroll_frac
        if pos == 0:
            self.current_frag = None
        self.update_dest_label()

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

    def update_dest_label(self):
        val = self.view.scroll_frac
        self.dest_label.setText(self.base_msg + '<br>' +
                    _('File:') + ' ' + self.current_name + '<br>' +
                                self.get_loctext(val))

    @property
    def result(self):
        return (self.current_item, self.current_where, self.current_name,
                self.current_frag, unicode_type(self.name.text()))
