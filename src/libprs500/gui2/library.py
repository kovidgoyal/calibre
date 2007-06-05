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
import os, textwrap, traceback, time, re
from datetime import timedelta
from math import cos, sin, pi
from PyQt4.QtGui import QTableView, QProgressDialog, QAbstractItemView, QColor, \
                        QItemDelegate, QPainterPath, QLinearGradient, QBrush, \
                        QPen, QStyle, QPainter, QLineEdit, QApplication, \
                        QPalette
from PyQt4.QtCore import QAbstractTableModel, QVariant, Qt, QString, \
                         QCoreApplication, SIGNAL, QObject, QSize

from libprs500.library.database import LibraryDatabase
from libprs500.gui2 import NONE

class LibraryDelegate(QItemDelegate):
    COLOR = QColor("blue")
    SIZE     = 16
    PEN      = QPen(COLOR, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    
    def __init__(self, parent, rating_column=-1):
        QItemDelegate.__init__(self, parent)
        self.rating_column = rating_column
        self.star_path = QPainterPath()
        self.star_path.moveTo(90, 50)
        for i in range(1, 5):
            self.star_path.lineTo(50 + 40 * cos(0.8 * i * pi), \
                                  50 + 40 * sin(0.8 * i * pi))
        self.star_path.closeSubpath()
        self.star_path.setFillRule(Qt.WindingFill)
        gradient = QLinearGradient(0, 0, 0, 100)
        gradient.setColorAt(0.0, self.COLOR)
        gradient.setColorAt(1.0, self.COLOR)
        self. brush = QBrush(gradient)
        self.factor = self.SIZE/100.        

    def sizeHint(self, option, index):
        if index.column() != self.rating_column:
            return QItemDelegate.sizeHint(self, option, index)
        num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        return QSize(num*(self.SIZE), self.SIZE+4)
    
    def paint(self, painter, option, index):
        if index.column() != self.rating_column:
            return QItemDelegate.paint(self, painter, option, index)
        num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        def draw_star(): 
            painter.save()
            painter.scale(self.factor, self.factor)
            painter.translate(50.0, 50.0)
            painter.rotate(-20)
            painter.translate(-50.0, -50.0)
            painter.drawPath(self.star_path)
            painter.restore()
        
        painter.save()
        try:
            if option.state & QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
            painter.setRenderHint(QPainter.Antialiasing)
            y = option.rect.center().y()-self.SIZE/2. 
            x = option.rect.right()  - self.SIZE
            painter.setPen(self.PEN)      
            painter.setBrush(self.brush)      
            painter.translate(x, y)
            for i in range(num):
                draw_star()
                painter.translate(-self.SIZE, 0)
        except Exception, e:
            traceback.print_exc(e)
        painter.restore()
        
class BooksView(QTableView):
    wrapper = textwrap.TextWrapper(width=20)
    
    @classmethod
    def wrap(cls, s, width=20):         
        cls.wrapper.width = width
        return cls.wrapper.fill(s)
    
    @classmethod
    def human_readable(cls, size):
        """ Convert a size in bytes into a human readable form """
        if size < 1024: 
            divisor, suffix = 1, "B"
        elif size < 1024*1024: 
            divisor, suffix = 1024., "KB"
        elif size < 1024*1024*1024: 
            divisor, suffix = 1024*1024, "MB"
        elif size < 1024*1024*1024*1024: 
            divisor, suffix = 1024*1024, "GB"
        size = str(size/divisor)
        if size.find(".") > -1: 
            size = size[:size.find(".")+2]
        return size + " " + suffix
    
    def __init__(self, parent):
        QTableView.__init__(self, parent)
        self.display_parent = parent
        self.model = BooksModel(self)
        self.setModel(self.model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.setItemDelegate(LibraryDelegate(self, rating_column=4))
        QObject.connect(self.model, SIGNAL('sorted()'), self.resizeRowsToContents)
        QObject.connect(self.model, SIGNAL('searched()'), self.resizeRowsToContents)
        self.verticalHeader().setVisible(False)
        
    def set_database(self, db):
        self.model.set_database(db)
        
    def migrate_database(self):
        if self.model.database_needs_migration():
            print 'Migrating database from pre 0.4.0 version'
            path = os.path.abspath(os.path.expanduser('~/library.db'))
            progress = QProgressDialog('Upgrading database from pre 0.4.0 version.<br>'+\
                                       'The new database is stored in the file <b>'+self.model.db.dbpath,
                                       QString(), 0, LibraryDatabase.sizeof_old_database(path),
                                       self)
            progress.setModal(True)
            app = QCoreApplication.instance()
            def meter(count):
                progress.setValue(count)
                app.processEvents()
            progress.setWindowTitle('Upgrading database')
            progress.show()
            LibraryDatabase.import_old_database(path, self.model.db.conn, meter)
            
    def connect_to_search_box(self, sb):
        QObject.connect(sb, SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'), self.model.search)
            

class BooksModel(QAbstractTableModel):
    
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        self.db = None
        self.cols = ['title', 'authors', 'size', 'date', 'rating', 'publisher']
        self.sorted_on = None
        
    def set_database(self, db):
        if isinstance(db, (QString, basestring)):
            db = LibraryDatabase(os.path.expanduser(str(db)))
        self.db = db
        
    def search(self, text, refinement):
        tokens = []
        quot = re.search('"(.*?)"', text)
        while quot:
            tokens.append(quot.group(1))
            text = text.replace('"'+quot.group(1)+'"', '')
            quot = re.search('"(.*?)"', text)
        tokens += text.split(' ')
        self.db.filter(tokens, refinement)
        self.reset()
        self.emit(SIGNAL('searched()'))
    
    def sort(self, col, order):
        if not self.db:
            return
        ascending = order == Qt.AscendingOrder
        self.db.refresh(self.cols[col], ascending)
        self.reset()
        self.emit(SIGNAL('sorted()'))
        self.sorted_on = (col, order)
        
    def database_needs_migration(self):
        path = os.path.expanduser('~/library.db')
        return self.db.is_empty() and \
               os.path.exists(path) and\
               LibraryDatabase.sizeof_old_database(path) > 0
            
    def columnCount(self, parent):
        return len(self.cols)
    
    def rowCount(self, parent):
        return self.db.rows() if self.db else 0
    
    def data(self, index, role):
        if role == Qt.DisplayRole or role == Qt.EditRole:      
            row, col = index.row(), index.column()
            if col == 0:
                text = self.db.title(row)
                if text:
                    return QVariant(BooksView.wrap(text, width=35))
            elif col == 1: 
                au = self.db.authors(row)
                if au:
                    au = au.split(',')
                    jau = [ BooksView.wrap(a, width=30).strip() for a in au ]
                    return QVariant("\n".join(jau))
            elif col == 2:
                size = self.db.max_size(row)
                if size:
                    return QVariant(BooksView.human_readable(size))
            elif col == 3:
                dt = self.db.timestamp(row)
                if dt:
                    dt = dt - timedelta(seconds=time.timezone) + timedelta(hours=time.daylight)
                    return QVariant(dt.strftime('%d %b %Y'))
            elif col == 4: 
                r = self.db.rating(row)
                r = r/2 if r else 0
                return QVariant(r)
            elif col == 5: 
                pub = self.db.publisher(row)
                if pub: 
                    return QVariant(BooksView.wrap(pub, 20))
            return NONE
        elif role == Qt.TextAlignmentRole and index.column() in [2, 3, 4]:
            return QVariant(Qt.AlignRight | Qt.AlignVCenter)
        elif role == Qt.ToolTipRole and index.isValid():
            if index.column() in [0, 1, 4, 5]:
                edit = "Double click to <b>edit</b> me<br><br>"
            else: 
                edit = ""
            return QVariant(edit + "You can <b>drag and drop</b> me to the \
                            desktop to save all my formats to your hard disk.")
        return NONE
    
    def headerData(self, section, orientation, role):    
        if role != Qt.DisplayRole:
            return NONE
        text = ""
        if orientation == Qt.Horizontal:      
            if   section == 0: text = "Title"
            elif section == 1: text = "Author(s)"
            elif section == 2: text = "Size"
            elif section == 3: text = "Date"
            elif section == 4: text = "Rating"
            elif section == 5: text = "Publisher"
            return QVariant(self.trUtf8(text))
        else: 
            return NONE
        
    def flags(self, index):
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():       
            if index.column() not in [2, 3]:  
                flags |= Qt.ItemIsEditable    
        return flags
    
    def setData(self, index, value, role):
        done = False
        if role == Qt.EditRole:
            row, col = index.row(), index.column()
            if col in [2,3]:
                return False
            val = unicode(value.toString().toUtf8(), 'utf-8').strip() if col != 4 else \
                  int(value.toInt()[0])
            if col == 4:
                val = 0 if val < 0 else 5 if val > 5 else val
                val *= 2
            column = self.cols[col]
            self.db.set(row, column, val)           
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
                                index, index)
            if col == self.sorted_on[0]:
                self.sort(col, self.sorted_on[1])
            done = True
        return done
    
class SearchBox(QLineEdit):
    def __init__(self, parent):
        QLineEdit.__init__(self, parent)
        self.setText('Search by title, author, publisher, tags and comments')
        self.home(False)
        QObject.connect(self, SIGNAL('textEdited(QString)'), self.text_edited_slot)
        self.default_palette = QApplication.palette(self)
        gray = QPalette(self.default_palette)
        gray.setBrush(QPalette.Text, QBrush(QColor('lightgray')))
        self.setPalette(gray)
        self.initial_state = True
        self.prev_search = ''
        self.timer = None
        self.interval = 1000 #: Time to wait before emitting search signal
        
    def keyPressEvent(self, event):
        if self.initial_state:
            self.setText('')
            self.initial_state = False
            self.setPalette(self.default_palette)
        QLineEdit.keyPressEvent(self, event)
    
    def text_edited_slot(self, text):
        text = str(text)
        self.prev_text = text
        self.timer = self.startTimer(self.interval)
        
    def timerEvent(self, event):
        self.killTimer(event.timerId())
        if event.timerId() == self.timer:
            text = str(self.text())
            refinement = text.startswith(self.prev_search)
            self.prev_search = text
            self.emit(SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'), text, refinement)