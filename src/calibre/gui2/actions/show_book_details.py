#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import Qt, sip

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.book_info import BookInfo, DialogNumbers
from calibre.gui2 import error_dialog


class ShowBookDetailsAction(InterfaceAction):

    name = 'Show Book Details'
    action_spec = (_('Book details'), 'dialog_information.png',
                   _('Show the detailed metadata for the current book in a separate window'), _('I'))
    action_shortcut_name = _('Show Book details in a separate window')
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = _('Show Book details in a separate window')

    def genesis(self):
        self.dialogs = [None, None, None]
        m = self.qaction.menu()
        self.show_info_locked = l = self.create_menu_action(m,
            'show_locked_details', _('Show Book details in a separate locked window'),
            icon='drm-locked.png', shortcut=None)
        l.triggered.connect(self.open_locked_window)
        l = self.create_menu_action(m,
            'close_all_details', _('Close all Book details windows'), icon='close.png', shortcut=None)
        l.triggered.connect(self.close_all_windows)
        self.qaction.triggered.connect(self.show_book_info)

    def show_book_info(self, *args, **kwargs):
        library_path = kwargs.get('library_path', None)
        book_id = kwargs.get('book_id', None)
        library_id = kwargs.get('library_id', None)
        locked = kwargs.get('locked', False)
        index = self.gui.library_view.currentIndex()
        if self.gui.current_view() is not self.gui.library_view and not library_path:
            error_dialog(self.gui, _('No detailed info available'),
                _('No detailed information is available for books '
                  'on the device.')).exec()
            return
        if library_path:
            dn = DialogNumbers.DetailsLink
        else:
            if not index.isValid():
                return
            dn = DialogNumbers.Locked if locked else DialogNumbers.Slaved
        if self.dialogs[dn] is not None:
            if dn == DialogNumbers.Slaved:
                # This is the slaved window. It will update automatically
                return
            else:
                # Replace the other windows. There is a signals race condition
                # between closing the existing window and opening the new one,
                # so do all the work here
                d = self.dialogs[dn]
                d.closed.disconnect(self.closed)
                d.done(0)
                self.dialogs[dn] = None
        try:
            d = BookInfo(self.gui, self.gui.library_view, index,
                    self.gui.book_details.handle_click_from_popup, dialog_number=dn,
                    library_id=library_id, library_path=library_path, book_id=book_id)
        except ValueError as e:
            error_dialog(self.gui, _('Book not found'), str(e)).exec()
            return

        d.open_cover_with.connect(self.gui.bd_open_cover_with, type=Qt.ConnectionType.QueuedConnection)
        self.dialogs[dn] = d
        d.closed.connect(self.closed, type=Qt.ConnectionType.QueuedConnection)
        d.show()

    def open_locked_window(self):
        self.show_book_info(locked=True)

    def shutting_down(self):
        self.close_all_windows()

    def close_all_windows(self):
        for dialog in [d for d in self.dialogs if d is not None]:
            dialog.done(0)

    def library_about_to_change(self, *args):
        for dialog in [d for d in self.dialogs[1:] if d is not None]:
            dialog.done(0)

    def closed(self, d):
        try:
            d.closed.disconnect(self.closed)
            self.dialogs[d.dialog_number] = None
        except ValueError:
            pass
        else:
            sip.delete(d)
            del d
