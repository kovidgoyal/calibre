#!/usr/bin/env python
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QApplication, QEvent, QObject, QPoint, Qt, pyqtSignal
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
        self.webengine_crash_message = f'The Qt WebEngine Render process crashed with termination type: {termination_type} and exit code: {exit_code}'
        prints(self.webengine_crash_message)
        if self._last_reload_at is not None and monotonic() - self._last_reload_at < 2:
            self.render_process_failed.emit()
            prints('The Qt WebEngine Render process crashed too often')
        else:
            self._last_reload_at = monotonic()
            self.reload()
            self.render_process_restarted.emit()
            prints('Restarting Qt WebEngine')


class SelectPopupFixer(QObject):
    """Prevent the popup shown for an HTML <select> element from swallowing
    the click that opened it.

    When there is not enough room for the popup between the bottom of the
    element and the bottom of the screen, the windowing system moves the popup
    up, on top of the element itself. The mouse release that completes the
    click opening the popup is then delivered to whatever item happens to lie
    under the pointer, silently changing the value of the combobox. QComboBox
    has the same problem and works around it by ignoring mouse releases for a
    short while after showing a popup under the pointer, which is what we do
    here as well."""

    # Maximum time between the click on the combobox and the popup being shown
    # for the two to be considered part of the same interaction.
    MAX_POPUP_DELAY = 1  # seconds
    # How far the pointer must move for the click to count as a drag onto an
    # item rather than a click on the combobox. Same value as QComboBox uses.
    DRAG_THRESHOLD = 9  # pixels

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.press_pos = QPoint()
        self.press_at = 0.0
        self.popup = None
        self.ignore_release_until = 0.0
        view.destroyed.connect(self.view_destroyed)
        qapp = QApplication.instance()
        if qapp is not None:
            # Mouse events go to the render widget (the view's focus proxy)
            # and the popup is a separate top level window, so we have to
            # watch events application wide.
            qapp.installEventFilter(self)

    def view_destroyed(self):
        self.view = self.popup = None
        self.ignore_release_until = 0.0
        qapp = QApplication.instance()
        if qapp is not None:
            qapp.removeEventFilter(self)

    def eventFilter(self, a0, a1):
        etype = a1.type()
        if etype in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            self.mouse_pressed(a0, a1)
        elif etype == QEvent.Type.Show:
            self.widget_shown(a0)
        elif self.ignore_release_until:
            if etype == QEvent.Type.MouseButtonRelease:
                return self.is_click_through(a0, a1)
            if etype == QEvent.Type.MouseMove and (a1.globalPosition().toPoint() - self.press_pos).manhattanLength() > self.DRAG_THRESHOLD:
                # The user is dragging onto an item rather than clicking on the
                # combobox, so the release is meaningful after all.
                self.ignore_release_until = 0.0
        return False

    def mouse_pressed(self, obj, ev):
        # A press while a popup of ours is open is the user actually choosing
        # an item, so its release must be allowed through.
        self.ignore_release_until = 0.0
        if self.view is None or ev.button() != Qt.MouseButton.LeftButton or not obj.isWidgetType():
            return
        if obj is self.view or self.view.isAncestorOf(obj):
            self.press_pos = ev.globalPosition().toPoint()
            self.press_at = monotonic()

    def widget_shown(self, obj):
        if not self.press_at or monotonic() - self.press_at > self.MAX_POPUP_DELAY or not obj.isWidgetType():
            return
        if (obj.windowFlags() & Qt.WindowType.WindowType_Mask) == Qt.WindowType.Popup:
            # The geometry of the popup is not final at this point, the
            # windowing system can still move it to fit on screen, so whether
            # it ends up under the pointer is tested when the release arrives.
            self.popup = obj
            self.ignore_release_until = monotonic() + QApplication.doubleClickInterval() / 1000
            self.press_at = 0.0

    def is_click_through(self, obj, ev):
        if self.popup is None or monotonic() > self.ignore_release_until:
            self.ignore_release_until = 0.0
            return False
        try:
            # The popup has a mouse grab, so it gets the release even when the
            # pointer is outside it, in which case the release is not a click
            # through and must be allowed to close the popup.
            if obj is not self.popup and obj is not self.popup.windowHandle():
                return False
            return self.popup.rect().contains(ev.position().toPoint())
        except RuntimeError:  # popup already destroyed
            self.popup = None
            self.ignore_release_until = 0.0
        return False
