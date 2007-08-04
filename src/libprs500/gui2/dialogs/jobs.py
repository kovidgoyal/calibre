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

from libprs500.gui2.dialogs import Dialog
from libprs500.gui2.dialogs.jobs_ui import Ui_JobsDialog
from libprs500 import __appname__

class JobsDialog(Ui_JobsDialog, Dialog):
    def __init__(self, window, model):
        Ui_JobsDialog.__init__(self)
        Dialog.__init__(self, window)
        self.setupUi(self.dialog)
        self.jobs_view.setModel(model)
        self.model = model
        self.dialog.setWindowModality(Qt.NonModal)
        self.dialog.setWindowTitle(__appname__ + ' - Active Jobs')
        QObject.connect(self.jobs_view.model(), SIGNAL('modelReset()'), 
                        self.jobs_view.resizeColumnsToContents)
        
    def show(self):
        self.dialog.show()
        self.jobs_view.resizeColumnsToContents()
        
    def hide(self):
        self.dialog.hide()
