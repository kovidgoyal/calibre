#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

from calibre.gui2.actions import InterfaceAction
from calibre.utils.localization import _


class RestartAction(InterfaceAction):
    name = 'Restart'
    action_spec = (_('Restart'), 'restart.png', _('Restart calibre'), 'Ctrl+R')

    def genesis(self):
        self.qaction.triggered.connect(self.restart)

    def restart(self, *args):
        self.gui.quit(restart=True)
