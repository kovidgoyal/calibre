__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, sys, textwrap, collections, traceback, time, re
from xml.parsers.expat import ExpatError
from functools import partial
from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, QUrl, QTimer
from PyQt4.QtGui import QPixmap, QColor, QPainter, QMenu, QIcon, QMessageBox, \
                        QToolButton, QDialog, QDesktopServices, QFileDialog
from PyQt4.QtSvg import QSvgRenderer

from calibre import __version__, __appname__, islinux, sanitize_file_name, \
                    iswindows, isosx, preferred_encoding
from calibre.ptempfile import PersistentTemporaryFile
from calibre.ebooks.metadata.meta import get_metadata
from calibre.devices.errors import FreeSpaceError
from calibre.devices.interface import Device
from calibre.utils.config import prefs, dynamic
from calibre.gui2 import APP_UID, warning_dialog, choose_files, error_dialog, \
                           initialize_file_icon_provider, question_dialog,\
                           pixmap_to_data, choose_dir, ORG_NAME, \
                           set_sidebar_directories, Dispatcher, \
                           SingleApplication, Application, available_height, \
                           max_available_height, config
from calibre.gui2.cover_flow import CoverFlow, DatabaseImages, pictureflowerror
from calibre.library.database import LibraryDatabase
from calibre.gui2.update import CheckForUpdates
from calibre.gui2.main_window import MainWindow, option_parser
from calibre.gui2.main_ui import Ui_MainWindow
from calibre.gui2.device import DeviceManager
from calibre.gui2.status import StatusBar
from calibre.gui2.jobs2 import JobManager
from calibre.gui2.news import NewsMenu
from calibre.gui2.dialogs.metadata_single import MetadataSingleDialog
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.gui2.dialogs.jobs import JobsDialog
from calibre.gui2.dialogs.conversion_error import ConversionErrorDialog
from calibre.gui2.tools import convert_single_ebook, convert_bulk_ebooks, set_conversion_defaults, fetch_news
from calibre.gui2.dialogs.config import ConfigDialog
from calibre.gui2.dialogs.search import SearchDialog
from calibre.gui2.dialogs.user_profiles import UserProfiles
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2.dialogs.book_info import BookInfo
from calibre.ebooks.metadata.meta import set_metadata
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.html import gui_main as html2oeb
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.library.database2 import LibraryDatabase2, CoverCache
from calibre.parallel import JobKilled
from calibre.utils.filenames import ascii_filename
from calibre.gui2.widgets import WarningDialog

