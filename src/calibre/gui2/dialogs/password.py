

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from PyQt5.Qt import QDialog, QLineEdit, Qt

from calibre.gui2.dialogs.password_ui import Ui_Dialog
from calibre.gui2 import dynamic
from polyglot.builtins import unicode_type


class PasswordDialog(QDialog, Ui_Dialog):

    def __init__(self, window, name, msg):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.setupUi(self)
        self.cfg_key = re.sub(r'[^0-9a-zA-Z]', '_', name)

        un = dynamic[self.cfg_key+'__un']
        pw = dynamic[self.cfg_key+'__pw']
        if not un:
            un = ''
        if not pw:
            pw = ''
        self.gui_username.setText(un)
        self.gui_password.setText(pw)
        self.sname = name
        self.msg.setText(msg)
        self.show_password.stateChanged[(int)].connect(self.toggle_password)

    def toggle_password(self, state):
        if state == Qt.Unchecked:
            self.gui_password.setEchoMode(QLineEdit.Password)
        else:
            self.gui_password.setEchoMode(QLineEdit.Normal)

    def username(self):
        return unicode_type(self.gui_username.text())

    def password(self):
        return unicode_type(self.gui_password.text())

    def accept(self):
        dynamic.set(self.cfg_key+'__un', unicode_type(self.gui_username.text()))
        dynamic.set(self.cfg_key+'__pw', unicode_type(self.gui_password.text()))
        QDialog.accept(self)
