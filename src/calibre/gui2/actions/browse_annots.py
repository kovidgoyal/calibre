#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import Qt

from calibre.gui2.actions import InterfaceAction


class BrowseAnnotationsAction(InterfaceAction):

    name = 'Browse Annotations'
    action_spec = (_('Browse annotations'), 'highlight.png',
                   _('Browse highlights and bookmarks from all books in the library'), _('B'))
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.show_browser)
        self._browser = None

    @property
    def browser(self):
        if self._browser is None:
            from calibre.gui2.library.annotations import AnnotationsBrowser
            self._browser = AnnotationsBrowser(self.gui)
            self._browser.show_book.connect(self.open_book, type=Qt.QueuedConnection)
            self._browser.open_annotation.connect(self.open_annotation, type=Qt.QueuedConnection)
        return self._browser

    def show_browser(self):
        self.browser.show_dialog()

    def library_changed(self, db):
        if self._browser is not None:
            self._browser.reinitialize()

    def open_book(self, book_id, fmt):
        self.gui.library_view.select_rows({book_id})

    def open_annotation(self, book_id, fmt, cfi):
        self.gui.iactions['View'].view_format_by_id(book_id, fmt, open_at=cfi)
