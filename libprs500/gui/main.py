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
from database import LibraryDatabase
import images
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QObject, QThread, QCoreApplication, QEventLoop, QString, QStandardItem, QStandardItemModel, QStatusBar, QVariant, QAbstractTableModel, \
                                   QAbstractItemView, QImage, QPixmap, QIcon, QSize, QMessageBox, QSettings, QFileDialog, QErrorMessage
from PyQt4 import uic
import sys, pkg_resources, re, string, time, os, os.path, traceback, textwrap, zlib
from stat import ST_SIZE
from tempfile import TemporaryFile, NamedTemporaryFile
from exceptions import Exception as Exception
import xml.dom.minidom as dom
from xml.dom.ext import PrettyPrint as PrettyPrint
from operator import itemgetter

NONE = QVariant()
TIME_WRITE_FMT  = "%d %b %Y"
COVER_HEIGHT = 80

def human_readable(size):
  """ Convert a size in bytes into a human readle form """
  if size < 1024: divisor, suffix = 1, "B"
  elif size < 1024*1024: divisor, suffix = 1024., "KB"
  elif size < 1024*1024*1024: divisor, suffix = 1024*1024, "MB"
  elif size < 1024*1024*1024*1024: divisor, suffix = 1024*1024, "GB"
  size = str(size/divisor)
  if size.find(".") > -1: size = size[:size.find(".")+2]
  return size + " " + suffix


def wrap(s, width=20):
  return textwrap.fill(str(s), width) 

class LibraryBooksModel(QAbstractTableModel):
  FIELDS = ["id", "title", "authors", "size", "date", "publisher", "tags"]
  TIME_READ_FMT = "%Y-%m-%d %H:%M:%S"
  def __init__(self, parent, db_path):
    QAbstractTableModel.__init__(self, parent)
    self.db    = LibraryDatabase(db_path)
    self._data = self.db.get_table(self.FIELDS)
    self._orig_data = self._data
    self.image_file = None
    self.sort(0, Qt.DescendingOrder)
    
  def rowCount(self, parent): return len(self._data)
  def columnCount(self, parent): return len(self.FIELDS)-2
    
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
      elif section == 4: text = "Publisher"
      return QVariant(self.trUtf8(text))
    else: return QVariant(str(1+section))
    
  def info(self, row):
    row = self._data[row]
    cover = self.db.get_cover(row["id"])
    exts = ",".join(self.db.get_extensions(row["id"]))    
    if not cover: 
      cover = QPixmap(":/images/book.png")
      self.image_file = None
    else:
      pix = QPixmap()
      self.image_file = NamedTemporaryFile()
      self.image_file.write(cover)
      self.image_file.flush()
      pix.loadFromData(cover, "", Qt.AutoColor)
      cover = pix.scaledToHeight(COVER_HEIGHT, Qt.SmoothTransformation)
    return row["title"], row["authors"], human_readable(int(row["size"])), exts, cover
  
  def data(self, index, role):
    if role == Qt.DisplayRole:      
      row, col = index.row(), index.column()
      text = None
      row = self._data[row]
      if   col == 0: text = wrap(row["title"], width=25)
      elif col == 1: 
        au = row["authors"]
        if au : text = wrap(re.sub("&", "\n", au), width=25)
      elif col == 2: text = human_readable(row["size"])
      elif col == 3: text = time.strftime(TIME_WRITE_FMT, time.strptime(row["date"], self.TIME_READ_FMT))
      elif col == 4: 
        pub = row["publisher"]
        if pub: text = wrap(pub, 20)
      if not text: text = "Unknown"
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
    if col == 4: key, func = "publisher", lambda x : x.lower() if x else ""
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

