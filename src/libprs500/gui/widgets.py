##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
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
import re
import os
import textwrap
import time 
import traceback
from operator import itemgetter, attrgetter
from socket import gethostname
from urlparse import urlparse, urlunparse
from urllib import quote, unquote
from math import sin, cos, pi

from libprs500.gui import Error, _Warning
from libprs500.ptempfile import PersistentTemporaryFile
from libprs500 import iswindows

from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QApplication, QString, QFont, QAbstractListModel, \
                     QVariant, QAbstractTableModel, QTableView, QListView, \
                     QLabel, QAbstractItemView, QPixmap, QIcon, QSize, \
                     QSpinBox, QPoint, QPainterPath, QItemDelegate, QPainter, \
                     QPen, QColor, QLinearGradient, QBrush, QStyle, \
                     QByteArray, QBuffer, QMimeData, \
                     QDrag, QRect                     

NONE = QVariant() #: Null value to return from the data function of item models
TIME_WRITE_FMT  = "%d %b %Y" #: The display format used to show dates

class FileDragAndDrop(object):
    _drag_start_position = QPoint()
    _dragged_files = []
    
    @classmethod
    def _bytes_to_string(cls, qba):
        """ 
        Assumes qba is encoded in ASCII which is usually fine, since
        this method is used mainly for escaped URIs.
        @type qba: QByteArray 
        """
        return str(QString.fromAscii(qba.data())).strip()        
    
    @classmethod
    def _get_r_ok_files(cls, event):
        """ 
        Return list of paths from event that point to files to
        which the user has read permission.
        """
        files = []
        md = event.mimeData()
        if md.hasFormat("text/uri-list"):
            candidates = cls._bytes_to_string(md.data("text/uri-list")).split()
            for url in candidates:
                o = urlparse(url)        
                if o.scheme and o.scheme != 'file':
                    _Warning(o.scheme +  " not supported in drop events", None)
                    continue
                path = unquote(o.path)
                if iswindows and path.startswith('/'):
                    path = path[1:]
                if not os.access(path, os.R_OK):
                    _Warning("You do not have read permission for: " + path, None)
                    continue
                if os.path.isdir(path):
                    root, dirs, files2 = os.walk(path)
                    for _file in files2:
                        path = root + _file
                        if os.access(path, os.R_OK): 
                            files.append(path)
                else: 
                    files.append(path)
        return files
    
    def __init__(self, QtBaseClass, enable_drag=True):
        self.QtBaseClass = QtBaseClass
        self.enable_drag = enable_drag
    
    def mousePressEvent(self, event):
        self.QtBaseClass.mousePressEvent(self, event)
        if self.enable_drag:
            if event.button == Qt.LeftButton:
                self._drag_start_position = event.pos()
    
    
    def mouseMoveEvent(self, event):
        self.QtBaseClass.mousePressEvent(self, event)
        if self.enable_drag:
            if event.buttons() & Qt.LeftButton != Qt.LeftButton: 
                return
            if (event.pos() - self._drag_start_position).manhattanLength() < \
                                            QApplication.startDragDistance(): 
                return
            self.start_drag(self._drag_start_position)
    
    
    def start_drag(self, pos): 
        raise NotImplementedError()
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("text/uri-list"): 
            event.acceptProposedAction()
    
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
    
    def dropEvent(self, event):
        files = self._get_r_ok_files(event)
        if files:
            try:
                event.setDropAction(Qt.CopyAction)
                if self.files_dropped(files, event): 
                    event.accept()
            except Exception, e:        
                Error("There was an error processing the dropped files.", e)
                raise e
    
    
    def files_dropped(self, files, event): 
        raise NotImplementedError()
    
    def drag_object_from_files(self, files):
        if files:
            drag = QDrag(self)
            mime_data = QMimeData()
            self._dragged_files, urls = [], []
            for _file in files:        
                urls.append(urlunparse(('file', quote(gethostname()), \
                                quote(_file.name.encode('utf-8')), '', '', '')))
                self._dragged_files.append(_file)      
            mime_data.setData("text/uri-list", QByteArray("\n".join(urls)))
            user = os.getenv('USER')
            if user: 
                mime_data.setData("text/x-xdnd-username", QByteArray(user))
            drag.setMimeData(mime_data)
            return drag
    
    def drag_object(self, extensions):
        if extensions:
            files = []
            for ext in extensions:
                f = PersistentTemporaryFile(suffix="."+ext)
                files.append(f)
            return self.drag_object_from_files(files), self._dragged_files


