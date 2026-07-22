#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

from qt.core import QUrl

from calibre.gui2 import open_url
from calibre.gui2.actions import InterfaceAction
from calibre.utils.localization import _, localize_user_manual_link


class HelpAction(InterfaceAction):
    name = 'Help'
    action_spec = (
        _('Help'),
        'help.png',
        _('Browse the calibre User Manual'),
        _('F1'),
    )

    def genesis(self):
        self.qaction.triggered.connect(self.show_help)

    def show_help(self, *args):
        open_url(QUrl(localize_user_manual_link('https://manual.calibre-ebook.com')))
