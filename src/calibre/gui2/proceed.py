#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import namedtuple

from qt.core import (
    QWidget, Qt, QLabel, QVBoxLayout, QDialogButtonBox, QApplication, QTimer, QPixmap, QEvent,
    QSize, pyqtSignal, QIcon, QPlainTextEdit, QCheckBox, QPainter, QHBoxLayout, QFontMetrics,
    QPainterPath, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve, QSizePolicy, QImage, QPalette)

from calibre.constants import __version__
from calibre.gui2.dialogs.message_box import ViewLog

Question = namedtuple('Question', 'payload callback cancel_callback '
        'title msg html_log log_viewer_title log_is_file det_msg '
        'show_copy_button checkbox_msg checkbox_checked action_callback '
        'action_label action_icon focus_action show_det show_ok icon '
        'log_viewer_unique_name')


class Icon(QWidget):

    @pyqtProperty(float)
    def fraction(self):
        return self._fraction

    @fraction.setter
    def fraction(self, val):
        self._fraction = max(0, min(2, float(val)))
        self.update()

    def showEvent(self, ev):
        self.animation.start()
        return QWidget.showEvent(self, ev)

    def hideEvent(self, ev):
        self.animation.stop()
        return QWidget.hideEvent(self, ev)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_icon('dialog_question.png')
        self.default_icon = self.icon
        self._fraction = 0.0
        self.animation = a = QPropertyAnimation(self, b"fraction", self)
        a.setDuration(2000), a.setEasingCurve(QEasingCurve.Type.Linear)
        a.setStartValue(0.0), a.setEndValue(2.0), a.setLoopCount(10)

    def set_icon(self, icon):
        if isinstance(icon, QIcon):
            self.icon = icon.pixmap(self.sizeHint())
        elif icon is None:
            self.icon = self.default_icon
        else:
            self.icon = QIcon.ic(icon).pixmap(self.sizeHint())
        self.update()

    def sizeHint(self):
        return QSize(64, 64)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setOpacity(min(1, abs(1 - self._fraction)))
        p.drawPixmap(self.rect(), self.icon)
        p.end()


class PlainTextEdit(QPlainTextEdit):

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        ans = QPlainTextEdit.sizeHint(self)
        ans.setWidth(fm.averageCharWidth() * 50)
        return ans


