#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

from functools import partial

from calibre.gui2.actions import InterfaceAction
from calibre.utils.localization import _


class OpenFolderAction(InterfaceAction):
    name = 'Open Folder'
    action_spec = (
        _('Open book folder'),
        'document_open.png',
        _("Open the folder containing the current book's files"),
        _('O'),
    )
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = _('Open book folder')

    def genesis(self):
        va = self.gui.iactions['View'].view_folder
        self.qaction.triggered.connect(va)
        a = self.create_menu_action(self.qaction.menu(), 'show-data-folder', _('Open book data folder'), icon='document_open.png', shortcut=())
        a.triggered.connect(partial(va, data_folder=True))

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)
