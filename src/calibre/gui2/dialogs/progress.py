#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

''''''

from PyQt5.Qt import QDialog, pyqtSignal, Qt, QVBoxLayout, QLabel, QFont

from calibre.gui2.dialogs.progress_ui import Ui_Dialog
from calibre.gui2.progress_indicator import ProgressIndicator

class ProgressDialog(QDialog, Ui_Dialog):

    canceled_signal = pyqtSignal()

    def __init__(self, title, msg='', min=0, max=99, parent=None,
            cancelable=True):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle(title)
        self.title.setText(title)
        self.message.setText(msg)
        self.setWindowModality(Qt.ApplicationModal)
        self.set_min(min)
        self.set_max(max)
        self.bar.setValue(min)
        self.canceled = False

        self.button_box.rejected.connect(self._canceled)
        if not cancelable:
            self.button_box.setVisible(False)
        self.cancelable = cancelable

    def set_msg(self, msg=''):
        self.message.setText(msg)

    def set_value(self, val):
        self.bar.setValue(val)

    @dynamic_property
    def value(self):
        def fset(self, val):
            return self.bar.setValue(val)
        def fget(self):
            return self.bar.value()
        return property(fget=fget, fset=fset)


    def set_min(self, min):
        self.bar.setMinimum(min)

    def set_max(self, max):
        self.bar.setMaximum(max)

    @dynamic_property
    def max(self):
        def fget(self): return self.bar.maximum()
        def fset(self, val): self.bar.setMaximum(val)
        return property(fget=fget, fset=fset)


    def _canceled(self, *args):
        self.canceled = True
        self.button_box.setDisabled(True)
        self.title.setText(_('Aborting...'))
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
        #self.msg.setWordWrap(True)
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
        pass # Cannot cancel this dialog
