#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json
from collections import defaultdict

from PyQt5.Qt import (
    QUrl, QWidget, QHBoxLayout, QSize, pyqtSlot, QVBoxLayout, QToolButton,
    QIcon, pyqtSignal)
from PyQt5.QtWebKitWidgets import QWebView, QWebPage
from PyQt5.QtWebKit import QWebSettings

from calibre import prints
from calibre.constants import DEBUG, FAKE_PROTOCOL, FAKE_HOST
from calibre.ebooks.oeb.display.webview import load_html


class FootnotesPage(QWebPage):

    def __init__(self, parent):
        QWebPage.__init__(self, parent)
        self.js_loader = None
        self._footnote_data = ''
        from calibre.gui2.viewer.documentview import apply_basic_settings
        settings = self.settings()
        apply_basic_settings(settings)
        settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, False)
        self.setLinkDelegationPolicy(self.DelegateAllLinks)
        self.mainFrame().javaScriptWindowObjectCleared.connect(self.add_window_objects)
        self.add_window_objects()

    def add_window_objects(self, add_ready_listener=True):
        self.mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        evaljs = self.mainFrame().evaluateJavaScript
        if self.js_loader is not None:
            for x in 'utils extract'.split():
                evaljs(self.js_loader.get(x))

    @pyqtSlot(str)
    def debug(self, msg):
        prints(msg)

    @pyqtSlot(result=str)
    def footnote_data(self):
        return self._footnote_data

    def set_footnote_data(self, target, known_targets):
        self._footnote_data = json.dumps({'target':target, 'known_targets':known_targets})
        if self._footnote_data:
            self.mainFrame().evaluateJavaScript(
                'data = JSON.parse(py_bridge.footnote_data()); calibre_extract.show_footnote(data["target"], data["known_targets"])')

    def javaScriptAlert(self, frame, msg):
        prints('FootnoteView:alert::', msg)

    def javaScriptConsoleMessage(self, msg, lineno, source_id):
        if DEBUG:
            prints('FootnoteView:%s:%s:'%(unicode(source_id), lineno), unicode(msg))


class FootnotesView(QWidget):

    follow_link = pyqtSignal()
    close_view = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        self.vl = vl = QVBoxLayout()
        self.view = v = QWebView(self)
        self._page = FootnotesPage(v)
        v.setPage(self._page)
        l.addWidget(v), l.addLayout(vl)
        self.goto_button = b = QToolButton(self)
        b.setIcon(QIcon(I('forward.png'))), b.setToolTip(_('Go to this footnote in the main view'))
        b.clicked.connect(self.follow_link)
        vl.addWidget(b)
        self.close_button = b = QToolButton(self)
        b.setIcon(QIcon(I('window-close.png'))), b.setToolTip(_('Close the footnotes window'))
        b.clicked.connect(self.close_view)
        vl.addWidget(b)

    def page(self):
        return self._page

    def sizeHint(self):
        return QSize(400, 200)


class Footnotes(object):

    def __init__(self, view):
        self.view = view
        self.clear()

    def set_footnotes_view(self, fv):
        self.footnotes_view = fv
        self.clone_settings()
        fv.page().linkClicked.connect(self.view.footnote_link_clicked)
        fv.page().js_loader = self.view.document.js_loader

    def clone_settings(self):
        source = self.view.document.settings()
        settings = self.footnotes_view.page().settings()
        for x in 'DefaultFontSize DefaultFixedFontSize MinimumLogicalFontSize MinimumFontSize StandardFont SerifFont SansSerifFont FixedFont'.split():
            func = 'setFontSize' if x.endswith('FontSize') else 'setFontFamily'
            getattr(settings, func)(getattr(QWebSettings, x), getattr(source, 'f' + func[4:])(getattr(QWebSettings, x)))
        settings.setUserStyleSheetUrl(source.userStyleSheetUrl())

    def clear(self):
        self.known_footnote_targets = defaultdict(set)
        self.showing_url = None

    def spine_path(self, path):
        try:
            si = self.view.manager.iterator.spine.index(path)
            return self.view.manager.iterator.spine[si]
        except (AttributeError, ValueError):
            pass

    def get_footnote_data(self, a, qurl):
        current_path = self.view.path()
        if not current_path:
            return  # Not viewing a local file
        dest_path = self.spine_path(self.view.path(qurl))
        if dest_path is not None:
            if dest_path == current_path:
                # We deliberately ignore linked to anchors if the destination is
                # the same as the source, because many books have section ToCs
                # that are linked back from their destinations, for example,
                # the calibre User Manual
                linked_to_anchors = {}
            else:
                linked_to_anchors = {anchor:0 for path, anchor in dest_path.verified_links if path == current_path}
            if a.evaluateJavaScript('calibre_extract.is_footnote_link(this, "%s://%s", %s)' % (FAKE_PROTOCOL, FAKE_HOST, json.dumps(linked_to_anchors))):
                if dest_path not in self.known_footnote_targets:
                    self.known_footnote_targets[dest_path] = s = set()
                    for item in self.view.manager.iterator.spine:
                        for path, target in item.verified_links:
                            if target and path == dest_path:
                                s.add(target)
                return (dest_path, qurl.fragment(QUrl.FullyDecoded), qurl)

    def show_footnote(self, fd):
        path, target, self.showing_url = fd

        if hasattr(self, 'footnotes_view'):
            if load_html(path, self.footnotes_view.view, codec=getattr(path, 'encoding', 'utf-8'),
                         mime_type=getattr(path, 'mime_type', 'text/html')):
                self.footnotes_view.page().set_footnote_data(target, {k:True for k in self.known_footnote_targets[path]})
