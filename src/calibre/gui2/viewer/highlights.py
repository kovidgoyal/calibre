#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from itertools import chain

from PyQt5.Qt import (
    QItemSelectionModel, QListWidget, QListWidgetItem, Qt, QVBoxLayout, QWidget
)

from calibre.gui2 import error_dialog
from calibre.gui2.viewer.search import SearchInput
from polyglot.builtins import range


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

    def find_query(self, query):
        cr = self.currentRow()
        pat = query.regex
        if query.backwards:
            if cr < 0:
                cr = self.count()
            indices = chain(range(cr - 1, -1, -1), range(self.count() - 1, cr, -1))
        else:
            if cr < 0:
                cr = -1
            indices = chain(range(cr + 1, self.count()), range(0, cr + 1))
        for i in indices:
            item = self.item(i)
            h = item.data(Qt.UserRole)
            if pat.search(h['highlighted_text']) is not None or pat.search(h.get('notes') or '') is not None:
                self.set_current_row(i)
                return True
        return False

    def set_current_row(self, row):
        self.setCurrentRow(row, QItemSelectionModel.ClearAndSelect)


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
        if not self.highlights.find_query(query):
            error_dialog(self, _('No matches'), _(
                'No highlights match the search: {}').format(query.text), show=True)

    def focus(self):
        self.highlights_list.setFocus(Qt.OtherFocusReason)
