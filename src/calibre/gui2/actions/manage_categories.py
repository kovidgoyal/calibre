#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#

from calibre.gui2.actions import InterfaceAction


class ManageCategoriesAction(InterfaceAction):

    name = 'Manage categories'
    action_spec = (_('Manage categories'), 'tags.png',
                   _('Manage categories: authors, tags, series, etc.'), '')
    action_type = 'current'
    action_add_menu = True
    dont_add_to = frozenset(['context-menu-device', 'menubar-device'])

    def genesis(self):
        self.menu = m = self.qaction.menu()
        self.qaction.triggered.connect(self.show_menu)
        m.aboutToShow.connect(self.about_to_show_menu)

    # We want to show the menu when a toolbar button is clicked. Apparently
    # the only way to do that is to scan the toolbar(s) for the action button
    # then exec the associated menu. The search is done here to take adding and
    # removing the action from toolbars into account.
    #
    # If a shortcut is triggered and there isn't a toolbar button visible then
    # show the menu in the upper left corner of the library view pane. Yes, this
    # is a bit weird but it works as well as a popping up a dialog.
    def show_menu(self):
        from calibre.gui2.actions.saved_searches import show_menu_under_widget
        show_menu_under_widget(self.gui, self.menu, self.qaction, self.name)

    def about_to_show_menu(self):
        db = self.gui.current_db
        self.gui.populate_manage_categories_menu(db, self.menu)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        for action in self.menu.actions():
            action.setEnabled(enabled)
