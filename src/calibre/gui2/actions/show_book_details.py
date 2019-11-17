#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import Qt
try:
    from PyQt5 import sip
except ImportError:
    import sip

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

    def show_book_info(self, *args):
        if self.gui.current_view() is not self.gui.library_view:
            error_dialog(self.gui, _('No detailed info available'),
                _('No detailed information is available for books '
                  'on the device.')).exec_()
            return
        index = self.gui.library_view.currentIndex()
        if index.isValid():
            d = BookInfo(self.gui, self.gui.library_view, index,
                    self.gui.book_details.handle_click)
            d.open_cover_with.connect(self.gui.bd_open_cover_with, type=Qt.QueuedConnection)
            self.memory.append(d)
            d.closed.connect(self.closed, type=Qt.QueuedConnection)
            d.show()

    def closed(self, d):
        try:
            d.closed.disconnect(self.closed)
            self.memory.remove(d)
        except ValueError:
            pass
        else:
            sip.delete(d)
            del d
