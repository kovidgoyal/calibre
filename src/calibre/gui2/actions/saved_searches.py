#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#
from functools import partial

from qt.core import QPoint, QIcon

from calibre.gui2.actions import InterfaceAction
from calibre.utils.icu import primary_sort_key


class SavedSearchesAction(InterfaceAction):

    name = 'Saved searches'
    action_spec = (_('Saved searches'), 'folder_saved_search.png',
                   _('Show a menu of saved searches'), '')
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
        for x in self.gui.bars_manager.main_bars + self.gui.bars_manager.child_bars:
            try:
                w = x.widgetForAction(self.qaction)
                # It seems that multiple copies of the action can exist, such as
                # when the device-connected menu is changed while the device is
                # connected. Use the one that has an actual position.
                if w.pos().x() == 0:
                    continue
                # The button might be hidden
                if not w.isVisible():
                    continue
                # The w.height() assures that the menu opens below the button.
                self.menu.exec(w.mapToGlobal(QPoint(0, w.height())))
                return
            except:
                continue
        # No visible button found. Fall back to displaying in upper left corner
        # of the library view.
        self.menu.exec(self.gui.library_view.mapToGlobal(QPoint(10, 10)))

    def about_to_show_menu(self):
        db = self.gui.current_db
        m = self.menu
        m.clear()
        submenus = {}
        for name in sorted(db.saved_search_names(), key=lambda x: primary_sort_key(x.strip())):
            components = tuple(n.strip() for n in name.split('.'))
            hierarchy = components[:-1]
            last = components[-1]
            current_menu = m
            # Walk the hierarchy, creating submenus as needed
            for i,c in enumerate(hierarchy, start=1):
                hierarchical_prefix = '.'.join(hierarchy[:i])
                if hierarchical_prefix not in submenus:
                    current_menu = current_menu.addMenu(c)
                    current_menu.setIcon(QIcon.ic('folder_saved_search.png'))
                    submenus[hierarchical_prefix] = current_menu
                else:
                    current_menu = submenus[hierarchical_prefix]
            ac = current_menu.addAction(last, partial(self.gui.search.set_search_string, 'search:"='+name+'"'))
            ac.setIcon(QIcon.ic('search.png'))

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        for action in self.menu.actions():
            action.setEnabled(enabled)
