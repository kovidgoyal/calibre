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
        self.dialogs = [None, ]

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
            # Window #0 is slaved to changes in the book list. As such
            # it must not be used for details from other libraries.
            for dn,v in enumerate(self.dialogs):
                if dn == 0 and library_path:
                    continue
                if v is None:
                    break
            else:
                self.dialogs.append(None)
                dn += 1

            try:
                d = BookInfo(self.gui, self.gui.library_view, index,
                        self.gui.book_details.handle_click, dialog_number=dn,
                        library_id=library_id, library_path=library_path, book_id=book_id, query=query)
            except ValueError as e:
                error_dialog(self.gui, _('Book not found'), str(e)).exec()
                return

            d.open_cover_with.connect(self.gui.bd_open_cover_with, type=Qt.ConnectionType.QueuedConnection)
            self.dialogs[dn] = d
            d.closed.connect(self.closed, type=Qt.ConnectionType.QueuedConnection)
            d.show()

    def shutting_down(self):
        for d in self.dialogs:
            if d:
                d.done(0)

    def library_about_to_change(self, *args):
        for i,d in enumerate(self.dialogs):
            if i == 0:
                continue
            if d:
                d.done(0)

    def closed(self, d):
        try:
            d.closed.disconnect(self.closed)
            self.dialogs[d.dialog_number] = None
        except ValueError:
            pass
        else:
            sip.delete(d)
            del d
