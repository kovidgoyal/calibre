#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
from qt.core import (
    QDialogButtonBox, QHBoxLayout, QIcon, QLabel, QSize, QStackedWidget, QVBoxLayout
)

from calibre.gui2.fts.scan import ScanStatus
from calibre.gui2.fts.search import ResultsPanel
from calibre.gui2.fts.utils import get_db
from calibre.gui2.widgets2 import Dialog


class FTSDialog(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Search the text of all books in the library'), 'library-fts-dialog-2',
                         default_buttons=QDialogButtonBox.StandardButton.Close)
        self.setWindowIcon(QIcon.ic('fts.png'))

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.stack = s = QStackedWidget(self)
        l.addWidget(s)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        self.indexing_label = il = QLabel(self)
        il.setToolTip('<p>' + _(
            'Indexing of all books in this library is not yet complete, so search results'
            ' will not be from all books. Click the show indexing status button to see details.'))
        h.addWidget(il), h.addStretch(), h.addWidget(self.bb)
        self.scan_status = ss = ScanStatus(self)
        ss.switch_to_search_panel.connect(self.show_results_panel)
        self.results_panel = rp = ResultsPanel(self)
        rp.switch_to_scan_panel.connect(self.show_scan_status)
        s.addWidget(ss), s.addWidget(rp)
        self.show_appropriate_panel()
        self.update_indexing_label()
        self.scan_status.indexing_progress_changed.connect(self.update_indexing_label)

    def show_appropriate_panel(self):
        ss = self.scan_status
        if ss.indexing_enabled and ss.indexing_progress.almost_complete:
            self.show_results_panel()
        else:
            self.show_scan_status()

    def update_indexing_label(self):
        ip = self.scan_status.indexing_progress
        if self.stack.currentWidget() is self.scan_status or ip.complete:
            self.indexing_label.setVisible(False)
        else:
            self.indexing_label.setVisible(True)
            try:
                p = (ip.total - ip.left) / ip.total
            except Exception:
                self.indexing_label.setVisible(False)
            else:
                if p < 1:
                    q = f'{p:.0%}'
                    t = _('Indexing is almost complete') if q == '100%' else _('Indexing is only {} done').format(q)
                    ss = ''
                    if p < 0.9:
                        ss = 'QLabel { color: red }'
                    self.indexing_label.setStyleSheet(ss)
                    self.indexing_label.setText(t)
                else:
                    self.indexing_label.setVisible(False)

    def show_scan_status(self):
        self.stack.setCurrentWidget(self.scan_status)
        self.scan_status.specialize_button_box(self.bb)
        self.update_indexing_label()

    def show_results_panel(self):
        self.stack.setCurrentWidget(self.results_panel)
        self.results_panel.specialize_button_box(self.bb)
        self.update_indexing_label()
        self.results_panel.on_show()

    def library_changed(self):
        self.results_panel.clear_results()
        self.scan_status.reset_indexing_state_for_current_db()
        self.show_appropriate_panel()

    def sizeHint(self):
        return QSize(1000, 680)

    def show(self):
        super().show()
        self.scan_status.startup()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    get_db.db = db(os.path.expanduser('~/test library'))
    app = Application([])
    d = FTSDialog()
    d.exec()