class DeviceBooksModel(QAbstractTableModel):
  TIME_READ_FMT  = "%a, %d %b %Y %H:%M:%S %Z"  
  def __init__(self, parent, data):
    QAbstractTableModel.__init__(self, parent)
    self._data = data
    self._orig_data = data
    self.image_file = None
  
  def set_data(self, data):
    self.emit(SIGNAL("layoutAboutToBeChanged()"))
    self._data = data
    self._orig_data = data
    self.sort(0, Qt.DescendingOrder)
    
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
      if col == 0: text = book["title"]
      elif col == 1: text = book["author"]
      elif col == 2: text = human_readable(int(book["size"]))
      elif col == 3: text = time.strftime(TIME_WRITE_FMT, time.strptime(book["date"], self.TIME_READ_FMT))
      return QVariant(text)
    elif role == Qt.TextAlignmentRole and index.column() in [2,3]:
      return QVariant(Qt.AlignRight)
    return NONE
    
  def info(self, row):
    row = self._data[row]    
    try:
      cover = row["thumbnail"]
      pix = QPixmap()
      self.image_file = NamedTemporaryFile()
      self.image_file.write(cover)
      self.image_file.flush()
      pix.loadFromData(cover, "", Qt.AutoColor)
      cover = pix.scaledToHeight(COVER_HEIGHT, Qt.SmoothTransformation)      
    except Exception, e: 
      self.image_file = None
      cover = QPixmap(":/images/book.png")
    return row["title"], row["author"], human_readable(int(row["size"])), row["mime"], cover
  
  def sort(self, col, order):
    def getter(key, func):  return lambda x : func(itemgetter(key)(x))
    if col == 0: key, func = "title", string.lower
    if col == 1: key, func = "author", lambda x : x.split()[-1:][0].lower()
    if col == 2: key, func = "size", int
    if col == 3: key, func = "date", lambda x: time.mktime(time.strptime(x, self.TIME_READ_FMT))
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
        if q in book["title"].lower() or q in book["author"].lower(): continue
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
    
    

