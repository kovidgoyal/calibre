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
from libprs500.communicate import PRS500Device as device
from libprs500.errors import *
from libprs500.lrf.meta import LRFMetaFile, LRFException
from libprs500.gui import import_ui
from database import LibraryDatabase
from editbook import EditBookDialog

from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QObject, QThread, QCoreApplication, QEventLoop, QString, QTreeWidgetItem, QStandardItemModel, QStatusBar, QVariant, QAbstractTableModel, \
                                   QAbstractItemView, QImage, QPixmap, QIcon, QSize, QMessageBox, QSettings, QFileDialog, QErrorMessage, QDialog, QSpinBox,\
                                   QPainterPath, QItemDelegate, QPainter, QPen, QColor, QLinearGradient, QBrush, QStyle,\
                                   qInstallMsgHandler, qDebug, qFatal, qWarning, qCritical
from PyQt4 import uic
import sys, re, string, time, os, os.path, traceback, textwrap, zlib
from stat import ST_SIZE
from tempfile import TemporaryFile, NamedTemporaryFile
from exceptions import Exception as Exception
import xml.dom.minidom as dom
from xml.dom.ext import PrettyPrint as PrettyPrint
from operator import itemgetter, attrgetter
from math import sin, cos, pi

DEFAULT_BOOK_COVER = None
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
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
    col = index.column()
    if col not in [2,3]:
      flags |= Qt.ItemIsEditable
    return flags
  
  def set_data(self, db):
    self.emit(SIGNAL("layoutAboutToBeChanged()"))
    self.db    = db
    self._data = self.db.get_table(self.FIELDS)    
    self._orig_data = self._data
    self.sort(0, Qt.DescendingOrder)
    
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
    if not cover: 
      cover = DEFAULT_BOOK_COVER
      self.image_file = None
    else:
      pix = QPixmap()
      self.image_file = NamedTemporaryFile()
      self.image_file.write(cover)
      self.image_file.flush()
      pix.loadFromData(cover, "", Qt.AutoColor)
      cover = pix.scaledToHeight(COVER_HEIGHT, Qt.SmoothTransformation)
    return row["title"], row["authors"], human_readable(int(row["size"])), exts, cover
  
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
    for index in indices:
      id = self.id_from_index(index)
      self.db.delete_by_id(id)
      row = index.row()
      self._data[row:row+1] = []
      for i in range(len(self._orig_data)):
        if self._orig_data[i]["id"] == id: 
          self._orig_data[i:i+1] = []
          i -=1
    self.emit(SIGNAL("layoutChanged()"))
    self.db.commit()    

class DeviceBooksModel(QAbstractTableModel):
  def __init__(self, parent):
    QAbstractTableModel.__init__(self, parent)  
    self._data = []
    self._orig_data = []
    
  def set_data(self, book_list):
    self.emit(SIGNAL("layoutAboutToBeChanged()"))
    self._data = book_list
    self._orig_data = book_list    
    
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
    try:
      cover = row.thumbnail
      pix = QPixmap()
      self.image_file = NamedTemporaryFile()
      self.image_file.write(cover)
      self.image_file.flush()
      pix.loadFromData(cover, "", Qt.AutoColor)
      cover = pix.scaledToHeight(COVER_HEIGHT, Qt.SmoothTransformation)      
    except Exception, e: 
      self.image_file = None
      cover = DEFAULT_BOOK_COVER
    return row.title, row.author, human_readable(row.size), row.mime, cover
  
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
    
  def path(self, index):  return self._data[index.row()]["path"]
  def title(self, index):  return self._data[index.row()]["title"]
    
    


