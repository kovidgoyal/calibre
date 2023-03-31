#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import Qt, sip

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.book_info import BookInfo
from calibre.gui2 import error_dialog


class ShowBookDetailsAction(InterfaceAction):

    name = 'Show Book Details'
    action_spec = (_('Show Book details'), 'dialog_information.png',
                   _('Show the detailed metadata for the current book in a separate window'), _('I'))
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.show_book_info)
        self.memory = []

    def show_book_info(self, *args, **kwargs):
        library_path = kwargs.get('library_path', None)
        book_id = kwargs.get('book_id', None)
        library_id = kwargs.get('library_id', None)
        query = kwargs.get('query', None)
        index = self.gui.library_view.currentIndex()
        if self.gui.current_view() is not self.gui.library_view and not library_path:
            error_dialog(self.gui, _('No detailed info available'),
                _('No detailed information is available for books '
                  'on the device.')).exec()
            return
        if library_path or index.isValid():
            try:
                d = BookInfo(self.gui, self.gui.library_view, index,
                        self.gui.book_details.handle_click,
                        library_id=library_id, library_path=library_path, book_id=book_id, query=query)
            except ValueError as e:
                error_dialog(self.gui, _('Book not found'), str(e)).exec()
                return

            d.open_cover_with.connect(self.gui.bd_open_cover_with, type=Qt.ConnectionType.QueuedConnection)
            self.memory.append(d)
            d.closed.connect(self.closed, type=Qt.ConnectionType.QueuedConnection)
            d.show()

    def shutting_down(self):
        for d in self.memory:
            d.close()
        self.memory = []

    def library_about_to_change(self, *args):
        for d in self.memory:
            if d.for_external_library:
                d.close()

    def closed(self, d):
        try:
            d.closed.disconnect(self.closed)
            self.memory.remove(d)
        except ValueError:
            pass
        else:
            sip.delete(d)
            del d