class TableView(FileDragAndDrop, QTableView):
    wrapper = textwrap.TextWrapper(width=20)
    
    def __init__(self, parent):
        FileDragAndDrop.__init__(self, QTableView)
        QTableView.__init__(self, parent)
    
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
    
    def render_to_pixmap(self, indices):
        rect = self.visualRect(indices[0])
        rects = []
        for i in range(len(indices)):
            rects.append(self.visualRect(indices[i]))
            rect |= rects[i]
        rect = rect.intersected(self.viewport().rect())
        pixmap = QPixmap(rect.size())
        pixmap.fill(self.palette().base().color())
        painter = QPainter(pixmap)
        option = self.viewOptions()
        option.state |= QStyle.State_Selected
        for j in range(len(indices)):
            option.rect = QRect(rects[j].topLeft() - rect.topLeft(), \
                                    rects[j].size())
            self.itemDelegate(indices[j]).paint(painter, option, indices[j])
        painter.end()
        return pixmap
    
    def drag_object_from_files(self, files):
        drag = FileDragAndDrop.drag_object_from_files(self, files)
        drag.setPixmap(self.render_to_pixmap(self.selectedIndexes()))
        return drag

        

class CoverDisplay(FileDragAndDrop, QLabel):
    def __init__(self, parent):
        FileDragAndDrop.__init__(self, QLabel)
        QLabel.__init__(self, parent)
    def files_dropped(self, files, event):
        pix = QPixmap()
        for _file in files:
            pix = QPixmap(_file)
            if not pix.isNull(): break
        if not pix.isNull():      
            self.emit(SIGNAL("cover_received(QPixmap)"), pix)
            return True
    
    def start_drag(self, event):
        drag, files = self.drag_object(["jpeg"])
        if drag and files:
            _file = files[0]
            _file.close()
            drag.setPixmap(self.pixmap().scaledToHeight(68, \
                                                    Qt.SmoothTransformation))
            self.pixmap().save(os.path.abspath(_file.name))
            drag.start(Qt.MoveAction)

class DeviceView(FileDragAndDrop, QListView):
    def __init__(self, parent):
        FileDragAndDrop.__init__(self, QListView, enable_drag=False)
        QListView.__init__(self, parent)
    
    def hide_reader(self, x):
        self.model().update_devices(reader=not x)
    
    def hide_card(self, x):
        self.model().update_devices(card=not x)
      
    def files_dropped(self, files, event):
        ids = []
        md = event.mimeData()
        if md.hasFormat("application/x-libprs500-id"):
            ids = [ int(id) for id in FileDragAndDrop._bytes_to_string(\
                                md.data("application/x-libprs500-id")).split()]
        index = self.indexAt(event.pos())
        if index.isValid():
            return self.model().files_dropped(files, index, ids)

class DeviceBooksView(TableView):
    def __init__(self, parent):
        TableView.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)

