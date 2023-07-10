#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley

from enum import Enum
from functools import partial
from qt.core import QIcon, QToolButton

from calibre.gui2.actions import InterfaceAction


class Panel(Enum):
    ' See gui2.init for these '
    SEARCH_BAR = 'sb'
    TAG_BROWSER = 'tb'
    BOOK_DETAILS = 'bd'
    GRID_VIEW = 'gv'
    COVER_BROWSER = 'cb'
    QUICKVIEW = 'qv'


class LayoutActions(InterfaceAction):

    name = 'Layout Actions'
    action_spec = (_('Layout actions'), 'tags.png',
                   _('Add/remove layout items: search bar, tag browser, etc.'), None)
    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset({'context-menu-device', 'menubar-device'})

    def gui_layout_complete(self):
        m = self.qaction.menu()
        m.addAction(_('Hide all'), self.hide_all)
        for button, name in zip(self.gui.layout_buttons, self.gui.button_order):
            m.addSeparator()
            ic = QIcon.ic(button.icname)
            m.addAction(ic, _('Show {}').format(button.label), partial(self.set_visible, Panel(name), True))
            m.addAction(ic, _('Hide {}').format(button.label), partial(self.set_visible, Panel(name), False))

    def _change_item(self, button, show=True):
        if button.isChecked() and not show:
            button.click()
        elif not button.isChecked() and show:
            button.click()

    def _button_from_enum(self, name: Panel):
        for q, b in zip(self.gui.button_order, self.gui.layout_buttons):
            if q == name.value:
                return b

    def set_visible(self, name: Panel, show=True):
        self._change_item(self._button_from_enum(name), show)

    def is_visible(self, name: Panel):
        self._button_from_enum(name).isChecked()

    def hide_all(self):
        for name in self.gui.button_order:
            self.set_visible(Panel(name), show=False)

    def show_all(self):
        for name in self.gui.button_order:
            self.set_visible(Panel(name), show=True)

    def button_names(self):
        names = {}
        for p in Panel:
            names[self._button_from_enum(p).label] = p
        return names
