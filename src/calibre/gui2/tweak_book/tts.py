#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
import traceback
from time import monotonic

from qt.core import QDialog, QDialogButtonBox, QHBoxLayout, QIcon, QLabel, QProgressBar, QStackedLayout, Qt, QTextBrowser, QVBoxLayout, QWidget, pyqtSignal

from calibre.db.utils import human_readable_interval
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.widgets import BusyCursor


class EngineSettingsWidget(QWidget):

    def __init__(self, parent=None):
        from calibre.gui2.tts.config import EmbeddingConfig
        super().__init__(parent)
        self.h = h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.conf = c = EmbeddingConfig(self)
        h.addWidget(c)
        self.help = q = QTextBrowser(self)
        h.addWidget(q, 10)
        q.setHtml(_('''
<h2>Add Text-to-speech narration</h2>

<p>Add an audio overlay to this book using Text-to-speech technology. Then users reading this book in a reader that supports
audio overlays, such as the calibre viewer, will be able to hear the text read to them, if they wish.

<p>You can mark different passages to be spoken by different voices as shown in the example below:

<div><code>&lt;p data-calibre-tts="{0}"&gt;This will be voiced by "{0}"&lt;/p&gt;</code></div>
<div><code>&lt;p data-calibre-tts="{1}"&gt;This will be voiced by "{1}"&lt;/p&gt;</code></div>

<p style="font-size: small">Note that generating the Text-to-speech audio will be quite slow,
at the rate of approximately one sentence per couple of seconds, depending on your computer's hardware,
so consider leave it running overnight.
''').format('cory', 'ryan'))
        self.save_settings = c.save_settings


class Progress(QWidget):

    cancel_requested: bool = False
    current_stage: str = ''
    stage_start_at: float = 0

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.v = v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addStretch(10)
        self.stage_label = la = QLabel(self)
        v.addWidget(la, alignment=Qt.AlignmentFlag.AlignCenter)
        self.bar = b = QProgressBar(self)
        v.addWidget(b)
        self.detail_label = la = QLabel(self)
        v.addWidget(la, alignment=Qt.AlignmentFlag.AlignCenter)
        self.time_left = la = QLabel(self)
        v.addWidget(la, alignment=Qt.AlignmentFlag.AlignCenter)
        v.addStretch(10)

    def __call__(self, stage: str, item: str, count: int, total: int) -> bool:
        self.stage_label.setText('<b>' + stage)
        self.detail_label.setText(item)
        self.detail_label.setVisible(bool(item))
        self.bar.setRange(0, total)
        self.bar.setValue(count)
        now = monotonic()
        if self.current_stage != stage:
            self.stage_start_at = now
            self.current_stage = stage
        if (time_elapsed := now - self.stage_start_at) >= 5:
            rate = count / time_elapsed
            time_left = (total - count) / rate
            self.time_left.setText(_('Time to complete this stage: {1}').format(stage, human_readable_interval(time_left)))
        else:
            self.time_left.setText(_('Estimating time left'))
        return self.cancel_requested


class TTSEmbed(Dialog):

    report_progress = pyqtSignal(object, object)
    worker_done = pyqtSignal(object)
    ensure_voices_downloaded_signal = pyqtSignal(object, object)

    def __init__(self, container, parent=None):
        self.container = container
        super().__init__(_('Add Text-to-speech narration'), 'tts-overlay-dialog', parent=parent)

    def setup_ui(self):
        from threading import Thread
        self.worker_thread = Thread(target=self.worker, daemon=True)
        self.worker_done.connect(self.on_worker_done, type=Qt.ConnectionType.QueuedConnection)
        self.ensure_voices_downloaded_signal.connect(self.do_ensure_voices_downloaded, type=Qt.ConnectionType.QueuedConnection)
        self.v = v = QVBoxLayout(self)
        self.engine_settings_widget = e = EngineSettingsWidget(self)
        self.stack = s = QStackedLayout()
        s.addWidget(e)
        s.setCurrentIndex(0)
        v.addLayout(s)

        self.progress = p = Progress(self)
        self.report_progress.connect(self.do_report_progress, type=Qt.ConnectionType.QueuedConnection)
        s.addWidget(p)

        self.remove_media_button = b = self.bb.addButton(_('&Remove existing audio'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setToolTip(_('Remove any exisiting audio overlays, such as a previously created Text-to-speech narration from this book'))
        b.setIcon(QIcon.ic('trash.png'))
        b.clicked.connect(self.remove_media)
        v.addWidget(self.bb)
        self.update_button_box()
        self.stack.currentChanged.connect(self.update_button_box)

    def update_button_box(self):
        if self.stack.currentIndex() == 0:
            self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            self.remove_media_button.setVisible(True)
        else:
            self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Cancel)
            self.remove_media_button.setVisible(False)

    def remove_media(self):
        from calibre.ebooks.oeb.polish.tts import remove_embedded_tts
        remove_embedded_tts(self.container)
        super().accept()

    def accept(self):
        if self.stack.currentIndex() == 0:
            self.engine_settings_widget.save_settings()
            self.stack.setCurrentIndex(1)
            self.worker_thread.start()

    def do_report_progress(self, a, kw):
        self.progress(*a, **kw)

    def worker(self):
        from calibre.ebooks.oeb.polish.tts import embed_tts
        def report_progress(*a, **kw):
            self.report_progress.emit(a, kw)
            return self.progress.cancel_requested
        try:
            err = embed_tts(self.container, report_progress, self.ensure_voices_downloaded)
        except Exception as e:
            err = e
            err.det_msg = traceback.format_exc()
        self.worker_done.emit(err)

    def ensure_voices_downloaded(self, callback):
        from queue import Queue
        queue = Queue()
        self.ensure_voices_downloaded_signal.emit(callback, queue)
        e = queue.get()
        if isinstance(e, Exception):
            raise e
        return e

    def do_ensure_voices_downloaded(self, callback, queue):
        try:
            queue.put(callback(self))
        except Exception as e:
            e.det_msg = traceback.format_exc()
            queue.put(e)

    def on_worker_done(self, err_or_ok):
        if isinstance(err_or_ok, Exception):
            error_dialog(self, _('Text-to-speech narration failed'), str(err_or_ok), det_msg=getattr(err_or_ok, 'det_msg', ''), show=True)
            return super().reject()
        return super().accept() if err_or_ok else super().reject()

    def reject(self):
        if self.stack.currentIndex() == 0:
            return super().reject()
        with BusyCursor():
            self.progress.cancel_requested = True
            self.bb.setEnabled(False)
            self.setWindowTitle(_('Cancelling, please wait...'))
            self.worker_thread.join()
        return super().reject()


def develop():
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.gui2 import Application
    path = sys.argv[-1]
    container = get_container(path, tweak_mode=True)
    app = Application([])
    d = TTSEmbed(container)
    if d.exec() == QDialog.DialogCode.Accepted:
        b, e = os.path.splitext(path)
        outpath = b + '-tts' + e
        container.commit(outpath)
        print('Output saved to:', outpath)
    del d
    del app


if __name__ == '__main__':
    develop()
