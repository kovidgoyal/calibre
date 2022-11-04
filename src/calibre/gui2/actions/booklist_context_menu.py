#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#

from calibre.gui2.actions import InterfaceAction


class BooklistContextMenuAction(InterfaceAction):

    name = 'Booklist context menu'
    action_spec = (_('Book list header menu'), 'context_menu.png',
                   _('Show the book list header context menu'), ())
    action_type = 'current'
    action_add_menu = False
    dont_add_to = frozenset(['context-menu-device', 'menubar-device'])

    def genesis(self):
        self.qaction.triggered.connect(self.show_context_menu)

    def show_context_menu(self):
        self.gui.library_view.show_column_header_context_menu_from_action()

    def location_selected(self, loc):
        self.qaction.setEnabled(loc == 'library')
