#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import QListWidget, QListWidgetItem, Qt, QVBoxLayout, QWidget

from calibre.gui2.viewer.search import SearchInput


class Highlights(QListWidget):

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSpacing(2)

    def load(self, highlights):
        self.clear()
        for h in highlights:
            i = QListWidgetItem(h['highlighted_text'], self)
            i.setData(Qt.UserRole, h)


class HighlightsPanel(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.search_input = si = SearchInput(self, 'highlights-search')
        si.do_search.connect(self.search_requested)
        l.addWidget(si)

        self.highlights = h = Highlights(self)
        l.addWidget(h)
        self.load = h.load

    def search_requested(self, query):
        pass

    def focus(self):
        self.highlights_list.setFocus(Qt.OtherFocusReason)
