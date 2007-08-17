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
'''Display active jobs'''

from PyQt4.QtCore import Qt, QObject, SIGNAL
from PyQt4.QtGui import QDialog

from libprs500.gui2.dialogs.jobs_ui import Ui_JobsDialog
from libprs500 import __appname__

class JobsDialog(QDialog, Ui_JobsDialog):
    def __init__(self, window, model):
        QDialog.__init__(self, window)
        Ui_JobsDialog.__init__(self)
        self.setupUi(self)
        self.jobs_view.setModel(model)
        self.model = model
        self.setWindowModality(Qt.NonModal)
        self.setWindowTitle(__appname__ + ' - Active Jobs')
        QObject.connect(self.jobs_view.model(), SIGNAL('modelReset()'), 
                        self.jobs_view.resizeColumnsToContents)
        
    def closeEvent(self, e):
        self.jobs_view.write_settings()
        e.accept()
