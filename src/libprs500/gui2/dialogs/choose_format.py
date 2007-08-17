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

from PyQt4.QtGui import QDialog, QListWidgetItem

from libprs500.gui2 import file_icon_provider
from libprs500.gui2.dialogs.choose_format_ui import Ui_ChooseFormatDialog

class ChooseFormatDialog(QDialog, Ui_ChooseFormatDialog):
    
    def __init__(self, window, msg, formats):
        QDialog.__init__(self, window)
        Ui_ChooseFormatDialog.__init__(self)
        self.setupUi(self)
        
        self.msg.setText(msg)
        for format in formats:
            self.formats.addItem(QListWidgetItem(file_icon_provider().icon_from_ext(format.lower()),
                                                 format.upper()))
        self._formats = formats
        self.formats.setCurrentRow(0)
        
    def format(self):
        self._formats[self.formats.currentRow()]
    
    