class LibraryBooksView(TableView):
    def __init__(self, parent):    
        TableView.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.setItemDelegate(LibraryDelegate(self, rating_column=4))
    
    def dragEnterEvent(self, event):
        if not event.mimeData().hasFormat("application/x-libprs500-id"):
            FileDragAndDrop.dragEnterEvent(self, event)
    
    
    def start_drag(self, pos):    
        index = self.indexAt(pos)
        if index.isValid():
            rows = frozenset([ index.row() for index in self.selectedIndexes()])
            files = self.model().extract_formats(rows)            
            drag = self.drag_object_from_files(files)
            if drag:
                ids = [ str(self.model().id_from_row(row)) for row in rows ]
                drag.mimeData().setData("application/x-libprs500-id", \
                        QByteArray("\n".join(ids)))
                drag.start()
    
    
    def files_dropped(self, files, event):
        if not files: return
        index = self.indexAt(event.pos())    
        if index.isValid():
            self.model().add_formats(files, index)      
        else: self.emit(SIGNAL('books_dropped'), files)      




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
    
    def createEditor(self, parent, option, index):
        if index.column() != 4:
            return QItemDelegate.createEditor(self, parent, option, index)
        editor = QSpinBox(parent)
        editor.setSuffix(" stars")
        editor.setMinimum(0)
        editor.setMaximum(5)
        editor.installEventFilter(self)
        return editor
    
    def setEditorData(self, editor, index):
        if index.column() != 4:
            return QItemDelegate.setEditorData(self, editor, index)
        val = index.model()._data[index.row()]["rating"]
        if not val: val = 0
        editor.setValue(val)
    
    def setModelData(self, editor, model, index):
        if index.column() != 4:
            return QItemDelegate.setModelData(self, editor, model, index)
        editor.interpretText()
        index.model().setData(index, QVariant(editor.value()), Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        if index.column() != 4:
            return QItemDelegate.updateEditorGeometry(self, editor, option, index)
        editor.setGeometry(option.rect)



class LibraryBooksModel(QAbstractTableModel):
    FIELDS = ["id", "title", "authors", "size", "date", "rating", "publisher", \
              "tags", "comments"]  
    TIME_READ_FMT = "%Y-%m-%d %H:%M:%S"
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)
        self.db    = None 
        self._data = None
        self._orig_data = None
    
    def extract_formats(self, rows):
        files = []
        for row in rows:      
            _id = self.id_from_row(row)
            au = self._data[row]["authors"] if self._data[row]["authors"] \
                                            else "Unknown"
            basename = re.sub("\n", "", "_"+str(_id)+"_"+\
                                self._data[row]["title"]+" by "+ au)
            exts = self.db.get_extensions(_id)
            for ext in exts:
                fmt = self.db.get_format(_id, ext)
                if not ext: 
                    ext =""
                else: 
                    ext = "."+ext
                name = basename+ext                
                file = PersistentTemporaryFile(suffix=name)
                if not fmt: 
                    continue
                file.write(fmt)
                file.close() 
                files.append(file)
        return files
    
    def update_cover(self, index, pix):
        spix = pix.scaledToHeight(68, Qt.SmoothTransformation)
        _id = self.id_from_index(index)
        qb, sqb = QBuffer(), QBuffer()
        qb.open(QBuffer.ReadWrite)
        sqb.open(QBuffer.ReadWrite)
        pix.save(qb, "JPG")
        spix.save(sqb, "JPG")
        data = str(qb.data())
        sdata = str(sqb.data())
        qb.close()
        sqb.close()
        self.db.update_cover(_id, data, scaled=sdata)
        self.refresh_row(index.row())
    
    def add_formats(self, paths, index):
        for path in paths:
            f = open(path, "rb")      
            title = os.path.basename(path)
            ext = title[title.rfind(".")+1:].lower() if "." in title > -1 else None
            _id = self.id_from_index(index)
            self.db.add_format(_id, ext, f)
            f.close()
        self.refresh_row(index.row())
        self.emit(SIGNAL('formats_added'), index)
    
    def rowCount(self, parent): 
        return len(self._data)
        
    def columnCount(self, parent): 
        return len(self.FIELDS)-3
    
    def setData(self, index, value, role):
        done = False
        if role == Qt.EditRole:
            row = index.row()
            _id = self._data[row]["id"]
            col = index.column()
            val = unicode(value.toString().toUtf8(), 'utf-8').strip()
            if col == 0: 
                col = "title"
            elif col == 1: 
                col = "authors"
            elif col == 2: 
                return False
            elif col == 3: 
                return False
            elif col == 4: 
                col, val = "rating", int(value.toInt()[0])
                if val < 0:  
                    val = 0
                if val > 5: 
                    val = 5
            elif col == 5: 
                col = "publisher"
            else: 
                return False
            self.db.set_metadata_item(_id, col, val)
            self._data[row][col] = val      
            self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
                                index, index)
            for i in range(len(self._orig_data)):
                if self._orig_data[i]["id"] == self._data[row]["id"]:
                    self._orig_data[i][col] = self._data[row][col]
                    break      
            done = True
        return done
    
    def update_tags_and_comments(self, index, tags, comments):
        _id = self.id_from_index(index)
        self.db.set_metadata_item(_id, "tags", tags)
        self.db.set_metadata_item(_id, "comments", comments)
        self.refresh_row(index.row())
    
    def flags(self, index):
        flags = QAbstractTableModel.flags(self, index)
        if index.isValid():       
            if index.column() not in [2, 3]:  
                flags |= Qt.ItemIsEditable    
        return flags
    
    def set_data(self, db):    
        self.db    = db
        self._data = self.db.get_table(self.FIELDS)    
        self._orig_data = self._data
        self.sort(0, Qt.DescendingOrder)
        self.reset()
    
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
        else: return QVariant(str(1+section))
    
    def info(self, row):
        row = self._data[row]
        cover = self.db.get_cover(row["id"])
        exts = ",".join(self.db.get_extensions(row["id"]))    
        if cover:
            pix = QPixmap()
            pix.loadFromData(cover, "", Qt.AutoColor)
            cover = None if pix.isNull() else pix      
        tags = row["tags"]
        if not tags: tags = ""
        comments = row["comments"]
        if not comments: 
            comments = ""
        comments = TableView.wrap(comments, width=80)
        return exts, tags, comments, cover
    
    def id_from_index(self, index): return self._data[index.row()]["id"]
    def id_from_row(self, row): return self._data[row]["id"]
    
    def refresh_row(self, row):
        datum = self.db.get_row_by_id(self._data[row]["id"], self.FIELDS)
        self._data[row:row+1] = [datum]
        for i in range(len(self._orig_data)):
            if self._orig_data[i]["id"] == datum["id"]:
                self._orig_data[i:i+1] = [datum]
                break
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
                    self.index(row, 0), self.index(row, self.columnCount(0)-1))
    
    def book_info(self, _id):
        """ Return title, authors and cover in a dict """
        cover = self.db.get_cover(_id)
        info = self.db.get_row_by_id(_id, ["title", "authors"])
        info["cover"] = cover
        return info
    
    def data(self, index, role):
        if role == Qt.DisplayRole or role == Qt.EditRole:      
            row, col = index.row(), index.column()
            text = None
            row = self._data[row]
            if col == 4: 
                r = row["rating"] if row["rating"] else 0
                if r < 0: 
                    r = 0
                if r > 5: 
                    r = 5
                return QVariant(r)
            if   col == 0: 
                text = TableView.wrap(row["title"], width=35)
            elif col == 1: 
                au = row["authors"]
                if au:
                    au = au.split("&")
                    jau = [ TableView.wrap(a, width=30).strip() for a in au ]
                    text = "\n".join(jau)
            elif col == 2: 
                text = TableView.human_readable(row["size"])
            elif col == 3: 
                text = time.strftime(TIME_WRITE_FMT, \
                                time.strptime(row["date"], self.TIME_READ_FMT))
            elif col == 5: 
                pub = row["publisher"]
                if pub: 
                    text = TableView.wrap(pub, 20)
            if text == None: 
                text = "Unknown"
            return QVariant(text)
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
    
    def sort(self, col, order):
        descending = order != Qt.AscendingOrder
        def getter(key, func):  
            return lambda x : func(itemgetter(key)(x))
        if col == 0: key, func = "title", lambda x : x.lower()
        if col == 1: key, func = "authors", lambda x : x.split()[-1:][0].lower()\
                                                       if x else ""
        if col == 2: key, func = "size", int
        if col == 3: key, func = "date", lambda x: time.mktime(\
                                            time.strptime(x, self.TIME_READ_FMT))
        if col == 4: key, func = "rating", lambda x: x if x else 0
        if col == 5: key, func = "publisher", lambda x : x.lower() if x else ""
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        self._data.sort(key=getter(key, func))
        if descending: self._data.reverse()
        self.emit(SIGNAL("layoutChanged()"))
        self.emit(SIGNAL("sorted()"))
    
    def search(self, query):
        def query_in(book, q):
            au = book["authors"]
            if not au : au = "unknown"
            pub = book["publisher"]
            if not pub : pub = "unknown"
            return q in book["title"].lower() or q in au.lower() or \
                                                                q in pub.lower()
        queries = unicode(query, 'utf-8').lower().split()
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        self._data = []
        for book in self._orig_data:
            match = True
            for q in queries:
                if query_in(book, q) : continue
                else:
                    match = False
                    break
            if match: self._data.append(book)
        self.emit(SIGNAL("layoutChanged()"))
        self.emit(SIGNAL("searched()"))
    
    def delete(self, indices):
        if len(indices): self.emit(SIGNAL("layoutAboutToBeChanged()"))
        items = [ self._data[index.row()] for index in indices ]    
        for item in items:
            _id = item["id"]
            try:
                self._data.remove(item)
            except ValueError: continue
            self.db.delete_by_id(_id)
            for x in self._orig_data:
                if x["id"] == _id: self._orig_data.remove(x)
        self.emit(SIGNAL("layoutChanged()"))
        self.emit(SIGNAL("deleted()"))
        self.db.commit()    
    
    def add_book(self, path):
        """ Must call search and sort on this models view after this """
        _id = self.db.add_book(path)    
        self._orig_data.append(self.db.get_row_by_id(_id, self.FIELDS))