Ui_MainWindow = import_ui("main.ui")
class MainWindow(QObject, Ui_MainWindow): 
  
  def show_device(self, yes):
    """ If C{yes} show the items on the device otherwise show the items in the library """
    self.device_view.clearSelection(), self.library_view.clearSelection()
    self.book_cover.hide(), self.book_info.hide()
    if yes: 
      self.device_view.show(), self.library_view.hide()
      self.current_view = self.device_view
    else: 
      self.device_view.hide(), self.library_view.show()
      self.current_view = self.library_view
    self.current_view.sortByColumn(3, Qt.DescendingOrder)
      
  
  def tree_clicked(self, item, col):
    if item:
      text = str(item.text(0))
      if text == "Books": text = str(item.parent().text(0))
      if "Library" in text:
        self.show_device(False)
      elif "SONY Reader" in text:
        self.device_view.setModel(self.reader_model)
        QObject.connect(self.device_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
        self.show_device(True)       
      elif "Storage Card" in text:
        self.device_view.setModel(self.card_model)
        QObject.connect(self.device_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
        self.show_device(True)
        
  
  def set_device_data(self, data): 
    model.set_data(data) 
    self.device_view.resizeColumnsToContents()
  
  def model_modified(self):
    if self.library_view.isVisible(): view = self.library_view
    else: view = self.device_view
    view.clearSelection()    
    view.resizeColumnsToContents()
    self.book_cover.hide()
    self.book_info.hide()
    QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)    
  
  def resize_columns(self, topleft, bottomright):
    if self.library_view.isVisible(): view = self.library_view
    else: view = self.device_view
    for c in range(topleft.column(), bottomright.column()+1):
      view.resizeColumnToContents(c)
  
  def show_book(self, current, previous):
    title, author, size, mime, thumbnail = current.model().info(current.row())
    self.book_info.setText(self.BOOK_TEMPLATE.arg(title).arg(size).arg(author).arg(mime))
    self.book_cover.setPixmap(thumbnail)
    try:
      name = os.path.abspath(current.model().image_file.name)
      self.book_cover.setToolTip('<img src="'+name+'">')
    except Exception, e: self.book_cover.setToolTip('<img src=":/default_cover">')
    self.book_cover.show()
    self.book_info.show()
  
  
  def list_context_event(self, event):
    print "TODO:"
  
  
  
  def delete(self, action):
    if self.device_view.isVisible():
      rows   = self.device_view.selectionModel().selectedRows()
      items = [ row.model().title(row) + ": " +  row.model().path(row)[row.model().path(row).rfind("/")+1:] for row in rows ]
      ret = QMessageBox.question(self.window, self.trUtf8("SONY Reader - confirm"),  self.trUtf8("Are you sure you want to delete these items from the device?\n\n") + "\n".join(items), 
               QMessageBox.YesToAll | QMessageBox.No, QMessageBox.YesToAll)
      if ret == QMessageBox.YesToAll:
        self.window.setCursor(Qt.WaitCursor)
        paths, mc, cc = [], False, False
        for book in rows:
          path = book.model().path(book)
          if path[0] == "/": file, prefix, mc = self.main_xml, "xs1:", True
          else:                    file, prefix, cc = self.cache_xml, "",       True
          file.seek(0)
          document = dom.parse(file)
          books = document.getElementsByTagName(prefix + "text")
          for candidate in books:
            if candidate.attributes["path"].value in path:
              paths.append(path)
              candidate.parentNode.removeChild(candidate)
              break
          file.close()
          file = TemporaryFile()
          PrettyPrint(document, file)        
          if len(prefix) > 0: self.main_xml = file
          else: self.cache_xml = file
        for path in paths:
          self.dev.del_file(path)
          model.delete_by_path(path)        
        self.cache_xml.seek(0)
        self.main_xml.seek(0)
        self.status("Files deleted. Updating media list on device")
        if mc: 
          self.dev.del_file(self.dev.MEDIA_XML)
          self.dev.put_file(self.main_xml, self.dev.MEDIA_XML)
        if cc: 
          self.dev.del_file(self.card+self.dev.CACHE_XML)
          self.dev.put_file(self.cache_xml, self.card+self.dev.CACHE_XML)
      self.window.setCursor(Qt.ArrowCursor)
    else:      
      self.library_model.delete(self.library_view.selectionModel().selectedRows())
  
  def read_settings(self):
    settings = QSettings()
    settings.beginGroup("MainWindow")
    self.window.resize(settings.value("size", QVariant(QSize(1000, 700))).toSize())
    settings.endGroup()
    self.database_path = settings.value("database path", QVariant(os.path.expanduser("~/library.db"))).toString()
    
  def write_settings(self):
    settings = QSettings()
    settings.beginGroup("MainWindow")
    settings.setValue("size", QVariant(self.window.size()))
    settings.endGroup()
  
  def close_event(self, e):
    self.write_settings()
    e.accept()
  
  def add(self, action):
    settings = QSettings()
    dir = settings.value("add books dialog dir", QVariant(os.path.expanduser("~"))).toString()
    files = QFileDialog.getOpenFileNames(self.window, "Choose books to add to library", dir, "Books (*.lrf *.lrx *.rtf *.pdf *.txt);;All files (*)")
    if not files.isEmpty():
      x = str(files[0])
      settings.setValue("add books dialog dir", QVariant(os.path.dirname(x)))
      files = str(files.join("|||")).split("|||")      
      for file in files:
        file = os.path.abspath(file)
        title, author, cover, publisher = None, None, None, None
        if ext == "lrf":
          try: 
            lrf = LRFMetaFile(open(file, "r+b"))
            title = lrf.title
            author = lrf.author
            publisher = lrf.publisher
            cover = lrf.thumbnail
            if "unknown" in author.lower(): author = None
          except IOError, e:
            self.show_error(e, "Unable to access <b>"+file+"</b>")
            return
          except LRFException: pass
          self.library_model.add(file, title, author, publisher, cover)
      
  def edit(self, action):    
    if self.library_view.isVisible():
      rows = self.library_view.selectionModel().selectedRows()
      for row in rows:
        id = self.library_model.id_from_index(row)
        dialog = QDialog(self.window)
        ed = EditBookDialog(dialog, id, self.library_model.db)
        if dialog.exec_() == QDialog.Accepted:
          self.library_model.refresh_row(row.row())
          
  
  def show_error(self, e, msg): 
    QErrorMessage(self.window).showMessage(msg+"<br><b>Error: </b>"+str(e)+"<br><br>Traceback:<br>"+traceback.format_exc(e))
  
  def __init__(self, window, log_packets):
    QObject.__init__(self)
    Ui_MainWindow.__init__(self)
  
    self.dev = device(report_progress=self.progress, log_packets=log_packets)
    self.is_connected = False    
    self.setupUi(window)
    self.card = None
    self.window = window
    window.closeEvent = self.close_event
    self.read_settings()
    
    # Setup Library Book list
    self.library_model = LibraryBooksModel(window)
    self.library_model.set_data(LibraryDatabase(str(self.database_path)))
    self.library_view.setModel(self.library_model)
    self.current_view = self.library_view
    self.library_view.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.library_view.setSortingEnabled(True)
    self.library_view.contextMenuEvent = self.list_context_event
    self.library_view.setItemDelegate(LibraryDelegate(self.library_view))
    QObject.connect(self.library_model, SIGNAL("layoutChanged()"), self.library_view.resizeRowsToContents)
    QObject.connect(self.library_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
    QObject.connect(self.search, SIGNAL("textChanged(QString)"), self.library_model.search)
    QObject.connect(self.library_model, SIGNAL("sorted()"), self.model_modified)
    QObject.connect(self.library_model, SIGNAL("searched()"), self.model_modified)
    QObject.connect(self.library_model, SIGNAL("deleted()"), self.model_modified)    
    QObject.connect(self.library_model, SIGNAL("dataChanged(QModelIndex, QModelIndex)"), self.resize_columns)
    self.library_view.resizeColumnsToContents()
    
    # Create Device tree
    QObject.connect(self.device_tree, SIGNAL("itemClicked ( QTreeWidgetItem *, int )"), self.tree_clicked)
    QObject.connect(self.device_tree, SIGNAL("itemActivated ( QTreeWidgetItem *, int )"), self.tree_clicked)
    self.device_tree.header().hide()    
    library = QTreeWidgetItem(self.device_tree, QTreeWidgetItem.Type)
    library.setData(0, Qt.DisplayRole, QVariant("Library"))
    library.setData(0, Qt.DecorationRole, QVariant(QIcon(":/library")))
    books =QTreeWidgetItem(library, QTreeWidgetItem.Type)
    books.setData(0, Qt.DisplayRole, QVariant("Books"))
    self.device_tree.expandItem(library)    
    buffer = QTreeWidgetItem(self.device_tree, QTreeWidgetItem.Type)
    buffer.setFlags(Qt.ItemFlags())
    library = QTreeWidgetItem(self.device_tree, QTreeWidgetItem.Type)
    library.setData(0, Qt.DisplayRole, QVariant("SONY Reader"))
    library.setData(0, Qt.DecorationRole, QVariant(QIcon(":/reader")))
    books =QTreeWidgetItem(library, QTreeWidgetItem.Type)
    books.setData(0, Qt.DisplayRole, QVariant("Books"))
    self.device_tree.expandItem(library)    
    buffer = QTreeWidgetItem(self.device_tree, QTreeWidgetItem.Type)
    buffer.setFlags(Qt.ItemFlags())
    library = QTreeWidgetItem(self.device_tree, QTreeWidgetItem.Type)
    library.setData(0, Qt.DisplayRole, QVariant("Storage Card"))
    library.setData(0, Qt.DecorationRole, QVariant(QIcon(":/card")))
    books =QTreeWidgetItem(library, QTreeWidgetItem.Type)
    books.setData(0, Qt.DisplayRole, QVariant("Books"))
    self.device_tree.expandItem(library)    
    self.device_tree.reader = self.device_tree.topLevelItem(2)
    self.device_tree.card = self.device_tree.topLevelItem(4)
    def hider(i):
      def do(s, x): s.topLevelItem(i).setHidden(x), s.topLevelItem(i+1).setHidden(x)
      return do
    self.device_tree.hide_reader = hider(1)
    self.device_tree.hide_card = hider(3)
    self.device_tree.hide_reader(self.device_tree, True)
    self.device_tree.hide_card(self.device_tree, True)
    
    
    # Create Device Book list
    self.reader_model = DeviceBooksModel(window)    
    self.card_model = DeviceBooksModel(window)    
    self.device_view.setModel(self.reader_model)
    self.device_view.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.device_view.setSortingEnabled(True)
    self.device_view.contextMenuEvent = self.list_context_event
    QObject.connect(self.device_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
    for model in (self.reader_model, self. card_model):
      QObject.connect(model, SIGNAL("layoutChanged()"), self.device_view.resizeRowsToContents)
      QObject.connect(self.search, SIGNAL("textChanged(QString)"), model.search)
      QObject.connect(model, SIGNAL("sorted()"), self.model_modified)
      QObject.connect(model, SIGNAL("searched()"), self.model_modified)
      QObject.connect(model, SIGNAL("deleted()"), self.model_modified)
      QObject.connect(model, SIGNAL("dataChanged(QModelIndex, QModelIndex)"), self.resize_columns)
    
    # Setup book display
    self.BOOK_TEMPLATE = self.book_info.text()    
    self.BOOK_IMAGE       = DEFAULT_BOOK_COVER
    self.book_cover.hide()
    self.book_info.hide()
    
    # Connect actions
    QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add)
    QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete)
    QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit)
    
    self.device_detector = self.startTimer(1000)
    self.splitter.setStretchFactor(1,100)
    self.search.setFocus(Qt.OtherFocusReason)
    self.show_device(False)
    window.show()    
    
  def timerEvent(self, e):
    if e.timerId() == self.device_detector:
      is_connected = self.dev.is_connected()
      if is_connected and not self.is_connected:
        self.establish_connection()
      elif not is_connected and self.is_connected:
        self.device_removed()
  
  def device_removed(self, timeout=False):
    """ @todo: only reset stuff if library is not shown """
    self.is_connected = False
    self.df.setText("SONY Reader: <br><br>Storage card:")
    self.device_tree.hide_reader(self.device_tree, True)
    self.device_tree.hide_card(self.device_tree, True)
    self.book_cover.hide()
    self.book_info.hide()
    self.device_view.hide()
    self.library_view.show()
    
  
  def timeout_error(self):
    """ @todo: display error dialog """
    pass
  
  def progress(self, val):
    if val < 0:
      self.progress_bar.setMaximum(0)
    else: self.progress_bar.setValue(val)
    QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
  
  def status(self, msg):
    self.progress_bar.setMaximum(100)
    self.progress_bar.reset()
    self.progress_bar.setFormat(msg + ": %p%")
    self.progress(0)
    QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
  
  def establish_connection(self):
    self.window.setCursor(Qt.WaitCursor)
    self.status("Connecting to device")    
    try:
      space = self.dev.available_space()
    except DeviceError:
      self.dev.reconnect()
      return    
    except ProtocolError, e: 
      traceback.print_exc(e)
      print >> sys.stderr, "Unable to connect device. Please try unplugiing and reconnecting it"
      qFatal("Unable to connect device. Please try unplugiing and reconnecting it")
      
    sc = space[1][1] if space[1][1] else space[2][1]
    self.df.setText("SONY Reader:  " + human_readable(space[0][1]) + "<br><br>Storage card: " + human_readable(sc))
    self.is_connected = True
    if space[1][2] > 0: card = "a:"
    elif space[2][2] > 0: card = "b:"
    else: card = None
    if card: self.device_tree.hide_card(self.device_tree, False)
    else: self.device_tree.hide_card(self.device_tree, True)
    self.device_tree.hide_reader(self.device_tree, False)
    self.status("Loading media list from SONY Reader")
    self.reader_model.set_data(self.dev.books())
    if card: self.status("Loading media list from Storage Card")
    self.card_model.set_data(self.dev.books(oncard=True))
    self.progress(100)
    self.window.setCursor(Qt.ArrowCursor)
    
