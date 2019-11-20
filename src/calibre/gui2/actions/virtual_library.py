#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from PyQt5.Qt import QToolButton, QAction

from calibre.gui2.actions import InterfaceAction


class VirtualLibraryAction(InterfaceAction):

    name = 'Virtual library'
    action_spec = (
        _('Virtual library'), 'vl.png', _('Change the current Virtual library'),
        None
    )
    action_type = 'current'
    action_add_menu = True
    popup_type = QToolButton.InstantPopup
    dont_add_to = frozenset(('context-menu-device', 'menubar-device'))

    def genesis(self):
        self.menu = m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)
        self.qs_action = QAction(self.gui)
        self.gui.addAction(self.qs_action)
        self.qs_action.triggered.connect(self.gui.choose_vl_triggerred)
        self.gui.keyboard.register_shortcut(self.unique_name + ' - ' + 'quick-select-vl',
            _('Quick select Virtual library'), default_keys=('Ctrl+T',),
            action=self.qs_action, description=_('Quick select a Virtual library'),
            group=self.action_spec[0])

    def about_to_show_menu(self):
        self.gui.build_virtual_library_menu(self.menu, add_tabs_action=False)
