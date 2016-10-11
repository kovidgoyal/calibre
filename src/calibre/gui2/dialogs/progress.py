#!/usr/bin/env  python2
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import (
    QDialog, pyqtSignal, Qt, QVBoxLayout, QLabel, QFont, QProgressBar,
    QDialogButtonBox, QApplication, QFontMetrics, QHBoxLayout, QIcon)

from calibre.gui2 import elided_text
from calibre.gui2.progress_indicator import ProgressIndicator


class ProgressDialog(QDialog):

    canceled_signal = pyqtSignal()

    def __init__(self, title, msg=u'\u00a0', min=0, max=99, parent=None, cancelable=True, icon=None):
        QDialog.__init__(self, parent)
        if icon is None:
            self.l = l = QVBoxLayout(self)
        else:
            self.h = h = QHBoxLayout(self)
            self.icon = i = QLabel(self)
            if not isinstance(icon, QIcon):
                icon = QIcon(I(icon))
            i.setPixmap(icon.pixmap(64))
            h.addWidget(i, alignment=Qt.AlignTop | Qt.AlignHCenter)
            self.l = l = QVBoxLayout()
            h.addLayout(l)
            self.setWindowIcon(icon)

        self.title_label = t = QLabel(title)
        self.setWindowTitle(title)
        t.setStyleSheet('QLabel { font-weight: bold }'), t.setAlignment(Qt.AlignCenter), t.setTextFormat(Qt.PlainText)
        l.addWidget(t)

        self.bar = b = QProgressBar(self)
        b.setMinimum(min), b.setMaximum(max), b.setValue(min)
        l.addWidget(b)

        self.message = m = QLabel(self)
        fm = QFontMetrics(self.font())
        m.setAlignment(Qt.AlignCenter), m.setMinimumWidth(fm.averageCharWidth() * 80), m.setTextFormat(Qt.PlainText)
        l.addWidget(m)
        self.msg = msg

        self.button_box = bb = QDialogButtonBox(QDialogButtonBox.Abort, self)
        bb.rejected.connect(self._canceled)
        l.addWidget(bb)

        self.setWindowModality(Qt.ApplicationModal)
        self.canceled = False

        if not cancelable:
            bb.setVisible(False)
        self.cancelable = cancelable
        self.resize(self.sizeHint())

    def set_msg(self, msg=''):
        self.msg = msg

    def set_value(self, val):
        self.value = val

    @dynamic_property
    def value(self):
        def fset(self, val):
            return self.bar.setValue(val)

        def fget(self):
            return self.bar.value()
        return property(fget=fget, fset=fset)

    def set_min(self, min):
        self.min = min

    def set_max(self, max):
        self.max = max

    @dynamic_property
    def max(self):
        def fget(self):
            return self.bar.maximum()

        def fset(self, val):
            self.bar.setMaximum(val)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def min(self):
        def fget(self):
            return self.bar.minimum()

        def fset(self, val):
            self.bar.setMinimum(val)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def title(self):
        def fget(self):
            return self.title_label.text()

        def fset(self, val):
            self.title_label.setText(unicode(val or ''))
        return property(fget=fget, fset=fset)

    @dynamic_property
    def msg(self):
        def fget(self):
            return self.message.text()

        def fset(self, val):
            val = unicode(val or '')
            self.message.setText(elided_text(val, self.font(), self.message.minimumWidth()-10))
        return property(fget=fget, fset=fset)

    def _canceled(self, *args):
        self.canceled = True
        self.button_box.setDisabled(True)
        self.title = _('Aborting...')
        self.canceled_signal.emit()

    def reject(self):
        if not self.cancelable:
            return
        QDialog.reject(self)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            if self.cancelable:
                self._canceled()
        else:
            QDialog.keyPressEvent(self, ev)


class BlockingBusy(QDialog):

    def __init__(self, msg, parent=None, window_title=_('Working')):
        QDialog.__init__(self, parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.msg = QLabel(msg)
        # self.msg.setWordWrap(True)
        self.font = QFont()
        self.font.setPointSize(self.font.pointSize() + 8)
        self.msg.setFont(self.font)
        self.pi = ProgressIndicator(self)
        self.pi.setDisplaySize(100)
        self._layout.addWidget(self.pi, 0, Qt.AlignHCenter)
        self._layout.addSpacing(15)
        self._layout.addWidget(self.msg, 0, Qt.AlignHCenter)
        self.start()
        self.setWindowTitle(window_title)
        self.resize(self.sizeHint())

    def start(self):
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()

    def accept(self):
        self.stop()
        return QDialog.accept(self)

    def reject(self):
        pass  # Cannot cancel this dialog

if __name__ == '__main__':
    from PyQt5.Qt import QTimer
    app = QApplication([])
    d = ProgressDialog('A title', 'A message', icon='lt.png')
    d.show(), d.canceled_signal.connect(app.quit)
    QTimer.singleShot(1000, lambda : (setattr(d, 'value', 10), setattr(d, 'msg', ('A message ' * 100))))
    app.exec_()
