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
from PyQt4.QtGui import QListView, QIcon, QFont, QLabel, QListWidget, QListWidgetItem
from PyQt4.QtCore import QAbstractListModel, QVariant, Qt, QSize, SIGNAL, QObject

from libprs500.gui2.jobs import ConversionJob, DetailView
from libprs500.gui2 import human_readable, NONE, TableView
from libprs500 import fit_image, get_font_families

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
    
    def __init__(self, parent):
        TableView.__init__(self, parent)
        self.connect(self, SIGNAL('activated(QModelIndex)'), self.show_details)
        
    def show_details(self, index):
        row = index.row()
        job = self.model().row_to_job(row)[0]
        DetailView(self, job).exec_()
            

class FontFamilyModel(QAbstractListModel):
    
    def __init__(self, *args):
        QAbstractListModel.__init__(self, *args)
        self.family_map = get_font_families()
        self.families = self.family_map.keys()
        self.families.sort()
        self.families[:0] = ['None']
        
    def rowCount(self, *args):
        return len(self.families)
    
    def data(self, index, role):
        try:
            family = self.families[index.row()]
        except:
            import traceback
            traceback.print_exc()
            return NONE
        if role == Qt.DisplayRole:
            return QVariant(family)
        if role == Qt.FontRole:
            return QVariant(QFont(family))
        return NONE
    
    def path_of(self, family):
        if family != None:
            return self.family_map[family]
        return None
    
    def index_of(self, family):
        return self.families.index(family.strip())
    

class BasicListItem(QListWidgetItem):
    
    def __init__(self, text, user_data=None):
        QListWidgetItem.__init__(self, text)
        self.user_data = user_data
        
    def __eq__(self, other):
        if hasattr(other, 'text'):
            return self.text() == other.text()
        return False

class BasicList(QListWidget):
    
    def add_item(self, text, user_data=None, replace=False):
        item = BasicListItem(text, user_data)
        
        for oitem in self.items():
            if oitem == item:
                if replace:
                    self.takeItem(self.row(oitem))
                else:
                    raise ValueError('Item already in list')
            
        self.addItem(item)
    
    def remove_selected_items(self, *args):
        for item in self.selectedItems():
            self.takeItem(self.row(item))
    
    def items(self):
        for i in range(self.count()):
            yield self.item(i)
