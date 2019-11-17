#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.actions import InterfaceAction


class AddToLibraryAction(InterfaceAction):

    name = 'Add To Library'
    action_spec = (_('Add books to library'), 'add_book.png',
            _('Add books to your calibre library from the connected device'),
            ())
    dont_add_to = frozenset(('menubar', 'toolbar', 'context-menu', 'toolbar-child'))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.add_books_to_library)

    def location_selected(self, loc):
        enabled = loc != 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def add_books_to_library(self, *args):
        self.gui.iactions['Add Books'].add_books_from_device(
                self.gui.current_view())
