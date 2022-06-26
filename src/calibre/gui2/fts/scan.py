#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import os
import time
from collections import deque
from qt.core import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QIcon, QLabel, QPushButton,
    QRadioButton, QVBoxLayout, QWidget, pyqtSignal
)

from calibre import detect_ncpus
from calibre.db.cache import Cache
from calibre.db.listeners import EventType
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.fts.utils import get_db
from calibre.gui2.jobs import human_readable_interval
from calibre.gui2.ui import get_gui


class IndexingProgress:

    def __init__(self):
        self.left = self.total = -1
        self.clear_rate_information()

    def __repr__(self):
        return f'IndexingProgress(left={self.left}, total={self.total})'

    def clear_rate_information(self):
        self.done_events = deque()

    def update(self, left, total):
        changed = (left, total) != (self.left, self.total)
        if changed:
            done_num = self.left - left
            if done_num:
                self.done_events.append((done_num, time.monotonic()))
                if len(self.done_events) > 50:
                    self.done_events.popleft()
        self.left, self.total = left, total
        return changed

    @property
    def complete(self):
        return not self.left or not self.total

    @property
    def almost_complete(self):
        return self.complete or (self.left / self.total) < 0.1

    @property
    def time_left(self):
        if self.left < 2:
            return _('almost done')
        if len(self.done_events) < 5:
            return _('calculating time left')
        try:
            start_time = self.done_events[0][1]
            end_time = self.done_events[-1][1]
            num_done = sum(x[0] for x in self.done_events) - self.done_events[0][0]
            rate = num_done / max(0.1, end_time - start_time)
            seconds_left = self.left / rate
            return _('~{} left').format(human_readable_interval(seconds_left))
        except Exception:
            return _('calculating time left')


class ScanProgress(QWidget):

    switch_to_search_panel = pyqtSignal()

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
            'Normally, calibre indexes books slowly, in the background,'
            ' to avoid overloading your computer. You can instead have'
            ' calibre speed up indexing. This is useful if you intend to leave your'
            ' computer running overnight to quickly finish the indexing.'
            ' Both your computer and calibre will be less responsive while'
            ' fast indexing is active.'
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
        self.switch_anyway = sa = QPushButton(self)
        sa.clicked.connect(self.switch_to_search_panel)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(sa), h.addStretch(10)
        l.addLayout(h)

    @property
    def indexing_progress(self):
        return self.parent().indexing_progress

    def change_speed(self):
        db = get_db()
        if self.fast_button.isChecked():
            db.fts_indexing_sleep_time = 0.1
            db.set_fts_num_of_workers(max(1, detect_ncpus()))
        else:
            db.fts_indexing_sleep_time = Cache.fts_indexing_sleep_time
            db.set_fts_num_of_workers(1)
        self.indexing_progress.clear_rate_information()

    def update(self, complete, left, total):
        if complete:
            t = _('All book files indexed')
            self.warn_label.setVisible(False)
            self.switch_anyway.setIcon(QIcon.ic('search.png'))
            self.switch_anyway.setText(_('Start &searching'))
        else:
            done = total - left
            p = done / (total or 1)
            p = f'{p:.0%}'
            if p == '100%':
                p = _('almost 100%')
            t = _('{0} of {1} book files, {2} have been indexed, {3}').format(done, total, p, self.indexing_progress.time_left)
            self.warn_label.setVisible(True)
            self.switch_anyway.setIcon(QIcon.ic('dialog_warning.png'))
            self.switch_anyway.setText(_('Start &searching even with incomplete indexing'))
        self.status_label.setText(t)


class ScanStatus(QWidget):

    indexing_progress_changed = pyqtSignal(bool, int, int)
    switch_to_search_panel = pyqtSignal()

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
        sc.switch_to_search_panel.connect(self.switch_to_search_panel)
        self.indexing_progress_changed.connect(self.scan_progress.update)
        l.addWidget(sc)

        l.addStretch(10)
        self.apply_fts_state()
        self.enable_fts.toggled.connect(self.change_fts_state)
        self.update_stats()
        gui = get_gui()
        if gui is None:
            self.db.add_listener(self)
        else:
            gui.add_db_listener(self.gui_update_event)

    def gui_update_event(self, db, event_type, event_data):
        if event_type is EventType.indexing_progress_changed:
            self.update_stats()

    def __call__(self, event_type, library_id, event_data):
        if event_type is EventType.indexing_progress_changed:
            self.update_stats()

    def update_stats(self):
        changed = self.indexing_progress.update(*self.db.fts_indexing_progress())
        if changed:
            self.indexing_progress_changed.emit(self.indexing_progress.complete, self.indexing_progress.left, self.indexing_progress.total)

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

    def specialize_button_box(self, bb: QDialogButtonBox):
        bb.clear()
        bb.addButton(QDialogButtonBox.StandardButton.Close)
        b = bb.addButton(_('Re-index'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('view-refresh.png'))
        b.setToolTip(_('Re-index all books in this library'))
        b.clicked.connect(self.reindex)

    def reindex(self):
        if not confirm(_(
                'This will force calibre to re-index all the books in this library, which'
                ' can take a long time. Are you sure?'), 'fts-reindex-confirm', self):
            return
        from calibre.gui2.widgets import BusyCursor
        with BusyCursor():
            self.db.reindex_fts()

    @property
    def indexing_enabled(self):
        return self.enable_fts.isChecked()

    def reset_indexing_state_for_current_db(self):
        self.enable_fts.blockSignals(True)
        self.enable_fts.setChecked(self.db.is_fts_enabled())
        self.enable_fts.blockSignals(False)
        self.update_stats()
        self.apply_fts_state()

    def startup(self):
        self.indexing_progress.clear_rate_information()

    def shutdown(self):
        self.scan_progress.slow_button.setChecked(True)
        self.reset_indexing_state_for_current_db()
        self.indexing_progress.clear_rate_information()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    d = QDialog()
    l = QVBoxLayout(d)
    bb = QDialogButtonBox(d)
    bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
    get_db.db = db(os.path.expanduser('~/test library'))
    w = ScanStatus(parent=d)
    l.addWidget(w)
    l.addWidget(bb)
    w.specialize_button_box(bb)
    d.exec()
