__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.QtGui import QDialog, QLineEdit
from PyQt4.QtCore import QVariant, SIGNAL, Qt

from calibre.gui2.dialogs.password_ui import Ui_Dialog
from calibre.gui2 import qstring_to_unicode
from calibre import Settings

class PasswordDialog(QDialog, Ui_Dialog):
    
    def __init__(self, window, name, msg):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.setupUi(self)
        
        settings = Settings()
        un = settings.get(name+': un', u'')
        pw = settings.get(name+': pw', u'')
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
        settings.set(self.sname+': un', unicode(self.gui_username.text()))
        settings.set(self.sname+': pw', unicode(self.gui_password.text()))
        QDialog.accept(self)
