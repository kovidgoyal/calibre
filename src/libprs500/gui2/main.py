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
import os, sys, traceback, StringIO, textwrap

from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, \
                         QSettings, QVariant, QSize, QThread
from PyQt4.QtGui import QPixmap, QColor, QPainter, QMenu, QIcon, QMessageBox
from PyQt4.QtSvg import QSvgRenderer

from libprs500 import __version__, __appname__, iswindows, isosx
from libprs500.ebooks.metadata.meta import get_metadata
from libprs500.devices.errors import FreeSpaceError
from libprs500.devices.interface import Device
from libprs500.gui2 import APP_TITLE, warning_dialog, choose_files, error_dialog, \
                           initialize_file_icon_provider, BOOK_EXTENSIONS, \
                           pixmap_to_data
from libprs500.gui2.main_ui import Ui_MainWindow
from libprs500.gui2.device import DeviceDetector, DeviceManager
from libprs500.gui2.status import StatusBar
from libprs500.gui2.jobs import JobManager
from libprs500.gui2.dialogs.metadata_single import MetadataSingleDialog
from libprs500.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from libprs500.gui2.dialogs.jobs import JobsDialog


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
        self.jobs_dialog = JobsDialog(self.window, self.job_manager)
        self.device_manager = None
        self.upload_memory = {}
        self.delete_memory = {}
        self.default_thumbnail = None
        self.device_error_dialog = error_dialog(self.window, 'Error communicating with device', ' ')
        self.device_error_dialog.setModal(Qt.NonModal)
        self.tb_wrapper = textwrap.TextWrapper(width=40)
        ####################### Location View ########################
        QObject.connect(self.location_view, SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        QObject.connect(self.stack, SIGNAL('currentChanged(int)'), 
                        self.location_view.location_changed)
        
        ####################### Vanity ########################
        self.vanity_template = self.vanity.text().arg(__version__)
        self.vanity.setText(self.vanity_template.arg(' '))
        
        ####################### Status Bar #####################
        self.status_bar = StatusBar(self.jobs_dialog)
        self.window.setStatusBar(self.status_bar)
        QObject.connect(self.job_manager, SIGNAL('job_added(int)'), self.status_bar.job_added)
        QObject.connect(self.job_manager, SIGNAL('job_done(int)'), self.status_bar.job_done)
        
        ####################### Setup Toolbar #####################
        sm = QMenu()
        sm.addAction(QIcon(':/images/reader.svg'), 'Send to main memory')
        sm.addAction(QIcon(':/images/sd.svg'), 'Send to storage card')
        self.sync_menu = sm # Needed
        md = QMenu()
        md.addAction('Edit metadata individually')
        md.addAction('Edit metadata in bulk')
        self.metadata_menu = md
        QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add_books)
        QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete_books)
        QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit_metadata)
        QObject.connect(md.actions()[0], SIGNAL('triggered(bool)'), self.edit_metadata)
        QObject.connect(md.actions()[1], SIGNAL('triggered(bool)'), self.edit_bulk_metadata)
        QObject.connect(self.action_sync, SIGNAL("triggered(bool)"), self.sync_to_main_memory)        
        QObject.connect(sm.actions()[0], SIGNAL('triggered(bool)'), self.sync_to_main_memory)
        QObject.connect(sm.actions()[1], SIGNAL('triggered(bool)'), self.sync_to_card)
        
        self.action_sync.setMenu(sm)
        self.action_edit.setMenu(md)
        self.tool_bar.addAction(self.action_sync)
        self.tool_bar.addAction(self.action_edit)
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
            self.status_bar.showMessage('Device: '+cls.__name__+' detected.', 3000)
            self.action_sync.setEnabled(True)
        else:
            self.job_manager.terminate_device_jobs()
            self.device_manager.device_removed()
            self.location_view.model().update_devices()
            self.action_sync.setEnabled(False)
            if self.current_view() != self.library_view:
                self.status_bar.reset_info()
                self.location_selected('library')
            
    def info_read(self, id, description, result, exception, formatted_traceback):
        '''
        Called once device information has been read.
        '''
        if exception:
            self.device_job_exception(id, description, exception, formatted_traceback)
            return
        info, cp, fs = result
        self.location_view.model().update_devices(cp, fs)
        self.vanity.setText(self.vanity_template.arg('Connected '+' '.join(info[:-1])))
        func = self.device_manager.books_func()
        self.job_manager.run_device_job(self.metadata_downloaded, func)
        
    def metadata_downloaded(self, id, description, result, exception, formatted_traceback):
        '''
        Called once metadata has been read for all books on the device.
        '''
        if exception:
            self.device_job_exception(id, description, exception, formatted_traceback)
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
    
    def metadata_synced(self, id, description, result, exception, formatted_traceback):
        '''
        Called once metadata has been uploaded.
        '''
        if exception:
            self.device_job_exception(id, description, exception, formatted_traceback)
            return
        cp, fs = result
        self.location_view.model().update_devices(cp, fs)
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
        titles = ', '.join([i['title'] for i in metadata])
        id = self.job_manager.run_device_job(self.books_uploaded,
                                        self.device_manager.upload_books_func(),
                                        files, names, on_card=on_card,
                                        job_extra_description=titles 
                                        )
        self.upload_memory[id] = metadata
    
    def books_uploaded(self, id, description, result, exception, formatted_traceback):
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
                self.device_job_exception(id, description, exception, formatted_traceback)
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
        
            
    def books_deleted(self, id, description, result, exception, formatted_traceback):
        '''
        Called once deletion is done on the device
        '''
        for view in (self.memory_view, self.card_view):
            view.model().deletion_done(id, bool(exception))
        if exception:
            self.device_job_exception(id, description, exception, formatted_traceback)            
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
            d = error_dialog(self.window, 'Cannot edit metadata', 'No books selected')
            d.exec_()
            return
        changed = False
        for row in rows:
            if MetadataSingleDialog(self.window, row.row(), 
                                    self.library_view.model().db).changed:
                changed = True                        
        
        if changed:
            self.library_view.model().resort()
            self.library_view.model().research()
            
    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.window, 'Cannot edit metadata', 'No books selected')
            d.exec_()
            return
        if MetadataBulkDialog(self.window, rows, self.library_view.model().db).changed:
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
            d = warning_dialog(self.window, 'No suitable formats', 
                    'Could not upload the following books to the device, as no suitable formats were found:<br><ul>%s</ul>'%(bad,))
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
        self.status_bar.reset_info()
        self.current_view().clearSelection()
        self.current_view().setCurrentIndex(self.current_view().model().index(0, 0))
                
    
    def wrap_traceback(self, tb):
        tb = unicode(tb, 'utf8', 'replace')
        tb = '\n'.join(self.tb_wrapper.wrap(tb))
        return tb
    
    def device_job_exception(self, id, description, exception, formatted_traceback):
        '''
        Handle exceptions in threaded jobs.
        '''
        print >>sys.stderr, 'Error in job:', description
        print >>sys.stderr, exception
        print >>sys.stderr, formatted_traceback
        if not self.device_error_dialog.isVisible():
            msg =  u'<p><b>%s</b>: '%(exception.__class__.__name__,) + unicode(str(exception), 'utf8', 'replace') + u'</p>'
            msg += u'<p>Failed to perform <b>job</b>: '+description
            msg += u'<p>Further device related error messages will not be shown while this message is visible.'
            msg += u'<p>Detailed <b>traceback</b>:<pre>'
            msg += self.wrap_traceback(formatted_traceback)
            self.device_error_dialog.setText(msg)
            self.device_error_dialog.show()
        
        
    
    def read_settings(self):
        settings = QSettings()
        settings.beginGroup("MainWindow")
        self.window.resize(settings.value("size", QVariant(QSize(800, 600))).toSize())
        settings.endGroup()
        self.database_path = settings.value("database path", 
                QVariant(os.path.join(os.path.expanduser('~'),'library1.db'))).toString()
    
    def write_settings(self):
        settings = QSettings()
        settings.beginGroup("MainWindow")
        settings.setValue("size", QVariant(self.window.size()))
        settings.endGroup()
    
    def close_event(self, e):
        msg = 'There are active jobs. Are you sure you want to quit?'
        if self.job_manager.has_device_jobs():
            msg = '<p>'+__appname__ + ' is communicating with the device!<br>'+\
                  'Quitting may cause corruption on the device.<br>'+\
                  'Are you sure you want to quit?'
        if self.job_manager.has_jobs():
            d = QMessageBox(QMessageBox.Warning, 'WARNING: Active jobs', msg,
                            QMessageBox.Yes|QMessageBox.No, self.window)
            d.setIconPixmap(QPixmap(':/images/dialog_warning.svg'))
            d.setDefaultButton(QMessageBox.No)
            if d.exec_() == QMessageBox.Yes:
                self.write_settings()
                e.accept()
            else:
                e.ignore()
                
    def unhandled_exception(self, type, value, tb):
        sio = StringIO.StringIO()
        traceback.print_exception(type, value, tb, file=sio)
        fe = sio.getvalue()
        print >>sys.stderr, fe
        if type == KeyboardInterrupt:
            self.window.close()
            self.window.thread().exit(0)
        msg = '<p><b>' + unicode(str(value), 'utf8', 'replace') + '</b></p>'
        msg += '<p>Detailed <b>traceback</b>:<pre>'+self.wrap_traceback(fe)+'</pre>'
        d = error_dialog(self.window, 'ERROR: Unhandled exception', msg)
        d.exec_()

def main():    
    from PyQt4.Qt import QApplication, QMainWindow
    app = QApplication(sys.argv)    
    window = QMainWindow()
    window.setWindowTitle(APP_TITLE)
    QCoreApplication.setOrganizationName("KovidsBrain")
    QCoreApplication.setApplicationName(APP_TITLE)
    
    initialize_file_icon_provider()
    main = Main(window)        
    sys.excepthook = main.unhandled_exception    
    return app.exec_()
    
        
if __name__ == '__main__':
    sys.exit(main())