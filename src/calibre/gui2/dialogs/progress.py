#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal kovid@kovidgoyal.net

from typing import TYPE_CHECKING

from qt.core import QApplication, QDialog, QDialogButtonBox, QFont, QFontMetrics, QHBoxLayout, QIcon, QLabel, QProgressBar, QSize, Qt, QVBoxLayout, pyqtSignal

from calibre.gui2 import elided_text, question_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QKeyEvent, QWidget


class ProgressDialog(QDialog):
    canceled_signal = pyqtSignal()

    def __init__(
        self,
        title: str,
        msg: str = '\u00a0',
        min: int = 0,
        max: int = 99,
        parent: QWidget | None = None,
        cancelable: bool = True,
        icon: QIcon | str | None = None,
        cancel_confirm_msg: str = '',
    ) -> None:
        QDialog.__init__(self, parent)
        self.cancel_confirm_msg = cancel_confirm_msg
        if icon is None:
            self.l = l = QVBoxLayout(self)
        else:
            self.h = h = QHBoxLayout(self)
            self.icon = i = QLabel(self)
            if not isinstance(icon, QIcon):
                icon = QIcon.ic(icon)
            i.setPixmap(icon.pixmap(64))
            h.addWidget(i, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            self.l = l = QVBoxLayout()
            h.addLayout(l)
            self.setWindowIcon(icon)

        self.title_label = t = QLabel(title)
        self.setWindowTitle(title)
        (
            t.setStyleSheet('QLabel { font-weight: bold }'),
            t.setAlignment(Qt.AlignmentFlag.AlignCenter),
            t.setTextFormat(Qt.TextFormat.PlainText),
        )
        l.addWidget(t)

        self.bar = b = QProgressBar(self)
        b.setMinimum(min), b.setMaximum(max), b.setValue(min)
        l.addWidget(b)

        self.message = m = QLabel(self)
        fm = QFontMetrics(self.font())
        (
            m.setAlignment(Qt.AlignmentFlag.AlignCenter),
            m.setMinimumWidth(fm.averageCharWidth() * 80),
            m.setTextFormat(Qt.TextFormat.PlainText),
        )
        l.addWidget(m)
        self.msg = msg

        self.button_box = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Abort, self)
        bb.rejected.connect(self._canceled)
        l.addWidget(bb)

        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.canceled = False

        if not cancelable:
            bb.setVisible(False)
        self.cancelable = cancelable
        self.resize(self.sizeHint())

    def set_msg(self, msg: str = '') -> None:
        self.msg = msg

    def set_value(self, val: int) -> None:
        self.value = val

    @property
    def value(self) -> int:
        return self.bar.value()

    @value.setter
    def value(self, val: int) -> None:
        self.bar.setValue(val)

    def set_min(self, min: int) -> None:
        self.min = min

    def set_max(self, max: int) -> None:
        self.max = max

    @property
    def max(self) -> int:
        return self.bar.maximum()

    @max.setter
    def max(self, val: int) -> None:
        self.bar.setMaximum(val)

    @property
    def min(self) -> int:
        return self.bar.minimum()

    @min.setter
    def min(self, val: int) -> None:
        self.bar.setMinimum(val)

    @property
    def title(self) -> str:
        return self.title_label.text()

    @title.setter
    def title(self, val: str | None) -> None:
        self.title_label.setText(str(val or ''))

    @property
    def msg(self) -> str:
        return self.message.text()

    @msg.setter
    def msg(self, val: str | None) -> None:
        val = str(val or '')
        self.message.setText(elided_text(val, self.font(), self.message.minimumWidth() - 10))

    def _canceled(self, *args: object) -> None:
        if self.cancel_confirm_msg:
            if not question_dialog(
                self,
                _('Are you sure?'),
                self.cancel_confirm_msg,
                override_icon='dialog_warning.png',
                yes_text=_('Yes, abort'),
                no_text=_('No, keep copying'),
            ):
                return
        self.canceled = True
        self.button_box.setDisabled(True)
        self.title = _('Aborting...')
        self.canceled_signal.emit()

    def reject(self) -> None:
        if not self.cancelable:
            return
        QDialog.reject(self)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        assert a0 is not None
        if a0.key() == Qt.Key.Key_Escape:
            if self.cancelable:
                self._canceled()
        else:
            QDialog.keyPressEvent(self, a0)


class BlockingBusy(QDialog):
    def __init__(self, msg: str, parent: QWidget | None = None, window_title: str = _('Working')) -> None:
        QDialog.__init__(self, parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.msg = QLabel(msg)
        # self.msg.setWordWrap(True)
        self._label_font = QFont()
        self._label_font.setPointSize(self._label_font.pointSize() + 8)
        self.msg.setFont(self._label_font)
        self.pi = ProgressIndicator(self)
        self.pi.setDisplaySize(QSize(100, 100))
        self._layout.addWidget(self.pi, 0, Qt.AlignmentFlag.AlignHCenter)
        self._layout.addSpacing(15)
        self._layout.addWidget(self.msg, 0, Qt.AlignmentFlag.AlignHCenter)
        self.start()
        self.setWindowTitle(window_title)
        self.resize(self.sizeHint())

    def start(self) -> None:
        self.pi.startAnimation()

    def stop(self) -> None:
        self.pi.stopAnimation()

    def accept(self) -> None:
        self.stop()
        return QDialog.accept(self)

    def reject(self) -> None:
        pass  # Cannot cancel this dialog


if __name__ == '__main__':
    from qt.core import QTimer

    app = QApplication([])
    d = ProgressDialog('A title', 'A message', icon='lt.png')
    d.show(), d.canceled_signal.connect(app.quit)
    QTimer.singleShot(1000, lambda: (setattr(d, 'value', 10), setattr(d, 'msg', ('A message ' * 100))))
    app.exec()
