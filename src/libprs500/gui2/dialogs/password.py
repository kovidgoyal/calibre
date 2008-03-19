##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from PyQt4.QtGui import QDialog, QLineEdit
from PyQt4.QtCore import QVariant, SIGNAL, Qt

from libprs500.gui2.dialogs.password_ui import Ui_Dialog
from libprs500.gui2 import qstring_to_unicode
from libprs500 import Settings

class PasswordDialog(QDialog, Ui_Dialog):
    
    def __init__(self, window, name, msg):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.setupUi(self)
        
        settings = Settings()
        un = settings.value(name+': un', QVariant('')).toString()
        pw = settings.value(name+': pw', QVariant('')).toString()
        self.gui_username.setText(un)
        self.gui_password.setText(pw)
        self.sname = name 
        self.msg.setText(msg)
        self.connect(self.show_password, SIGNAL('stateChanged(int)'), self.toggle_password)
        
    def toggle_password(self, state):
        if state == Qt.Unchecked:
            self.gui_password.setEchoMode(QLineEdit.Password)
        else:
            self.gui_password.setEchoMode(QLineEdit.Normal)
    
    def username(self):
        return qstring_to_unicode(self.gui_username.text())
    
    def password(self):
        return qstring_to_unicode(self.gui_password.text())
    
    def accept(self):
        settings = Settings()
        settings.setValue(self.sname+': un', QVariant(self.gui_username.text()))
        settings.setValue(self.sname+': pw', QVariant(self.gui_password.text()))
        QDialog.accept(self)
