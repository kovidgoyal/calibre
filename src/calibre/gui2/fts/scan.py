#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
from qt.core import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QRadioButton, QTimer, QVBoxLayout,
    QWidget
)

from calibre import detect_ncpus
from calibre.db.cache import Cache
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.fts.utils import get_db


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
        self.wl = la = QLabel(_(
            'Normally, calibre indexes books slowly in the background,'
            ' to avoid overloading your computer. You can instead ask'
            ' calibre to speed up indexing, if you intend to leave your'
            ' computer running overnight or similar to quickly finish the indexing.'
            ' Doing so will likely make both calibre and your computer less responsive,'
            ' while the fast indexing is running.'
        ))
        la.setWordWrap(True)
        l.addWidget(la)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(QLabel(_('Indexing speed:')))
        self.slow_button = sb = QRadioButton(_('&Slow'), self)
        sb.setChecked(True)
        h.addWidget(sb)
        self.fast_button = fb = QRadioButton(_('&Fast'), self)
        h.addWidget(fb)
        fb.toggled.connect(self.change_speed)
        h.addStretch(10)

        l.addStretch(10)
        self.warn_label = la = QLabel('<p><span style="color: red">{}</span>: {}'.format(
            _('WARNING'), _(
                'Not all the books in this library have been indexed yet.'
                ' Searching will yield incomplete results.')))
        la.setWordWrap(True)
        l.addWidget(la)

    def change_speed(self):
        db = get_db()
        if self.fast_button.isChecked():
            db.fts_indexing_sleep_time = 0.1
            db.set_fts_num_of_workers(max(1, detect_ncpus()))
        else:
            db.fts_indexing_sleep_time = Cache.fts_indexing_sleep_time
            db.set_fts_num_of_workers(1)

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
        if isinstance(parent, QDialog):
            parent.finished.connect(self.shutdown)
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

    def shutdown(self):
        self.indexing_status_timer.stop()
        self.scan_progress.slow_button.setChecked(True)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    get_db.db = db(os.path.expanduser('~/test library'))
    app = Application([])
    w = ScanStatus()
    w.show()
    app.exec_()
    w.shutdown()
