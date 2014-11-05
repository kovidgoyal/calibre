#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json
from collections import defaultdict

from PyQt5.Qt import QUrl, QWidget, QHBoxLayout, QSize
from PyQt5.QtWebKitWidgets import QWebView, QWebPage
from PyQt5.QtWebKit import QWebSettings

from calibre import prints

class FootnotesPage(QWebPage):

    def __init__(self, parent):
        QWebPage.__init__(self, parent)
        from calibre.gui2.viewer.documentview import apply_basic_settings
        settings = self.settings()
        apply_basic_settings(settings)
        settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, False)


class FootnotesView(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        self.view = v = QWebView(self)
        l.addWidget(v)

    def page(self):
        return self.view.page()

    def sizeHint(self):
        return QSize(400, 200)


class Footnotes(object):

    def __init__(self, view):
        self.view = view
        self.clear()

    def set_footnotes_view(self, fv):
        self.footnotes_view = fv
        self.clone_settings()

    def clone_settings(self):
        source = self.view.document.settings()
        settings = self.footnotes_view.page().settings()
        for x in 'DefaultFontSize DefaultFixedFontSize MinimumLogicalFontSize MinimumFontSize StandardFont SerifFont SansSerifFont FixedFont'.split():
            func = 'setFontSize' if x.endswith('FontSize') else 'setFontFamily'
            getattr(settings, func)(getattr(QWebSettings, x), getattr(source, 'f' + func[4:])(getattr(QWebSettings, x)))
        settings.setUserStyleSheetUrl(source.userStyleSheetUrl())

    def clear(self):
        self.footnote_data_cache = {}
        self.known_footnote_targets = defaultdict(set)

    def spine_index(self, path):
        try:
            return self.view.manager.iterator.spine.index(path)
        except (AttributeError, ValueError):
            return -1

    def load_footnote_data(self, current_url):
        fd = self.footnote_data_cache[current_url] = {}
        try:
            raw = self.view.document.javascript('window.calibre_extract.get_footnote_data()', typ='string')
            for x in json.loads(raw):
                if x not in fd:
                    qu = QUrl(x)
                    path = qu.toLocalFile()
                    si = self.spine_index(path)
                    if si > -1:
                        target = qu.fragment(QUrl.FullyDecoded)
                        fd[qu.toString()] = (path, target)
                        self.known_footnote_targets[path].add(target)
        except Exception:
            prints('Failed to get footnote data, with error:')
            import traceback
            traceback.print_exc()
        return fd

    def get_footnote_data(self, qurl):
        current_url = unicode(self.view.document.mainFrame().baseUrl().toLocalFile())
        if not current_url:
            return  # Not viewing a local file
        fd = self.footnote_data_cache.get(current_url)
        if fd is None:
            fd = self.load_footnote_data(current_url)
        return fd.get(qurl.toString())
