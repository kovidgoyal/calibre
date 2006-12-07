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

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QApplication, QString, QFont, QStandardItemModel, QStandardItem, QVariant, QAbstractTableModel, QTableView, QTreeView, QLabel,\
                                   QAbstractItemView, QPixmap, QIcon, QSize, QMessageBox, QSettings, QFileDialog, QErrorMessage, QDialog, QSpinBox, QPoint, QTemporaryFile, QDir,\
                                   QPainterPath, QItemDelegate, QPainter, QPen, QColor, QLinearGradient, QBrush, QStyle,\
                                   QStringList, QByteArray, QBuffer, QMimeData, QTextStream, QIODevice, QDrag,\
                                   qDebug, qFatal, qWarning, qCritical
import re, os, string, textwrap, time, traceback

from operator import itemgetter, attrgetter
from socket import gethostname
from urlparse import urlparse, urlunparse
from urllib import quote, unquote
from math import sin, cos, pi
from libprs500 import TEMPORARY_FILENAME_TEMPLATE as TFT
from libprs500.lrf.meta import LRFMetaFile

NONE = QVariant()
TIME_WRITE_FMT  = "%d %b %Y"
COVER_HEIGHT = 80

def human_readable(size):
  """ Convert a size in bytes into a human readable form """
  if size < 1024: divisor, suffix = 1, "B"
  elif size < 1024*1024: divisor, suffix = 1024., "KB"
  elif size < 1024*1024*1024: divisor, suffix = 1024*1024, "MB"
  elif size < 1024*1024*1024*1024: divisor, suffix = 1024*1024, "GB"
  size = str(size/divisor)
  if size.find(".") > -1: size = size[:size.find(".")+2]
  return size + " " + suffix


def wrap(s, width=20):
  return textwrap.fill(str(s), width) 

def get_r_ok_files(event):
  """ @type event: QDropEvent """
  files = []
  md = event.mimeData()
  if md.hasFormat("text/uri-list"):
    candidates = bytes_to_string(md.data("text/uri-list")).split("\n")
    print candidates
    for path in candidates:
      path = os.path.abspath(re.sub(r"^file://", "", path))
      if os.path.isfile(path) and os.access(path, os.R_OK): files.append(path)
  return files
  

def bytes_to_string(qba):
  """ @type qba: QByteArray """
  return unicode(QString.fromUtf8(qba.data())).strip()

class FileDragAndDrop(object):
  _drag_start_position = QPoint()
  
  @classmethod
  def _bytes_to_string(cls, qba):
    """ @type qba: QByteArray """
    return unicode(QString.fromUtf8(qba.data())).strip()
  
  @classmethod
  def _get_r_ok_files(cls, event):
    files = []
    md = event.mimeData()
    if md.hasFormat("text/uri-list"):
      candidates = cls._bytes_to_string(md.data("text/uri-list")).split()
      for url in candidates:
        o = urlparse(url)
        if o.scheme != 'file':
          qWarning(o.scheme + " not supported in drop events")
          continue
        path = unquote(o.path)
        if not os.access(path, os.R_OK):
          qWarning("You do not have read permission for: " + path)
          continue
        if os.path.isdir(path):
          root, dirs, files2 = os.walk(path)
          for file in files2:
            path = root + file
            if os.access(path, os.R_OK): files.append(path)
        else: files.append(path)
    return files
  
  def mousePressEvent(self, event):
    if event.button == Qt.LeftButton:
      self._drag_start_position = event.pos()
  
  def mouseMoveEvent(self, event):
    if event.buttons() & Qt.LeftButton != Qt.LeftButton: return
    if (event.pos() - self._drag_start_position).manhattanLength() < QApplication.startDragDistance(): return
    self.start_drag(self._drag_start_position)
    
  def start_drag(self, pos): pass
  
  def dragEnterEvent(self, event):
    if event.mimeData().hasFormat("text/uri-list"): event.acceptProposedAction()
  
  def dragMoveEvent(self, event):
    event.acceptProposedAction()
  
  def dropEvent(self, event):
    files = self._get_r_ok_files(event)
    if files:
      if self.files_dropped(files): event.acceptProposedAction()
      
  def files_dropped(self, files): return False
  
  def drag_object(self, extensions):
    if extensions:
      drag = QDrag(self)
      mime_data = QMimeData()
      self._dragged_files, urls = [], []
      for ext in extensions:
        f = TemporaryFile(ext=ext)
        f.open()
        urls.append(urlunparse(('file', quote(gethostname()), quote(str(f.fileName())), '','','')))
        self._dragged_files.append(f)
      mime_data.setData("text/uri-list", QByteArray("\n".join(urls)))
      user = None
      try: user = os.environ['USER']
      except: pass
      if user: mime_data.setData("text/x-xdnd-username", QByteArray(user))
      drag.setMimeData(mime_data)
      return drag, self._dragged_files
        
  

