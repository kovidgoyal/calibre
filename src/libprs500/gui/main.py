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
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.Warning
""" Create and launch the GUI """
import sys
import re
import os
import traceback
import tempfile

from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, \
                         QSettings, QVariant, QSize, QEventLoop, QString, \
                         QBuffer, QIODevice, QModelIndex
from PyQt4.QtGui import QPixmap, QErrorMessage, QLineEdit, \
                        QMessageBox, QFileDialog, QIcon, QDialog, QInputDialog
from PyQt4.Qt import qDebug, qFatal, qWarning, qCritical

from libprs500.prs500 import PRS500 as device
from libprs500.errors import *
from libprs500.gui import import_ui, installErrorHandler, Error, _Warning, \
                          extension, APP_TITLE
from libprs500.gui.widgets import LibraryBooksModel, DeviceBooksModel, \
                                  DeviceModel
from database import LibraryDatabase
from editbook import EditBookDialog


DEFAULT_BOOK_COVER = None
LIBRARY_BOOK_TEMPLATE = QString("<b>Formats:</b> %1<br><b>Tags:</b> %2<br>%3") 
DEVICE_BOOK_TEMPLATE = QString("<table><tr><td><b>Title: </b>%1</td><td> \
                                <b>&nbsp;Size:</b> %2</td></tr>\
                                <tr><td><b>Author: </b>%3</td>\
                                <td><b>&nbsp;Type: </b>%4</td></tr></table>")

