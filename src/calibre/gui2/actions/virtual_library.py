#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import QToolButton

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
    dont_add_to = frozenset(['context-menu-device', 'menubar-device'])

    def genesis(self):
        self.menu = m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)

    def about_to_show_menu(self):
        self.gui.build_virtual_library_menu(self.menu, add_tabs_action=False)