Ui_MainWindow, bclass = uic.loadUiType(pkg_resources.resource_stream(__name__, "main.ui"))
class MainWindow(QObject, Ui_MainWindow): 
  
  def tree_clicked(self, index):
    def show_device(yes):
      if yes: self.device_view.show(), self.library_view.hide()
      else: self.device_view.hide(), self.library_view.show()
    item = self.tree.itemFromIndex(index)
    text = str(item.text())
    if text == "Library":
      show_device(False)
    elif text == "SONY Reader":
      show_device(True)
      self.set_device_data(self.main_books + self.card_books)
    elif text == "Main Memory":
      show_device(True)
      self.set_device_data(self.main_books)
    elif text == "Storage Card":
      show_device(True)
      self.set_device_data(self.card_books)
    elif text == "Books":
      text = str(item.parent().text())
      if text == "Library":
        show_device(False)        
      elif text == "Main Memory":
        show_device(True)
        self.set_device_data(self.main_books)  
      elif text == "Storage Card":
        show_device(True)
        self.set_data(self.card_books)
  
  def set_device_data(self, data): 
    self.device_model.set_data(data) 
    self.device_view.resizeColumnsToContents()
  
  def model_modified(self):
    self.device_view.clearSelection()
    self.library_view.clearSelection()
    self.book_cover.hide()
    self.book_info.hide()
    QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)    
  
  def show_book(self, current, previous):
    title, author, size, mime, thumbnail = current.model().info(current.row())
    self.book_info.setText(self.BOOK_TEMPLATE.arg(title).arg(size).arg(author).arg(mime))
    self.book_cover.setPixmap(thumbnail)
    try:
      name = os.path.abspath(current.model().image_file.name)
      self.book_cover.setToolTip('<img src="'+name+'">')
    except Exception, e: self.book_cover.setToolTip('<img src=":/images/book.png">')
    self.book_cover.show()
    self.book_info.show()
  
  def clear(self, checked): self.search.setText("")
  
  def list_context_event(self, event):
    print "TODO:"
  
  def do_delete(self, rows):
    if self.device_model.__class__.__name__ == "DeviceBooksdevice_model":
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
        self.device_model.delete_by_path(path)        
      self.cache_xml.seek(0)
      self.main_xml.seek(0)
      self.status("Files deleted. Updating media list on device")
      if mc: 
        self.dev.del_file(self.dev.MEDIA_XML)
        self.dev.put_file(self.main_xml, self.dev.MEDIA_XML)
      if cc: 
        self.dev.del_file(self.card+self.dev.CACHE_XML)
        self.dev.put_file(self.cache_xml, self.card+self.dev.CACHE_XML)
  
  def delete(self, action):
    self.window.setCursor(Qt.WaitCursor)
    rows   = self.device_view.selectionModel().selectedRows()
    items = [ row.model().title(row) + ": " +  row.model().path(row)[row.model().path(row).rfind("/")+1:] for row in rows ]
    ret = QMessageBox.question(self.window, self.trUtf8("SONY Reader - confirm"),  self.trUtf8("Are you sure you want to delete these items from the device?\n\n") + "\n".join(items), 
             QMessageBox.YesToAll | QMessageBox.No, QMessageBox.YesToAll)
    if ret == QMessageBox.YesToAll:
      self.do_delete(rows)
    self.window.setCursor(Qt.ArrowCursor)
  
  def read_settings(self):
    settings = QSettings()
    settings.beginGroup("MainWindow")
    self.window.resize(settings.value("size", QVariant(QSize(1000, 700))).toSize())
    settings.endGroup()
    self.database_path = settings.value("database path", QVariant(os.path.expanduser("~/library.sqlite"))).toString()
    
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
      
  def show_error(self, e, msg): 
    QErrorMessage(self.window).showMessage(msg+"<br><b>Error: </b>"+str(e)+"<br><br>Traceback:<br>"+traceback.format_exc(e))
  
  def __init__(self, window):
    QObject.__init__(self)
    Ui_MainWindow.__init__(self)    
    self.dev = device(report_progress=self.progress)
    self.is_connected = False    
    self.setupUi(window)
    self.card = None
    self.window = window
    window.closeEvent = self.close_event
    self.read_settings()
    
    # Setup Library Book list
    self.library_model = LibraryBooksModel(window, str(self.database_path))
    self.library_view.setModel(self.library_model)
    self.library_view.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.library_view.setSortingEnabled(True)
    self.library_view.contextMenuEvent = self.list_context_event
    QObject.connect(self.library_model, SIGNAL("layoutChanged()"), self.library_view.resizeRowsToContents)
    QObject.connect(self.library_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
    QObject.connect(self.search, SIGNAL("textChanged(QString)"), self.library_model.search)
    QObject.connect(self.library_model, SIGNAL("sorted()"), self.model_modified)
    QObject.connect(self.library_model, SIGNAL("searched()"), self.model_modified)
    QObject.connect(self.library_model, SIGNAL("deleted()"), self.model_modified)    
    self.library_view.resizeColumnsToContents()
    
    
    # Create Device list
    self.tree = QStandardItemModel()
    library = QStandardItem(QString("Library"))
    library.setIcon(QIcon(":/images/mycomputer.png"))
    font = library.font()
    font.setBold(True)    
    self.tree.appendRow(library)
    library.setFont(font)
    library.appendRow(QStandardItem(QString("Books")))
    blank = QStandardItem(" ")
    blank.setEnabled(False)
    self.tree.appendRow(blank)
    self.reader = QStandardItem(QString("SONY Reader"))    
    mm = QStandardItem(QString("Main Memory"))
    mm.appendRow(QStandardItem(QString("Books")))
    self.reader.appendRow(mm)
    mc = QStandardItem(QString("Storage Card"))
    mc.appendRow(QStandardItem(QString("Books")))
    self.reader.appendRow(mc)
    self.reader.setIcon(QIcon(":/images/reader.png"))
    self.tree.appendRow(self.reader)
    self.reader.setFont(font)
    self.treeView.setModel(self.tree)    
    self.treeView.header().hide()
    self.treeView.setExpanded(library.index(), True)
    self.treeView.setExpanded(self.reader.index(), True)
    self.treeView.setExpanded(mm.index(), True)
    self.treeView.setExpanded(mc.index(), True)
    self.treeView.setRowHidden(2, self.tree.invisibleRootItem().index(), True)
    QObject.connect(self.treeView, SIGNAL("activated(QModelIndex)"),  self.tree_clicked)
    QObject.connect(self.treeView, SIGNAL("clicked(QModelIndex)"),  self.tree_clicked)
    
    # Create Device Book list
    self.device_model = DeviceBooksModel(window, [])    
    self.device_view.setModel(self.device_model)
    self.device_view.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.device_view.setSortingEnabled(True)
    self.device_view.contextMenuEvent = self.list_context_event
    QObject.connect(self.device_model, SIGNAL("layoutChanged()"), self.device_view.resizeRowsToContents)
    QObject.connect(self.device_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
    QObject.connect(self.search, SIGNAL("textChanged(QString)"), self.device_model.search)
    QObject.connect(self.device_model, SIGNAL("sorted()"), self.model_modified)
    QObject.connect(self.device_model, SIGNAL("searched()"), self.model_modified)
    QObject.connect(self.device_model, SIGNAL("deleted()"), self.model_modified)
    self.clearButton.setIcon(QIcon(":/images/clear.png"))
    QObject.connect(self.clearButton, SIGNAL("clicked(bool)"), self.clear)
    self.device_view.hide()
    
    # Setup book display
    self.BOOK_TEMPLATE = self.book_info.text()    
    self.BOOK_IMAGE       = QPixmap(":/images/book.png")
    self.book_cover.hide()
    self.book_info.hide()
    
    # Populate toolbar
    self.add_action = self.tool_bar.addAction(QIcon(":/images/fileopen.png"), "Add files to Library")
    self.add_action.setShortcut(Qt.Key_A)
    QObject.connect(self.add_action, SIGNAL("triggered(bool)"), self.add)
    self.del_action = self.tool_bar.addAction(QIcon(":/images/delete.png"), "Delete selected items") 
    self.del_action.setShortcut(Qt.Key_Delete)
    QObject.connect(self.del_action, SIGNAL("triggered(bool)"), self.delete)
    
    
    self.device_detector = self.startTimer(1000)
    self.splitter.setStretchFactor(0,0)
    self.splitter.setStretchFactor(1,100)
    self.search.setFocus(Qt.OtherFocusReason)
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
    self.df.setText("Main memory: <br><br>Storage card:")
    self.card = None
    self.treeView.setRowHidden(2, self.tree.invisibleRootItem().index(), True)
    self.device_model.set_data([])
    self.book_cover.hide()
    self.book_info.hide()
    self.device_view.hide()
    
  
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
    QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
  
  def establish_connection(self):
    self.window.setCursor(Qt.WaitCursor)
    self.status("Connecting to device")    
    try:
      space = self.dev.available_space()
    except TimeoutError:
      c = 0
      self.status("Waiting for device to initialize")
      while c < 100: # Delay for 10s while device is initializing
        if c % 10 == c/10:
          self.progress(c)
        QThread.currentThread().msleep(100)
        c += 1   
      space = self.dev.available_space()    
    sc = space[1][1] if space[1][1] else space[2][1]
    self.df.setText("Main memory:  " + human_readable(space[0][1]) + "<br><br>Storage card: " + human_readable(sc))
    self.is_connected = True
    if space[1][2] > 0: self.card = "a:"
    elif space[2][2] > 0: self.card = "b:"
    else: self.card = None
    if self.card: self.treeView.setRowHidden(1, self.reader.index(), False)
    else: self.treeView.setRowHidden(1, self.reader.index(), True)
    self.treeView.setRowHidden(2, self.tree.invisibleRootItem().index(), False)
    self.status("Loading media list from device")
    mb, cb, mx, cx = self.dev.books()    
    
    for x in (mb, cb):
      for book in x:
        if "&" in book["author"]:
          book["author"] = re.sub(r"&\s*", r"\n", book["author"])
          
    self.main_books = mb
    self.card_books = cb
    self.main_xml = mx
    self.cache_xml = cx
    self.window.setCursor(Qt.ArrowCursor)
    
def main():
    from PyQt4.Qt import QApplication, QMainWindow
    app = QApplication(sys.argv)
    window = QMainWindow()
    QCoreApplication.setOrganizationName("KovidsBrain")
    QCoreApplication.setApplicationName("prs500-gui")
    gui = MainWindow(window)    
    ret = app.exec_()    
    return ret
    
