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
import images
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QObject, QThread, QCoreApplication, QEventLoop, QString, QStandardItem, QStandardItemModel, QStatusBar, QVariant, QAbstractTableModel, \
                                   QAbstractItemView, QImage, QPixmap, QIcon, QSize
from PyQt4 import uic
import sys, pkg_resources, re, string
from operator import itemgetter

NONE = QVariant()

def human_readable(size):
  """ Convert a size in bytes into a human readle form """
  if size < 1024: divisor, suffix = 1, "B"
  elif size < 1024*1024: divisor, suffix = 1024., "KB"
  elif size < 1024*1024*1024: divisor, suffix = 1024*1024, "MB"
  elif size < 1024*1024*1024*1024: divisor, suffix = 1024*1024, "GB"
  size = str(size/divisor)
  if size.find(".") > -1: size = size[:size.find(".")+2]
  return size + " " + suffix

class DeviceBooksModel(QAbstractTableModel):
  
  def __init__(self, parent, data):
    QAbstractTableModel.__init__(self, parent)
    self._data = data
    self._orig_data = data
  
  def set_data(self, data):
    self.emit(SIGNAL("layoutAboutToBeChanged()"))
    self._data = data
    self._orig_data = data
    self.sort(0, Qt.DescendingOrder)
    
  def rowCount(self, parent): return len(self._data)
  def columnCount(self, parent): return 3
  
  def headerData(self, section, orientation, role):
    if role != Qt.DisplayRole:
      return NONE
    text = ""
    if orientation == Qt.Horizontal:      
      if section == 0: text = "Title"
      elif section == 1: text = "Author(s)"
      elif section == 2: text = "Size"
      return QVariant(self.trUtf8(text))
    else: return QVariant(str(1+section))
    
  def data(self, index, role):
    if role == Qt.DisplayRole:
      row, col = index.row(), index.column()
      book = self._data[row]
      if col == 0: text = book["title"]
      elif col == 1: text = book["author"]
      elif col == 2: text = human_readable(int(book["size"]))
      return QVariant(text)
    elif role == Qt.TextAlignmentRole and index.column() == 2:
      return QVariant(Qt.AlignRight)
    elif role == Qt.DecorationRole and index.column() == 0:
      book = self._data[index.row()]
      if book.has_key("thumbnail"):
        return QVariant(book["thumbnail"])
    return NONE
    
  def info(self, row):
    row = self._data[row]
    return row["title"], row["author"], human_readable(int(row["size"])), row["mime"], row["thumbnail"].pixmap(60, 80, QIcon.Normal, QIcon.On)
  
  def sort(self, col, order):
    def getter(key, func):  return lambda x : func(itemgetter(key)(x))
    if col == 0: key, func = "title", string.lower
    if col == 1: key, func = "author", lambda x : x.split()[-1:][0].lower()
    if col == 2: key, func = "size", int
    descending = order != Qt.AscendingOrder
    self.emit(SIGNAL("layoutAboutToBeChanged()"))
    self._data.sort(key=getter(key, func))
    if descending: self._data.reverse()
    self.emit(SIGNAL("layoutChanged()"))
    self.emit(SIGNAL("sorted()"))

  def search(self, query):
    queries = unicode(query).lower().split()
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
    

Ui_MainWindow, bclass = uic.loadUiType(pkg_resources.resource_stream(__name__, "main.ui"))
class MainWindow(QObject, Ui_MainWindow):
  
  def tree_clicked(self, index):
    item = self.tree.itemFromIndex(index)
    text = str(item.text())
    if text == "Library":
      print "Library Clicked"
    elif text == "SONY Reader":
      self.set_data(self.main_books + self.card_books)
    elif text == "Main Memory":
      self.set_data(self.main_books)
    elif text == "Storage Card":
      self.set_data(self.card_books)
    elif text == "Books":
      text = str(item.parent().text())
      if text == "Library":
        print "Library --> Books Clicked"
      elif text == "Main Memory":
        self.set_data(self.main_books)  
      elif text == "Storage Card":
        self.set_data(self.card_books)
  
  def set_data(self, data):
    self.model.set_data(data)    
    self.table_view.resizeColumnsToContents()
    
  
  def data_sorted(self):
    self.table_view.resizeRowsToContents()
    self.table_view.clearSelection()
    self.book_cover.hide()
    self.book_info.hide()
  
  def show_book(self, current, previous):
    title, author, size, mime, thumbnail = current.model().info(current.row())
    self.book_info.setText(self.BOOK_TEMPLATE.arg(title).arg(size).arg(author).arg(mime))
    self.book_cover.setPixmap(thumbnail)
    self.book_cover.show()
    self.book_info.show()
    
  def searched(self):
    self.table_view.clearSelection()
    self.book_cover.hide()
    self.book_info.hide()
    self.table_view.resizeRowsToContents()
  
  def clear(self, checked): self.search.setText("")
  
  def __init__(self, window):
    QObject.__init__(self)
    Ui_MainWindow.__init__(self)    
    self.dev = device(report_progress=self.progress)
    self.is_connected = False    
    self.setupUi(window)
    self.card = None    
    # Create Tree
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
    
    # Create Table
    self.model = DeviceBooksModel(window, [])
    QObject.connect(self.model, SIGNAL("sorted()"), self.data_sorted)
    self.table_view.setModel(self.model)
    self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.table_view.setSortingEnabled(True)
    QObject.connect(self.table_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
    QObject.connect(self.search, SIGNAL("textChanged(QString)"), self.model.search)
    QObject.connect(self.model, SIGNAL("searched()"), self.searched)
    self.clearButton.setIcon(QIcon(":/images/clear.png"))
    QObject.connect(self.clearButton, SIGNAL("clicked(bool)"), self.clear)
    
    # Setup book display
    self.BOOK_TEMPLATE = self.book_info.text()    
    self.BOOK_IMAGE       = QPixmap(":/images/book.png")
    self.book_cover.hide()
    self.book_info.hide()
    
    self.device_detector = self.startTimer(1000)
    self.splitter.setStretchFactor(0,0)
    self.splitter.setStretchFactor(1,100)
    self.search.setFocus(Qt.OtherFocusReason)
    self.window = window
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
    self.model.set_data([])
    self.book_cover.hide()
    self.book_info.hide()
    
  
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
    if space[1][2] > 0: self.card = "a:/"
    elif space[2][2] > 0: self.card = "b:/"
    else: self.card = None
    if self.card: self.treeView.setRowHidden(1, self.reader.index(), False)
    else: self.treeView.setRowHidden(1, self.reader.index(), True)
    self.treeView.setRowHidden(2, self.tree.invisibleRootItem().index(), False)
    self.status("Loading media list")
    mb, cb, mx, cx = self.dev.books()    
    
    for x in (mb, cb):
      for book in x:
        if book.has_key("thumbnail"):
          book["thumbnail"] = QIcon(QPixmap.fromImage(QImage.fromData(book["thumbnail"])))
        else: book["thumbnail"] = QIcon(self.BOOK_IMAGE)
        if "&" in book["author"]:
          book["author"] = re.sub(r"&\s*", r"\n", book["author"])
          
    self.main_books = mb
    self.card_books = cb
    self.main_xml = mx
    self.cache_xml = cx
    
def main():
    from PyQt4.Qt import QApplication, QMainWindow
    app = QApplication(sys.argv)
    window = QMainWindow()    
    gui = MainWindow(window)
    return app.exec_()
    