class TemporaryFile(QTemporaryFile):
  def __init__(self, ext=""):
    if ext: ext = "." + ext
    path = QDir.tempPath() + "/" + TFT + "_XXXXXX"+ext
    QTemporaryFile.__init__(self, path)

class CoverDisplay(FileDragAndDrop, QLabel):
  def files_dropped(self, files):
    pix = QPixmap()
    for file in files:
      pix = QPixmap(file)
      if not pix.isNull(): break
    if not pix.isNull():      
      self.emit(SIGNAL("cover_received(QPixmap)"), pix)
      return True
  
  def start_drag(self, event):
    drag, files = self.drag_object(["jpeg"])
    if drag and files:
      file = files[0]
      drag.setPixmap(self.pixmap())
      self.pixmap().save(file)
      file.close()
      drag.start(Qt.MoveAction)
    
class DeviceView(QTreeView):
  def __init__(self, parent):
    QTreeView.__init__(self, parent)
    self.header().hide()    
    self.setIconSize(QSize(32,32))
    
  def hide_reader(self, x):
    self.setRowHidden(2, self.model().indexFromItem(self.model().invisibleRootItem()), x)
    
  def hide_card(self, x):
    self.setRowHidden(4, self.model().indexFromItem(self.model().invisibleRootItem()), x)

class DeviceBooksView(QTableView):
  def __init__(self, parent):
    QTableView.__init__(self, parent)
    self.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.setSortingEnabled(True)

class LibraryBooksView(QTableView):
  def __init__(self, parent):
    QTableView.__init__(self, parent)
    self.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.setSortingEnabled(True)
    self.setItemDelegate(LibraryDelegate(self))
    
  def get_verified_path(self, mime_data):
    if mime_data.hasFormat("text/plain"):
      text = unicode(mime_data.text())
      text = re.sub(r"^file://", "", text)
      if os.access(os.path.abspath(text), os.R_OK): return text
    return None
  def dragEnterEvent(self, event):
    if self.get_verified_path(event.mimeData()): event.acceptProposedAction()
    
  def dragMoveEvent(self, event): event.acceptProposedAction()
  
  def dropEvent(self, event):
    path = self.get_verified_path(event.mimeData())
    if path: 
      if self.model().handle_drop(path, self.indexAt(event.pos())): event.acceptProposedAction()
      


