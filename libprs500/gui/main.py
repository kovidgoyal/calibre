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
from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, QSettings, QVariant, QSize, QEventLoop
from PyQt4.QtGui import QPixmap, QAbstractItemView, QErrorMessage, QMessageBox, QFileDialog
from PyQt4.Qt import qInstallMsgHandler, qDebug, qFatal, qWarning, qCritical
from PyQt4 import uic

from libprs500.communicate import PRS500Device as device
from libprs500.errors import *
from libprs500.lrf.meta import LRFMetaFile, LRFException
from libprs500.gui import import_ui
from libprs500.gui.widgets import LibraryBooksModel, DeviceBooksModel, DeviceModel, human_readable
from database import LibraryDatabase
from editbook import EditBookDialog

import sys, re, os, traceback

DEFAULT_BOOK_COVER = None

Ui_MainWindow = import_ui("main.ui")
class MainWindow(QObject, Ui_MainWindow): 
  
  def show_device(self, yes):
    """ If C{yes} show the items on the device otherwise show the items in the library """
    self.device_view.clearSelection(), self.library_view.clearSelection()
    self.book_cover.hide(), self.book_info.hide()
    if yes: 
      self.device_view.show(), self.library_view.hide()
      self.book_cover.setAcceptDrops(False)
      self.current_view = self.device_view      
    else: 
      self.device_view.hide(), self.library_view.show()
      self.book_cover.setAcceptDrops(True)
      self.current_view = self.library_view
    self.current_view.sortByColumn(3, Qt.DescendingOrder)
      
  
  def tree_clicked(self, index):
    if index.isValid():
      text = (index.data(Qt.DisplayRole).toString())      
      if "Books" in text: text = str(index.parent().data(Qt.DisplayRole).toString())
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
    if not thumbnail: thumbnail = DEFAULT_BOOK_COVER
    self.book_cover.setPixmap(thumbnail)
    try:
      name = os.path.abspath(current.model().image_file.name)
      self.book_cover.setToolTip('<img src="'+name+'">')
    except Exception, e: self.book_cover.setToolTip('<img src=":/default_cover">')
    self.book_cover.show()
    self.book_info.show()
  
  
  def delete(self, action):
    count = str(len(self.current_view.selectionModel().selectedRows()))
    ret = QMessageBox.question(self.window, self.trUtf8("SONY Reader - confirm"),  self.trUtf8("Are you sure you want to <b>permanently delete</b> these ") +count+self.trUtf8(" items?"), QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
    if ret != QMessageBox.Yes: return
    self.window.setCursor(Qt.WaitCursor)
    if self.library_view.isVisible():
      self.library_model.delete(self.library_view.selectionModel().selectedRows())
    else:
      rows   = self.device_view.selectionModel().selectedRows()
      items = [ row.model().title(row) + ": " +  row.model().path(row)[row.model().path(row).rfind("/")+1:] for row in rows ]
       
      if ret == QMessageBox.YesToAll:
        
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
        self.library_view.model().add_book(file)
        self.search.clear()
        hv = self.library_view.horizontalHeader()
        col = hv.sortIndicatorSection()
        order = hv.sortIndicatorOrder()
        self.library_view.model().sort(col, order)
      
      
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
    QErrorMessage(self.window).showMessage(msg+"<br><b>Error: </b>"+str(e)+"<br><br>"+re.sub("\n","<br>", traceback.format_exc(e)))
  
  def update_cover(self, pix):    
    if not pix.isNull():
      try:
        self.library_view.model().update_cover(self.library_view.currentIndex(), pix)
        self.book_cover.setPixmap(pix)
      except Exception, e: self.show_error(e, "Unable to change cover")
      
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
    QObject.connect(self.library_model, SIGNAL("layoutChanged()"), self.library_view.resizeRowsToContents)
    QObject.connect(self.library_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
    QObject.connect(self.search, SIGNAL("textChanged(QString)"), self.library_model.search)
    QObject.connect(self.library_model, SIGNAL("sorted()"), self.model_modified)
    QObject.connect(self.library_model, SIGNAL("searched()"), self.model_modified)
    QObject.connect(self.library_model, SIGNAL("deleted()"), self.model_modified)    
    QObject.connect(self.library_model, SIGNAL("dataChanged(QModelIndex, QModelIndex)"), self.resize_columns)
    self.library_view.resizeColumnsToContents()
    
    # Create Device tree
    QObject.connect(self.device_tree, SIGNAL("activated(QModelIndex)"), self.tree_clicked)
    QObject.connect(self.device_tree, SIGNAL("clicked(QModelIndex)"), self.tree_clicked)        
    model = DeviceModel(self.device_tree)
    self.device_tree.setModel(model)
    self.device_tree.expand(model.indexFromItem(model.library))
    self.device_tree.expand(model.indexFromItem(model.reader))
    self.device_tree.expand(model.indexFromItem(model.card))
    self.device_tree.hide_reader(True)
    self.device_tree.hide_card(True)
    
    # Create Device Book list
    self.reader_model = DeviceBooksModel(window)    
    self.card_model = DeviceBooksModel(window)    
    self.device_view.setModel(self.reader_model)
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
    
    # DnD setup
    QObject.connect(self.book_cover, SIGNAL("cover_received(QPixmap)"), self.update_cover)
    
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
    self.device_tree.hide_reader(True)
    self.device_tree.hide_card(True)
    self.book_cover.hide()
    self.book_info.hide()
    self.device_view.hide()
    self.library_view.show()
  
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
      qFatal("Unable to connect to device. Please try unplugging and reconnecting it")
      
    sc = space[1][1] if space[1][1] else space[2][1]
    self.df.setText("SONY Reader:  " + human_readable(space[0][1]) + "<br><br>Storage card: " + human_readable(sc))
    self.is_connected = True
    if space[1][2] > 0: card = "a:"
    elif space[2][2] > 0: card = "b:"
    else: card = None
    if card: self.device_tree.hide_card(False)
    else: self.device_tree.hide_card(True)
    self.device_tree.hide_reader(False)
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
    QCoreApplication.setOrganizationName("KovidsBrain")
    QCoreApplication.setApplicationName("SONY Reader")
    gui = MainWindow(window, options.log_packets)    
    ret = app.exec_()    
    return ret
    
if __name__ == "__main__": main()