def main():
    from optparse import OptionParser
    from libprs500 import __version__ as VERSION
    parser = OptionParser(usage="usage: %prog [options]", version=VERSION)
    parser.add_option("--log-packets", help="print out packet stream to stdout. "+\
                    "The numbers in the left column are byte offsets that allow the packet size to be read off easily.", \
                    dest="log_packets", action="store_true", default=False)
    options, args = parser.parse_args()
    from PyQt4.Qt import QApplication, QMainWindow
    app = QApplication(sys.argv)
    global DEFAULT_BOOK_COVER
    DEFAULT_BOOK_COVER = QPixmap(":/default_cover")
    window = QMainWindow()
    def handle_exceptions(t, val, tb):
      sys.__excepthook__(t, val, tb)
      try: 
        qCritical("There was an unexpected error: \n"+"\n".join(traceback.format_exception(t, val, tb)))
      except: pass      
    sys.excepthook = handle_exceptions
    QCoreApplication.setOrganizationName("KovidsBrain")
    QCoreApplication.setApplicationName("SONY Reader")
    handler = QErrorMessage.qtHandler()
    handler.resize(600, 400)
    handler.setModal(True)
    gui = MainWindow(window, options.log_packets)    
    ret = app.exec_()    
    return ret
    
if __name__ == "__main__": main()
