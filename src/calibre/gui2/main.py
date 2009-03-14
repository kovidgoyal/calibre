from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, sys, textwrap, collections, traceback, time
from xml.parsers.expat import ExpatError
from functools import partial
from PyQt4.Qt import Qt, SIGNAL, QObject, QCoreApplication, QUrl, QTimer, \
                     QModelIndex, QPixmap, QColor, QPainter, QMenu, QIcon, \
                     QToolButton, QDialog, QDesktopServices, QFileDialog, \
                     QSystemTrayIcon, QApplication, QKeySequence, QAction, \
                     QProgressDialog, QMessageBox, QStackedLayout
from PyQt4.QtSvg import QSvgRenderer

from calibre import __version__, __appname__, islinux, sanitize_file_name, \
                    iswindows, isosx, preferred_encoding
from calibre.ptempfile import PersistentTemporaryFile
from calibre.devices.errors import FreeSpaceError
from calibre.devices.interface import Device
from calibre.utils.config import prefs, dynamic
from calibre.gui2 import APP_UID, warning_dialog, choose_files, error_dialog, \
                           initialize_file_icon_provider, question_dialog,\
                           pixmap_to_data, choose_dir, ORG_NAME, \
                           set_sidebar_directories, Dispatcher, \
                           SingleApplication, Application, available_height, \
                           max_available_height, config, info_dialog, \
                           available_width, GetMetadata
from calibre.gui2.cover_flow import CoverFlow, DatabaseImages, pictureflowerror
from calibre.gui2.dialogs.scheduler import Scheduler
from calibre.gui2.update import CheckForUpdates
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2.main_window import MainWindow, option_parser as _option_parser
from calibre.gui2.main_ui import Ui_MainWindow
from calibre.gui2.device import DeviceManager
from calibre.gui2.status import StatusBar
from calibre.gui2.jobs2 import JobManager
from calibre.gui2.dialogs.metadata_single import MetadataSingleDialog
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.gui2.dialogs.jobs import JobsDialog
from calibre.gui2.dialogs.conversion_error import ConversionErrorDialog
from calibre.gui2.tools import convert_single_ebook, convert_bulk_ebooks, \
                                set_conversion_defaults, fetch_scheduled_recipe
from calibre.gui2.dialogs.config import ConfigDialog
from calibre.gui2.dialogs.search import SearchDialog
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2.dialogs.book_info import BookInfo
from calibre.ebooks.metadata.meta import set_metadata
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.library.database2 import LibraryDatabase2, CoverCache
from calibre.parallel import JobKilled
from calibre.utils.filenames import ascii_filename
from calibre.gui2.dialogs.confirm_delete import confirm