class DeviceBooksModel(QAbstractTableModel):
    @apply
    def booklist(): 
        doc = """ The booklist this model is based on """
        def fget(self):
            return self._orig_data
        return property(doc=doc, fget=fget)
    
    def __init__(self, parent):
        QAbstractTableModel.__init__(self, parent)  
        self._data = []
        self._orig_data = []
    
    def set_data(self, book_list):    
        self._data = book_list
        self._orig_data = book_list
        self.reset()
    
    def rowCount(self, parent): 
        return len(self._data)
    
    def columnCount(self, parent): 
        return 4
    
    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        text = ""
        if orientation == Qt.Horizontal:      
            if section == 0: text = "Title"
            elif section == 1: text = "Author(s)"
            elif section == 2: text = "Size"
            elif section == 3: text = "Date"
            return QVariant(self.trUtf8(text))
        else: return QVariant(str(1+section))
    
    def data(self, index, role):    
        if role == Qt.DisplayRole:
            row, col = index.row(), index.column()
            book = self._data[row]
            if col == 0: 
                text = TableView.wrap(book.title, width=40)
            elif col == 1:
                au = book.authors
                au = au.split("&")
                jau = [ TableView.wrap(a, width=25).strip() for a in au ]
                text = "\n".join(jau)                
            elif col == 2: 
                text = TableView.human_readable(book.size)
            elif col == 3: 
                text = time.strftime(TIME_WRITE_FMT, book.datetime)
            return QVariant(text)
        elif role == Qt.TextAlignmentRole and index.column() in [2, 3]:
            return QVariant(Qt.AlignRight | Qt.AlignVCenter)
        return NONE
    
    def info(self, row):
        row = self._data[row]
        cover = None
        try:
            cover = row.thumbnail
            pix = QPixmap()
            pix.loadFromData(cover, "", Qt.AutoColor)
            cover = None if pix.isNull() else pix
        except: 
            traceback.print_exc()
        au = row.authors if row.authors else "Unknown"
        return row.title, au, TableView.human_readable(row.size), row.mime, cover
    
    def sort(self, col, order):
        def getter(key, func): 
            return lambda x : func(attrgetter(key)(x))
        if col == 0: key, func = "title", lambda x : x.lower()
        if col == 1: key, func = "authors", lambda x :  x.split()[-1:][0].lower()
        if col == 2: key, func = "size", int
        if col == 3: key, func = "datetime", lambda x: x
        descending = order != Qt.AscendingOrder
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        self._data.sort(key=getter(key, func))
        if descending: self._data.reverse()
        self.emit(SIGNAL("layoutChanged()"))
        self.emit(SIGNAL("sorted()"))
    
    def search(self, query):
        queries = unicode(query, 'utf-8').lower().split()
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        self._data = []
        for book in self._orig_data:
            match = True
            for q in queries:
                if q in book.title.lower() or q in book.authors.lower(): continue
                else:
                    match = False
                    break
            if match: self._data.append(book)
        self.emit(SIGNAL("layoutChanged()"))
        self.emit(SIGNAL("searched()"))
    
    def delete(self, indices):
        paths = []
        rows = [ index.row() for index in indices ]
        if not rows: 
            return
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        elems = [ self._data[row] for row in rows ]
        for e in elems:
            _id = e.id
            paths.append(e.path)
            self._orig_data.delete_book(_id)
            try: 
                self._data.remove(e)
            except ValueError: 
                pass
        self.emit(SIGNAL("layoutChanged()"))
        return paths
    
    def path(self, index):  
        return self._data[index.row()].path
    def title(self, index): 
        return self._data[index.row()].title





