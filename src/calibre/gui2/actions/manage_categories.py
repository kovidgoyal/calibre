#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#
from qt.core import QToolButton

from calibre.gui2.actions import InterfaceAction


class ManageCategoriesAction(InterfaceAction):

    name = 'Manage categories'
    action_spec = (_('Manage categories'), 'tags.png',
                   _('Manage categories: authors, tags, series, etc.'), '')
    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset(['context-menu-device', 'menubar-device'])

    def genesis(self):
        self.menu = m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)

    def about_to_show_menu(self):
        db = self.gui.current_db
        self.gui.populate_manage_categories_menu(db, self.menu)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        for action in self.menu.actions():
            action.setEnabled(enabled)
