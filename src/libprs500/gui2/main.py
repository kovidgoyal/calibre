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
from libprs500 import sanitize_file_name
import os, sys, textwrap, cStringIO, collections, traceback

from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, \
                         QSettings, QVariant, QSize, QThread
from PyQt4.QtGui import QPixmap, QColor, QPainter, QMenu, QIcon, QMessageBox, \
                        QToolButton, QDialog
from PyQt4.QtSvg import QSvgRenderer

from libprs500 import __version__, __appname__, islinux
from libprs500.ptempfile import PersistentTemporaryFile
from libprs500.ebooks.metadata.meta import get_metadata
from libprs500.ebooks.lrf.web.convert_from import main as web2lrf
from libprs500.ebooks.lrf.any.convert_from import main as any2lrf
from libprs500.devices.errors import FreeSpaceError
from libprs500.devices.interface import Device
from libprs500.gui2 import APP_UID, warning_dialog, choose_files, error_dialog, \
                           initialize_file_icon_provider, BOOK_EXTENSIONS, \
                           pixmap_to_data, choose_dir, ORG_NAME
from libprs500.gui2.main_window import MainWindow
from libprs500.gui2.main_ui import Ui_MainWindow
from libprs500.gui2.device import DeviceDetector, DeviceManager
from libprs500.gui2.status import StatusBar
from libprs500.gui2.jobs import JobManager
from libprs500.gui2.dialogs.metadata_single import MetadataSingleDialog
from libprs500.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from libprs500.gui2.dialogs.jobs import JobsDialog
from libprs500.gui2.dialogs.conversion_error import ConversionErrorDialog 
from libprs500.gui2.dialogs.lrf_single import LRFSingleDialog
from libprs500.gui2.dialogs.password import PasswordDialog
from libprs500.gui2.lrf_renderer.main import file_renderer
from libprs500.gui2.lrf_renderer.main import option_parser as lrfviewerop
from libprs500.library.database import DatabaseLocked
from libprs500.ebooks.metadata.meta import set_metadata
from libprs500.ebooks.metadata import MetaInformation


