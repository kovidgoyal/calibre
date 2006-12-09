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
from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, QSettings, QVariant, QSize, QEventLoop, QString
from PyQt4.QtGui import QPixmap, QAbstractItemView, QErrorMessage, QMessageBox, QFileDialog, QIcon
from PyQt4.Qt import qInstallMsgHandler, qDebug, qFatal, qWarning, qCritical
from PyQt4 import uic

from libprs500.communicate import PRS500Device as device
from libprs500.errors import *
from libprs500.lrf.meta import LRFMetaFile, LRFException
from libprs500.gui import import_ui, installErrorHandler, Error, Warning, extension, APP_TITLE
from libprs500.gui.widgets import LibraryBooksModel, DeviceBooksModel, DeviceModel, TableView
from database import LibraryDatabase
from editbook import EditBookDialog

import sys, re, os, traceback, tempfile

DEFAULT_BOOK_COVER = None
LIBRARY_BOOK_TEMPLATE = QString("<table><tr><td><b>Formats:</b> %1 </td><td><b>Tags:</b> %2</td></tr><tr><td><b>Comments:</b>%3</td></tr></table>")
DEVICE_BOOK_TEMPLATE = QString("<table><tr><td><b>Title: </b>%1</td><td><b>&nbsp;Size:</b> %2</td></tr><tr><td><b>Author: </b>%3</td><td><b>&nbsp;Type: </b>%4</td></tr></table>")

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
      self.search.clear()
      show_dev = True
      model = self.device_tree.model()
      if model.is_library(index):
        show_dev = False
      elif model.is_reader(index):
        self.device_view.setModel(self.reader_model)
        QObject.connect(self.device_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
      elif model.is_card(index):
        self.device_view.setModel(self.card_model)
        QObject.connect(self.device_view.selectionModel(), SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)        
      self.show_device(show_dev)  
      
  
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
    if self.library_view.isVisible():
      formats, tags, comments, cover = current.model().info(current.row())
      data = LIBRARY_BOOK_TEMPLATE.arg(formats).arg(tags).arg(comments)
      tooltip = "To save the cover, drag it to the desktop.<br>To change the cover drag the new cover onto this picture"
    else:
      title, author, size, mime, cover = current.model().info(current.row())
      data = DEVICE_BOOK_TEMPLATE.arg(title).arg(size).arg(author).arg(mime)
      tooltip = "To save the cover, drag it to the desktop."
    self.book_info.setText(data)
    self.book_cover.setToolTip(tooltip)
    if not cover: cover = DEFAULT_BOOK_COVER
    self.book_cover.setPixmap(cover)
    self.book_cover.show()
    self.book_info.show()
  
  def formats_added(self, index):
    if index == self.library_view.currentIndex():
      self.show_book(index, index)
  
  def delete(self, action):
    count = str(len(self.current_view.selectionModel().selectedRows()))
    ret = QMessageBox.question(self.window, self.trUtf8(APP_TITLE + " - confirm"),  self.trUtf8("Are you sure you want to <b>permanently delete</b> these ") +count+self.trUtf8(" item(s)?"), QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
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
    self.add_books(files)
    
  def add_books(self, files):
    self.window.setCursor(Qt.WaitCursor)
    for file in files:
      file = os.path.abspath(file)
      self.library_view.model().add_book(file)
      if self.library_view.isVisible(): self.search.clear()
      else: self.library_model.search("")
      hv = self.library_view.horizontalHeader()
      col = hv.sortIndicatorSection()
      order = hv.sortIndicatorOrder()
      self.library_view.model().sort(col, order)
    self.window.setCursor(Qt.ArrowCursor)
    
      
  def edit(self, action):    
    if self.library_view.isVisible():
      rows = self.library_view.selectionModel().selectedRows()
      for row in rows:
        id = self.library_model.id_from_index(row)
        dialog = QDialog(self.window)
        ed = EditBookDialog(dialog, id, self.library_model.db)
        if dialog.exec_() == QDialog.Accepted:
          self.library_model.refresh_row(row.row())
          
  
  def update_cover(self, pix):    
    if not pix.isNull():
      try:
        self.library_view.model().update_cover(self.library_view.currentIndex(), pix)
        self.book_cover.setPixmap(pix)
      except Exception, e: Error("Unable to change cover", e)
      
  def upload_books(self, to, files, ids):
    def update_models():
      hv = self.device_view.horizontalHeader()
      col = hv.sortIndicatorSection()
      order = hv.sortIndicatorOrder()
      model = self.card_model if oncard else self.reader_model
      model.sort(col, order)
      if self.device_view.isVisible() and self.device_view.model() == model: self.search.clear()
      else: model.search("")
      
    self.window.setCursor(Qt.WaitCursor)
    oncard = False if to == "reader" else True
    ename = "file"
    booklists = (self.reader_model._orig_data, self.card_model._orig_data)
    try:
      if ids:
        for id in ids:
          formats = []
          info = self.library_view.model().book_info(id, ["title", "authors", "cover"])
          ename = info["title"]
          for f in files: 
            if re.match("......_"+str(id)+"_", f):
              formats.append(f)
          file = None
          try:
            for format in self.dev.FORMATS:
              for f in formats:
                if extension(format) == format:
                  file = f
                  raise StopIteration()
          except StopIteration: pass        
          if not file: 
           Error("The library does not have any compatible formats for " + ename)
           continue
          f = open(file, "rb")          
          self.status("Sending "+info["title"]+" to device")
          try:
            self.dev.add_book(f, "libprs500_"+str(id)+"."+extension(file), info, booklists, oncard=oncard)          
            update_models()
          finally: f.close()
      else:
        for file in files:
          ename = file
          if extension(file) not in self.dev.FORMATS:
            Error(ename + " is not in a supported format")
            continue
          info = { "title":file, "authors":"Unknown", cover:None }
          f = open(file, "rb")
          self.status("Sending "+info["title"]+" to device")
          try:
            self.dev.add_book(f, os.path.basename(file), info, booklists, oncard=oncard)
            update_models()
          finally: f.close()
    except Exception, e:
      Error("Unable to send "+ename+" to device", e)
    finally: self.window.setCursor(Qt.WaitCursor)
  
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
    QObject.connect(self.library_view, SIGNAL('books_dropped'), self.add_books)
    QObject.connect(self.library_model, SIGNAL('formats_added'), self.formats_added)
    self.library_view.resizeColumnsToContents()
    
    # Create Device tree
    model = DeviceModel(self.device_tree)
    QObject.connect(self.device_tree, SIGNAL("activated(QModelIndex)"), self.tree_clicked)
    QObject.connect(self.device_tree, SIGNAL("clicked(QModelIndex)"), self.tree_clicked)        
    QObject.connect(model, SIGNAL('books_dropped'), self.add_books)
    QObject.connect(model, SIGNAL('upload_books'), self.upload_books)
    self.device_tree.setModel(model)   
    
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
    self.book_cover.hide()
    self.book_info.hide()
    
    # Connect actions
    QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add)
    QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete)
    QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit)
    
    # DnD setup
    QObject.connect(self.book_cover, SIGNAL("cover_received(QPixmap)"), self.update_cover)
    
    self.device_detector = self.startTimer(1000)
    self.search.setFocus(Qt.OtherFocusReason)
    self.show_device(False)
    self.df_template = self.df.text()
    self.df.setText(self.df_template.arg("").arg("").arg(""))
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
    self.df.setText(self.df_template.arg("").arg("").arg(""))
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
      info = self.dev.get_device_information(end_session=False)
    except DeviceBusy, e:
      qFatal(str(e))
    except DeviceError:
      self.dev.reconnect()
      return    
    except ProtocolError, e: 
      traceback.print_exc(e)
      qFatal("Unable to connect to device. Please try unplugging and reconnecting it")
    self.df.setText(self.df_template.arg("Connected: "+info[0]).arg(info[1]).arg(info[2]))
    space = self.dev.available_space(end_session=False)  
    sc = space[1][1] if space[1][1] else space[2][1]    
    self.device_tree.model().update_free_space(space[0][1], sc)
    self.is_connected = True
    if space[1][2] > 0: self.card = "a:"
    elif space[2][2] > 0: self.card = "b:"
    else: self.card = None
    if self.card: self.device_tree.hide_card(False)
    else: self.device_tree.hide_card(True)
    self.device_tree.hide_reader(False)
    self.status("Loading media list from SONY Reader")
    self.reader_model.set_data(self.dev.books(end_session=False))
    if self.card: self.status("Loading media list from Storage Card")
    self.card_model.set_data(self.dev.books(oncard=True))
    self.progress(100)
    self.window.setCursor(Qt.ArrowCursor)
    
def main():
    from optparse import OptionParser
    from libprs500 import __version__ as VERSION
    lock = os.path.join(tempfile.gettempdir(),"libprs500_gui_lock")
    if os.access(lock, os.F_OK):
      print >>sys.stderr, "Another instance of", APP_TITLE, "is running"
      print >>sys.stderr, "If you are sure this is not the case then manually delete the file", lock
      sys.exit(1)
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
    window.setWindowTitle(APP_TITLE)
    window.setWindowIcon(QIcon(":/icon"))
    installErrorHandler(QErrorMessage(window))
    QCoreApplication.setOrganizationName("KovidsBrain")
    QCoreApplication.setApplicationName(APP_TITLE)
    gui = MainWindow(window, options.log_packets)    
    f = open(lock, "w")
    f.close()
    try:
      ret = app.exec_()    
    finally: os.remove(lock)
    return ret
    
if __name__ == "__main__": main()
