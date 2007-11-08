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
from PyQt4.QtGui import QDialog

from libprs500.gui2.dialogs.conversion_error_ui import Ui_ConversionErrorDialog

class ConversionErrorDialog(QDialog, Ui_ConversionErrorDialog):
    
    def __init__(self, window, title, html, show=False):
        QDialog.__init__(self, window)
        Ui_ConversionErrorDialog.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(title)
        self.set_message(html)
        if show:
            self.show()
        
    def set_message(self, html):
        self.text.setHtml('<html><body>%s</body></html'%(html,))
    