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
from PyQt4.QtGui import QPixmap, QErrorMessage, \
                        QMessageBox, QFileDialog, QIcon, QDialog
from PyQt4.Qt import qDebug, qFatal, qWarning, qCritical

from libprs500.communicate import PRS500Device as device
from libprs500.books import fix_ids
from libprs500.errors import *
from libprs500.gui import import_ui, installErrorHandler, Error, _Warning, \
                          extension, APP_TITLE
from libprs500.gui.widgets import LibraryBooksModel, DeviceBooksModel, \
                                  DeviceModel
from database import LibraryDatabase
from editbook import EditBookDialog


DEFAULT_BOOK_COVER = None
LIBRARY_BOOK_TEMPLATE = QString("<table><tr><td><b>Formats:</b> %1  \
                                 </td><td><b>Tags:</b> %2</td></tr> \
                                 <tr><td><b>Comments:</b>%3</td></tr></table>")
DEVICE_BOOK_TEMPLATE = QString("<table><tr><td><b>Title: </b>%1</td><td> \
                                <b>&nbsp;Size:</b> %2</td></tr>\
                                <tr><td><b>Author: </b>%3</td>\
                                <td><b>&nbsp;Type: </b>%4</td></tr></table>")

Ui_MainWindow = import_ui("main.ui")
class Main(QObject, Ui_MainWindow): 
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
            self.device_view.show()
            self.library_view.hide()
            self.book_cover.setAcceptDrops(False)
            self.current_view = self.device_view      
        else: 
            self.device_view.hide()
            self.library_view.show()
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
        if self.library_view.isVisible(): view = self.library_view
        else: view = self.device_view
        view.clearSelection()    
        view.resizeColumnsToContents()
        self.book_cover.hide()
        self.book_info.hide()
        QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)    
    
    def resize_columns(self, topleft, bottomright):
        if self.library_view.isVisible(): 
            view = self.library_view
        else: view = self.device_view
        for c in range(topleft.column(), bottomright.column()+1):
            view.resizeColumnToContents(c)
    
    def show_book(self, current, previous):    
        if self.library_view.isVisible():
            formats, tags, comments, cover = current.model().info(current.row())
            data = LIBRARY_BOOK_TEMPLATE.arg(formats).arg(tags).arg(comments)
            tooltip = "To save the cover, drag it to the desktop.<br>To \
                       change the cover drag the new cover onto this picture"
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
            self.status("Deleting files from device")
            paths = self.device_view.model().delete(rows)
            for path in paths:
                self.status("Deleting "+path[path.rfind("/")+1:])
                self.dev.del_file(path, end_session=False)
            fix_ids(self.reader_model.booklist, self.card_model.booklist)
            self.status("Syncing media list to reader")
            self.dev.upload_book_list(self.reader_model.booklist)
            if len(self.card_model.booklist):
                self.status("Syncing media list to card")
                self.dev.upload_book_list(self.card_model.booklist)
            self.update_availabe_space()
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
            x = str(files[0])
            settings.setValue("add books dialog dir", QVariant(os.path.dirname(x)))
            files = str(files.join("|||")).split("|||")      
        self.add_books(files)
    
    def add_books(self, files):
        self.window.setCursor(Qt.WaitCursor)
        for _file in files:
            _file = os.path.abspath(_file)
            self.library_view.model().add_book(_file)
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
                _id = self.library_model.id_from_index(row)
                dialog = QDialog(self.window)
                EditBookDialog(dialog, _id, self.library_model.db)
                if dialog.exec_() == QDialog.Accepted:
                    self.library_model.refresh_row(row.row())
    
    
    def update_cover(self, pix):    
        if not pix.isNull():
            try:
                self.library_view.model().update_cover(self.library_view\
                        .currentIndex(), pix)
                self.book_cover.setPixmap(pix)
            except Exception, e: Error("Unable to change cover", e)
    
    def upload_books(self, to, files, ids):
        oncard = False if to == "reader" else True
        booklists = (self.reader_model.booklist, self.card_model.booklist)
        def update_models():
            hv = self.device_view.horizontalHeader()
            col = hv.sortIndicatorSection()
            order = hv.sortIndicatorOrder()
            model = self.card_model if oncard else self.reader_model
            model.sort(col, order)
            if self.device_view.isVisible() and self.device_view.model()\
                    == model: self.search.clear()
            else: model.search("")
        
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
                        if re.match("......_"+str(_id)+"_", os.path.basename(f)):
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
    
    def __init__(self, window, log_packets):
        QObject.__init__(self)
        Ui_MainWindow.__init__(self)
        
        self.dev = device(report_progress=self.progress, log_packets=log_packets)
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
        QObject.connect(self.library_model, SIGNAL("layoutChanged()"), \
                        self.library_view.resizeRowsToContents)
        QObject.connect(self.library_view.selectionModel(), \
            SIGNAL("currentChanged(QModelIndex, QModelIndex)"), self.show_book)
        QObject.connect(self.search, SIGNAL("textChanged(QString)"), \
                        self.library_model.search)
        QObject.connect(self.library_model, SIGNAL("sorted()"), self.model_modified)
        QObject.connect(self.library_model, SIGNAL("searched()"), \
                        self.model_modified)
        QObject.connect(self.library_model, SIGNAL("deleted()"), \
                        self.model_modified)    
        QObject.connect(self.library_model, \
            SIGNAL("dataChanged(QModelIndex, QModelIndex)"), self.resize_columns)
        QObject.connect(self.library_view, \
            SIGNAL('books_dropped'), self.add_books)
        QObject.connect(self.library_model, \
            SIGNAL('formats_added'), self.formats_added)
        self.library_view.resizeColumnsToContents()
        
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
            QObject.connect(model, SIGNAL("dataChanged(QModelIndex, QModelIndex)")\
                , self.resize_columns)
        
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
        self.connect(self.detector, SIGNAL("device_removed()"), self.device_removed)
        self.search.setFocus(Qt.OtherFocusReason)
        self.show_device(False)
        self.df_template = self.df.text()
        self.df.setText(self.df_template.arg("").arg("").arg(""))
        window.show()    
    
    def device_removed(self):
        """ @todo: only reset stuff if library is not shown """
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
            self.detector.connection_failed()
            return    
        except ProtocolError, e: 
            traceback.print_exc(e)
            qFatal("Unable to connect to device. Please try unplugging and"+\
                   " reconnecting it")
        self.df.setText(self.df_template.arg("Connected: "+info[0])\
                .arg(info[1]).arg(info[2]))
        self.update_availabe_space(end_session=False)
        self.card = self.dev.card()
        self.is_connected = True    
        if self.card: self.device_tree.hide_card(False)
        else: self.device_tree.hide_card(True)
        self.device_tree.hide_reader(False)
        self.status("Loading media list from SONY Reader")
        self.reader_model.set_data(self.dev.books(end_session=False))
        if self.card: self.status("Loading media list from Storage Card")
        self.card_model.set_data(self.dev.books(oncard=True))
        self.progress(100)
        self.window.setCursor(Qt.ArrowCursor)
    
    def update_availabe_space(self, end_session=True):
        space = self.dev.free_space(end_session=end_session)  
        sc = space[1] if int(space[1])>0 else space[2]    
        self.device_tree.model().update_free_space(space[0], sc)

