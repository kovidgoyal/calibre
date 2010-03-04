#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

''''''

from PyQt4.Qt import QDialog, SIGNAL, Qt

from calibre.gui2.dialogs.progress_ui import Ui_Dialog

class ProgressDialog(QDialog, Ui_Dialog):

    def __init__(self, title, msg='', min=0, max=99, parent=None):
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

        self.connect(self.button_box, SIGNAL('rejected()'), self._canceled)

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

    def _canceled(self, *args):
        self.canceled = True
        self.button_box.setDisabled(True)
        self.title.setText(_('Aborting...'))
        self.emit(SIGNAL('canceled()'))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self._canceled()
        else:
            QDialog.keyPressEvent(self, ev)
