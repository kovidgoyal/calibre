#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
from qt.core import QDialogButtonBox, QHBoxLayout, QSize, QStackedWidget, QVBoxLayout

from calibre.gui2.fts.utils import get_db
from calibre.gui2.widgets2 import Dialog

from calibre.gui2.fts.scan import ScanStatus
from calibre.gui2.fts.search import ResultsPanel


class FTSDialog(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Search the text of all books in the library'), 'library-fts-dialog-2',
                         default_buttons=QDialogButtonBox.StandardButton.Close)

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.stack = s = QStackedWidget(self)
        l.addWidget(s)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        h.addWidget(self.bb)
        self.scan_status = ss = ScanStatus(self)
        ss.switch_to_search_panel.connect(self.show_results_panel)
        self.results_panel = rp = ResultsPanel(self)
        s.addWidget(ss), s.addWidget(rp)
        if ss.indexing_progress.almost_complete:
            self.show_results_panel()
        else:
            self.show_scan_status()

    def show_scan_status(self):
        self.stack.setCurrentWidget(self.scan_status)
        self.scan_status.specialize_button_box(self.bb)

    def show_results_panel(self):
        self.stack.setCurrentWidget(self.results_panel)
        self.results_panel.specialize_button_box(self.bb)
        self.results_panel.on_show()

    def library_changed(self):
        self.results_panel.clear_results()

    def sizeHint(self):
        return QSize(1000, 680)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    get_db.db = db(os.path.expanduser('~/test library'))
    app = Application([])
    d = FTSDialog()
    d.exec()