class LockFile(object):
    def __init__(self, path):
        self.path = path
        f = open(path, "w")
        f.close()
    
    def __del__(self):
        if os.access(self.path, os.F_OK): os.remove(self.path)

class DeviceConnectDetector(QObject):
    
    def timerEvent(self, e):
        if e.timerId() == self.device_detector:
            is_connected = self.dev.is_connected()
            if is_connected and not self.is_connected:
                self.emit(SIGNAL("device_connected()"))
                self.is_connected = True
            elif not is_connected and self.is_connected:
                self.emit(SIGNAL("device_removed()"))       
                self.is_connected = False
    
    def connection_failed(self):
        # TODO: Do something intelligent if we're using HAL
        self.is_connected = False
    
    def udi_is_device(self, udi):
        ans = False
        try:
            devobj = bus.get_object('org.freedesktop.Hal', udi)
            dev = dbus.Interface(devobj, "org.freedesktop.Hal.Device")
            properties = dev.GetAllProperties()
            vendor_id = int(properties["usb_device.vendor_id"]), 
            product_id = int(properties["usb_device.product_id"])
            if self.dev.signature() == (vendor_id, product_id): ans = True
        except:
            self.device_detector = self.startTimer(1000)
        return ans
    
    def device_added_callback(self, udi):    
        if self.udi_is_device(udi): 
            self.emit(SIGNAL("device_connected()"))
    
    def device_removed_callback(self, udi):
        if self.udi_is_device(udi):
            self.emit(SIGNAL("device_removed()"))
    
    def __init__(self, dev):
        QObject.__init__(self)
        self.dev = dev
        try:
            raise Exception("DBUS doesn't support the Qt mainloop")
            import dbus      
            bus = dbus.SystemBus()
            hal_manager_obj = bus.get_object('org.freedesktop.Hal',\
                                                '/org/freedesktop/Hal/Manager')
            hal_manager = dbus.Interface(hal_manager_obj,\
                                            'org.freedesktop.Hal.Manager')
            hal_manager.connect_to_signal('DeviceAdded', \
                                            self.device_added_callback)
            hal_manager.connect_to_signal('DeviceRemoved', \
                                            self.device_removed_callback)
        except Exception, e:
            #_Warning("Could not connect to HAL", e)
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
    lock = LockFile(lock)
    return app.exec_()

if __name__ == "__main__": 
    sys.exit(main())