class LibraryDelegate(QItemDelegate):
  COLOR = QColor("blue")
  SIZE     = 16
  PEN      = QPen(COLOR, 1, Qt.SolidLine, Qt.RoundCap,  Qt.RoundJoin)
  
  def __init__(self, parent):
    QItemDelegate.__init__(self, parent)
    self.star_path = QPainterPath()
    self.star_path.moveTo(90, 50)
    for i in range(1, 5):
      self.star_path.lineTo(50 + 40 * cos(0.8 * i * pi), 50 + 40 * sin(0.8 * i * pi))
    self.star_path.closeSubpath()
    self.star_path.setFillRule(Qt.WindingFill)
    gradient = QLinearGradient(0, 0, 0, 100)
    gradient.setColorAt(0.0, self.COLOR)
    gradient.setColorAt(1.0, self.COLOR)
    self. brush = QBrush(gradient)
    self.factor = self.SIZE/100.
    
    
  def sizeHint(self, option, index):
    if index.column() != 4:
      return QItemDelegate.sizeHint(self, option, index)
    num = index.model().data(index, Qt.DisplayRole).toInt()[0]
    return QSize(num*(self.SIZE), self.SIZE+4)
  
  def paint(self, painter, option, index):
    if index.column() != 4:
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
  FIELDS = ["id", "title", "authors", "size", "date", "rating", "publisher", "tags"]  
  TIME_READ_FMT = "%Y-%m-%d %H:%M:%S"
  def __init__(self, parent):
    QAbstractTableModel.__init__(self, parent)
    self.db    = None 
    self._data = None
    self._orig_data = None
    self.image_file = None
    
  def update_cover(self, index, pix):
    id = self.id_from_index(index)
    qb = QBuffer()
    qb.open(QBuffer.ReadWrite);
    pix.save(qb, "JPG")
    data = str(qb.data())
    qb.close()
    self.db.update_cover(id, data)
  
  def handle_drop(self, path, index):
    print "249", path, index.row()
    if index.isValid():
      f = open(path, "rb")      
      title = os.path.basename(path)
      ext = title[title.rfind(".")+1:].lower() if "." in title > -1 else None
      self.db.add_format(self.id_from_index(index), ext, f)
      f.close()
    else:
      pass # TODO: emit book add signal
    return True
    
  def rowCount(self, parent): return len(self._data)
  def columnCount(self, parent): return len(self.FIELDS)-2
    
  def setData(self, index, value, role):
    done = False
    if role == Qt.EditRole:
      row = index.row()
      id = self._data[row]["id"]
      col = index.column()
      val = str(value.toString())
      if col == 0: col = "title"
      elif col == 1: col = "authors"
      elif col == 2: return False
      elif col == 3: return False
      elif col == 4: 
        col, val = "rating", int(value.toInt()[0])
        if val < 0: val =0
        if val > 5: val = 5
      elif col == 5: col = "publisher"
      else: return False
      self.db.set_metadata_item(id, col, val)
      self._data[row][col] = val      
      self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), index, index)
      for i in range(len(self._orig_data)):
        if self._orig_data[i]["id"] == self._data[row]["id"]:
          self._orig_data[i][col] = self._data[row][col]
          break      
      done = True
    return done
  
  def flags(self, index):
    flags = QAbstractTableModel.flags(self, index)
    if index.isValid(): 
      flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
      if index.column() not in [2,3]:  flags |= Qt.ItemIsEditable
    else: flags |= Qt.ItemIsDropEnabled
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
    au = row["authors"]
    if not au: au = "Unknown"
    return row["title"], au, human_readable(int(row["size"])), exts, cover
  
  def id_from_index(self, index): return self._data[index.row()]["id"]
  
  def refresh_row(self, row):
    self._data[row] = self.db.get_row_by_id(self._data[row]["id"], self.FIELDS)
    for i in range(len(self._orig_data)):
      if self._orig_data[i]["id"] == self._data[row]["id"]:
        self._orig_data[i:i+1] = self._data[row]
        break
    self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), self.index(row, 0), self.index(row, self.columnCount(0)-1))
  
  def data(self, index, role):
    if role == Qt.DisplayRole or role == Qt.EditRole:      
      row, col = index.row(), index.column()
      text = None
      row = self._data[row]
      if col == 4: 
        r = row["rating"] if row["rating"] else 0
        if r < 0: r= 0
        if r > 5: r=5
        return QVariant(r)
      if   col == 0: text = wrap(row["title"], width=25)
      elif col == 1: 
        au = row["authors"]
        if au : text = wrap(re.sub("&", "\n", au), width=25)
      elif col == 2: text = human_readable(row["size"])
      elif col == 3: text = time.strftime(TIME_WRITE_FMT, time.strptime(row["date"], self.TIME_READ_FMT))
      elif col == 5: 
        pub = row["publisher"]
        if pub: text = wrap(pub, 20)
      if text == None: text = "Unknown"
      return QVariant(text)
    elif role == Qt.TextAlignmentRole and index.column() in [2,3,4]:
      return QVariant(Qt.AlignRight)
    return NONE
      
  def sort(self, col, order):
    descending = order != Qt.AscendingOrder
    def getter(key, func):  return lambda x : func(itemgetter(key)(x))
    if col == 0: key, func = "title", string.lower
    if col == 1: key, func = "authors", lambda x : x.split()[-1:][0].lower() if x else ""
    if col == 2: key, func = "size", int
    if col == 3: key, func = "date", lambda x: time.mktime(time.strptime(x, self.TIME_READ_FMT))
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
      return q in book["title"].lower() or q in au.lower() or q in pub.lower()
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
      id = item["id"]
      try:
        self._data.remove(item)
      except ValueError: continue
      self.db.delete_by_id(id)
      for x in self._orig_data:
        if x["id"] == id: self._orig_data.remove(x)
    self.emit(SIGNAL("layoutChanged()"))
    self.emit(SIGNAL("deleted()"))
    self.db.commit()    

  def add_book(self, path):
    """ Must call search and sort after this """
    id = self.db.add_book(path)    
    self._orig_data.append(self.db.get_row_by_id(id, self.FIELDS))
    
  def mimeTypes(self):
    s = QStringList()
    s << "application/vnd.text.list" # Title, authors
    s << "image/jpeg"                    # 60x80 thumbnail
    s << "application/x-sony-bbeb"
    s << "application/pdf"
    s << "text/rtf"
    s <<  "text/plain"    
    return s
    
  def mimeData(self, indices):
    mime_data = QMimeData()    
    encoded_data = QByteArray()    
    rows = []
    for index in indices:
      if index.isValid():
        row = index.row()
        if row in rows: continue
        title, authors, size, exts, cover = self.info(row)
        encoded_data.append(title)
        encoded_data.append(authors)
        rows.append(row)
    mime_data.setData("application/vnd.text.list", encoded_data)
    return mime_data
    