Ui_MainWindow = import_ui("main.ui")
class Main(QObject, Ui_MainWindow): 
    def report_error(func):
        """ 
        Decorator to ensure that unhandled exceptions are displayed 
        to users via the GUI
        """
        def function(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception, e:
                Error("There was an error calling " + func.__name__, e)
                raise
        return function
        
    """ Create GUI """
    def show_device(self, yes):
        """ 
        If C{yes} show the items on the device otherwise show the items 
        in the library 
        """
        self.device_view.selectionModel().reset()
        self.library_view.selectionModel().reset()
        self.book_cover.hide() 
        self.book_info.hide()
        if yes: 
            self.action_add.setEnabled(False)
            self.action_edit.setEnabled(False)
            self.device_view.show()
            self.library_view.hide()
            self.book_cover.setAcceptDrops(False)
            self.device_view.resizeColumnsToContents()
            self.device_view.resizeRowsToContents()
        else: 
            self.action_add.setEnabled(True)
            self.action_edit.setEnabled(True)
            self.device_view.hide()
            self.library_view.show()
            self.book_cover.setAcceptDrops(True)
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
                QObject.connect(self.device_view.selectionModel(), \
                SIGNAL("currentChanged(QModelIndex, QModelIndex)"), \
                self.show_book)
            elif model.is_card(index):
                self.device_view.setModel(self.card_model)
                QObject.connect(self.device_view.selectionModel(), \
                SIGNAL("currentChanged(QModelIndex, QModelIndex)"), \
                self.show_book)        
            self.show_device(show_dev)  
    
    
    def model_modified(self):
        if self.current_view.selectionModel():
            self.current_view.selectionModel().reset()
        self.current_view.resizeColumnsToContents()
        self.current_view.resizeRowsToContents()
        self.book_cover.hide()
        self.book_info.hide()
        QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)    
    
    def resize_rows_and_columns(self, topleft, bottomright):
        for c in range(topleft.column(), bottomright.column()+1):
            self.current_view.resizeColumnToContents(c)
        for r in range(topleft.row(), bottomright.row()+1):
            self.current_view.resizeRowToContents(r)
    
    def show_book(self, current, previous):
        if not current.isValid():
            return
        if self.library_view.isVisible():
            formats, tags, comments, cover = self.library_model\
                                                        .info(current.row())
            comments = re.sub('\n', '<br>', comments)
            data = LIBRARY_BOOK_TEMPLATE.arg(formats).arg(tags).arg(comments)
            tooltip = "To save the cover, drag it to the desktop.<br>To \
                       change the cover drag the new cover onto this picture"
        else:
            title, author, size, mime, cover = self.device_view.model()\
                                                        .info(current.row())
            data = DEVICE_BOOK_TEMPLATE.arg(title).arg(size).arg(author).arg(mime)
            tooltip = "To save the cover, drag it to the desktop."
        self.book_info.setText(data)
        self.book_cover.setToolTip(tooltip)
        if not cover: cover = DEFAULT_BOOK_COVER
        self.book_cover.setPixmap(cover)
        self.book_cover.show()
        self.book_info.show()
        self.current_view.scrollTo(current)
    
    def formats_added(self, index):
        if index == self.library_view.currentIndex():
            self.show_book(index, index)
    
    @report_error
    def delete(self, action):        
        rows = self.current_view.selectionModel().selectedRows()
        if not len(rows): 
            return 
        count = str(len(rows))
        ret = QMessageBox.question(self.window, self.trUtf8(APP_TITLE + \
            " - confirm"),  self.trUtf8("Are you sure you want to \
            <b>permanently delete</b> these ") +count+self.trUtf8(" item(s)?"), \
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ret != QMessageBox.Yes: 
            return
        self.window.setCursor(Qt.WaitCursor)
        if self.library_view.isVisible():
            self.library_model.delete(self.library_view.selectionModel()\
                                    .selectedRows())
        else:
            self.status("Deleting books and updating metadata on device")
            paths = self.device_view.model().delete(rows)
            self.dev.remove_book(paths, (self.reader_model.booklist, \
                                 self.card_model.booklist), end_session=False)
            self.update_availabe_space()
            self.model_modified()
        self.show_book(self.current_view.currentIndex(), QModelIndex())
        self.window.setCursor(Qt.ArrowCursor)
    
    def read_settings(self):
        settings = QSettings()
        settings.beginGroup("MainWindow")
        self.window.resize(settings.value("size", QVariant(QSize(1000, 700))).\
                            toSize())
        settings.endGroup()
        self.database_path = settings.value("database path", QVariant(os.path\
                                    .expanduser("~/library.db"))).toString()
    
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
        _dir = settings.value("add books dialog dir", \
                QVariant(os.path.expanduser("~"))).toString()
        files = QFileDialog.getOpenFileNames(self.window, \
            "Choose books to add to library", _dir, \
            "Books (*.lrf *.lrx *.rtf *.pdf *.txt);;All files (*)")
        if not files.isEmpty():
            x = unicode(files[0].toUtf8(), 'utf-8')
            settings.setValue("add books dialog dir", \
                                            QVariant(os.path.dirname(x)))
            files = unicode(files.join("|||").toUtf8(), 'utf-8').split("|||")      
            self.add_books(files)
    
    @report_error
    def add_books(self, files):
        self.window.setCursor(Qt.WaitCursor)
        try:
            for _file in files:
                _file = os.path.abspath(_file)
                self.library_view.model().add_book(_file)
                if self.library_view.isVisible(): 
                    if len(str(self.search.text())):
                        self.search.clear()
                    else:
                        self.library_model.search("")
                else: 
                    self.library_model.search("")
                hv = self.library_view.horizontalHeader()
                col = hv.sortIndicatorSection()
                order = hv.sortIndicatorOrder()
                self.library_view.model().sort(col, order)
        finally:
            self.window.setCursor(Qt.ArrowCursor)
    
    @report_error
    def edit(self, action):    
        if self.library_view.isVisible():
            rows = self.library_view.selectionModel().selectedRows()            
            for row in rows:
                _id = self.library_model.id_from_index(row)
                dialog = QDialog(self.window)
                ebd = EditBookDialog(dialog, _id, self.library_model.db)
                if dialog.exec_() == QDialog.Accepted:
                    title = unicode(ebd.title.text().toUtf8(), 'utf-8').strip()
                    authors = unicode(ebd.authors.text().toUtf8(), 'utf-8').strip()
                    rating = ebd.rating.value()
                    tags = unicode(ebd.tags.text().toUtf8(), 'utf-8').strip()
                    publisher = unicode(ebd.publisher.text().toUtf8(), \
                                        'utf-8').strip()
                    comments = unicode(ebd.comments.toPlainText().toUtf8(), \
                                        'utf-8').strip()
                    pix = ebd.cover.pixmap()
                    if not pix.isNull():
                        self.update_cover(pix)
                    model = self.library_view.model()
                    if title:
                        index = model.index(row.row(), 0)
                        model.setData(index, QVariant(title), Qt.EditRole)
                    if authors:
                        index = model.index(row.row(), 1)
                        model.setData(index, QVariant(authors), Qt.EditRole)
                    if publisher:
                        index = model.index(row.row(), 5)
                        model.setData(index, QVariant(publisher), Qt.EditRole)
                    index = model.index(row.row(), 4)
                    model.setData(index, QVariant(rating), Qt.EditRole)
                    self.update_tags_and_comments(row, tags, comments)
                    self.library_model.refresh_row(row.row())
            self.show_book(self.current_view.currentIndex(), QModelIndex())
    
    
    def update_tags_and_comments(self, index, tags, comments):
        self.library_model.update_tags_and_comments(index, tags, comments)
        
    @report_error
    def update_cover(self, pix):    
        if not pix.isNull():
            try:
                self.library_view.model().update_cover(self.library_view\
                        .currentIndex(), pix)
                self.book_cover.setPixmap(pix)
            except Exception, e: 
                Error("Unable to change cover", e)
    
    @report_error
    def upload_books(self, to, files, ids):
        oncard = False if to == "reader" else True
        booklists = (self.reader_model.booklist, self.card_model.booklist)
        def update_models():
            hv = self.device_view.horizontalHeader()
            col = hv.sortIndicatorSection()
            order = hv.sortIndicatorOrder()
            model = self.card_model if oncard else self.reader_model
            model.sort(col, order)
            if self.device_view.isVisible() and \
                                        self.device_view.model() == model: 
                if len(str(self.search.text())):
                    self.search.clear()
                else:
                    self.device_view.model().search("")
            else: 
                model.search("")
        
        def sync_lists():
            self.status("Syncing media list to device main memory")
            self.dev.upload_book_list(booklists[0])
            if len(booklists[1]):
                self.status("Syncing media list to storage card")
                self.dev.upload_book_list(booklists[1])
        
        self.window.setCursor(Qt.WaitCursor)
        ename = "file"    
        try:
            if ids:
                for _id in ids:
                    formats = []
                    info = self.library_view.model().book_info(_id)
                    if info["cover"]:
                        pix = QPixmap()
                        pix.loadFromData(str(info["cover"]))
                        if pix.isNull(): 
                            pix = DEFAULT_BOOK_COVER            
                        pix = pix.scaledToHeight(self.dev.THUMBNAIL_HEIGHT, \
                                Qt.SmoothTransformation) 
                        _buffer = QBuffer()
                        _buffer.open(QIODevice.WriteOnly)
                        pix.save(_buffer, "JPEG")
                        info["cover"] = (pix.width(), pix.height(), \
                                    str(_buffer.buffer()))
                    ename = info["title"]
                    for f in files: 
                        if re.match("libprs500_\S+_......_" + \
                                str(_id) + "_", os.path.basename(f)):
                            formats.append(f)
                    _file = None
                    try:
                        for format in self.dev.FORMATS:
                            for f in formats:
                                if extension(f) == format:
                                    _file = f
                                    raise StopIteration()
                    except StopIteration: pass        
                    if not _file: 
                        Error("The library does not have any formats that "+\
                              "can be viewed on the device for " + ename, None)
                        continue
                    f = open(_file, "rb")          
                    self.status("Sending "+info["title"]+" to device")
                    try:
                        self.dev.add_book(f, "libprs500_"+str(_id)+"."+\
                            extension(_file), info, booklists, oncard=oncard, \
                            end_session=False)          
                        update_models()
                    except PathError, e:
                        if "already exists" in str(e): 
                            Error(info["title"] + \
                                    " already exists on the device", None)
                            self.progress(100)
                            continue
                        else: raise
                    finally: f.close()
                sync_lists()        
            else:
                for _file in files:
                    ename = _file
                    if extension(_file) not in self.dev.FORMATS:
                        Error(ename + " is not in a supported format")
                        continue
                    info = { "title":os.path.basename(_file), \
                            "authors":"Unknown", "cover":(None, None, None) }
                    f = open(_file, "rb")
                    self.status("Sending "+info["title"]+" to device")
                    try:
                        self.dev.add_book(f, os.path.basename(_file), info, \
                                    booklists, oncard=oncard, end_session=False)
                        update_models()
                    except PathError, e:
                        if "already exists" in str(e): 
                            Error(info["title"] + \
                                    " already exists on the device", None)
                            self.progress(100)
                            continue
                        else: raise
                    finally: f.close()
                sync_lists()
        except Exception, e:
            Error("Unable to send "+ename+" to device", e)
        finally: 
            self.window.setCursor(Qt.ArrowCursor)
            self.update_availabe_space()
    
    @apply
    def current_view():
        doc = """ The currently visible view """
        def fget(self):
            return self.library_view if self.library_view.isVisible() \
                                     else self.device_view
        return property(doc=doc, fget=fget)
    
    def __init__(self, window, log_packets):
        QObject.__init__(self)
        Ui_MainWindow.__init__(self)
        
        self.key = '-1'
        self.log_packets = log_packets
        self.dev = device(key=self.key, report_progress=self.progress, \
                          log_packets=self.log_packets)
        self.setupUi(window)
        self.card = None
        self.window = window
        window.closeEvent = self.close_event
        self.read_settings()
        
        # Setup Library Book list
        self.library_model = LibraryBooksModel(window)
        self.library_model.set_data(LibraryDatabase(str(self.database_path)))
        self.library_view.setModel(self.library_model)
        QObject.connect(self.library_model, SIGNAL("layoutChanged()"), \
                        self.library_view.resizeRowsToContents)
        QObject.connect(self.library_view.selectionModel(), \
            SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
        QObject.connect(self.search, SIGNAL("textChanged(QString)"), \
                        self.library_model.search)
        QObject.connect(self.library_model, SIGNAL("sorted()"), \
                        self.model_modified)
        QObject.connect(self.library_model, SIGNAL("searched()"), \
                        self.model_modified)
        QObject.connect(self.library_model, SIGNAL("deleted()"), \
                        self.model_modified)    
        QObject.connect(self.library_model, \
            SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
            self.resize_rows_and_columns)
        QObject.connect(self.library_view, \
            SIGNAL('books_dropped'), self.add_books)
        QObject.connect(self.library_model, \
            SIGNAL('formats_added'), self.formats_added)
        self.library_view.sortByColumn(3, Qt.DescendingOrder)
        
        # Create Device tree
        model = DeviceModel(self.device_tree)
        QObject.connect(self.device_tree, SIGNAL("activated(QModelIndex)"), \
                        self.tree_clicked)
        QObject.connect(self.device_tree, SIGNAL("clicked(QModelIndex)"), \
                        self.tree_clicked)        
        QObject.connect(model, SIGNAL('books_dropped'), self.add_books)
        QObject.connect(model, SIGNAL('upload_books'), self.upload_books)
        self.device_tree.setModel(model)   
        
        # Create Device Book list
        self.reader_model = DeviceBooksModel(window)    
        self.card_model = DeviceBooksModel(window)    
        self.device_view.setModel(self.reader_model)
        QObject.connect(self.device_view.selectionModel(), \
            SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
        for model in (self.reader_model, self. card_model):
            QObject.connect(model, SIGNAL("layoutChanged()"), \
                self.device_view.resizeRowsToContents)
            QObject.connect(self.search, SIGNAL("textChanged(QString)"), \
                model.search)
            QObject.connect(model, SIGNAL("sorted()"), self.model_modified)
            QObject.connect(model, SIGNAL("searched()"), self.model_modified)
            QObject.connect(model, SIGNAL("deleted()"), self.model_modified)
            QObject.connect(model, \
                SIGNAL("dataChanged(QModelIndex, QModelIndex)"), \
                self.resize_rows_and_columns)
        
        # Setup book display    
        self.book_cover.hide()
        self.book_info.hide()
        
        # Connect actions
        QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add)
        QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete)
        QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit)
        
        # DnD setup
        QObject.connect(self.book_cover, SIGNAL("cover_received(QPixmap)"), \
                self.update_cover)
        
        self.detector = DeviceConnectDetector(self.dev)
        self.connect(self.detector, SIGNAL("device_connected()"), \
                self.establish_connection)
        self.connect(self.detector, SIGNAL("device_removed()"), \
                     self.device_removed)
        self.search.setFocus(Qt.OtherFocusReason)
        self.show_device(False)
        self.df_template = self.df.text()
        self.df.setText(self.df_template.arg("").arg("").arg(""))
        window.show()
        self.library_view.resizeColumnsToContents()
        self.library_view.resizeRowsToContents()
        
    
    def device_removed(self):
        self.df.setText(self.df_template.arg("").arg("").arg(""))
        self.device_tree.hide_reader(True)
        self.device_tree.hide_card(True)
        self.device_tree.selectionModel().reset()
        self.status('SONY Reader disconnected')
        self.progress(100)
        if self.device_view.isVisible():
            self.device_view.hide()
            self.library_view.selectionModel().reset()
            self.library_view.show()
            self.book_cover.hide()
            self.book_info.hide()
    
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
        except DeviceBusy:            
            self.status("Device is in use by another application")
            self.window.setCursor(Qt.ArrowCursor)
            return
        except DeviceError, err:
            traceback.print_exc(err)
            self.dev.reconnect()
            self.thread().msleep(100)
            return self.establish_connection()
        except DeviceLocked:
            key, ok = QInputDialog.getText(self.window, 'Unlock device', \
                                'Key to unlock device:', QLineEdit.Password)
            self.key = str(key)
            if not ok:
                self.status('Device locked')
                self.window.setCursor(Qt.ArrowCursor)
                return
            else:
                self.dev.key = key
                return self.establish_connection()
        except ProtocolError, e: 
            traceback.print_exc(e)
            qFatal("Unable to connect to device. Please try unplugging and"+\
                   " reconnecting it")
        self.update_availabe_space(end_session=False)
        self.card = self.dev.card() 
        if self.card: self.device_tree.hide_card(False)
        else: self.device_tree.hide_card(True)
        self.device_tree.hide_reader(False)
        self.status("Loading media list from SONY Reader")
        self.reader_model.set_data(self.dev.books(end_session=False))
        if self.card: 
            self.status("Loading media list from Storage Card")
        self.card_model.set_data(self.dev.books(oncard=True))
        self.progress(100)
        self.df.setText(self.df_template.arg("Connected: "+info[0])\
                .arg(info[1]).arg(info[2]))
        self.window.setCursor(Qt.ArrowCursor)
    
    def update_availabe_space(self, end_session=True):
        space = self.dev.free_space(end_session=end_session)  
        sc = space[1] if int(space[1])>0 else space[2]    
        self.device_tree.model().update_free_space(space[0], sc)

