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
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.Warning
import os, tempfile, sys

from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, \
                         QSettings, QVariant, QSize, QThread
from PyQt4.QtGui import QPixmap, QColor, QPainter, QMenu, QIcon
from PyQt4.QtSvg import QSvgRenderer

from libprs500 import __version__, __appname__
from libprs500.ebooks.metadata.meta import get_metadata
from libprs500.devices.errors import FreeSpaceError
from libprs500.devices.interface import Device
from libprs500.gui2 import APP_TITLE, warning_dialog, choose_files, error_dialog, \
                           initialize_file_icon_provider, BOOK_EXTENSIONS, \
                           pixmap_to_data
from libprs500.gui2.main_ui import Ui_MainWindow
from libprs500.gui2.device import DeviceDetector, DeviceManager
from libprs500.gui2.status import StatusBar
from libprs500.gui2.jobs import JobManager, JobException
from libprs500.gui2.dialogs.metadata_single import MetadataSingleDialog

class Main(QObject, Ui_MainWindow):
    
    def set_default_thumbnail(self, height):
        r = QSvgRenderer(':/images/book.svg')
        pixmap = QPixmap(height, height)
        pixmap.fill(QColor(255,255,255))
        p = QPainter(pixmap)
        r.render(p)
        p.end()
        self.default_thumbnail = (pixmap.width(), pixmap.height(), pixmap_to_data(pixmap))
    
    def __init__(self, window):
        QObject.__init__(self)
        Ui_MainWindow.__init__(self)
        self.window = window
        self.setupUi(window)
        self.read_settings()
        self.job_manager = JobManager()
        self.device_manager = None
        self.upload_memory = {}
        self.delete_memory = {}
        self.default_thumbnail = None
        ####################### Location View ########################
        QObject.connect(self.location_view, SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        
        ####################### Vanity ########################
        self.vanity_template = self.vanity.text().arg(__version__)
        self.vanity.setText(self.vanity_template.arg(' '))
        
        ####################### Status Bar #####################
        self.status_bar = StatusBar()
        self.window.setStatusBar(self.status_bar)
        QObject.connect(self.job_manager, SIGNAL('job_added(int)'), self.status_bar.job_added)
        QObject.connect(self.job_manager, SIGNAL('no_more_jobs()'), self.status_bar.no_more_jobs)
        
        ####################### Setup Toolbar #####################
        sm = QMenu()
        sm.addAction(QIcon(':/images/reader.svg'), 'Send to main memory')
        sm.addAction(QIcon(':/images/sd.svg'), 'Send to storage card')
        self.sync_menu = sm # Needed
        QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add_books)
        QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete_books)
        QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit_metadata)
        QObject.connect(self.action_sync, SIGNAL("triggered(bool)"), self.sync_to_main_memory)        
        QObject.connect(sm.actions()[0], SIGNAL('triggered(bool)'), self.sync_to_main_memory)
        QObject.connect(sm.actions()[1], SIGNAL('triggered(bool)'), self.sync_to_card)
        self.action_sync.setMenu(sm)
        self.tool_bar.insertAction(self.action_edit, self.action_sync)
        self.tool_bar.setContextMenuPolicy(Qt.PreventContextMenu)
        
        ####################### Library view ########################
        self.library_view.set_database(self.database_path)
        for func, target in [
                             ('connect_to_search_box', self.search),
                             ('connect_to_book_display', self.status_bar.book_info.show_data),
                             ]:
            for view in (self.library_view, self.memory_view, self.card_view):
                getattr(view, func)(target)
                
        self.memory_view.connect_dirtied_signal(self.upload_booklists)
        self.card_view.connect_dirtied_signal(self.upload_booklists)
        
        window.closeEvent = self.close_event
        window.show()
        self.stack.setCurrentIndex(0)
        self.library_view.migrate_database()
        self.library_view.sortByColumn(3, Qt.DescendingOrder)        
        self.library_view.resizeColumnsToContents()
        self.library_view.resizeRowsToContents()
        self.search.setFocus(Qt.OtherFocusReason)
        
        ####################### Setup device detection ########################
        self.detector = DeviceDetector(sleep_time=2000)
        QObject.connect(self.detector, SIGNAL('connected(PyQt_PyObject, PyQt_PyObject)'), 
                        self.device_detected, Qt.QueuedConnection)
        self.detector.start(QThread.InheritPriority)
        
    
    def current_view(self):
        '''Convenience method that returns the currently visible view '''
        idx = self.stack.currentIndex()
        if idx == 0:
            return self.library_view
        if idx == 1:
            return self.memory_view
        if idx == 2:
            return self.card_view
        
    def booklists(self):
        return self.memory_view.model().db, self.card_view.model().db
            
        
    
    ########################## Connect to device ##############################
    def device_detected(self, cls, connected):
        '''
        Called when a device is connected to the computer.
        '''
        if connected:    
            self.device_manager = DeviceManager(cls)
            func = self.device_manager.info_func()
            self.job_manager.run_device_job(self.info_read, func)
            self.set_default_thumbnail(cls.THUMBNAIL_HEIGHT)
            
    def info_read(self, id, result, exception, formatted_traceback):
        '''
        Called once device information has been read.
        '''
        if exception:
            self.job_exception(id, exception, formatted_traceback)
            return
        info, cp, fs = result
        self.location_view.model().update_devices(cp, fs)
        self.vanity.setText(self.vanity_template.arg('Connected '+' '.join(info[:-1])))
        func = self.device_manager.books_func()
        self.job_manager.run_device_job(self.metadata_downloaded, func)
        
    def metadata_downloaded(self, id, result, exception, formatted_traceback):
        '''
        Called once metadata has been read for all books on the device.
        '''
        if exception:
            self.job_exception(id, exception, formatted_traceback)
            return
        mainlist, cardlist = result
        self.memory_view.set_database(mainlist)
        self.card_view.set_database(cardlist)
        for view in (self.memory_view, self.card_view):
            view.sortByColumn(3, Qt.DescendingOrder)            
            view.resizeColumnsToContents()
            view.resizeRowsToContents()
            view.resize_on_select = not view.isVisible()
        #self.location_selected('main')
    ############################################################################
    
    
    ############################# Upload booklists #############################
    def upload_booklists(self):
        '''
        Upload metadata to device.
        '''
        self.job_manager.run_device_job(self.metadata_synced, 
                                        self.device_manager.sync_booklists_func(),
                                        self.booklists())
    
    def metadata_synced(self, id, result, exception, formatted_traceback):
        '''
        Called once metadata has been uploaded.
        '''
        if exception:
            self.job_exception(id, exception, formatted_traceback)
            return
    ############################################################################
    
    
    ################################# Add books ################################
    def add_books(self, checked):
        '''
        Add books from the local filesystem to either the library or the device.
        '''
        books = choose_files(self.window, 'add books dialog dir', 'Select books',
                             filters=[('Books', BOOK_EXTENSIONS)])
        if not books:
            return
        on_card = False if self.stack.currentIndex() != 2 else True
        # Get format and metadata information
        formats, metadata, names, infos = [], [], [], []        
        for book in books:
            format = os.path.splitext(book)[1]
            format = format[1:] if format else None
            stream = open(book, 'rb')
            mi = get_metadata(stream, stream_type=format)
            if not mi.title:
                mi.title = os.path.splitext(os.path.basename(book))[0]
            formats.append(format)
            metadata.append(mi)
            names.append(os.path.basename(book))
            infos.append({'title':mi.title, 'authors':mi.author, 'cover':self.default_thumbnail})
        
        if self.stack.currentIndex() == 0:
            model = self.current_view().model()
            model.add_books(books, formats, metadata)
            model.resort()
            model.research()
        else:
            self.upload_books(books, names, infos, on_card=on_card)
            self.status_bar.showMessage('Adding books to device.', 2000)
    
    def upload_books(self, files, names, metadata, on_card=False):
        '''
        Upload books to device.
        @param files: List of either paths to files or file like objects
        '''
        id = self.job_manager.run_device_job(self.books_uploaded,
                                        self.device_manager.upload_books_func(),
                                        files, names, on_card=on_card 
                                        )
        self.upload_memory[id] = metadata
    
    def books_uploaded(self, id, result, exception, formatted_traceback):
        '''
        Called once books have been uploaded.
        '''
        metadata = self.upload_memory.pop(id)
        if exception:
            if isinstance(exception, FreeSpaceError):
                where = 'in main memory.' if 'memory' in str(exception) else 'on the storage card.'
                titles = '\n'.join(['<li>'+mi['title']+'</li>' for mi in metadata])
                d = error_dialog(self.window, 'No space on device',
                                 '<p>Cannot upload books to device there is no more free space available '+where+
                                 '</p>\n<ul>%s</ul>'%(titles,))
                d.exec_()                
            else:
                self.job_exception(id, exception, formatted_traceback)
            return
        
        self.device_manager.add_books_to_metadata(result, metadata, self.booklists())
        
        self.upload_booklists()
        
        for view in (self.memory_view, self.card_view):
            view.model().resort()
            view.model().research()
            
        
    ############################################################################    
    
    ############################### Delete books ###############################
    def delete_books(self, checked):
        '''
        Delete selected books from device or library.
        '''
        view = self.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        if self.stack.currentIndex() == 0:
            view.model().delete_books(rows)
        else:
            view = self.memory_view if self.stack.currentIndex() == 1 else self.card_view            
            paths = view.model().paths(rows)
            id = self.remove_paths(paths)
            self.delete_memory[id] = paths
            view.model().mark_for_deletion(id, rows)
            self.status_bar.showMessage('Deleting books from device.', 1000)
            
    def remove_paths(self, paths):
        return self.job_manager.run_device_job(self.books_deleted,
                                self.device_manager.delete_books_func(), paths)
        
            
    def books_deleted(self, id, result, exception, formatted_traceback):
        '''
        Called once deletion is done on the device
        '''
        for view in (self.memory_view, self.card_view):
            view.model().deletion_done(id, bool(exception))
        if exception:
            self.job_exception(id, exception, formatted_traceback)            
            return
        
        self.upload_booklists()
        
        if self.delete_memory.has_key(id):
            paths = self.delete_memory.pop(id)
            self.device_manager.remove_books_from_metadata(paths, self.booklists())
        
            for view in (self.memory_view, self.card_view):
                view.model().remap()
            
    ############################################################################
    
    ############################### Edit metadata ##############################
    def edit_metadata(self, checked):
        '''
        Edit metadata of selected books in library individually.
        '''
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        changed = False
        for row in rows:
            if MetadataSingleDialog(self.window, row.row(), 
                                    self.library_view.model().db).changed:
                changed = True                        
        
        if changed:
            self.library_view.model().resort()
            self.library_view.model().research()
            
    ############################################################################
    
    ############################# Syncing to device#############################
    def sync_to_main_memory(self, checked):
        self.sync_to_device(False)
        
    def sync_to_card(self, checked):
        self.sync_to_device(True)
        
    def cover_to_thumbnail(self, data):
        p = QPixmap()
        p.loadFromData(data)
        if not p.isNull():
            ht = self.device_manager.device_class.THUMBNAIL_HEIGHT if self.device_manager else \
                       Device.THUMBNAIL_HEIGHT
            p = p.scaledToHeight(ht, Qt.SmoothTransformation)
            return (p.width(), p.height(), pixmap_to_data(p))
    
    def sync_to_device(self, on_card):
        rows = self.library_view.selectionModel().selectedRows()
        if not self.device_manager or not rows or len(rows) == 0:
            return
        ids = iter(self.library_view.model().id(r) for r in rows)
        metadata = self.library_view.model().get_metadata(rows)
        for mi in metadata:
            cdata = mi['cover']
            if cdata:
                mi['cover'] = self.cover_to_thumbnail(cdata)
        metadata = iter(metadata)
        files = self.library_view.model().get_preferred_formats(rows, 
                                    self.device_manager.device_class.FORMATS)
        bad, good, gf, names = [], [], [], []
        for f in files:
            mi = metadata.next()
            id = ids.next()
            if f is None:
                bad.append(mi['title'])
            else:
                good.append(mi)
                gf.append(f)
                names.append('%s_%d%s'%(__appname__, id, os.path.splitext(f.name)[1]))
        self.upload_books(gf, names, good, on_card)
        self.status_bar.showMessage('Sending books to device.', 5000)
        if bad:
            bad = '\n'.join('<li>%s</li>'%(i,) for i in bad)
            d = warning_dialog(self.window, 'No suitable formats', 'Could not upload the following books to the device, as no suitable formats were found:<br><ul>%s</ul>'%(bad,))
            d.exec_()
                
            
    ############################################################################
    
    def location_selected(self, location):
        '''
        Called when a location icon is clicked (e.g. Library)
        '''
        page = 0 if location == 'library' else 1 if location == 'main' else 2
        self.stack.setCurrentIndex(page)
        view = self.memory_view if page == 1 else self.card_view if page == 2 else None
        if view:
            if view.resize_on_select:
                view.resizeRowsToContents()
                view.resizeColumnsToContents()
                view.resize_on_select = False
    
    def job_exception(self, id, exception, formatted_traceback):
        '''
        Handle exceptions in threaded jobs.
        '''
        raise JobException, str(exception) + '\n\r' + formatted_traceback
        
    
    def read_settings(self):
        settings = QSettings()
        settings.beginGroup("MainWindow")
        self.window.resize(settings.value("size", QVariant(QSize(1000, 700))).toSize())
        settings.endGroup()
        self.database_path = settings.value("database path", QVariant(os.path\
                                    .expanduser("~/library1.db"))).toString()
    
    def write_settings(self):
        settings = QSettings()
        settings.beginGroup("MainWindow")
        settings.setValue("size", QVariant(self.window.size()))
        settings.endGroup()
    
    def close_event(self, e):
        self.write_settings()
        e.accept()

