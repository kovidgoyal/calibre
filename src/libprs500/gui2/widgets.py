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
'''
Miscellanous widgets used in the GUI
'''
from PyQt4.QtGui import QListView, QIcon, QFont, QLabel
from PyQt4.QtCore import QAbstractListModel, QVariant, Qt, QSize, SIGNAL, QObject

from libprs500.gui2 import human_readable, NONE, TableView
from libprs500 import fit_image

class ImageView(QLabel):
    
    MAX_WIDTH  = 400
    MAX_HEIGHT = 300
    
    def setPixmap(self, pixmap):
        QLabel.setPixmap(self, pixmap)
        width, height = fit_image(pixmap.width(), pixmap.height(), self.MAX_WIDTH, self.MAX_HEIGHT)[1:]
        self.setMaximumWidth(width)
        self.setMaximumHeight(height) 

class LocationModel(QAbstractListModel):
    def __init__(self, parent):
        QAbstractListModel.__init__(self, parent)
        self.icons = [QVariant(QIcon(':/library')),
                      QVariant(QIcon(':/images/reader.svg')),
                      QVariant(QIcon(':/images/sd.svg'))]
        self.text = [_('Library'),
                     _('Reader\n%s available'),
                     _('Card\n%s available')]
        self.free = [-1, -1]
        self.highlight_row = 0            
        
    def rowCount(self, parent):
        return 1 + sum([1 for i in self.free if i >= 0])
    
    def data(self, index, role):
        row = index.row()    
        data = NONE
        if role == Qt.DisplayRole:
            text = self.text[row]%(human_readable(self.free[row-1])) if row > 0 \
                            else self.text[row]
            data = QVariant(text)
        elif role == Qt.DecorationRole:                
            data = self.icons[row]
        elif role == Qt.SizeHintRole:
            if row == 1: 
                return QVariant(QSize(150, 65))
        elif role == Qt.FontRole and row == self.highlight_row: 
            font = QFont()
            font.setBold(True)
            data =  QVariant(font)
        return data
    
    def headerData(self, section, orientation, role):
        return NONE
    
    def update_devices(self, cp=None, fs=[-1, -1, -1]):
        self.free[0] = fs[0]
        self.free[1] = max(fs[1:])
        if cp == None:
            self.free[1] = -1
        self.reset()        
        
    def location_changed(self, row):
        self.highlight_row = row
        self.reset()

class LocationView(QListView):
        
    def __init__(self, parent):
        QListView.__init__(self, parent)
        self.setModel(LocationModel(self))
        self.reset()
        QObject.connect(self.selectionModel(), SIGNAL('currentChanged(QModelIndex, QModelIndex)'), self.current_changed)        
    
    def current_changed(self, current, previous):
        i = current.row()
        location = 'library' if i == 0 else 'main' if i == 1 else 'card'
        self.emit(SIGNAL('location_selected(PyQt_PyObject)'), location)
        
    def location_changed(self, row):
        if 0 <= row and row <= 2:
            self.model().location_changed(row)
                        
class JobsView(TableView):
    pass