class Main(MainWindow, Ui_MainWindow):

    def set_default_thumbnail(self, height):
        r = QSvgRenderer(':/images/book.svg')
        pixmap = QPixmap(height, height)
        pixmap.fill(QColor(255,255,255))
        p = QPainter(pixmap)
        r.render(p)
        p.end()
        self.default_thumbnail = (pixmap.width(), pixmap.height(), pixmap_to_data(pixmap))

    def __init__(self, single_instance, opts, actions, parent=None):
        self.preferences_action, self.quit_action = actions
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
        self.verbose = opts.verbose
        self.get_metadata = GetMetadata()
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
        self.system_tray_icon = QSystemTrayIcon(QIcon(':/library'), self)
        if not config['systray_icon']:
            self.system_tray_icon.hide()
        else:
            self.system_tray_icon.show()
        self.system_tray_menu = QMenu()
        self.restore_action = self.system_tray_menu.addAction(QIcon(':/images/page.svg'), _('&Restore'))
        self.donate_action  = self.system_tray_menu.addAction(QIcon(':/images/donate.svg'), _('&Donate to support calibre'))
        self.donate_button.setDefaultAction(self.donate_action)
        self.addAction(self.quit_action)
        self.action_restart = QAction(_('&Restart'), self)
        self.addAction(self.action_restart)
        self.system_tray_menu.addAction(self.quit_action)
        self.quit_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Q))
        self.action_restart.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_R))
        self.action_show_book_details.setShortcut(QKeySequence(Qt.Key_I))
        self.addAction(self.action_show_book_details)
        self.system_tray_icon.setContextMenu(self.system_tray_menu)
        self.connect(self.quit_action, SIGNAL('triggered(bool)'), self.quit)
        self.connect(self.donate_action, SIGNAL('triggered(bool)'), self.donate)
        self.connect(self.restore_action, SIGNAL('triggered(bool)'), lambda c : self.show())
        self.connect(self.action_show_book_details, SIGNAL('triggered(bool)'), self.show_book_info)
        self.connect(self.action_restart, SIGNAL('triggered(bool)'), 
                     lambda c : self.quit(None, restart=True))
        self.connect(self.system_tray_icon, SIGNAL('activated(QSystemTrayIcon::ActivationReason)'), 
                     self.system_tray_icon_activated)
        self.tool_bar.contextMenuEvent = self.no_op
        ####################### Location View ########################
        QObject.connect(self.location_view, SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        QObject.connect(self.stack, SIGNAL('currentChanged(int)'),
                        self.location_view.location_changed)
        
        self.output_formats = sorted(['EPUB', 'MOBI', 'LRF'])
        for f in self.output_formats:
            self.output_format.addItem(f)
        self.output_format.setCurrentIndex(self.output_formats.index(prefs['output_format']))
        self.connect(self.output_format, SIGNAL('currentIndexChanged(QString)'), 
                     self.change_output_format, Qt.QueuedConnection)

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
        self.status_bar = StatusBar(self.jobs_dialog, self.system_tray_icon)
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
        sm.addAction(self.action_send_specific_format_to_device)
        self.connect(self.action_send_specific_format_to_device, 
                     SIGNAL('triggered()'), self.send_specific_format_to_device)
        sm.addSeparator()
        sm.addAction(_('Send to storage card by default'))
        sm.actions()[-1].setCheckable(True)
        QObject.connect(sm.actions()[-1], SIGNAL('toggled(bool)'), 
                        self.do_default_sync)

        sm.actions()[-1].setChecked(config.get('send_to_storage_card_by_default'))
        self.do_default_sync(sm.actions()[-1].isChecked())
        self.sync_menu = sm # Needed
        md = QMenu()
        md.addAction(_('Edit metadata individually'))
        md.addSeparator()
        md.addAction(_('Edit metadata in bulk'))
        self.metadata_menu = md
        self.add_menu = QMenu()
        self.add_menu.addAction(_('Add books from a single directory'))
        self.add_menu.addAction(_('Add books from directories, including sub-directories (One book per directory, assumes every ebook file is the same book in a different format)'))
        self.add_menu.addAction(_('Add books from directories, including sub directories (Multiple books per directory, assumes every ebook file is a different book)'))
        self.action_add.setMenu(self.add_menu)
        QObject.connect(self.action_add, SIGNAL("triggered(bool)"), self.add_books)
        QObject.connect(self.add_menu.actions()[0], SIGNAL("triggered(bool)"), self.add_books)
        QObject.connect(self.add_menu.actions()[1], SIGNAL("triggered(bool)"), self.add_recursive_single)
        QObject.connect(self.add_menu.actions()[2], SIGNAL("triggered(bool)"), self.add_recursive_multiple)
        QObject.connect(self.action_del, SIGNAL("triggered(bool)"), self.delete_books)
        QObject.connect(self.action_edit, SIGNAL("triggered(bool)"), self.edit_metadata)
        QObject.connect(md.actions()[0], SIGNAL('triggered(bool)'), partial(self.edit_metadata, bulk=False))
        QObject.connect(md.actions()[2], SIGNAL('triggered(bool)'), partial(self.edit_metadata, bulk=True))
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
        self.connect(self.action_open_containing_folder, SIGNAL('triggered(bool)'), self.view_folder)
        self.action_open_containing_folder.setShortcut(Qt.Key_O)
        self.addAction(self.action_open_containing_folder)
        self.action_sync.setShortcut(Qt.Key_D)
        self.action_sync.setMenu(sm)
        self.action_edit.setMenu(md)
        self.action_save.setMenu(self.save_menu)
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
        self.tool_bar.widgetForAction(self.action_news).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_edit).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_sync).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_convert).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_save).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_add).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_view).setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.setContextMenuPolicy(Qt.PreventContextMenu)

        QObject.connect(self.config_button, SIGNAL('clicked(bool)'), self.do_config)
        self.connect(self.preferences_action, SIGNAL('triggered(bool)'), self.do_config)
        self.connect(self.action_preferences, SIGNAL('triggered(bool)'), self.do_config)
        QObject.connect(self.advanced_search_button, SIGNAL('clicked(bool)'), self.do_advanced_search)
        
        ####################### Library view ########################
        similar_menu = QMenu(_('Similar books...'))
        similar_menu.addAction(self.action_books_by_same_author)
        similar_menu.addAction(self.action_books_in_this_series)
        similar_menu.addAction(self.action_books_with_the_same_tags)
        similar_menu.addAction(self.action_books_by_this_publisher)
        self.action_books_by_same_author.setShortcut(Qt.ALT + Qt.Key_A)
        self.action_books_in_this_series.setShortcut(Qt.ALT + Qt.Key_S)
        self.action_books_by_this_publisher.setShortcut(Qt.ALT + Qt.Key_P)
        self.action_books_with_the_same_tags.setShortcut(Qt.ALT+Qt.Key_T)
        self.addAction(self.action_books_by_same_author)
        self.addAction(self.action_books_by_this_publisher)
        self.addAction(self.action_books_in_this_series)
        self.addAction(self.action_books_with_the_same_tags)
        self.similar_menu = similar_menu
        self.connect(self.action_books_by_same_author, SIGNAL('triggered()'),
                     lambda : self.show_similar_books('author'))
        self.connect(self.action_books_in_this_series, SIGNAL('triggered()'),
                     lambda : self.show_similar_books('series'))
        self.connect(self.action_books_with_the_same_tags, SIGNAL('triggered()'),
                     lambda : self.show_similar_books('tag'))
        self.connect(self.action_books_by_this_publisher, SIGNAL('triggered()'),
                     lambda : self.show_similar_books('publisher'))
        self.library_view.set_context_menu(self.action_edit, self.action_sync, 
                                           self.action_convert, self.action_view, 
                                           self.action_save, self.action_open_containing_folder,
                                           self.action_show_book_details,
                                           similar_menu=similar_menu)
        self.memory_view.set_context_menu(None, None, None, self.action_view, self.action_save, None, None)
        self.card_view.set_context_menu(None, None, None, self.action_view, self.action_save, None, None)
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
        if self.system_tray_icon.isVisible() and opts.start_in_tray:
            self.hide()
        self.stack.setCurrentIndex(0)
        try:
            db = LibraryDatabase2(self.library_path)
        except Exception, err:
            error_dialog(self, _('Bad database location'), unicode(err)).exec_()
            dir = unicode(QFileDialog.getExistingDirectory(self,
                            _('Choose a location for your ebook library.'), os.path.expanduser('~')))
            if not dir:
                QCoreApplication.exit(1)
            else:
                self.library_path = dir
                db = LibraryDatabase2(self.library_path)
        self.library_view.set_database(db)
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
        self.connect(self.library_view.model(), SIGNAL('count_changed(int)'), self.location_view.count_changed)
        self.connect(self.library_view.model(), SIGNAL('count_changed(int)'),
                     self.tags_view.recount)
        self.library_view.model().count_changed()
        ########################### Cover Flow ################################
        self.cover_flow = None
        if CoverFlow is not None:
            text_height = 40 if config['separate_cover_flow'] else 25
            ah = available_height()
            cfh = ah-100
            cfh = 3./5 * cfh - text_height
            if not config['separate_cover_flow']:
                cfh = 220 if ah > 950 else 170 if ah > 850 else 140
            self.cover_flow = CoverFlow(height=cfh, text_height=text_height)
            self.cover_flow.setVisible(False)
            if not config['separate_cover_flow']:
                self.library.layout().addWidget(self.cover_flow)
            self.connect(self.cover_flow, SIGNAL('currentChanged(int)'), 
                         self.sync_cf_to_listview)
            self.connect(self.cover_flow, SIGNAL('itemActivated(int)'), 
                         self.show_book_info)
            self.connect(self.status_bar.cover_flow_button, 
                         SIGNAL('toggled(bool)'), self.toggle_cover_flow)
            self.connect(self.cover_flow, SIGNAL('stop()'), 
                         self.status_bar.cover_flow_button.toggle)
            QObject.connect(self.library_view.selectionModel(), 
                            SIGNAL('currentRowChanged(QModelIndex, QModelIndex)'),
                            self.sync_cf_to_listview)
            self.db_images = DatabaseImages(self.library_view.model())
            self.cover_flow.setImages(self.db_images)
        else:
            self.status_bar.cover_flow_button.disable(pictureflowerror)


        self.setMaximumHeight(max_available_height())

        ####################### Setup device detection ########################
        self.device_manager = DeviceManager(Dispatcher(self.device_detected), self.job_manager)
        self.device_manager.start()
        
        
        if config['autolaunch_server']:
            from calibre.library.server import start_threaded_server
            from calibre.library import server_config
            self.content_server = start_threaded_server(db, server_config().parse())
            self.test_server_timer = QTimer.singleShot(10000, self.test_server)
        
        
        self.scheduler = Scheduler(self)
        self.action_news.setMenu(self.scheduler.news_menu)
        self.connect(self.action_news, SIGNAL('triggered(bool)'), self.scheduler.show_dialog)
        self.location_view.setCurrentIndex(self.location_view.model().index(0))
    
    def no_op(self, *args):
        pass
    
    def system_tray_icon_activated(self, r):
        if r == QSystemTrayIcon.Trigger:
            if self.isVisible():
                for window in QApplication.topLevelWidgets():
                    if isinstance(window, (MainWindow, QDialog)) and window.isVisible():
                        window.hide()
                        setattr(window, '__systray_minimized', True)
            else:
                for window in QApplication.topLevelWidgets():
                    if getattr(window, '__systray_minimized', False):
                        window.show()
                        setattr(window, '__systray_minimized', False)
                         
    
    def do_default_sync(self, checked):
        config.set('send_to_storage_card_by_default', bool(checked))
        QObject.disconnect(self.action_sync, SIGNAL("triggered(bool)"), 
                           self.sync_to_main_memory)
        QObject.disconnect(self.action_sync, SIGNAL("triggered(bool)"), 
                           self.sync_to_card)
        QObject.connect(self.action_sync, SIGNAL("triggered(bool)"), 
                        self.sync_to_card if checked else self.sync_to_main_memory)
    
    def change_output_format(self, x):
        of = unicode(x).strip()
        if of != prefs['output_format']:
            if of not in ('LRF', 'EPUB', 'MOBI'):
                warning_dialog(self, 'Warning', 
                               '<p>%s support is still in beta. If you find bugs, please report them by opening a <a href="http://calibre.kovidgoyal.net">ticket</a>.'%of).exec_()
            prefs.set('output_format', of)
        
        
    def test_server(self, *args):
        if self.content_server.exception is not None:
            error_dialog(self, _('Failed to start content server'), 
                         unicode(self.content_server.exception)).exec_()

    def show_similar_books(self, type):
        search, join = [], ' '
        idx = self.library_view.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        if type == 'series':
            series = idx.model().db.series(row)
            if series:
                search = ['series:'+series]
        elif type == 'publisher':
            publisher = idx.model().db.publisher(row)
            if publisher:
                search = ['publisher:'+publisher]
        elif type == 'tag':
            tags = idx.model().db.tags(row)
            if tags:
                search = ['tag:'+t for t in tags.split(',')]
        elif type == 'author':
            authors = idx.model().db.authors(row)
            if authors:
                search = ['author:'+a.strip().replace('|', ',') for a in authors.split(',')]
                join = ' or '
        if search:
            self.search.set_search_string(join.join(search))
            
                
    
    def toggle_cover_flow(self, show):
        if config['separate_cover_flow']:
            if show:
                d = QDialog(self)
                ah, aw = available_height(), available_width()
                d.resize(int(aw/2.), ah-60)
                d._layout = QStackedLayout()
                d.setLayout(d._layout)
                d.setWindowTitle(_('Browse by covers'))
                d.layout().addWidget(self.cover_flow)
                self.cover_flow.setVisible(True)
                self.cover_flow.setFocus(Qt.OtherFocusReason)
                self.library_view.scrollTo(self.library_view.currentIndex())
                d.show()
                self.connect(d, SIGNAL('finished(int)'), 
                             lambda x: self.status_bar.cover_flow_button.setChecked(False))
                self.cf_dialog = d
            else:
                cfd = getattr(self, 'cf_dialog', None)
                if cfd is not None:
                    self.cover_flow.setVisible(False)
                    cfd.hide()
                    self.cf_dialog = None
        else:
            if show:
                self.library_view.setCurrentIndex(self.library_view.currentIndex())
                self.cover_flow.setVisible(True)
                self.cover_flow.setFocus(Qt.OtherFocusReason)
                #self.status_bar.book_info.book_data.setMaximumHeight(100)
                #self.status_bar.setMaximumHeight(120)
                self.library_view.scrollTo(self.library_view.currentIndex())
            else:
                self.cover_flow.setVisible(False)
                #self.status_bar.book_info.book_data.setMaximumHeight(1000)
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
        if hasattr(index, 'row') and self.cover_flow.isVisible() and \
                self.cover_flow.currentSlide() != index.row():
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
            self.library_view.model().refresh()
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
        self.device_info = _('Connected ')+info[0]
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
        self.sync_news()
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
        root = choose_dir(self, 'recursive book import root dir dialog', 
                          'Select root folder')
        if not root:
            return
        from calibre.gui2.add import AddRecursive
        self._add_recursive_thread = AddRecursive(root, 
                                self.library_view.model().db, self.get_metadata,
                                single, self)
        self.connect(self._add_recursive_thread, SIGNAL('finished()'),
                     self._recursive_files_added)
        self._add_recursive_thread.start()
    
    def _recursive_files_added(self):
        self._add_recursive_thread.process_duplicates()
        if self._add_recursive_thread.number_of_books_added > 0:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()
            self.library_view.model().count_changed()
        self._add_recursive_thread = None
        
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
                             filters=[
                                      (_('Books'), BOOK_EXTENSIONS),
                                      (_('EPUB Books'), ['epub']),
                                      (_('LRF Books'), ['lrf']),
                                      (_('HTML Books'), ['htm', 'html', 'xhtm', 'xhtml']),
                                      (_('LIT Books'), ['lit']),
                                      (_('MOBI Books'), ['mobi', 'prc']),
                                      (_('Text books'), ['txt', 'rtf']),
                                      (_('PDF Books'), ['pdf']),
                                      (_('Comics'), ['cbz', 'cbr']),
                                      (_('Archives'), ['zip', 'rar']),
                                      ])
        if not books:
            return
        to_device = self.stack.currentIndex() != 0
        self._add_books(books, to_device)
        

    def _add_books(self, paths, to_device, on_card=None):
        if on_card is None:
            on_card = self.stack.currentIndex() == 2
        if not paths:
            return
        from calibre.gui2.add import AddFiles
        self._add_files_thread = AddFiles(paths, self.default_thumbnail, 
                                          self.get_metadata,
                                          None if to_device else \
                                          self.library_view.model().db
                                          )
        self._add_files_thread.send_to_device = to_device
        self._add_files_thread.on_card = on_card
        self._add_files_thread.create_progress_dialog(_('Adding books...'),
                                                _('Reading metadata...'), self)
        self.connect(self._add_files_thread, SIGNAL('finished()'),
                     self._files_added)
        self._add_files_thread.start()
    
    def _files_added(self):
        t = self._add_files_thread
        self._add_files_thread = None
        if not t.canceled:
            if t.send_to_device:
                self.upload_books(t.paths, 
                                  list(map(sanitize_file_name, t.names)), 
                                  t.infos, on_card=t.on_card)
                self.status_bar.showMessage(_('Uploading books to device.'), 2000)
            else:
                t.process_duplicates()
        if t.number_of_books_added > 0:
            self.library_view.model().books_added(t.number_of_books_added)
            self.db_images.reset()
        
    def upload_books(self, files, names, metadata, on_card=False, memory=None):
        '''
        Upload books to device.
        :param files: List of either paths to files or file like objects
        '''
        titles = [i['title'] for i in metadata]
        job = self.device_manager.upload_books(Dispatcher(self.books_uploaded),
                                        files, names, on_card=on_card, 
                                        metadata=metadata, titles=titles
                                        )
        self.upload_memory[job] = (metadata, on_card, memory, files)
    
    def books_uploaded(self, job):
        '''
        Called once books have been uploaded.
        '''
        metadata, on_card, memory, files = self.upload_memory.pop(job)
        
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
        for f in files:
            getattr(f, 'close', lambda : True)()
        if memory and memory[1]:
            self.library_view.model().delete_books_by_id(memory[1])


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
            if not confirm('<p>'+_('The selected books will be '
                                   '<b>permanently deleted</b> and the files '
                                   'removed from your computer. Are you sure?')
                                +'</p>', 'library_delete_books', self):
                return
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
        previous = self.library_view.currentIndex()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot edit metadata'), 
                             _('No books selected'))
            d.exec_()
            return

        if bulk or (bulk is None and len(rows) > 1):
            return self.edit_bulk_metadata(checked)
        
        def accepted(id):
            self.library_view.model().refresh_ids([id])

        for row in rows:
            d = MetadataSingleDialog(self, row.row(),
                                    self.library_view.model().db,
                                    accepted_callback=accepted)
            d.exec_()
        if rows:
            current = self.library_view.currentIndex()
            self.library_view.model().current_changed(current, previous)
            
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

    def sync_news(self):
        if self.device_connected:
            ids = list(dynamic.get('news_to_be_synced', set([])))
            ids = [id for id in ids if self.library_view.model().db.has_id(id)]
            files = self.library_view.model().get_preferred_formats_from_ids(
                                ids, self.device_manager.device_class.FORMATS)
            files = [f for f in files if f is not None]
            if not files:
                dynamic.set('news_to_be_synced', set([]))
                return
            metadata = self.library_view.model().get_metadata(ids, rows_are_ids=True)
            names = []
            for mi in metadata: 
                prefix = sanitize_file_name(mi['title'])
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id, os.path.splitext(f.name)[1]))
                cdata = mi['cover']
                if cdata:
                    mi['cover'] = self.cover_to_thumbnail(cdata)
            dynamic.set('news_to_be_synced', set([]))
            if config['upload_news_to_device'] and files:
                remove = ids if config['delete_news_from_library_on_upload'] else []
                on_card = self.location_view.model().free[0] < self.location_view.model().free[1]
                self.upload_books(files, names, metadata, on_card=on_card, memory=[[f.name for f in files], remove])
                self.status_bar.showMessage(_('Sending news to device.'), 5000)
                
    def send_specific_format_to_device(self):
        d = ChooseFormatDialog(self, _('Choose format to send to device'), 
                               self.device_manager.device_class.FORMATS)
        d.exec_()
        fmt = d.format().lower()
        on_card = config['send_to_storage_card_by_default']
        self.sync_to_device(on_card, False, specific_format=fmt)
        
    
    def sync_to_device(self, on_card, delete_from_library, specific_format=None):
        rows = self.library_view.selectionModel().selectedRows()
        if not self.device_manager or not rows or len(rows) == 0:
            return
        ids = iter(self.library_view.model().id(r) for r in rows)
        metadata, full_metadata = self.library_view.model().get_metadata(
                                                    rows, full_metadata=True)
        for mi in metadata:
            cdata = mi['cover']
            if cdata:
                mi['cover'] = self.cover_to_thumbnail(cdata)
        metadata, full_metadata = iter(metadata), iter(full_metadata)
        _files   = self.library_view.model().get_preferred_formats(rows,
                                    self.device_manager.device_class.FORMATS, 
                                    paths=True, set_metadata=True,
                                    specific_format=specific_format)
        files = [getattr(f, 'name', None) for f in _files]
        bad, good, gf, names, remove_ids = [], [], [], [], []
        for f in files:
            mi, smi = metadata.next(), full_metadata.next()
            id = ids.next()
            if f is None:
                bad.append(mi['title'])
            else:
                remove_ids.append(id)
                try:
                    with open(f, 'r+b') as _f:
                        set_metadata(_f, smi, f.rpartition('.')[2])
                except:
                    print 'Error setting metadata in book:', mi['title']
                    traceback.print_exc()
                good.append(mi)
                gf.append(f)
                t = mi['title']
                if not t:
                    t = _('Unknown')
                a = mi['authors']
                if not a:
                    a = _('Unknown')
                prefix = sanitize_file_name(t+' - '+a)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id, os.path.splitext(f)[1]))
        remove = remove_ids if delete_from_library else []
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
        
        progress = ProgressDialog(_('Saving to disk...'), min=0, max=len(rows),
                                  parent=self)
        
        def callback(count, msg):
            progress.set_value(count)
            progress.set_msg(_('Saved')+' '+msg)
            QApplication.processEvents()
            QApplication.sendPostedEvents()
            QApplication.flush()
            return not progress.canceled
        
        dir = choose_dir(self, 'save to disk dialog', _('Choose destination directory'))
        if not dir:
            return
            
        progress.show()
        QApplication.processEvents()
        QApplication.sendPostedEvents()
        QApplication.flush()
        try:
            if self.current_view() == self.library_view:
                failures = self.current_view().model().save_to_disk(rows, dir,
                                        single_dir=single_dir, callback=callback, 
                                        single_format=single_format)
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
        finally:
            progress.hide()
            
    def books_saved(self, job):
        if job.exception is not None:
            self.device_job_exception(job)            
            return

    ############################################################################

    ############################### Fetch news #################################

    def download_scheduled_recipe(self, recipe, script, callback):
        func, args, desc, fmt, temp_files = fetch_scheduled_recipe(recipe, script)
        job = self.job_manager.run_job(Dispatcher(self.scheduled_recipe_fetched), func, args=args,
                                            description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, recipe, callback)
        self.status_bar.showMessage(_('Fetching news from ')+recipe.title, 2000)
    
    def scheduled_recipe_fetched(self, job):
        temp_files, fmt, recipe, callback = self.conversion_jobs.pop(job)
        pt = temp_files[0]
        if job.exception is not None:
            self.job_exception(job)
            return
        id = self.library_view.model().add_news(pt.name, recipe)
        self.library_view.model().reset()
        sync = dynamic.get('news_to_be_synced', set([]))
        sync.add(id)
        dynamic.set('news_to_be_synced', sync)
        callback(recipe)
        self.status_bar.showMessage(recipe.title + _(' fetched.'), 3000)
        self.sync_news()
            
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
        
        res  = convert_bulk_ebooks(self, self.library_view.model().db, comics, others)
        if res is None:
            return
        jobs, changed = res 
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
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in self.library_view.selectionModel().selectedRows()]
        comics, others = r
        jobs, changed = convert_single_ebook(self, self.library_view.model().db, comics, others)
        for func, args, desc, fmt, id, temp_files in jobs:
            job = self.job_manager.run_job(Dispatcher(self.book_converted), 
                                            func, args=args, description=desc)
            self.conversion_jobs[job] = (temp_files, fmt, id)
            
        if changed:
            self.library_view.model().refresh_rows(rows)
            current = self.library_view.currentIndex()
            self.library_view.model().current_changed(current, previous)
                    
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
        self.tags_view.recount()
        if self.current_view() is self.library_view:
            current = self.library_view.currentIndex()
            self.library_view.model().current_changed(current, QModelIndex())
    
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
                    self.job_manager.server.run_free_job('lrfviewer', 
                                                        kwdargs=dict(args=args))
                else:
                    args = ['ebook-viewer', name]
                    if isosx:
                        args.append('--raise-window')
                    self.job_manager.server.run_free_job('ebook-viewer', 
                                                        kwdargs=dict(args=args))
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
    
    def view_folder(self, *args):
        rows = self.current_view().selectionModel().selectedRows()
        if self.current_view() is self.library_view:
            if not rows or len(rows) == 0:
                d = error_dialog(self, _('Cannot open folder'), _('No book selected'))
                d.exec_()
                return
        for row in rows:
            path = self.library_view.model().db.abspath(row.row())
            QDesktopServices.openUrl(QUrl('file:'+path))
        
    
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
            if 'MOBI' in formats:
                format = 'MOBI'
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

    def do_config(self, *args):
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
            self.action_open_containing_folder.setEnabled(True)
        else:
            self.action_sync.setEnabled(False)
            self.action_edit.setEnabled(False)
            self.action_convert.setEnabled(False)
            self.view_menu.actions()[1].setEnabled(False)
            self.action_open_containing_folder.setEnabled(False)
                
    def device_job_exception(self, job):
        '''
        Handle exceptions in threaded device jobs.
        '''
        try:
            if 'Could not read 32 bytes on the control bus.' in unicode(job.exception):
                error_dialog(self, _('Error talking to device'), 
                             _('There was a temporary error talking to the device. Please unplug and reconnect the device and or reboot.')).show()
                return
        except:
            pass
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
        if self.library_path is None: # Need to migrate to new database layout
            base = os.path.expanduser('~')
            if iswindows:
                from calibre import plugins
                from PyQt4.Qt import QDir
                base = plugins['winutil'][0].special_folder_path(plugins['winutil'][0].CSIDL_PERSONAL)
                if not base or not os.path.exists(base):
                    base = unicode(QDir.homePath()).replace('/', os.sep)
            dir = unicode(QFileDialog.getExistingDirectory(self, 
                            _('Choose a location for your ebook library.'), base))
            if not dir:
                dir = os.path.expanduser('~/Library')
            self.library_path = os.path.abspath(dir)
        if not os.path.exists(self.library_path):
            try:
                os.makedirs(self.library_path)
            except:
                self.library_path = os.path.expanduser('~/Library')
                error_dialog(self, _('Invalid library location'), 
                     _('Could not access %s. Using %s as the library.')%
                     (repr(self.library_path), repr(self.library_path)) 
                             ).exec_()
                os.makedirs(self.library_path)


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
    
    def quit(self, checked, restart=False):
        if not self.confirm_quit():
            return
        try:
            self.shutdown()
        except:
            pass
        self.restart_after_quit = restart
        QApplication.instance().quit()
            
    def donate(self, *args):
        BUTTON = '''
        <form action="https://www.paypal.com/cgi-bin/webscr" method="post">
            <input type="hidden" name="cmd" value="_s-xclick" />
            <input type="hidden" name="hosted_button_id" value="3029467" />
            <input type="image" src="https://www.paypal.com/en_US/i/btn/btn_donateCC_LG.gif" border="0" name="submit" alt="Donate to support calibre development" />
            <img alt="" border="0" src="https://www.paypal.com/en_US/i/scr/pixel.gif" width="1" height="1" />
        </form>
        '''
        MSG = _('is the result of the efforts of many volunteers from all over the world. If you find it useful, please consider donating to support its development.')
        HTML = u'''
        <html>
            <head>
                <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
                <title>Donate to support calibre</title>
            </head>
            <body style="background:white">
                <div><a href="http://calibre.kovidgoyal.net"><img style="border:0px" src="http://calibre.kovidgoyal.net/chrome/site/calibre_banner.png" alt="calibre" /></a></div>
                <p>Calibre %s</p>
                %s
            </body>
        </html>
        '''%(MSG, BUTTON)
        pt = PersistentTemporaryFile('_donate.htm')
        pt.write(HTML.encode('utf-8'))
        pt.close()
        QDesktopServices.openUrl(QUrl.fromLocalFile(pt.name))
            
    
    def confirm_quit(self):
        if self.job_manager.has_jobs():
            msg = _('There are active jobs. Are you sure you want to quit?')
            if self.job_manager.has_device_jobs():
                msg = '<p>'+__appname__ + _(''' is communicating with the device!<br>
                      'Quitting may cause corruption on the device.<br>
                      'Are you sure you want to quit?''')+'</p>'
            
            d = QMessageBox(QMessageBox.Warning, _('WARNING: Active jobs'), msg,
                            QMessageBox.Yes|QMessageBox.No, self)
            d.setIconPixmap(QPixmap(':/images/dialog_warning.svg'))
            d.setDefaultButton(QMessageBox.No)
            if d.exec_() != QMessageBox.Yes:
                return False
        return True

    
    def shutdown(self, write_settings=True):
        if write_settings:
            self.write_settings()
        self.job_manager.terminate_all_jobs()
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
        self.hide()
        return True

    
    def closeEvent(self, e):
        self.write_settings()
        if self.system_tray_icon.isVisible():
            if not dynamic['systray_msg'] and not isosx:
                info_dialog(self, 'calibre', 'calibre '+_('will keep running in the system tray. To close it, choose <b>Quit</b> in the context menu of the system tray.')).exec_()
                dynamic['systray_msg'] = True
            self.hide()
            e.ignore()
        else:
            if self.confirm_quit():
                try:
                    self.shutdown(write_settings=False)
                except:
                    pass
                e.accept()
            else:
                e.ignore()

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
        

