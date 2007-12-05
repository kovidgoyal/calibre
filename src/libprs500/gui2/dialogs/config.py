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
from libprs500.gui2 import error_dialog
import os

from PyQt4.QtGui import QDialog
from PyQt4.QtCore import QSettings, QVariant, SIGNAL

from libprs500.gui2.dialogs.config_ui import Ui_Dialog
from libprs500.gui2 import qstring_to_unicode, choose_dir

class ConfigDialog(QDialog, Ui_Dialog):
    
    def __init__(self, window):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.setupUi(self)
        
        settings = QSettings()
        path = qstring_to_unicode(\
        settings.value("database path", 
                QVariant(os.path.join(os.path.expanduser('~'),'library1.db'))).toString())
        
        self.location.setText(os.path.dirname(path))
        self.connect(self.browse_button, SIGNAL('clicked(bool)'), self.browse)
        
    def browse(self):
        dir = choose_dir(self, 'database location dialog', 'Select database location')
        self.location.setText(dir)
        
    def accept(self):
        path = qstring_to_unicode(self.location.text())        
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            d = error_dialog(self, 'Invalid database location', 'Invalid database location '+path+'<br>Must be a directory.')
            d.exec_()
        elif not os.access(path, os.W_OK):
            d = error_dialog(self, 'Invalid database location', 'Invalid database location.<br>Cannot write to '+path)
            d.exec_()
        else:
            self.database_location = os.path.abspath(path)
            QDialog.accept(self)