def main():
    lock = os.path.join(tempfile.gettempdir(),"libprs500_gui_lock")
    if os.access(lock, os.F_OK):
        print >>sys.stderr, "Another instance of", APP_TITLE, "is running"
        print >>sys.stderr, "If you are sure this is not the case then "+\
                            "manually delete the file", lock
        sys.exit(1)
    from PyQt4.Qt import QApplication, QMainWindow
    app = QApplication(sys.argv)    
    #from IPython.Shell import IPShellEmbed
    #ipshell = IPShellEmbed([],
    #                   banner = 'Dropping into IPython',
    #                   exit_msg = 'Leaving Interpreter, back to program.')
    #ipshell()
    #return 0
    window = QMainWindow()
    window.setWindowTitle(APP_TITLE)
    QCoreApplication.setOrganizationName("KovidsBrain")
    QCoreApplication.setApplicationName(APP_TITLE)
    initialize_file_icon_provider()
    main = Main(window)
    def unhandled_exception(type, value, tb):
        import traceback
        traceback.print_exception(type, value, tb, file=sys.stderr)
        if type == KeyboardInterrupt:
            QCoreApplication.exit(1)
    sys.excepthook = unhandled_exception
    
    return app.exec_()
    
        
if __name__ == '__main__':
    sys.exit(main())