class Main(MainWindow, Ui_MainWindow):
    
    def set_default_thumbnail(self, height):
        r = QSvgRenderer(':/images/book.svg')
        pixmap = QPixmap(height, height)
        pixmap.fill(QColor(255,255,255))
        p = QPainter(pixmap)
        r.render(p)
        p.end()
        self.default_thumbnail = (pixmap.width(), pixmap.height(), pixmap_to_data(pixmap))
    
    def __init__(self, parent=None):
        MainWindow.__init__(self, parent)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(__appname__)
        self.read_settings()
        self.job_manager = JobManager()
        self.jobs_dialog = JobsDialog(self, self.job_manager)
        self.device_manager = None
        self.upload_memory = {}
        self.delete_memory = {}
        self.conversion_jobs = {}
        self.persistent_files = []
        self.default_thumbnail = None
        self.device_error_dialog = ConversionErrorDialog(self, 'Error communicating with device', ' ')
        self.device_error_dialog.setModal(Qt.NonModal)
        self.tb_wrapper = textwrap.TextWrapper(width=40)
        self.device_connected = False
        self.viewers = collections.deque()
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
        self.setStatusBar(self.status_bar)
        QObject.connect(self.job_manager, SIGNAL('job_added(int)'), self.status_bar.job_added)
        QObject.connect(self.job_manager, SIGNAL('job_done(int)'), self.status_bar.job_done)
        
        ####################### Setup Toolbar #####################
        sm = QMenu()
        sm.addAction(QIcon(':/images/reader.svg'), _('Send to main memory'))
        sm.addAction(QIcon(':/images/sd.svg'), _('Send to storage card'))
        self.sync_menu = sm # Needed
        md = QMenu()
        md.addAction(_('Edit metadata individually'))
        md.addAction(_('Edit metadata in bulk'))
        self.metadata_menu = md
        QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add_books)
        QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete_books)
        QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit_metadata)
        QObject.connect(md.actions()[0], SIGNAL('triggered(bool)'), self.edit_metadata)
        QObject.connect(md.actions()[1], SIGNAL('triggered(bool)'), self.edit_bulk_metadata)
        QObject.connect(self.action_sync, SIGNAL("triggered(bool)"), self.sync_to_main_memory)        
        QObject.connect(sm.actions()[0], SIGNAL('triggered(bool)'), self.sync_to_main_memory)
        QObject.connect(sm.actions()[1], SIGNAL('triggered(bool)'), self.sync_to_card)
        QObject.connect(self.action_save, SIGNAL("triggered(bool)"), self.save_to_disk)
        QObject.connect(self.action_view, SIGNAL("triggered(bool)"), self.view_book)
        self.action_sync.setMenu(sm)
        self.action_edit.setMenu(md)
        nm = QMenu()
        nm.addAction(QIcon(':/images/news/bbc.png'), 'BBC')
        nm.addAction(QIcon(':/images/news/economist.png'), 'Economist')
        nm.addAction(QIcon(':/images/news/newsweek.png'), 'Newsweek')
        nm.addAction(QIcon(':/images/book.svg'), 'New York Review of Books')
        nm.addAction(QIcon(':/images/news/nytimes.png'), 'New York Times')
        
        QObject.connect(nm.actions()[0], SIGNAL('triggered(bool)'), self.fetch_news_bbc)
        QObject.connect(nm.actions()[1], SIGNAL('triggered(bool)'), self.fetch_news_economist)
        QObject.connect(nm.actions()[2], SIGNAL('triggered(bool)'), self.fetch_news_newsweek)
        QObject.connect(nm.actions()[3], SIGNAL('triggered(bool)'), self.fetch_news_nyreview)
        QObject.connect(nm.actions()[4], SIGNAL('triggered(bool)'), self.fetch_news_nytimes)
        
        self.news_menu = nm
        self.action_news.setMenu(nm)
        cm = QMenu()
        cm.addAction(_('Convert individually'))
        cm.addAction(_('Bulk convert'))
        self.action_convert.setMenu(cm)
        QObject.connect(cm.actions()[0], SIGNAL('triggered(bool)'), self.convert_single)
        QObject.connect(cm.actions()[1], SIGNAL('triggered(bool)'), self.convert_bulk)
        QObject.connect(self.action_convert, SIGNAL('triggered(bool)'), self.convert_single)        
        self.convert_menu = cm
        self.tool_bar.widgetForAction(self.action_news).setPopupMode(QToolButton.InstantPopup)
        self.tool_bar.widgetForAction(self.action_edit).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_sync).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_convert).setPopupMode(QToolButton.MenuButtonPopup)
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
        
        self.show()
        self.stack.setCurrentIndex(0)
        self.library_view.migrate_database()
        self.library_view.sortByColumn(3, Qt.DescendingOrder)
        if not self.library_view.restore_column_widths():        
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
    def device_detected(self, device, connected):
        '''
        Called when a device is connected to the computer.
        '''
        if connected:    
            self.device_manager = DeviceManager(device)
            func = self.device_manager.info_func()
            self.job_manager.run_device_job(self.info_read, func)
            self.set_default_thumbnail(device.THUMBNAIL_HEIGHT)
            self.status_bar.showMessage('Device: '+device.__class__.__name__+' detected.', 3000)
            self.action_sync.setEnabled(True)
            self.device_connected = True
        else:
            self.device_connected = False
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
            if not view.restore_column_widths():            
                view.resizeColumnsToContents()
            view.resizeRowsToContents()
            view.resize_on_select = not view.isVisible()
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
        books = choose_files(self, 'add books dialog dir', 'Select books',
                             filters=[('Books', BOOK_EXTENSIONS)])
        if not books:
            return
        to_device = self.stack.currentIndex() != 0
        self._add_books(books, to_device)
        if to_device:
            self.status_bar.showMessage('Uploading books to device.', 2000)
        
    def _add_books(self, paths, to_device):
        on_card = False if self.stack.currentIndex() != 2 else True
        # Get format and metadata information
        formats, metadata, names, infos = [], [], [], []
        for book in paths:
            format = os.path.splitext(book)[1]
            format = format[1:] if format else None
            stream = open(book, 'rb')
            mi = get_metadata(stream, stream_type=format)
            if not mi.title:
                mi.title = os.path.splitext(os.path.basename(book))[0]
            formats.append(format)
            metadata.append(mi)
            names.append(os.path.basename(book))
            if not mi.authors:
                mi.authors = ['Unknown']
            infos.append({'title':mi.title, 'authors':', '.join(mi.authors), 
                          'cover':self.default_thumbnail, 'tags':[]})
        
        if not to_device:
            model = self.current_view().model()
            model.add_books(paths, formats, metadata)
            model.resort()
            model.research()
        else:
            self.upload_books(paths, names, infos, on_card=on_card)            
    
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
        self.upload_memory[id] = (metadata, on_card)
    
    def books_uploaded(self, id, description, result, exception, formatted_traceback):
        '''
        Called once books have been uploaded.
        '''
        metadata, on_card = self.upload_memory.pop(id)
        if exception:
            if isinstance(exception, FreeSpaceError):
                where = 'in main memory.' if 'memory' in str(exception) else 'on the storage card.'
                titles = '\n'.join(['<li>'+mi['title']+'</li>' for mi in metadata])
                d = error_dialog(self, 'No space on device',
                                 '<p>Cannot upload books to device there is no more free space available '+where+
                                 '</p>\n<ul>%s</ul>'%(titles,))
                d.exec_()                
            else:
                self.device_job_exception(id, description, exception, formatted_traceback)
            return
        
        self.device_manager.add_books_to_metadata(result, metadata, self.booklists())
        
        self.upload_booklists()
        
        view = self.card_view if on_card else self.memory_view    
        view.model().resort(reset=False)
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
            self.delete_memory[id] = (paths, view.model())
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
        
        if self.delete_memory.has_key(id):
            paths, model = self.delete_memory.pop(id)
            self.device_manager.remove_books_from_metadata(paths, self.booklists())
            model.paths_deleted(paths)
            self.upload_booklists()            
            
    ############################################################################
    
    ############################### Edit metadata ##############################
    def edit_metadata(self, checked):
        '''
        Edit metadata of selected books in library individually.
        '''
        rows = self.library_view.selectionModel().selectedRows()
        if len(rows) > 1:
            return self.edit_bulk_metadata(checked)
        if not rows or len(rows) == 0:
            d = error_dialog(self, 'Cannot edit metadata', 'No books selected')
            d.exec_()
            return
        changed = False
        for row in rows:
            if MetadataSingleDialog(self, row.row(), 
                                    self.library_view.model().db).changed:
                changed = True                        
        
        if changed:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()
            
    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self, 'Cannot edit metadata', 'No books selected')
            d.exec_()
            return
        if MetadataBulkDialog(self, rows, self.library_view.model().db).changed:
            self.library_view.model().resort(reset=False)
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
                aus = mi['authors'].split(',')
                aus2 = []
                for a in aus:
                    aus2.extend(a.split('&'))
                try:
                    set_metadata(f, MetaInformation(mi['title'], aus2), f.name.rpartition('.')[2])
                except:
                    print 'Error setting metadata in book:', mi['title']
                    traceback.print_exc()
                good.append(mi)
                gf.append(f)
                t = mi['title']
                if not t:
                    t = 'Unknown'
                a = mi['authors']
                if not a:
                    a = 'Unknown'
                prefix = sanitize_file_name(t+' - '+a)
                if isinstance(prefix, unicode):
                    prefix = prefix.encode('ascii', 'ignore')
                else:
                    prefix = prefix.decode('ascii', 'ignore').encode('ascii', 'ignore')
                names.append('%s_%d%s'%(prefix, id, os.path.splitext(f.name)[1]))
        self.upload_books(gf, names, good, on_card)
        self.status_bar.showMessage('Sending books to device.', 5000)
        if bad:
            bad = '\n'.join('<li>%s</li>'%(i,) for i in bad)
            d = warning_dialog(self, 'No suitable formats', 
                    'Could not upload the following books to the device, as no suitable formats were found:<br><ul>%s</ul>'%(bad,))
            d.exec_()
                
            
    ############################################################################
    
    ############################## Save to disk ################################
    def save_to_disk(self, checked):
        rows = self.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, 'Cannot save to disk', 'No books selected')
            d.exec_()
            return
        dir = choose_dir(self, 'save to disk dialog', 'Choose destination directory')
        if not dir:
            return
        if self.current_view() == self.library_view:
            self.current_view().model().save_to_disk(rows, dir)
        else:
            paths = self.current_view().model().paths(rows)
            self.job_manager.run_device_job(self.books_saved,
                                self.device_manager.save_books_func(), paths, dir)
        
    def books_saved(self, id, description, result, exception, formatted_traceback):
        if exception:
            self.device_job_exception(id, description, exception, formatted_traceback)            
            return
            
    ############################################################################
    
    ############################### Fetch news #################################
    
    def fetch_news(self, profile, pretty, username=None, password=None):
        pt = PersistentTemporaryFile(suffix='.lrf')
        pt.close()
        args = ['web2lrf', '-o', pt.name, profile]
        if username:
            args.extend(['--username', username])
        if password:
            args.extend(['--password', password])
        id = self.job_manager.run_conversion_job(self.news_fetched, web2lrf, args=args,
                                            job_description='Fetch news from '+pretty)
        self.conversion_jobs[id] = (pt, 'lrf')
        self.status_bar.showMessage('Fetching news from '+pretty, 2000)
        
    def news_fetched(self, id, description, result, exception, formatted_traceback, log):
        pt, fmt = self.conversion_jobs.pop(id)
        if exception:
            self.conversion_job_exception(id, description, exception, formatted_traceback, log)
            return
        to_device = self.device_connected and fmt in self.device_manager.device_class.FORMATS
        self._add_books([pt.name], to_device)
        if to_device:
            self.status_bar.showMessage('News fetched. Uploading to device.', 2000)
            self.persistent_files.append(pt)
    
    def fetch_news_bbc(self, checked):
        self.fetch_news('bbc', 'BBC')
    
    def fetch_news_newsweek(self, checked):
        self.fetch_news('newsweek', 'Newsweek')
        
    def fetch_news_economist(self, checked):
        self.fetch_news('economist', 'The Economist')
    
    def fetch_news_nyreview(self, checked):
        self.fetch_news('newyorkreview', 'New York Review of Books')
    
    def fetch_news_nytimes(self, checked):
        d = PasswordDialog(self, 'nytimes info dialog', 
                           '<p>Please enter your username and password for nytimes.com<br>If you do not have an account, you can <a href="http://www.nytimes.com/gst/regi.html">register</a> for free.<br>Without a registration, some articles will not be downloaded correctly. Click OK to proceed.')
        d.exec_()
        if d.result() == QDialog.Accepted:
            un, pw = d.username(), d.password()
            self.fetch_news('nytimes', 'New York Times', username=un, password=pw)
    
    ############################################################################
    
    ############################### Convert ####################################
    def convert_bulk(self, checked):
        d = error_dialog(self, 'Cannot convert', 'Not yet implemented.')            
        d.exec_()
    
    def convert_single(self, checked):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, 'Cannot convert', 'No books selected')            
            d.exec_()
        
        changed = False
        for row in [r.row() for r in rows]:
            d = LRFSingleDialog(self, self.library_view.model().db, row)
            if d.selected_format:
                d.exec_()
                if d.result() == QDialog.Accepted:
                    changed = True
                    cmdline = d.cmdline
                    data = self.library_view.model().db.format(row, d.selected_format)
                    pt = PersistentTemporaryFile('.'+d.selected_format.lower())
                    pt.write(data)
                    pt.close()
                    of = PersistentTemporaryFile('.lrf')
                    of.close()
                    cmdline.extend(['-o', of.name])
                    cmdline.append(pt.name)
                    
                    id = self.job_manager.run_conversion_job(self.book_converted, 
                                                        any2lrf, args=cmdline,
                                    job_description='Convert book:'+d.title())
                    
                    
                    self.conversion_jobs[id] = (d.cover_file, pt, of, d.output_format, d.id)
        if changed:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()
        
                    
    def book_converted(self, id, description, result, exception, formatted_traceback, log):
        of, fmt, book_id = self.conversion_jobs.pop(id)[2:]
        if exception:
            self.conversion_job_exception(id, description, exception, formatted_traceback, log)
            return
        data = open(of.name, 'rb')
        self.library_view.model().db.add_format(book_id, fmt, data, index_is_id=True)
        data.close()
        self.status_bar.showMessage(description + ' completed', 2000)
    
    #############################View book######################################
    
    def view_book(self, triggered):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, 'Cannot view', 'No book selected')            
            d.exec_()
            return
        
        row = rows[0].row()
        formats = self.library_view.model().db.formats(row)
        title   = self.library_view.model().db.title(row)
        id      = self.library_view.model().db.id(row) 
        if 'LRF' not in formats.upper():
            d = error_dialog(self, 'Cannot view', '%s is not available in LRF format. Please convert it first.'%(title,))            
            d.exec_()
            return
        
        data = cStringIO.StringIO(self.library_view.model().db.format(row, 'LRF'))
        parser = lrfviewerop()
        opts   = parser.parse_args(['lrfviewer'])[0]
        
        viewer = file_renderer(data, opts)
        viewer.libprs500_db_id = id
        viewer.show()
        viewer.render()
        self.viewers.append(viewer)
        QObject.connect(viewer, SIGNAL('viewer_closed(PyQt_PyObject)'), self.viewer_closed)
        
    def viewer_closed(self, viewer):
        self.viewers.remove(viewer)
    
    ############################################################################
    
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
                if not view.restore_column_widths():
                    view.resizeColumnsToContents()
                view.resize_on_select = False
        self.status_bar.reset_info()
        self.current_view().clearSelection()
        if location == 'library':
            if self.device_connected:
                self.action_sync.setEnabled(True)
            self.action_edit.setEnabled(True)
            self.action_convert.setEnabled(True)
            self.action_view.setEnabled(True)
        else:
            self.action_sync.setEnabled(False)
            self.action_edit.setEnabled(False)
            self.action_convert.setEnabled(False)
            self.action_view.setEnabled(False)
                
    def device_job_exception(self, id, description, exception, formatted_traceback):
        '''
        Handle exceptions in threaded device jobs.
        '''
        if 'Could not read 32 bytes on the control bus.' in str(exception):
            error_dialog(self, 'Error talking to device', 
                         'There was a temporary error talking to the device. Please unplug and reconnect the device and or reboot.').show()
            return
        print >>sys.stderr, 'Error in job:', description.encode('utf8')
        print >>sys.stderr, exception
        print >>sys.stderr, formatted_traceback.encode('utf8')
        if not self.device_error_dialog.isVisible():
            msg =  u'<p><b>%s</b>: '%(exception.__class__.__name__,) + unicode(str(exception), 'utf8', 'replace') + u'</p>'
            msg += u'<p>Failed to perform <b>job</b>: '+description
            msg += u'<p>Further device related error messages will not be shown while this message is visible.'
            msg += u'<p>Detailed <b>traceback</b>:<pre>'
            msg += formatted_traceback
            self.device_error_dialog.set_message(msg)
            self.device_error_dialog.show()
            
    def conversion_job_exception(self, id, description, exception, formatted_traceback, log):
        print >>sys.stderr, 'Error in job:', description.encode('utf8')
        print >>sys.stderr, log.encode('utf8')
        print >>sys.stderr, exception
        print >>sys.stderr, formatted_traceback.encode('utf8')
        msg =  u'<p><b>%s</b>: '%(exception.__class__.__name__,) + unicode(str(exception), 'utf8', 'replace') + u'</p>'
        msg += u'<p>Failed to perform <b>job</b>: '+description
        msg += u'<p>Detailed <b>traceback</b>:<pre>'
        msg += formatted_traceback + '</pre>'
        msg += '<p><b>Log:</b></p><pre>'
        msg += log
        ConversionErrorDialog(self, 'Conversion Error', msg, show=True)
        
    
    def read_settings(self):
        settings = QSettings()
        settings.beginGroup("Main Window")
        self.resize(settings.value("size", QVariant(QSize(800, 600))).toSize())
        settings.endGroup()
        self.database_path = settings.value("database path", 
                QVariant(os.path.join(os.path.expanduser('~'),'library1.db'))).toString()
    
    def write_settings(self):
        settings = QSettings()
        settings.beginGroup("Main Window")
        settings.setValue("size", QVariant(self.size()))
        settings.endGroup()
        settings.beginGroup('Book Views')
        self.library_view.write_settings()
        if self.device_connected:
            self.memory_view.write_settings()
        settings.endGroup()
    
    def closeEvent(self, e):
        msg = 'There are active jobs. Are you sure you want to quit?'
        if self.job_manager.has_device_jobs():
            msg = '<p>'+__appname__ + ' is communicating with the device!<br>'+\
                  'Quitting may cause corruption on the device.<br>'+\
                  'Are you sure you want to quit?'
        if self.job_manager.has_jobs():
            d = QMessageBox(QMessageBox.Warning, 'WARNING: Active jobs', msg,
                            QMessageBox.Yes|QMessageBox.No, self)
            d.setIconPixmap(QPixmap(':/images/dialog_warning.svg'))
            d.setDefaultButton(QMessageBox.No)
            if d.exec_() != QMessageBox.Yes:
                e.ignore()
                return
        self.write_settings()
        e.accept()
        
                
    

def main(args=sys.argv):
    from PyQt4.Qt import QApplication
    pid = os.fork() if islinux else -1
    if pid <= 0:
        app = QApplication(args)    
        QCoreApplication.setOrganizationName(ORG_NAME)
        QCoreApplication.setApplicationName(APP_UID)        
        initialize_file_icon_provider()
        try:
            main = Main()
        except DatabaseLocked:
            QMessageBox.critical(None, 'Cannot Start '+__appname__, 
            'Another program is using the database. Perhaps %s is already running?'%(__appname__,))
            return 1
        sys.excepthook = main.unhandled_exception    
        return app.exec_()
    return 0
    
        
if __name__ == '__main__':
    sys.exit(main())
