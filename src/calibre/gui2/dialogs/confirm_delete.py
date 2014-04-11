#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QDialog, Qt, QPixmap, QIcon

from calibre import confirm_config_name
from calibre.gui2 import dynamic
from calibre.gui2.dialogs.confirm_delete_ui import Ui_Dialog

class Dialog(QDialog, Ui_Dialog):

    def __init__(self, msg, name, parent, config_set=dynamic):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.msg.setText(msg)
        self.name = name
        self.again.stateChanged.connect(self.toggle)
        self.buttonBox.setFocus(Qt.OtherFocusReason)
        self.config_set = config_set

    def toggle(self, *args):
        self.config_set[confirm_config_name(self.name)] = self.again.isChecked()


def confirm(msg, name, parent=None, pixmap='dialog_warning.png', title=None,
        show_cancel_button=True, confirm_msg=None, config_set=None):
    config_set = config_set or dynamic
    if not config_set.get(confirm_config_name(name), True):
        return True
    d = Dialog(msg, name, parent, config_set=config_set)
    d.label.setPixmap(QPixmap(I(pixmap)))
    d.setWindowIcon(QIcon(I(pixmap)))
    if title is not None:
        d.setWindowTitle(title)
    if not show_cancel_button:
        d.buttonBox.button(d.buttonBox.Cancel).setVisible(False)
    if confirm_msg is not None:
        d.again.setText(confirm_msg)
    d.resize(d.sizeHint())
    return d.exec_() == d.Accepted