class Main(MainWindow, Ui_MainWindow):

    def set_default_thumbnail(self, height):
        r = QSvgRenderer(':/images/book.svg')
        pixmap = QPixmap(height, height)
        pixmap.fill(QColor(255,255,255))
        p = QPainter(pixmap)
        r.render(p)
        p.end()
        self.default_thumbnail = (pixmap.width(), pixmap.height(), pixmap_to_data(pixmap))

    def __init__(self, single_instance, opts, parent=None):
        MainWindow.__init__(self, opts, parent)
        # Initialize fontconfig in a separate thread as this can be a lengthy
        # process if run for the first time on this machine
        self.fc = __import__('calibre.utils.fontconfig', fromlist=1)
        self.single_instance = single_instance
        if self.single_instance is not None:
            self.connect(self.single_instance, SIGNAL('message_received(PyQt_PyObject)'),
                         self.another_instance_wants_to_talk)

        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(__appname__)
        self.read_settings()
        self.job_manager = JobManager()
        self.jobs_dialog = JobsDialog(self, self.job_manager)
        self.upload_memory = {}
        self.delete_memory = {}
        self.conversion_jobs = {}
        self.persistent_files = []
        self.metadata_dialogs = []
        self.default_thumbnail = None
        self.device_error_dialog = ConversionErrorDialog(self, _('Error communicating with device'), ' ')
        self.device_error_dialog.setModal(Qt.NonModal)
        self.tb_wrapper = textwrap.TextWrapper(width=40)
        self.device_connected = False
        self.viewers = collections.deque()
        self.content_server = None
        
        ####################### Location View ########################
        QObject.connect(self.location_view, SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        QObject.connect(self.stack, SIGNAL('currentChanged(int)'),
                        self.location_view.location_changed)

        ####################### Vanity ########################
        self.vanity_template  = _('<p>For help visit <a href="http://%s.kovidgoyal.net/user_manual">%s.kovidgoyal.net</a><br>')%(__appname__, __appname__)
        self.vanity_template += _('<b>%s</b>: %s by <b>Kovid Goyal %%(version)s</b><br>%%(device)s</p>')%(__appname__, __version__)
        self.latest_version = ' '
        self.vanity.setText(self.vanity_template%dict(version=' ', device=' '))
        self.device_info = ' '
        self.update_checker = CheckForUpdates()
        QObject.connect(self.update_checker, SIGNAL('update_found(PyQt_PyObject)'),
                        self.update_found)
        self.update_checker.start()
        ####################### Status Bar #####################
        self.status_bar = StatusBar(self.jobs_dialog)
        self.setStatusBar(self.status_bar)
        QObject.connect(self.job_manager, SIGNAL('job_added(int)'), self.status_bar.job_added,
                        Qt.QueuedConnection)
        QObject.connect(self.job_manager, SIGNAL('job_done(int)'), self.status_bar.job_done,
                        Qt.QueuedConnection)
        QObject.connect(self.status_bar, SIGNAL('show_book_info()'), self.show_book_info)
        ####################### Setup Toolbar #####################
        sm = QMenu()
        sm.addAction(QIcon(':/images/reader.svg'), _('Send to main memory'))
        sm.addAction(QIcon(':/images/sd.svg'), _('Send to storage card'))
        sm.addAction(QIcon(':/images/reader.svg'), _('Send to main memory')+' '+_('and delete from library'))
        sm.addAction(QIcon(':/images/sd.svg'), _('Send to storage card')+' '+_('and delete from library'))
        sm.addSeparator()
        sm.addAction(_('Send to storage card by default'))
        sm.actions()[-1].setCheckable(True)
        def default_sync(checked):
            config.set('send_to_storage_card_by_default', bool(checked))
            QObject.disconnect(self.action_sync, SIGNAL("triggered(bool)"), self.sync_to_main_memory)
            QObject.disconnect(self.action_sync, SIGNAL("triggered(bool)"), self.sync_to_card)
            QObject.connect(self.action_sync, SIGNAL("triggered(bool)"), self.sync_to_card if checked else self.sync_to_main_memory)
        QObject.connect(sm.actions()[-1], SIGNAL('toggled(bool)'), default_sync)

        sm.actions()[-1].setChecked(config.get('send_to_storage_card_by_default'))
        default_sync(sm.actions()[-1].isChecked())    
        self.sync_menu = sm # Needed
        md = QMenu()
        md.addAction(_('Edit metadata individually'))
        md.addAction(_('Edit metadata in bulk'))
        self.metadata_menu = md
        self.add_menu = QMenu()
        self.add_menu.addAction(_('Add books from a single directory'))
        self.add_menu.addAction(_('Add books recursively (One book per directory, assumes every ebook file is the same book in a different format)'))
        self.add_menu.addAction(_('Add books recursively (Multiple books per directory, assumes every ebook file is a different book)'))
        self.action_add.setMenu(self.add_menu)
        QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add_books)
        QObject.connect(self.add_menu.actions()[0], SIGNAL("triggered(bool)"), self.add_books)
        QObject.connect(self.add_menu.actions()[1], SIGNAL("triggered(bool)"), self.add_recursive_single)
        QObject.connect(self.add_menu.actions()[2], SIGNAL("triggered(bool)"), self.add_recursive_multiple)
        QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete_books)
        QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit_metadata)
        QObject.connect(md.actions()[0], SIGNAL('triggered(bool)'), partial(self.edit_metadata, bulk=False))
        QObject.connect(md.actions()[1], SIGNAL('triggered(bool)'), self.edit_bulk_metadata)
        QObject.connect(sm.actions()[0], SIGNAL('triggered(bool)'), self.sync_to_main_memory)
        QObject.connect(sm.actions()[1], SIGNAL('triggered(bool)'), self.sync_to_card)
        QObject.connect(sm.actions()[2], SIGNAL('triggered(bool)'), partial(self.sync_to_main_memory, delete_from_library=True))
        QObject.connect(sm.actions()[3], SIGNAL('triggered(bool)'), partial(self.sync_to_card, delete_from_library=True))
        self.save_menu = QMenu()
        self.save_menu.addAction(_('Save to disk'))
        self.save_menu.addAction(_('Save to disk in a single directory'))
        self.save_menu.addAction(_('Save only %s format to disk')%config.get('save_to_disk_single_format').upper())
        
        self.view_menu = QMenu()
        self.view_menu.addAction(_('View'))
        self.view_menu.addAction(_('View specific format'))
        self.action_view.setMenu(self.view_menu)
        QObject.connect(self.action_save, SIGNAL("triggered(bool)"), self.save_to_disk)
        QObject.connect(self.save_menu.actions()[0], SIGNAL("triggered(bool)"), self.save_to_disk)
        QObject.connect(self.save_menu.actions()[1], SIGNAL("triggered(bool)"), self.save_to_single_dir)
        QObject.connect(self.save_menu.actions()[2], SIGNAL("triggered(bool)"), self.save_single_format_to_disk)
        QObject.connect(self.action_view, SIGNAL("triggered(bool)"), self.view_book)
        QObject.connect(self.view_menu.actions()[0], SIGNAL("triggered(bool)"), self.view_book)
        QObject.connect(self.view_menu.actions()[1], SIGNAL("triggered(bool)"), self.view_specific_format)
        self.action_sync.setMenu(sm)
        self.action_edit.setMenu(md)
        self.action_save.setMenu(self.save_menu)
        self.news_menu = NewsMenu(self.customize_feeds)
        self.action_news.setMenu(self.news_menu)
        QObject.connect(self.news_menu, SIGNAL('fetch_news(PyQt_PyObject)'), self.fetch_news)
        cm = QMenu()
        cm.addAction(_('Convert individually'))
        cm.addAction(_('Bulk convert'))
        cm.addSeparator()
        cm.addAction(_('Set defaults for conversion'))
        cm.addAction(_('Set defaults for conversion of comics'))
        self.action_convert.setMenu(cm)
        QObject.connect(cm.actions()[0], SIGNAL('triggered(bool)'), self.convert_single)
        QObject.connect(cm.actions()[1], SIGNAL('triggered(bool)'), self.convert_bulk)
        QObject.connect(cm.actions()[3], SIGNAL('triggered(bool)'), self.set_conversion_defaults)
        QObject.connect(cm.actions()[4], SIGNAL('triggered(bool)'), self.set_comic_conversion_defaults)
        QObject.connect(self.action_convert, SIGNAL('triggered(bool)'), self.convert_single)        
        self.convert_menu = cm
        self.tool_bar.widgetForAction(self.action_news).setPopupMode(QToolButton.InstantPopup)
        self.tool_bar.widgetForAction(self.action_edit).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_sync).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_convert).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_save).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_add).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_view).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.setContextMenuPolicy(Qt.PreventContextMenu)

        QObject.connect(self.config_button, SIGNAL('clicked(bool)'), self.do_config)
        QObject.connect(self.advanced_search_button, SIGNAL('clicked(bool)'), self.do_advanced_search)

        ####################### Library view ########################
        QObject.connect(self.library_view, SIGNAL('files_dropped(PyQt_PyObject)'),
                        self.files_dropped)
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
        try:
            db = LibraryDatabase2(self.library_path)
        except OSError, err:
            error_dialog(self, _('Bad database location'), unicode(err)).exec_()
            dir = unicode(QFileDialog.getExistingDirectory(self, 
                            _('Choose a location for your ebook library.'), os.path.expanduser('~')))
            if not dir:
                QCoreApplication.exit(1)
            else:
                self.library_path = dir
                db = LibraryDatabase2(self.library_path)
        self.library_view.set_database(db)
        if self.olddb is not None:
            from PyQt4.QtGui import QProgressDialog
            pd = QProgressDialog('', '', 0, 100, self)
            pd.setWindowModality(Qt.ApplicationModal)
            pd.setCancelButton(None)
            pd.setWindowTitle(_('Migrating database'))
            pd.show()
            number_of_books = db.migrate_old(self.olddb, pd)
            self.olddb.close()
            if number_of_books == 0:
                os.remove(self.olddb.dbpath)
            self.olddb = None
            prefs['library_path'] = self.library_path
        self.library_view.sortByColumn(*dynamic.get('sort_column', ('timestamp', Qt.DescendingOrder)))
        if not self.library_view.restore_column_widths():
            self.library_view.resizeColumnsToContents()
        self.library_view.resizeRowsToContents()
        self.search.setFocus(Qt.OtherFocusReason)
        self.cover_cache = CoverCache(self.library_path)
        self.cover_cache.start()
        self.library_view.model().cover_cache = self.cover_cache
        self.tags_view.setVisible(False)
        self.match_all.setVisible(False)
        self.match_any.setVisible(False)
        self.popularity.setVisible(False)
        self.tags_view.set_database(db, self.match_all, self.popularity)
        self.connect(self.tags_view, SIGNAL('tags_marked(PyQt_PyObject, PyQt_PyObject)'),
                     self.search.search_from_tags)
        self.connect(self.status_bar.tag_view_button, SIGNAL('toggled(bool)'), self.toggle_tags_view)
        self.connect(self.search, SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'),
                     self.tags_view.model().reinit)
        ########################### Cover Flow ################################
        self.cover_flow = None
        if CoverFlow is not None:
            self.cover_flow = CoverFlow(height=220 if available_height() > 950 else 170 if available_height() > 850 else 140)
            self.cover_flow.setVisible(False)
            self.library.layout().addWidget(self.cover_flow)
            self.connect(self.cover_flow, SIGNAL('currentChanged(int)'), self.sync_cf_to_listview)
            self.connect(self.cover_flow, SIGNAL('itemActivated(int)'), self.show_book_info)
            self.connect(self.status_bar.cover_flow_button, SIGNAL('toggled(bool)'), self.toggle_cover_flow)
            self.connect(self.cover_flow, SIGNAL('stop()'), self.status_bar.cover_flow_button.toggle)
            QObject.connect(self.library_view.selectionModel(), SIGNAL('currentRowChanged(QModelIndex, QModelIndex)'),
                        self.sync_cf_to_listview)
            self.db_images = DatabaseImages(self.library_view.model())
            self.cover_flow.setImages(self.db_images)
        else:
            self.status_bar.cover_flow_button.disable(pictureflowerror)


        self.setMaximumHeight(max_available_height())

        ####################### Setup device detection ########################
        self.device_manager = DeviceManager(Dispatcher(self.device_detected), self.job_manager)
        self.device_manager.start()
        
        self.news_menu.set_custom_feeds(self.library_view.model().db.get_feeds())
        
        if config['autolaunch_server']:
            from calibre.library.server import start_threaded_server
            from calibre.library import server_config
            self.content_server = start_threaded_server(db, server_config().parse())
            self.test_server_timer = QTimer.singleShot(10000, self.test_server)

    def test_server(self, *args):
        if self.content_server.exception is not None:
            error_dialog(self, _('Failed to start content server'), 
                         unicode(self.content_server.exception)).exec_()

    def toggle_cover_flow(self, show):
        if show:
            self.library_view.setCurrentIndex(self.library_view.currentIndex())
            self.cover_flow.setVisible(True)
            self.cover_flow.setFocus(Qt.OtherFocusReason)
            self.status_bar.book_info.book_data.setMaximumHeight(100)
            self.status_bar.setMaximumHeight(120)
            self.library_view.scrollTo(self.library_view.currentIndex())
        else:
            self.cover_flow.setVisible(False)
            self.status_bar.book_info.book_data.setMaximumHeight(1000)
        self.setMaximumHeight(available_height())

    def toggle_tags_view(self, show):
        if show:
            self.tags_view.setVisible(True)
            self.match_all.setVisible(True)
            self.match_any.setVisible(True)
            self.popularity.setVisible(True)
            self.tags_view.setFocus(Qt.OtherFocusReason)
        else:
            self.tags_view.setVisible(False)
            self.match_all.setVisible(False)
            self.match_any.setVisible(False)
            self.popularity.setVisible(False)

    def sync_cf_to_listview(self, index, *args):
        if not hasattr(index, 'row') and self.library_view.currentIndex().row() != index:
            index = self.library_view.model().index(index, 0)
            self.library_view.setCurrentIndex(index)
        if hasattr(index, 'row') and self.cover_flow.isVisible() and self.cover_flow.currentSlide() != index.row():
            self.cover_flow.setCurrentSlide(index.row())

    def another_instance_wants_to_talk(self, msg):
        if msg.startswith('launched:'):
            argv = eval(msg[len('launched:'):])
            if len(argv) > 1:
                path = os.path.abspath(argv[1])
                if os.access(path, os.R_OK):
                    self.add_filesystem_book(path)
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized|Qt.WindowActive)
            self.show()
            self.raise_()
            self.activateWindow()
        elif msg.startswith('refreshdb:'):
            self.library_view.model().resort()
            self.library_view.model().research()
        else:
            print msg


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
    def device_detected(self, connected):
        '''
        Called when a device is connected to the computer.
        '''
        if connected:
            self.device_manager.get_device_information(Dispatcher(self.info_read))
            self.set_default_thumbnail(self.device_manager.device.THUMBNAIL_HEIGHT)
            self.status_bar.showMessage(_('Device: ')+\
                self.device_manager.device.__class__.__name__+_(' detected.'), 3000)
            self.action_sync.setEnabled(True)
            self.device_connected = True
        else:
            self.device_connected = False
            self.location_view.model().update_devices()
            self.action_sync.setEnabled(False)
            self.vanity.setText(self.vanity_template%dict(version=self.latest_version, device=' '))
            self.device_info = ' '
            if self.current_view() != self.library_view:
                self.status_bar.reset_info()
                self.location_selected('library')
            
    def info_read(self, job):
        '''
        Called once device information has been read.
        '''
        if job.exception is not None:
            self.device_job_exception(job)
            return
        info, cp, fs = job.result
        self.location_view.model().update_devices(cp, fs)
        self.device_info = _('Connected ')+' '.join(info[:-1])
        self.vanity.setText(self.vanity_template%dict(version=self.latest_version, device=self.device_info))

        self.device_manager.books(Dispatcher(self.metadata_downloaded))
        
    def metadata_downloaded(self, job):
        '''
        Called once metadata has been read for all books on the device.
        '''
        if job.exception is not None:
            if isinstance(job.exception, ExpatError):
                error_dialog(self, _('Device database corrupted'),
                _('''
                <p>The database of books on the reader is corrupted. Try the following:
                <ol>
                <li>Unplug the reader. Wait for it to finish regenerating the database (i.e. wait till it is ready to be used). Plug it back in. Now it should work with %(app)s. If not try the next step.</li>
                <li>Quit %(app)s. Find the file media.xml in the reader's main memory. Delete it. Unplug the reader. Wait for it to regenerate the file. Re-connect it and start %(app)s.</li>
                </ol>
                ''')%dict(app=__appname__)).exec_()
            else:
                self.device_job_exception(job)
            return
        mainlist, cardlist = job.result
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
        self.device_manager.sync_booklists(Dispatcher(self.metadata_synced),
                                           self.booklists())
    
    def metadata_synced(self, job):
        '''
        Called once metadata has been uploaded.
        '''
        if job.exception is not None:
            self.device_job_exception(job)
            return
        cp, fs = job.result
        self.location_view.model().update_devices(cp, fs)
    ############################################################################


    ################################# Add books ################################

    def add_recursive(self, single):
        root = choose_dir(self, 'recursive book import root dir dialog', 'Select root folder')
        if not root:
            return
        duplicates = self.library_view.model().db.recursive_import(root, single)

        if duplicates:
            files = _('<p>Books with the same title as the following already exist in the database. Add them anyway?<ul>')
            for mi, formats in duplicates:
                files += '<li>'+mi.title+'</li>\n'
            d = WarningDialog(_('Duplicates found!'), _('Duplicates found!'), files+'</ul></p>', self)
            if d.exec_() == QDialog.Accepted:
                for mi, formats in duplicates:
                    self.library_view.model().db.import_book(mi, formats )

        self.library_view.model().resort()
        self.library_view.model().research()

    def add_recursive_single(self, checked):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming one book per folder.
        '''
        self.add_recursive(True)

    def add_recursive_multiple(self, checked):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming multiple books per folder.
        '''
        self.add_recursive(False)

    def files_dropped(self, paths):
        to_device = self.stack.currentIndex() != 0
        self._add_books(paths, to_device)


    def add_filesystem_book(self, path):
        if os.access(path, os.R_OK):
            books = [os.path.abspath(path)]
            to_device = self.stack.currentIndex() != 0
            self._add_books(books, to_device)
            if to_device:
                self.status_bar.showMessage(_('Uploading books to device.'), 2000)

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
            self.status_bar.showMessage(_('Uploading books to device.'), 2000)

    def _add_books(self, paths, to_device, on_card=None):
        if on_card is None:
            on_card = self.stack.currentIndex() == 2
        # Get format and metadata information
        formats, metadata, names, infos = [], [], [], []
        for book in paths:
            format = os.path.splitext(book)[1]
            format = format[1:] if format else None
            stream = open(book, 'rb')
            try:
                mi = get_metadata(stream, stream_type=format, use_libprs_metadata=True)
            except:
                mi = MetaInformation(None, None)
            if not mi.title:
                mi.title = os.path.splitext(os.path.basename(book))[0]
            if not mi.authors:
                mi.authors = [_('Unknown')]
            formats.append(format)
            metadata.append(mi)
            names.append(os.path.basename(book))
            infos.append({'title':mi.title, 'authors':', '.join(mi.authors),
                          'cover':self.default_thumbnail, 'tags':[]})

        if not to_device:
            model = self.library_view.model()
            html_pat = re.compile(r'\.x{0,1}htm(l{0,1})\s*$', re.IGNORECASE)
            paths = list(paths)
            for i, path in enumerate(paths):
                if html_pat.search(path) is not None:
                    try:
                        paths[i] = html2oeb(path)
                    except:
                        traceback.print_exc()
                        continue
                    if paths[i] is None:
                        paths[i] = path
                    else: 
                        formats[i] = 'zip'
            duplicates, number_added = model.add_books(paths, formats, metadata)
            if duplicates:
                files = _('<p>Books with the same title as the following already exist in the database. Add them anyway?<ul>')
                for mi in duplicates[2]:
                    files += '<li>'+mi.title+'</li>\n'
                d = WarningDialog(_('Duplicates found!'), _('Duplicates found!'), files+'</ul></p>', parent=self)
                if d.exec_() == QDialog.Accepted:
                    num = model.add_books(*duplicates, **dict(add_duplicates=True))[1]
                    number_added += num
            #self.library_view.sortByColumn(3, Qt.DescendingOrder)
            #model.research()
            model.books_added(number_added)
        else:
            self.upload_books(paths, list(map(sanitize_file_name, names)), infos, on_card=on_card)

    def upload_books(self, files, names, metadata, on_card=False, memory=None):
        '''
        Upload books to device.
        :param files: List of either paths to files or file like objects
        '''
        titles = [i['title'] for i in metadata]
        job = self.device_manager.upload_books(Dispatcher(self.books_uploaded),
                                        files, names, on_card=on_card,
                                        titles=titles
                                        )
        self.upload_memory[job] = (metadata, on_card, memory)
    
    def books_uploaded(self, job):
        '''
        Called once books have been uploaded.
        '''
        metadata, on_card, memory = self.upload_memory.pop(job)
        
        if job.exception is not None:
            if isinstance(job.exception, FreeSpaceError):
                where = 'in main memory.' if 'memory' in str(job.exception) else 'on the storage card.'
                titles = '\n'.join(['<li>'+mi['title']+'</li>' for mi in metadata])
                d = error_dialog(self, _('No space on device'),
                                 _('<p>Cannot upload books to device there is no more free space available ')+where+
                                 '</p>\n<ul>%s</ul>'%(titles,))
                d.exec_()
            else:
                self.device_job_exception(job)
            return
        
        self.device_manager.add_books_to_metadata(job.result, metadata, self.booklists())
        
        self.upload_booklists()

        view = self.card_view if on_card else self.memory_view
        view.model().resort(reset=False)
        view.model().research()
        if memory and memory[1]:
            rows = map(self.library_view.model().db.index, memory[1])
            self.library_view.model().delete_books(rows)


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
        if config['confirm_delete']:
            d = question_dialog(self, _('Confirm delete'), 
                            _('Are you sure you want to delete these %d books?')%len(rows))
            if d.exec_() != QMessageBox.Yes:
                return
            
        if self.stack.currentIndex() == 0:
            view.model().delete_books(rows)
        else:
            view = self.memory_view if self.stack.currentIndex() == 1 else self.card_view
            paths = view.model().paths(rows)
            job = self.remove_paths(paths)
            self.delete_memory[job] = (paths, view.model())
            view.model().mark_for_deletion(job, rows)
            self.status_bar.showMessage(_('Deleting books from device.'), 1000)

    def remove_paths(self, paths):
        return self.device_manager.delete_books(Dispatcher(self.books_deleted), paths)
            
    def books_deleted(self, job):
        '''
        Called once deletion is done on the device
        '''
        for view in (self.memory_view, self.card_view):
            view.model().deletion_done(job, bool(job.exception))
        if job.exception is not None:
            self.device_job_exception(job)            
            return
        
        if self.delete_memory.has_key(job):
            paths, model = self.delete_memory.pop(job)
            self.device_manager.remove_books_from_metadata(paths, self.booklists())
            model.paths_deleted(paths)
            self.upload_booklists()

    ############################################################################

    ############################### Edit metadata ##############################
    def edit_metadata(self, checked, bulk=None):
        '''
        Edit metadata of selected books in library.
        '''
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot edit metadata'), _('No books selected'))
            d.exec_()
            return

        if bulk or (bulk is None and len(rows) > 1):
            return self.edit_bulk_metadata(checked)

        for row in rows:
            d = MetadataSingleDialog(self, row.row(),
                                    self.library_view.model().db)

    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot edit metadata'), _('No books selected'))
            d.exec_()
            return
        if MetadataBulkDialog(self, rows, self.library_view.model().db).changed:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()

    ############################################################################

    ############################# Syncing to device#############################
    def sync_to_main_memory(self, checked, delete_from_library=False):
        self.sync_to_device(False, delete_from_library)

    def sync_to_card(self, checked, delete_from_library=False):
        self.sync_to_device(True, delete_from_library)

    def cover_to_thumbnail(self, data):
        p = QPixmap()
        p.loadFromData(data)
        if not p.isNull():
            ht = self.device_manager.device_class.THUMBNAIL_HEIGHT if self.device_manager else \
                       Device.THUMBNAIL_HEIGHT
            p = p.scaledToHeight(ht, Qt.SmoothTransformation)
            return (p.width(), p.height(), pixmap_to_data(p))

    def sync_to_device(self, on_card, delete_from_library):
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
        _files = self.library_view.model().get_preferred_formats(rows,
                                    self.device_manager.device_class.FORMATS, paths=True)
        files = [getattr(f, 'name', None) for f in _files]
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
                    smi = MetaInformation(mi['title'], aus2)
                    smi.comments = mi.get('comments', None)
                    _f = open(f, 'r+b')
                    set_metadata(_f, smi, f.rpartition('.')[2])
                    _f.close()
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
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id, os.path.splitext(f)[1]))
        remove = [self.library_view.model().id(r) for r in rows] if delete_from_library else []
        self.upload_books(gf, names, good, on_card, memory=(_files, remove))
        self.status_bar.showMessage(_('Sending books to device.'), 5000)
        if bad:
            bad = '\n'.join('<li>%s</li>'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                    _('Could not upload the following books to the device, as no suitable formats were found:<br><ul>%s</ul>')%(bad,))
            d.exec_()


    ############################################################################

    ############################## Save to disk ################################
    def save_single_format_to_disk(self, checked):
        self.save_to_disk(checked, True, config['save_to_disk_single_format'])
    
    def save_to_single_dir(self, checked):
        self.save_to_disk(checked, True)

    def save_to_disk(self, checked, single_dir=False, single_format=None):
        rows = self.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot save to disk'), _('No books selected'))
            d.exec_()
            return

        dir = choose_dir(self, 'save to disk dialog', ('Choose destination directory'))
        if not dir:
            return
        if self.current_view() == self.library_view:
            failures = self.current_view().model().save_to_disk(rows, dir,
                                    single_dir=single_dir, single_format=single_format)
            if failures and single_format is not None:
                msg = _('<p>Could not save the following books to disk, because the %s format is not available for them:<ul>')%single_format.upper()
                for f in failures:
                    msg += '<li>%s</li>'%f[1]
                msg += '</ul>'
                warning_dialog(self, _('Could not save some ebooks'), msg).exec_()
            QDesktopServices.openUrl(QUrl('file:'+dir))
        else:
            paths = self.current_view().model().paths(rows)
            self.device_manager.save_books(Dispatcher(self.books_saved), paths, dir)
            
    def books_saved(self, job):
        if job.exception is not None:
            self.device_job_exception(job)            
            return

    ############################################################################

    ############################### Fetch news #################################

    def customize_feeds(self, *args):
        d = UserProfiles(self, self.library_view.model().db.get_feeds())
        if d.exec_() == QDialog.Accepted:
            feeds = tuple(d.profiles())
            self.library_view.model().db.set_feeds(feeds)
            self.news_menu.set_custom_feeds(feeds)

    def fetch_news(self, data):
        func, args, desc, fmt, temp_files = fetch_news(data)
        self.status_bar.showMessage(_('Fetching news from ')+data['title'], 2000)
        job = self.job_manager.run_job(Dispatcher(self.news_fetched), func, args=args,
                                            description=desc)
        self.conversion_jobs[job] = (temp_files, fmt)
        self.status_bar.showMessage(_('Fetching news from ')+data['title'], 2000)
        
    def news_fetched(self, job):
        temp_files, fmt = self.conversion_jobs.pop(job)
        pt = temp_files[0]
        if job.exception is not None:
            self.job_exception(job)
            return
        to_device = self.device_connected and fmt.lower() in self.device_manager.device_class.FORMATS
        self._add_books([pt.name], to_device, 
            on_card=config.get('send_to_storage_card_by_default') and self.device_connected and bool(self.device_manager.device.card_prefix()))
        if to_device:
            self.status_bar.showMessage(_('News fetched. Uploading to device.'), 2000)
            self.persistent_files.append(pt)
        try:
            if not to_device:
                for f in temp_files:
                    if os.path.exists(f.name):
                        os.remove(f.name)
        except:
            pass

    ############################################################################

    ############################### Convert ####################################
    
    def get_books_for_conversion(self):
        rows = [r.row() for r in self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot convert'), _('No books selected'))
            d.exec_()
            return [], []
        comics, others = [], []
        db = self.library_view.model().db
        for r in rows:
            formats = db.formats(r)
            if not formats: continue
            formats = formats.lower().split(',')
            if 'cbr' in formats or 'cbz' in formats:
                comics.append(r)
            else:
                others.append(r)
        return comics, others
    
        
    def convert_bulk(self, checked):
        r = self.get_books_for_conversion()
        if r is None:
            return
        comics, others = r 
        
        jobs, changed  = convert_bulk_ebooks(self, self.library_view.model().db, comics, others) 
        for func, args, desc, fmt, id, temp_files in jobs:
            job = self.job_manager.run_job(Dispatcher(self.book_converted), 
                                            func, args=args, description=desc)
            self.conversion_jobs[job] = (temp_files, fmt, id)
            
        if changed:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()
            
    def set_conversion_defaults(self, checked):
        set_conversion_defaults(False, self, self.library_view.model().db)
        
    def set_comic_conversion_defaults(self, checked):
        set_conversion_defaults(True, self, self.library_view.model().db)
    
    def convert_single(self, checked):
        r = self.get_books_for_conversion()
        if r is None: return
        comics, others = r
        jobs, changed = convert_single_ebook(self, self.library_view.model().db, comics, others)
        for func, args, desc, fmt, id, temp_files in jobs:
            job = self.job_manager.run_job(Dispatcher(self.book_converted), 
                                            func, args=args, description=desc)
            self.conversion_jobs[job] = (temp_files, fmt, id)
            
        if changed:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()
                    
    def book_converted(self, job):
        temp_files, fmt, book_id = self.conversion_jobs.pop(job)
        try:
            if job.exception is not None:
                self.job_exception(job)
                return
            data = open(temp_files[-1].name, 'rb')
            self.library_view.model().db.add_format(book_id, fmt, data, index_is_id=True)
            data.close()
            self.status_bar.showMessage(job.description + (' completed'), 2000)
        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f.name):
                        os.remove(f.name)
                except:
                    pass
    
    #############################View book######################################

    def view_format(self, row, format):
        self._view_file(self.library_view.model().db.format(row, format, as_file=True).name)
        
    def book_downloaded_for_viewing(self, job):
        if job.exception:
            self.device_job_exception(job)            
            return
        self._view_file(job.result)
    
    def _view_file(self, name):
        self.setCursor(Qt.BusyCursor)
        try:
            ext = os.path.splitext(name)[1].upper().replace('.', '')
            if ext in config['internally_viewed_formats']:
                if ext == 'LRF':
                    args = ['lrfviewer', name]
                    self.job_manager.server.run_free_job('lrfviewer', kwdargs=dict(args=args))
                else:
                    args = ['ebook-viewer', name]
                    self.job_manager.server.run_free_job('ebook-viewer', kwdargs=dict(args=args))
            else:
                QDesktopServices.openUrl(QUrl('file:'+name))#launch(name)
            time.sleep(5) # User feedback
        finally:
            self.unsetCursor()

    def view_specific_format(self, triggered):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot view'), _('No book selected'))
            d.exec_()
            return

        row = rows[0].row()
        formats = self.library_view.model().db.formats(row).upper().split(',')
        d = ChooseFormatDialog(self, _('Choose the format to view'), formats)
        d.exec_()
        if d.result() == QDialog.Accepted:
            format = d.format()
            self.view_format(row, format)
        else:
            return

    def view_book(self, triggered):
        rows = self.current_view().selectionModel().selectedRows()
        if self.current_view() is self.library_view:
            if not rows or len(rows) == 0:
                d = error_dialog(self, _('Cannot view'), _('No book selected'))
                d.exec_()
                return

            row = rows[0].row()
            formats = self.library_view.model().db.formats(row).upper().split(',')
            title   = self.library_view.model().db.title(row)
            id      = self.library_view.model().db.id(row)
            format = None
            if len(formats) == 1:
                format = formats[0]
            if 'LRF' in formats:
                format = 'LRF'
            if 'EPUB' in formats:
                format = 'EPUB'
            if not formats:
                d = error_dialog(self, _('Cannot view'),
                        _('%s has no available formats.')%(title,))
                d.exec_()
                return
            if format is None:
                d = ChooseFormatDialog(self, _('Choose the format to view'), formats)
                d.exec_()
                if d.result() == QDialog.Accepted:
                    format = d.format()
                else:
                    return

            self.view_format(row, format)
        else:
            paths = self.current_view().model().paths(rows)
            if paths:
                pt = PersistentTemporaryFile('_viewer_'+os.path.splitext(paths[0])[1])
                self.persistent_files.append(pt)
                pt.close()
                self.device_manager.view_book(Dispatcher(self.book_downloaded_for_viewing),
                                              paths[0], pt.name)
                
        
    
    ############################################################################

    ########################### Do advanced search #############################

    def do_advanced_search(self, *args):
        d = SearchDialog(self)
        if d.exec_() == QDialog.Accepted:
            self.search.set_search_string(d.search_string())

    ############################################################################

    ############################### Do config ##################################

    def do_config(self):
        if self.job_manager.has_jobs():
            d = error_dialog(self, _('Cannot configure'), _('Cannot configure while there are running jobs.'))
            d.exec_()
            return
        d = ConfigDialog(self, self.library_view.model().db, server=self.content_server)
        d.exec_()
        self.content_server = d.server
        if d.result() == d.Accepted:
            self.tool_bar.setIconSize(config['toolbar_icon_size'])
            self.tool_bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if config['show_text_in_toolbar'] else Qt.ToolButtonIconOnly)
            self.save_menu.actions()[2].setText(_('Save only %s format to disk')%config.get('save_to_disk_single_format').upper())
            if self.library_path != d.database_location:
                try:
                    newloc = d.database_location
                    if not os.path.exists(os.path.join(newloc, 'metadata.db')):
                        if os.access(self.library_path, os.R_OK):
                            from PyQt4.QtGui import QProgressDialog
                            pd = QProgressDialog('', '', 0, 100, self)
                            pd.setWindowModality(Qt.ApplicationModal)
                            pd.setCancelButton(None)
                            pd.setWindowTitle(_('Copying database'))
                            pd.show()
                            self.status_bar.showMessage(_('Copying library to ')+newloc)
                            self.setCursor(Qt.BusyCursor)
                            self.library_view.setEnabled(False)
                            self.library_view.model().db.move_library_to(newloc, pd)
                    else:
                        try:
                            db = LibraryDatabase2(newloc)
                            self.library_view.set_database(db)
                        except Exception, err:
                            traceback.print_exc()
                            d = error_dialog(self, _('Invalid database'),
                                             _('<p>An invalid database already exists at %s, delete it before trying to move the existing database.<br>Error: %s')%(newloc, str(err)))
                            d.exec_()
                    self.library_path = self.library_view.model().db.library_path
                    prefs['library_path'] =  self.library_path
                except Exception, err:
                    traceback.print_exc()
                    d = error_dialog(self, _('Could not move database'), unicode(err))
                    d.exec_()
                finally:
                    self.unsetCursor()
                    self.library_view.setEnabled(True)
                    self.status_bar.clearMessage()
                    self.search.clear_to_help()
                    self.status_bar.reset_info()
                    self.library_view.sortByColumn(3, Qt.DescendingOrder)
                    self.library_view.resizeRowsToContents()
            if hasattr(d, 'directories'):
                set_sidebar_directories(d.directories)
            self.library_view.model().read_config()
            self.library_view.columns_sorted()

    ############################################################################

    ################################ Book info #################################

    def show_book_info(self, *args):
        if self.current_view() is not self.library_view:
            error_dialog(self, _('No detailed info available'),
                         _('No detailed information is available for books on the device.')).exec_()
            return
        index = self.library_view.currentIndex()
        if index.isValid():
            BookInfo(self, self.library_view, index).show()

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
            self.view_menu.actions()[1].setEnabled(True)
        else:
            self.action_sync.setEnabled(False)
            self.action_edit.setEnabled(False)
            self.action_convert.setEnabled(False)
            self.view_menu.actions()[1].setEnabled(False)
                
    def device_job_exception(self, job):
        '''
        Handle exceptions in threaded device jobs.
        '''
        if 'Could not read 32 bytes on the control bus.' in str(job.exception):
            error_dialog(self, _('Error talking to device'), 
                         _('There was a temporary error talking to the device. Please unplug and reconnect the device and or reboot.')).show()
            return
        try:
            print >>sys.stderr, job.console_text()
        except:
            pass
        if not self.device_error_dialog.isVisible():
            self.device_error_dialog.set_message(job.gui_text())
            self.device_error_dialog.show()
            
    def job_exception(self, job):
        try:
            if job.exception[0] == 'DRMError':
                error_dialog(self, _('Conversion Error'), 
                    _('<p>Could not convert: %s<p>It is a <a href="%s">DRM</a>ed book. You must first remove the DRM using 3rd party tools.')%(job.description.split(':')[-1], 'http://wiki.mobileread.com/wiki/DRM')).exec_()
                return
        except:
            pass
        only_msg = getattr(job.exception, 'only_msg', False)
        try:
            print job.console_text()
        except:
            pass
        if only_msg:
            try:
                exc = unicode(job.exception)
            except:
                exc = repr(job.exception)
            error_dialog(self, _('Conversion Error'), exc).exec_()
            return
        if isinstance(job.exception, JobKilled):
            return
        ConversionErrorDialog(self, _('Conversion Error'), job.gui_text(),
                              show=True)


    def initialize_database(self):
        self.library_path = prefs['library_path']
        self.olddb = None
        if self.library_path is None: # Need to migrate to new database layout
            QMessageBox.information(self, 'Database format changed',
                '''\
<p>calibre's book storage format has changed. Instead of storing book files in a database, the
files are now stored in a folder on your filesystem. You will now be asked to choose the folder 
in which you want to store your books files. Any existing books will be automatically migrated.
                ''')
            self.database_path = prefs['database_path']
            if not os.access(os.path.dirname(self.database_path), os.W_OK):
                error_dialog(self, _('Database does not exist'), 
                             _('The directory in which the database should be: %s no longer exists. Please choose a new database location.')%self.database_path).exec_()
                self.database_path = choose_dir(self, 'database path dialog', 
                                                _('Choose new location for database'))
                if not self.database_path:
                    self.database_path = os.path.expanduser('~').decode(sys.getfilesystemencoding())
                if not os.path.exists(self.database_path):
                    os.makedirs(self.database_path)
                self.database_path = os.path.join(self.database_path, 'library1.db')
                prefs['database_path'] = self.database_path
            home = os.path.dirname(self.database_path)
            if not os.path.exists(home):
                home = os.getcwd()
            dir = unicode(QFileDialog.getExistingDirectory(self, 
                            _('Choose a location for your ebook library.'), home))
            if not dir:
                dir = os.path.dirname(self.database_path)
            self.library_path = os.path.abspath(dir)
            try:
                self.olddb = LibraryDatabase(self.database_path)
            except:
                traceback.print_exc()
                self.olddb = None


    def read_settings(self):
        self.initialize_database()
        geometry = config['main_window_geometry']
        if geometry is not None:
            self.restoreGeometry(geometry)
        set_sidebar_directories(None)
        self.tool_bar.setIconSize(config['toolbar_icon_size'])
        self.tool_bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if config['show_text_in_toolbar'] else Qt.ToolButtonIconOnly)
        
    
    def write_settings(self):
        config.set('main_window_geometry', self.saveGeometry())
        dynamic.set('sort_column', self.library_view.model().sorted_on)
        self.library_view.write_settings()
        if self.device_connected:
            self.memory_view.write_settings()

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

        self.job_manager.terminate_all_jobs()
        self.write_settings()
        self.device_manager.keep_going = False
        self.cover_cache.stop()
        self.hide()
        self.cover_cache.terminate()
        try:
            try:
                if self.content_server is not None:
                    self.content_server.exit()
            except:
                pass
            time.sleep(2)
        except KeyboardInterrupt:
            pass
        e.accept()

    def update_found(self, version):
        os = 'windows' if iswindows else 'osx' if isosx else 'linux'
        url = 'http://%s.kovidgoyal.net/download_%s'%(__appname__, os)
        self.latest_version = _('<span style="color:red; font-weight:bold">Latest version: <a href="%s">%s</a></span>')%(url, version)
        self.vanity.setText(self.vanity_template%(dict(version=self.latest_version,
                                                    device=self.device_info)))
        self.vanity.update()
        if config.get('new_version_notification') and dynamic.get('update to version %s'%version, True):
            d = question_dialog(self, _('Update available'), _('%s has been updated to version %s. See the <a href="http://calibre.kovidgoyal.net/wiki/Changelog">new features</a>. Visit the download page?')%(__appname__, version))
            if d.exec_() == QMessageBox.Yes:
                url = 'http://calibre.kovidgoyal.net/download_'+('windows' if iswindows else 'osx' if isosx else 'linux')
                QDesktopServices.openUrl(QUrl(url))
            dynamic.set('update to version %s'%version, False)
        

