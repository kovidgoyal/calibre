#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import Qt

from calibre.gui2 import error_dialog
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
            self.gui.library_view.selection_changed.connect(self.selection_changed)
            self._browser = AnnotationsBrowser(self.gui)
            self._browser.show_book.connect(self.open_book, type=Qt.ConnectionType.QueuedConnection)
            self._browser.open_annotation.connect(self.open_annotation, type=Qt.ConnectionType.QueuedConnection)
        return self._browser

    def show_browser(self):
        self.browser.show_dialog(self.gui.library_view.get_selected_ids(as_set=True))

    def library_changed(self, db):
        if self._browser is not None:
            self._browser.reinitialize()

    def selection_changed(self):
        if self._browser is not None:
            self._browser.selection_changed()

    def open_book(self, book_id, fmt):
        if not self.gui.library_view.select_rows({book_id}):
            db = self.gui.current_db.new_api
            title = db.field_for('title', book_id)
            return error_dialog(self._browser or self.gui, _('Not visible'), _(
                'The book "{}" is not currently visible in the calibre library.'
                ' If you have a search or a Virtual library applied, first clear'
                ' it.').format(title), show=True)

    def open_annotation(self, book_id, fmt, cfi):
        self.gui.iactions['View'].view_format_by_id(book_id, fmt, open_at=cfi)
