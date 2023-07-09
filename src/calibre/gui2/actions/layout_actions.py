#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#

from functools import partial

from qt.core import QIcon, QToolButton

from calibre.gui2.actions import InterfaceAction


class LayoutActions(InterfaceAction):

    name = 'Layout Actions'
    action_spec = (_('Layout Actions'), 'tags.png',
                   _('Add/remove layout items: search bar, tag browser, etc.'), None)
    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset(['context-menu-device', 'menubar-device'])

    # The button names used by change_item_by_name() come from gui2.init. They are
    # 'sb' => Search Bar
    # 'tb' => Tag Browser
    # 'bd' => Book Details
    # 'gv' => Grid View
    # 'cb' => Cover Browser
    # 'qv' => QuickView

    def gui_layout_complete(self):
        m = self.qaction.menu()
        self.button_names = {}
        m.addAction(_('Hide all'), self.hide_all)
        for i,b in enumerate(self.gui.layout_buttons):
            m.addSeparator()
            self.button_names[self.gui.button_order[i]] = b
            ic = QIcon.ic(b.icname)
            m.addAction(ic, _('Show ') + b.label, partial(self.change_item, b, True))
            m.addAction(ic, _('Hide ') + b.label, partial(self.change_item, b, False))

    def change_item(self, button, show=True):
        if button.isChecked() and not show:
            button.click()
        elif not button.isChecked() and show:
            button.click()

    def change_item_by_name(self, name, show=True):
        self.change_item(self.button_names[name], show)

    def hide_all(self):
        for name in self.button_names:
            self.change_item_by_name(name, show=False)