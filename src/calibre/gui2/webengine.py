#!/usr/bin/env python
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import Qt, pyqtSignal
from qt.webengine import QWebEnginePage, QWebEngineView

from calibre import prints
from calibre.utils.monotonic import monotonic


class RestartingWebEngineView(QWebEngineView):

    render_process_restarted = pyqtSignal()
    render_process_failed = pyqtSignal()

    def __init__(self, parent=None):
        QWebEngineView.__init__(self, parent)
        self._last_reload_at = None
        self.renderProcessTerminated.connect(self.render_process_terminated)
        self.render_process_restarted.connect(self.reload, type=Qt.ConnectionType.QueuedConnection)

    def render_process_terminated(self, termination_type, exit_code):
        if termination_type == QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus:
            return
        self.webengine_crash_message = 'The Qt WebEngine Render process crashed with termination type: {} and exit code: {}'.format(
                termination_type, exit_code)
        prints(self.webengine_crash_message)
        if self._last_reload_at is not None and monotonic() - self._last_reload_at < 2:
            self.render_process_failed.emit()
            prints('The Qt WebEngine Render process crashed too often')
        else:
            self._last_reload_at = monotonic()
            self.render_process_restarted.emit()
            prints('Restarting Qt WebEngine')
