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
'''Various dialogs used in the GUI'''

from PyQt4.QtCore import QObject
from PyQt4.QtGui import  QDialog

class Dialog(QObject):
    def __init__(self, window):
        QObject.__init__(self, window)
        self.dialog = QDialog(window)
        self.accept = self.dialog.accept
        self.reject = self.dialog.reject
        self.window = window
        self.isVisible = self.dialog.isVisible
