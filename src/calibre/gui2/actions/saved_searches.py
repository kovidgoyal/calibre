#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#

from qt.core import QPoint, QMenu, QToolButton

from calibre.gui2.actions import InterfaceAction


def show_menu_under_widget(gui, menu, action, name):
    # First try the tool bar
    for x in gui.bars_manager.bars:
        try:
            w = x.widgetForAction(action)
            # It seems that multiple copies of the action can exist, such as
            # when the device-connected menu is changed while the device is
            # connected. Use the one that has an actual position.
            if w is None or w.pos().x() == 0:
                continue
            # The button might be hidden
            if not w.isVisible():
                continue
            # The w.height() assures that the menu opens below the button.
            menu.exec(w.mapToGlobal(QPoint(0, w.height())))
            return
        except Exception:
            continue
    # Now try the menu bar
    for x in gui.bars_manager.menu_bar.added_actions:
        # This depends on no two menus with the same name.
        # I don't know if this works on a Mac
        if x.text() == name:
            try:
                # The menu item might be hidden
                if not x.isVisible():
                    continue
                # We can't use x.trigger() because it doesn't put the menu
                # in the right place. Instead get the position of the menu
                # widget on the menu bar
                p = x.parent().menu_bar
                r = p.actionGeometry(x)
                # Make sure that the menu item is actually displayed in the menu
                # and not the overflow
                if p.geometry().width() < (r.x() + r.width()):
                    continue
                # Show the menu under the name in the menu bar
                menu.exec(p.mapToGlobal(QPoint(r.x()+2, r.height()-2)))
                return
            except Exception:
                continue
    # No visible button found. Fall back to displaying in upper left corner
    # of the library view.
    menu.exec(gui.library_view.mapToGlobal(QPoint(10, 10)))


class SavedSearchesAction(InterfaceAction):

    name = 'Saved searches'
    action_spec = (_('Saved searches'), 'folder_saved_search.png',
                   _('Show a menu of saved searches'), None)
    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset(('context-menu-device', 'menubar-device'))

    def genesis(self):
        self.menu = m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)

        # Create a "hidden" menu that can have a shortcut.
        self.hidden_menu = QMenu()
        self.shortcut_action = self.create_menu_action(
                        menu=self.hidden_menu,
                        unique_name='Saved searches',
                        text=_('Show a menu of saved searches'),
                        icon='folder_saved_search.png',
                        triggered=self.show_menu)

    # We want to show the menu when a shortcut is used. Apparently the only way
    # to do that is to scan the toolbar(s) for the action button then exec the
    # associated menu. The search is done here to take adding and removing the
    # action from toolbars into account.
    #
    # If a shortcut is triggered and there isn't a toolbar button visible then
    # show the menu in the upper left corner of the library view pane. Yes, this
    # is a bit weird but it works as well as a popping up a dialog.
    def show_menu(self):
        show_menu_under_widget(self.gui, self.menu, self.qaction, self.name)

    def about_to_show_menu(self):
        self.gui.populate_add_saved_search_menu(to_menu=self.menu)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        for action in self.menu.actions():
            action.setEnabled(enabled)
