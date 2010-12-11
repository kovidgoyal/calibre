#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import dynamic
from calibre.gui2.dialogs.confirm_delete_ui import Ui_Dialog
from PyQt4.Qt import QDialog, Qt, QPixmap, QIcon

def _config_name(name):
    return name + '_again'

class Dialog(QDialog, Ui_Dialog):

    def __init__(self, msg, name, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.msg.setText(msg)
        self.name = name
        self.again.stateChanged.connect(self.toggle)
        self.buttonBox.setFocus(Qt.OtherFocusReason)


    def toggle(self, *args):
        dynamic[_config_name(self.name)] = self.again.isChecked()

def confirm(msg, name, parent=None, pixmap='dialog_warning.png'):
    if not dynamic.get(_config_name(name), True):
        return True
    d = Dialog(msg, name, parent)
    d.label.setPixmap(QPixmap(I(pixmap)))
    d.setWindowIcon(QIcon(I(pixmap)))
    d.resize(d.sizeHint())
    return d.exec_() == d.Accepted
