#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import QCheckBox, QVBoxLayout, QWidget

from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.fts.utils import get_db


class ScanStatus(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)

        self.enable_fts = b = QCheckBox(self)
        b.setText(_('Index books in this library to allow searching their full text'))
        l.addWidget(b)
        self.apply_fts_state()
        b.toggled.connect(self.change_fts_state)

    def change_fts_state(self):
        if not self.enable_fts.isChecked():
            if not confirm(_('Disabling indexing will mean that all books will have to be re-scanned when re-enabling indexing.'
                             ' Are you sure?'), 'disable-fts-indexing', self):
                return
        self.db.enable_fts(enabled=self.enable_fts.isChecked())
        self.apply_fts_state()

    def apply_fts_state(self):
        b = self.enable_fts
        f = b.font()
        f.setBold(not b.isChecked())
        b.setFont(f)

    @property
    def db(self):
        return get_db()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    get_db.db = db(os.path.expanduser('~/test library'))
    app = Application([])
    w = ScanStatus()
    w.show()
    app.exec_()
