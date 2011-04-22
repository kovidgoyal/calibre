#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QDialog, Qt, QPixmap, QIcon

from calibre import confirm_config_name
from calibre.gui2 import dynamic
from calibre.gui2.dialogs.confirm_delete_ui import Ui_Dialog

class Dialog(QDialog, Ui_Dialog):

    def __init__(self, msg, name, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.msg.setText(msg)
        self.name = name
        self.again.stateChanged.connect(self.toggle)
        self.buttonBox.setFocus(Qt.OtherFocusReason)

    def toggle(self, *args):
        dynamic[confirm_config_name(self.name)] = self.again.isChecked()


def confirm(msg, name, parent=None, pixmap='dialog_warning.png', title=None,
        show_cancel_button=True):
    if not dynamic.get(confirm_config_name(name), True):
        return True
    d = Dialog(msg, name, parent)
    d.label.setPixmap(QPixmap(I(pixmap)))
    d.setWindowIcon(QIcon(I(pixmap)))
    if title is not None:
        d.setWindowTitle(title)
    if not show_cancel_button:
        d.buttonBox.button(d.buttonBox.Cancel).setVisible(False)
    d.resize(d.sizeHint())
    return d.exec_() == d.Accepted
