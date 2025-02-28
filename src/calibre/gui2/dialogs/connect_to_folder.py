#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QVBoxLayout

from calibre.gui2.widgets2 import Dialog


class ConnectToFolder(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Connect to folder'), 'connect-to-folderx', parent=parent)
        self.l = l = QVBoxLayout(self)