class DeviceBooksModel(QAbstractTableModel):
  def __init__(self, parent):
    QAbstractTableModel.__init__(self, parent)  
    self._data = []
    self._orig_data = []
    
  def set_data(self, book_list):    
    self._data = book_list
    self._orig_data = book_list
    self.reset()
    
  def rowCount(self, parent): return len(self._data)
  def columnCount(self, parent): return 4
  
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
      if col == 0: text = wrap(book.title, width=40)
      elif col == 1: text = re.sub("&\s*","\n", book.author)
      elif col == 2: text = human_readable(book.size)
      elif col == 3: text = time.strftime(TIME_WRITE_FMT, book.datetime)
      return QVariant(text)
    elif role == Qt.TextAlignmentRole and index.column() in [2,3]:
      return QVariant(Qt.AlignRight)
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
    au = row.author if row.author else "Unknown"
    return row.title, au, human_readable(row.size), row.mime, cover
  
  def sort(self, col, order):
    def getter(key, func):  return lambda x : func(attrgetter(key)(x))
    if col == 0: key, func = "title", string.lower
    if col == 1: key, func = "author", lambda x :  x.split()[-1:][0].lower()
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
        if q in book.title.lower() or q in book.author.lower(): continue
        else:
          match = False
          break
      if match: self._data.append(book)
    self.emit(SIGNAL("layoutChanged()"))
    self.emit(SIGNAL("searched()"))
    
  def delete_by_path(self, path):
    self.emit(SIGNAL("layoutAboutToBeChanged()"))
    index = -1
    for book in self._data:
      if path in book["path"]:
        self._data.remove(book)
        break
    for book in self._orig_data:
      if path in book["path"]:
        self._orig_data.remove(book)
        break
    self.emit(SIGNAL("layoutChanged()"))
    self.emit(SIGNAL("deleted()"))
    
  def path(self, index):  return self._data[index.row()].path
  def title(self, index):  return self._data[index.row()].title
    
    



class DeviceModel(QStandardItemModel):    
  def __init__(self, parent): 
    QStandardItemModel.__init__(self, parent)
    root = self.invisibleRootItem()
    font = QFont()
    font.setBold(True)
    self.library  = QStandardItem(QIcon(":/library"), QString("Library"))
    self.reader = QStandardItem(QIcon(":/reader"), "SONY Reader")
    self.card     = QStandardItem(QIcon(":/card"), "Storage Card")
    self.library.setFont(font)
    self.reader.setFont(font)
    self.card.setFont(font)
    self.blank   = QStandardItem("")
    self.blank.setFlags(Qt.ItemFlags())
    root.appendRow(self.library)
    root.appendRow(self.blank)
    root.appendRow(self.reader)
    root.appendRow(self.blank.clone())
    root.appendRow(self.card)
    self.library.appendRow(QStandardItem("Books"))
    self.reader.appendRow(QStandardItem("Books"))
    self.card.appendRow(QStandardItem("Books"))   
    
  
  

      