class DeviceModel(QAbstractListModel):
    
    memory_free      = 0
    card_free        = 0
    show_reader      = False
    show_card        = False
    
    def update_devices(self, reader=None, card=None):
        if reader != None: 
            self.show_reader = reader
        if card != None: 
            self.show_card = card
        self.emit(SIGNAL("layoutChanged()"))
    
    def rowCount(self, parent):
        base = 1
        if self.show_reader:
            base += 1
        if self.show_card:
            base += 1
        return base
    
    def update_free_space(self, reader, card):
        self.memory_free = reader
        self.card_free = card
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
                        self.index(1), self.index(2))
    
    def data(self, index, role):
        row = index.row()    
        data = NONE
        if role == Qt.DisplayRole:
            text = None
            if row == 0: 
                text = "Library"  
            if row == 1 and self.show_reader: 
                text = "Reader\n" + TableView.human_readable(self.memory_free) \
                                  + " available"        
            elif row == 2 and self.show_card: 
                text = "Card\n" + TableView.human_readable(self.card_free) \
                                + " available"
            if text: 
                data = QVariant(text)
        elif role == Qt.DecorationRole:      
            icon = None
            if row == 0: 
                icon = QIcon(":/library")
            elif row == 1 and self.show_reader: 
                icon =  QIcon(":/reader")
            elif self.show_card: 
                icon = QIcon(":/card")
            if icon: 
                data = QVariant(icon)
        elif role == Qt.SizeHintRole:
            if row == 1: 
                return QVariant(QSize(150, 70))
        elif role == Qt.FontRole: 
            font = QFont()
            font.setBold(True)
            data =  QVariant(font)
        return data
    
    def is_library(self, index): 
        return index.row() == 0
    def is_reader(self, index): 
        return index.row() == 1
    def is_card(self, index): 
        return index.row() == 2
    
    def files_dropped(self, files, index, ids):    
        ret = False
        if self.is_library(index) and not ids: 
            self.emit(SIGNAL("books_dropped"), files)
            ret = True
        elif self.is_reader(index):
            self.emit(SIGNAL("upload_books"), "reader", files, ids) 
        elif self.is_card(index):
            self.emit(SIGNAL("upload_books"), "card", files, ids) 
        return ret