class DeviceConnectDetector(QObject):
    
    def timerEvent(self, e):
        if e.timerId() == self.device_detector:
            is_connected = self.dev.is_connected()
            if is_connected and not self.is_connected:
                self.is_connected = True
                self.emit(SIGNAL("device_connected()"))
            elif not is_connected and self.is_connected:
                self.is_connected = False
                self.emit(SIGNAL("device_removed()"))
        
    def __init__(self, dev):
        QObject.__init__(self)
        self.dev = dev
        self.is_connected = False
        self.device_detector = self.startTimer(1000)

def main():
    from optparse import OptionParser
    from libprs500 import __version__ as VERSION
    lock = os.path.join(tempfile.gettempdir(),"libprs500_gui_lock")
    if os.access(lock, os.F_OK):
        print >>sys.stderr, "Another instance of", APP_TITLE, "is running"
        print >>sys.stderr, "If you are sure this is not the case then "+\
                            "manually delete the file", lock
        sys.exit(1)
    parser = OptionParser(usage="usage: %prog [options]", version=VERSION)
    parser.add_option("--log-packets", help="print out packet stream to stdout. "+\
                    "The numbers in the left column are byte offsets that allow"+\
                    " the packet size to be read off easily.", \
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
    Main(window, options.log_packets)    
    return app.exec_()

if __name__ == "__main__": 
    sys.exit(main())
