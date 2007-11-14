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

from PyQt4.QtGui import QGraphicsView
from PyQt4.QtCore import QSize

class BookView(QGraphicsView):
    
    MINIMUM_SIZE = QSize(400, 500)
    
    def __init__(self, *args):
        QGraphicsView.__init__(self, *args)
        self.preferred_size = self.MINIMUM_SIZE
    
    def minimumSizeHint(self):
        return self.MINIMUM_SIZE
    
    def sizeHint(self):
        return self.preferred_size
    
    def resize_for(self, width, height):
        self.preferred_size = QSize(width, height)
    