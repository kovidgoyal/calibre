#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley

from enum import Enum
from functools import partial
from qt.core import QToolButton

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
    action_spec = (_('Layout actions'), 'layout.png',
                   _('Add/remove layout items: search bar, tag browser, etc.'), None)
    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset({'context-menu-device', 'menubar-device'})

    def toggle_layout(self):
        self.gui.layout_container.toggle_layout()

    def gui_layout_complete(self):
        m = self.qaction.menu()
        m.aboutToShow.connect(self.populate_layout_menu)

    def populate_layout_menu(self):
        m = self.qaction.menu()
        m.clear()
        m.addAction(_('Hide all'), self.hide_all)
        for button, name in zip(self.gui.layout_buttons, self.gui.button_order):
            m.addSeparator()
            ic = button.icon()
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
        '''
        Show or hide the panel. Does nothing if the panel is already in the
        desired state.

        :param name: specifies which panel using a Panel enum
        :param show: If True, show the panel, otherwise hide the panel
        '''
        self._change_item(self._button_from_enum(name), show)

    def is_visible(self, name: Panel):
        '''
        Returns True if the panel is visible.

        :param name: specifies which panel using a Panel enum
        '''
        self._button_from_enum(name).isChecked()

    def hide_all(self):
        for name in self.gui.button_order:
            self.set_visible(Panel(name), show=False)

    def show_all(self):
        for name in self.gui.button_order:
            self.set_visible(Panel(name), show=True)

    def panel_titles(self):
        '''
        Return a dictionary of Panel Enum items to translated human readable title.
        Simplifies building dialogs, for example combo boxes of all the panel
        names or check boxes for each panel.

        :return: {Panel_enum_value: human readable title, ...}
        '''
        return {p: self._button_from_enum(p).label for p in Panel}
