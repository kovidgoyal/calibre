#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.match_books import MatchBooks

class MatchBookAction(InterfaceAction):

    name = 'Match Books'
    action_spec = (_('Match book to library'), 'book.png',
            _('Match this book to a book in the library'),
            ())
    dont_add_to = frozenset(['menubar', 'toolbar', 'context-menu', 'toolbar-child'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.match_books_in_library)

    def location_selected(self, loc):
        enabled = loc != 'library'
        self.qaction.setEnabled(enabled)

    def match_books_in_library(self, *args):
        view = self.gui.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) != 1:
            d = error_dialog(self.gui, _('Match books'), _('You must select one book'))
            d.exec_()
            return

        id_ = view.model().indices(rows)[0]
        MatchBooks(self.gui, view, id_).exec_()