def option_parser():
    parser = _option_parser('''\
%prog [opts] [path_to_ebook]

Launch the main calibre Graphical User Interface and optionally add the ebook at
path_to_ebook to the database.
''')
    parser.add_option('--with-library', default=None, action='store', 
                      help=_('Use the library located at the specified path.'))
    parser.add_option('--start-in-tray', default=False, action='store_true',
                      help=_('Start minimized to system tray.'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help=_('Log debugging information to console'))
    return parser

def main(args=sys.argv):
    from calibre.utils.lock import singleinstance
    
    pid = os.fork() if False and islinux else -1
    if pid <= 0:
        parser = option_parser()
        opts, args = parser.parse_args(args)
        if opts.with_library is not None and os.path.isdir(opts.with_library):
            prefs.set('library_path', opts.with_library)
            print 'Using library at', prefs['library_path']
        app = Application(args)
        actions = tuple(Main.create_application_menubar())
        app.setWindowIcon(QIcon(':/library'))
        QCoreApplication.setOrganizationName(ORG_NAME)
        QCoreApplication.setApplicationName(APP_UID)
        single_instance = None if SingleApplication is None else SingleApplication('calibre GUI')
        if not singleinstance('calibre GUI'):
            if len(args) > 1:
                args[1] = os.path.abspath(args[1])
            if single_instance is not None and single_instance.is_running() and \
               single_instance.send_message('launched:'+repr(args)):
                    return 0
            extra = '' if iswindows else \
            	('If you\'re sure it is not running, delete the file %s.'%os.path.expanduser('~/.calibre_calibre GUI.lock'))
            QMessageBox.critical(None, 'Cannot Start '+__appname__,
                                 '<p>%s is already running. %s</p>'%(__appname__, extra))
            return 1
        initialize_file_icon_provider()
        main = Main(single_instance, opts, actions)
        sys.excepthook = main.unhandled_exception
        if len(args) > 1:
            main.add_filesystem_book(args[1])
        ret = app.exec_()
        if getattr(main, 'restart_after_quit', False):
            e = sys.executable if getattr(sys, 'froze', False) else sys.argv[0] 
            print 'Restarting with:', e, sys.argv
            os.execvp(e, sys.argv)
        else:
            if iswindows:
                try:
                    main.system_tray_icon.hide()
                except:
                    pass
            return ret
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
