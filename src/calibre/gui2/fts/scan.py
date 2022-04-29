#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import (
    QCheckBox, QHBoxLayout, QLabel, QSpinBox, QTimer, QVBoxLayout, QWidget
)

from calibre import detect_ncpus
from calibre.db.fts.pool import Pool
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.fts.utils import get_db
from calibre.utils.config import dynamic


class IndexingProgress:

    def __init__(self):
        self.left = self.total = 0

    @property
    def complete(self):
        return not self.left or not self.total


class ScanProgress(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.status_label = la = QLabel('\xa0')
        la.setWordWrap(True)
        l.addWidget(la)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.niwl = la = QLabel(_('Number of workers used for indexing:'))
        h.addWidget(la)
        self.num_of_workers = n = QSpinBox(self)
        n.setMinimum(1)
        n.setMaximum(detect_ncpus())
        self.debounce_timer = t = QTimer(self)
        t.setInterval(750)
        t.timeout.connect(self.change_num_of_workers)
        t.setSingleShot(True)
        n.valueChanged.connect(self.schedule_change_num_of_workers)
        try:
            c = min(max(1, int(dynamic.get(Pool.MAX_WORKERS_PREF_NAME, 1))), n.maximum())
        except Exception:
            c = 1
        n.setValue(c)
        h.addWidget(n), h.addStretch(10)
        self.wl = la = QLabel(_(
            'Increasing the number of workers used for indexing will'
            ' speed up indexing at the cost of using more of the computer\'s resources.'
            ' Changes will take a few seconds to take effect.'
        ))
        la.setWordWrap(True)
        l.addWidget(la)
        self.warn_label = la = QLabel('<p><span style="color: red">{}</span>: {}'.format(
            _('WARNING'), _(
                'Not all the books in this library have been indexed yet.'
                ' Searching will yield incomplete results.')))
        la.setWordWrap(True)
        l.addWidget(la)

    def schedule_change_num_of_workers(self):
        self.debounce_timer.stop()
        self.debounce_timer.start()

    def change_num_of_workers(self):
        get_db().set_fts_num_of_workers(self.num_of_workers.value())

    def update(self, indexing_progress):
        if indexing_progress.complete:
            t = _('All book files indexed')
            self.warn_label.setVisible(False)
        else:
            done = indexing_progress.total - indexing_progress.left
            t = _('{0} of {1} book files ({2:.0%}) have been indexed').format(
                done, indexing_progress.total, done / indexing_progress.total)
            self.warn_label.setVisible(True)
        self.status_label.setText(t)


class ScanStatus(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.indexing_progress = IndexingProgress()
        self.l = l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)

        self.enable_fts = b = QCheckBox(self)
        b.setText(_('&Index books in this library to allow searching their full text'))
        b.setChecked(self.db.is_fts_enabled())
        l.addWidget(b)
        self.enable_msg = la = QLabel('<p>' + _(
            'In order to search the full text of books, the text must first be <i>indexed</i>. Once enabled, indexing is done'
            ' automatically, in the background, whenever new books are added to this calibre library.'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.scan_progress = sc = ScanProgress(self)
        l.addWidget(sc)

        l.addStretch(10)
        self.apply_fts_state()
        self.enable_fts.toggled.connect(self.change_fts_state)
        self.indexing_status_timer = t = QTimer(self)
        t.timeout.connect(self.update_stats)
        t.start(1000)
        self.update_stats()

    def update_stats(self):
        self.indexing_progress.left, self.indexing_progress.total = self.db.fts_indexing_progress()
        self.scan_progress.update(self.indexing_progress)

    def change_fts_state(self):
        if not self.enable_fts.isChecked() and not confirm(_(
            'Disabling indexing will mean that all books will have to be re-checked when re-enabling indexing. Are you sure?'
        ), 'disable-fts-indexing', self):
            return
        self.db.enable_fts(enabled=self.enable_fts.isChecked())
        self.apply_fts_state()

    def apply_fts_state(self):
        b = self.enable_fts
        f = b.font()
        indexing_enabled = b.isChecked()
        f.setBold(not indexing_enabled)
        b.setFont(f)
        self.enable_msg.setVisible(not indexing_enabled)
        self.scan_progress.setVisible(indexing_enabled)

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