class ProceedQuestion(QWidget):

    ask_question = pyqtSignal(object, object, object)

    @pyqtProperty(float)
    def show_fraction(self):
        return self._show_fraction

    @show_fraction.setter
    def show_fraction(self, val):
        self._show_fraction = max(0, min(1, float(val)))
        self.update()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setVisible(False)
        parent.installEventFilter(self)

        self._show_fraction = 0.0
        self.show_animation = a = QPropertyAnimation(self, b"show_fraction", self)
        a.setDuration(1000), a.setEasingCurve(QEasingCurve.Type.OutQuad)
        a.setStartValue(0.0), a.setEndValue(1.0)
        a.finished.connect(self.stop_show_animation)
        self.rendered_pixmap = None

        self.questions = []

        self.icon = ic = Icon(self)
        self.msg_label = msg = QLabel('some random filler text')
        msg.setWordWrap(True)
        self.bb = QDialogButtonBox()
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.log_button = self.bb.addButton(_('View log'), QDialogButtonBox.ButtonRole.ActionRole)
        self.log_button.setIcon(QIcon.ic('debug.png'))
        self.log_button.clicked.connect(self.show_log)
        self.copy_button = self.bb.addButton(_('&Copy to clipboard'),
                QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.action_button = self.bb.addButton('', QDialogButtonBox.ButtonRole.ActionRole)
        self.action_button.clicked.connect(self.action_clicked)
        self.show_det_msg = _('Show &details')
        self.hide_det_msg = _('Hide &details')
        self.det_msg_toggle = self.bb.addButton(self.show_det_msg, QDialogButtonBox.ButtonRole.ActionRole)
        self.det_msg_toggle.clicked.connect(self.toggle_det_msg)
        self.det_msg_toggle.setToolTip(
                _('Show detailed information about this error'))
        self.det_msg = PlainTextEdit(self)
        self.det_msg.setReadOnly(True)
        self.bb.setStandardButtons(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No | QDialogButtonBox.StandardButton.Ok)
        self.bb.button(QDialogButtonBox.StandardButton.Yes).setDefault(True)
        self.title_label = title = QLabel('A dummy title')
        f = title.font()
        f.setBold(True)
        title.setFont(f)

        self.checkbox = QCheckBox('', self)

        self._l = l = QVBoxLayout(self)
        self._h = h = QHBoxLayout()
        self._v = v = QVBoxLayout()
        v.addWidget(title), v.addWidget(msg)
        h.addWidget(ic), h.addSpacing(10), h.addLayout(v), l.addLayout(h)
        l.addSpacing(5)
        l.addWidget(self.checkbox)
        l.addWidget(self.det_msg)
        l.addWidget(self.bb)

        self.ask_question.connect(self.do_ask_question,
                type=Qt.ConnectionType.QueuedConnection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for child in self.findChildren(QWidget):
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFocusProxy(self.parent())
        self.resize_timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(100), t.timeout.connect(self.parent_resized)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize and self.isVisible():
            self.resize_timer.start()
        return False

    def parent_resized(self):
        if self.isVisible():
            self.do_resize()

    def copy_to_clipboard(self, *args):
        QApplication.clipboard().setText(
                'calibre, version %s\n%s: %s\n\n%s' %
                (__version__, str(self.windowTitle()),
                    str(self.msg_label.text()),
                    str(self.det_msg.toPlainText())))
        self.copy_button.setText(_('Copied'))

    def action_clicked(self):
        if self.questions:
            q = self.questions[0]
            self.questions[0] = q._replace(callback=q.action_callback)
        self.accept()

    def accept(self):
        if self.questions:
            payload, callback, cancel_callback = self.questions[0][:3]
            self.questions = self.questions[1:]
            cb = None
            if self.checkbox.isVisible():
                cb = bool(self.checkbox.isChecked())
            self.ask_question.emit(callback, payload, cb)
        self.hide()

    def reject(self):
        if self.questions:
            payload, callback, cancel_callback = self.questions[0][:3]
            self.questions = self.questions[1:]
            cb = None
            if self.checkbox.isVisible():
                cb = bool(self.checkbox.isChecked())
            self.ask_question.emit(cancel_callback, payload, cb)
        self.hide()

    def do_ask_question(self, callback, payload, checkbox_checked):
        if callable(callback):
            args = [payload]
            if checkbox_checked is not None:
                args.append(checkbox_checked)
            callback(*args)
        self.show_question()

    def toggle_det_msg(self, *args):
        vis = str(self.det_msg_toggle.text()) == self.hide_det_msg
        self.det_msg_toggle.setText(self.show_det_msg if vis else
                self.hide_det_msg)
        self.det_msg.setVisible(not vis)
        self.do_resize()

    def do_resize(self):
        sz = self.sizeHint()
        sz.setWidth(min(self.parent().width(), sz.width()))
        sb = self.parent().statusBar().height() + 10
        sz.setHeight(min(self.parent().height() - sb, sz.height()))
        self.resize(sz)
        self.position_widget()

    def show_question(self):
        if not self.questions:
            return
        if not self.isVisible():
            question = self.questions[0]
            self.msg_label.setText(question.msg)
            self.icon.set_icon(question.icon)
            self.title_label.setText(question.title)
            self.log_button.setVisible(bool(question.html_log))
            self.copy_button.setText(_('&Copy to clipboard'))
            if question.action_callback is not None:
                self.action_button.setText(question.action_label or '')
                self.action_button.setIcon(
                    QIcon() if question.action_icon is None else question.action_icon)
            # Force the button box to relayout its buttons, as button text
            # might have changed
            self.bb.setOrientation(Qt.Orientation.Vertical), self.bb.setOrientation(Qt.Orientation.Horizontal)
            self.det_msg.setPlainText(question.det_msg or '')
            self.det_msg.setVisible(False)
            self.det_msg_toggle.setVisible(bool(question.det_msg))
            self.det_msg_toggle.setText(self.show_det_msg)
            self.checkbox.setVisible(question.checkbox_msg is not None)
            if question.checkbox_msg is not None:
                self.checkbox.setText(question.checkbox_msg)
                self.checkbox.setChecked(question.checkbox_checked)
            self.bb.button(QDialogButtonBox.StandardButton.Ok).setVisible(question.show_ok)
            self.bb.button(QDialogButtonBox.StandardButton.Yes).setVisible(not question.show_ok)
            self.bb.button(QDialogButtonBox.StandardButton.No).setVisible(not question.show_ok)
            self.copy_button.setVisible(bool(question.show_copy_button))
            self.action_button.setVisible(question.action_callback is not None)
            self.toggle_det_msg() if question.show_det else self.do_resize()
            self.show_widget()
            button = self.action_button if question.focus_action and question.action_callback is not None else \
                (self.bb.button(QDialogButtonBox.StandardButton.Ok) if question.show_ok else self.bb.button(QDialogButtonBox.StandardButton.Yes))
            button.setDefault(True)
            self.raise_()
            self.start_show_animation()

    def start_show_animation(self):
        if self.rendered_pixmap is not None:
            return

        dpr = getattr(self, 'devicePixelRatioF', self.devicePixelRatio)()
        p = QImage(dpr * self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        p.setDevicePixelRatio(dpr)
        # For some reason, Qt scrolls the book view when rendering this widget,
        # for the very first time, so manually preserve its position
        pr = getattr(self.parent(), 'library_view', None)
        if not hasattr(pr, 'preserve_state'):
            self.render(p)
        else:
            with pr.preserve_state():
                self.render(p)
        self.rendered_pixmap = QPixmap.fromImage(p)
        self.original_visibility = v = []
        for child in self.findChildren(QWidget):
            if child.isVisible():
                child.setVisible(False)
                v.append(child)
        self.show_animation.start()

    def stop_show_animation(self):
        self.rendered_pixmap = None
        [c.setVisible(True) for c in getattr(self, 'original_visibility', ())]
        self.update()
        for child in self.findChildren(QWidget):
            child.update()
            if hasattr(child, 'viewport'):
                child.viewport().update()

    def position_widget(self):
        geom = self.parent().geometry()
        x = geom.width() - self.width() - 5
        sb = self.parent().statusBar()
        if sb is None:
            y = geom.height() - self.height()
        else:
            y = sb.geometry().top() - self.height()
        self.move(x, y)

    def show_widget(self):
        self.show()
        self.position_widget()

    def dummy_question(self, action_label=None):
        self(lambda *args:args, (), 'dummy log', 'Log Viewer', 'A Dummy Popup',
             'This is a dummy popup to easily test things, with a long line of text that should wrap. '
             'This is a dummy popup to easily test things, with a long line of text that should wrap',
             checkbox_msg='A dummy checkbox',
             action_callback=lambda *args: args, action_label=action_label or 'An action')

    def __call__(self, callback, payload, html_log, log_viewer_title, title,
            msg, det_msg='', show_copy_button=False, cancel_callback=None,
            log_is_file=False, checkbox_msg=None, checkbox_checked=False,
            action_callback=None, action_label=None, action_icon=None, focus_action=False,
            show_det=False, show_ok=False, icon=None, log_viewer_unique_name=None, **kw):
        '''
        A non modal popup that notifies the user that a background task has
        been completed. This class guarantees that only a single popup is
        visible at any one time. Other requests are queued and displayed after
        the user dismisses the current popup.

        :param callback: A callable that is called with payload if the user
        asks to proceed. Note that this is always called in the GUI thread.
        :param cancel_callback: A callable that is called with the payload if
        the users asks not to proceed.
        :param payload: Arbitrary object, passed to callback
        :param html_log: An HTML or plain text log
        :param log_viewer_title: The title for the log viewer window
        :param title: The title for this popup
        :param msg: The msg to display
        :param det_msg: Detailed message
        :param log_is_file: If True the html_log parameter is interpreted as
                            the path to a file on disk containing the log
                            encoded with utf-8
        :param checkbox_msg: If not None, a checkbox is displayed in the
                             dialog, showing this message. The callback is
                             called with both the payload and the state of the
                             checkbox as arguments.
        :param checkbox_checked: If True the checkbox is checked by default.
        :param action_callback: If not None, an extra button is added, which
                                when clicked will cause action_callback to be called
                                instead of callback. action_callback is called in
                                exactly the same way as callback.
        :param action_label: The text on the action button
        :param action_icon: The icon for the action button, must be a QIcon object or None
        :param focus_action: If True, the action button will be focused instead of the Yes button
        :param show_det: If True, the Detailed message will be shown initially
        :param show_ok: If True, OK will be shown instead of YES/NO
        :param icon: The icon to be used for this popop (defaults to question mark). Can be either a QIcon or a string to be used with QIcon.ic()
        :log_viewer_unique_name: If set, ViewLog will remember/reuse its size for this name in calibre.gui2.gprefs
        '''
        question = Question(
            payload, callback, cancel_callback, title, msg, html_log,
            log_viewer_title, log_is_file, det_msg, show_copy_button,
            checkbox_msg, checkbox_checked, action_callback, action_label,
            action_icon, focus_action, show_det, show_ok, icon, log_viewer_unique_name)
        self.questions.append(question)
        self.show_question()

    def show_log(self):
        if self.questions:
            q = self.questions[0]
            log = q.html_log
            if q.log_is_file:
                with open(log, 'rb') as f:
                    log = f.read().decode('utf-8')
            self.log_viewer = ViewLog(q.log_viewer_title, log,
                        parent=self, unique_name=q.log_viewer_unique_name)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        try:
            if self.rendered_pixmap is None:
                self.paint_background(painter)
            else:
                self.animated_paint(painter)
        finally:
            painter.end()

    def animated_paint(self, painter):
        top = (1 - self._show_fraction) * self.height()
        painter.drawPixmap(0, int(top), self.rendered_pixmap)

    def paint_background(self, painter):
        br = 12  # border_radius
        bw = 1  # border_width
        pal = self.palette()
        c = pal.color(QPalette.ColorRole.Window)
        c.setAlphaF(0.9)
        p = QPainterPath()
        p.addRoundedRect(QRectF(self.rect()), br, br)
        painter.fillPath(p, c)
        p.addRoundedRect(QRectF(self.rect()).adjusted(bw, bw, -bw, -bw), br, br)
        painter.fillPath(p, pal.color(QPalette.ColorRole.WindowText))


def main():
    from calibre.gui2 import Application
    from qt.core import QMainWindow, QStatusBar, QTimer
    app = Application([])
    w = QMainWindow()
    s = QStatusBar(w)
    w.setStatusBar(s)
    s.showMessage('Testing ProceedQuestion')
    w.show()
    p = ProceedQuestion(w)

    def doit():
        p.dummy_question()
        p.dummy_question(action_label='A very long button for testing relayout (indeed)')
        p(
            lambda p:None, None, 'ass2', 'ass2', 'testing2', 'testing2',
            det_msg='details shown first, with a long line to test wrapping of text and width layout',
            show_det=True, show_ok=True)
    QTimer.singleShot(10, doit)
    app.exec()


if __name__ == '__main__':
    main()