def main(args=sys.argv):
    from calibre.utils.lock import singleinstance
    
    pid = os.fork() if False and islinux else -1
    if pid <= 0:
        parser = option_parser('''\
%prog [opts] [path_to_ebook]

Launch the main calibre Graphical User Interface and optionally add the ebook at
path_to_ebook to the database.
''')
        parser.add_option('--with-library', default=None, action='store', 
                          help=_('Use the library located at the specified path.'))
        opts, args = parser.parse_args(args)
        if opts.with_library is not None and os.path.isdir(opts.with_library):
            prefs.set('library_path', opts.with_library)
            print 'Using library at', prefs['library_path']
        app = Application(args)
        app.setWindowIcon(QIcon(':/library'))
        QCoreApplication.setOrganizationName(ORG_NAME)
        QCoreApplication.setApplicationName(APP_UID)
        single_instance = None if SingleApplication is None else SingleApplication('calibre GUI')
        if not singleinstance('calibre GUI'):
            if single_instance is not None and single_instance.is_running() and \
               single_instance.send_message('launched:'+repr(args)):
                    return 0
            extra = '' if iswindows else \
            	('If you\'re sure it is not running, delete the file %s.'%os.path.expanduser('~/.calibre_calibre GUI.lock'))
            QMessageBox.critical(None, 'Cannot Start '+__appname__,
                                 '<p>%s is already running. %s</p>'%(__appname__, extra))
            return 1
        initialize_file_icon_provider()
        main = Main(single_instance, opts)
        sys.excepthook = main.unhandled_exception
        if len(args) > 1:
            main.add_filesystem_book(args[1])
        return app.exec_()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception, err:
        if not iswindows: raise
        tb = traceback.format_exc()
        from PyQt4.QtGui import QErrorMessage
        logfile = os.path.join(os.path.expanduser('~'), 'calibre.log')
        if os.path.exists(logfile):
            log = open(logfile).read().decode('utf-8', 'ignore')
            d = QErrorMessage('<b>Error:</b>%s<br><b>Traceback:</b><br>%s<b>Log:</b><br>'%(unicode(err), unicode(tb), log))
            d.exec_()
