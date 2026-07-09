#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.match_books import MatchBooks


class MatchBookAction(InterfaceAction):

    name = 'Match Books'
    action_spec = (_('Match book to library'), 'book.png',
            _('Match this book to a book in the library'),
            ())
    dont_add_to = frozenset(('menubar', 'toolbar', 'context-menu', 'toolbar-child', 'context-menu-cover-browser'))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.match_books_in_library)

    def location_selected(self, loc):
        enabled = loc != 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def match_books_in_library(self, *args):
        view = self.gui.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) != 1:
            d = error_dialog(self.gui, _('Match books'), _('You must select one book'))
            d.exec()
            return

        id_ = view.model().indices(rows)[0]
        MatchBooks(self.gui, view, id_, rows[0]).exec()


class ShowMatchedBookAction(InterfaceAction):

    name = 'Show Matched Book In Library'
    action_spec = (_('Show matched book in library'), 'lt.png',
            _('Show the book in the calibre library that matches this book'),
            ())
    dont_add_to = frozenset(('menubar', 'toolbar', 'context-menu', 'toolbar-child', 'context-menu-cover-browser'))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.show_matched_books_in_library)

    def location_selected(self, loc):
        enabled = loc != 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def show_matched_books_in_library(self, *args):
        view = self.gui.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) != 1:
            d = error_dialog(self.gui, _('Match books'), _('You must select one book'))
            d.exec()
            return

        device_book_index = view.model().indices(rows)[0]
        device_db = view.model().db
        db = self.gui.current_db.new_api
        book = device_db[device_book_index]
        matching_book_ids = db.books_matching_device_book(book.lpath)
        if not matching_book_ids:
            if question_dialog(self.gui, _('No matching books'), _(
                'No matching books found in the calibre library. Do you want to specify the'
                ' matching book manually?')):
                MatchBooks(self.gui, view, device_book_index, rows[0]).exec()
            return
        ids = tuple(sorted(matching_book_ids, reverse=True))
        self.gui.library_view.select_rows(ids)
        self.gui.show_library_view()
        self.gui.iactions['Edit Metadata'].refresh_books_after_metadata_edit(ids)
