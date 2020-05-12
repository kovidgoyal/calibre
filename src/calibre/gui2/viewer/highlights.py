#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from itertools import chain

from PyQt5.Qt import (
    QItemSelectionModel, QLabel, QListWidget, QListWidgetItem, Qt, QVBoxLayout,
    QWidget, pyqtSignal
)

from calibre.constants import plugins
from calibre.gui2 import error_dialog
from calibre.gui2.viewer.search import SearchInput
from calibre.gui2.viewer.web_view import get_manifest
from polyglot.builtins import range


def spine_index_for_highlight(highlight):
    ans = highlight['spine_index']
    manifest = get_manifest()
    if manifest is not None:
        spine = manifest['spine']
        name = highlight.get('spine_name')
        if name:
            try:
                idx = spine.index(name)
            except Exception:
                pass
            else:
                ans = idx
    return ans


class Highlights(QListWidget):

    jump_to_highlight = pyqtSignal(object)

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSpacing(2)
        pi = plugins['progress_indicator'][0]
        pi.set_no_activate_on_click(self)
        self.itemActivated.connect(self.item_activated)

    def load(self, highlights):
        self.clear()
        for h in highlights or ():
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

    def item_activated(self, item):
        self.jump_to_highlight.emit(item.data(Qt.UserRole))


class HighlightsPanel(QWidget):

    jump_to_cfi = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.search_input = si = SearchInput(self, 'highlights-search')
        si.do_search.connect(self.search_requested)
        l.addWidget(si)

        la = QLabel(_('Double click on an entry to jump to it'))
        la.setWordWrap(True)
        l.addWidget(la)

        self.highlights = h = Highlights(self)
        l.addWidget(h)
        h.jump_to_highlight.connect(self.jump_to_highlight)
        self.load = h.load

    def search_requested(self, query):
        if not self.highlights.find_query(query):
            error_dialog(self, _('No matches'), _(
                'No highlights match the search: {}').format(query.text), show=True)

    def focus(self):
        self.highlights.setFocus(Qt.OtherFocusReason)

    def jump_to_highlight(self, highlight):
        cfi = highlight['start_cfi']
        idx = spine_index_for_highlight(highlight)
        cfi = 'epubcfi(/{}{})'.format(2*(idx + 1), cfi)
        self.jump_to_cfi.emit(cfi)
