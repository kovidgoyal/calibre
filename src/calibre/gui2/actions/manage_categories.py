#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import (QPoint)

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

    # We want to show the menu when the toolbar button is clicked. Apparently
    # the only way to do that is to scan the toolbar(s) for the action button
    # then exec the associated menu. The search is done here to take adding and
    # removing the action from toolbars into account.
    def show_menu(self):
        for x in self.gui.bars_manager.main_bars + self.gui.bars_manager.child_bars:
            try:
                w = x.widgetForAction(self.qaction)
                # It seems that multiple copies of the action can exist, such as
                # when the device-connected menu is changed while the device is
                # connected. Use the one that has an actual position.
                if w.pos().x() == 0:
                    continue
                # The w.height() assures that the menu opens below the button.
                self.menu.exec(w.mapToGlobal(QPoint(0, w.height())))
                break
            except:
                continue

    def about_to_show_menu(self):
        db = self.gui.current_db
        self.gui.populate_manage_categories_menu(db, self.menu)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        for action in self.menu.actions():
            action.setEnabled(enabled)