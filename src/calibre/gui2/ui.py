#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''The main GUI'''

import os, sys, textwrap, collections, time
from xml.parsers.expat import ExpatError
from Queue import Queue, Empty
from threading import Thread
from functools import partial
from PyQt4.Qt import Qt, SIGNAL, QObject, QCoreApplication, QUrl, QTimer, \
                     QModelIndex, QPixmap, QColor, QPainter, QMenu, QIcon, \
                     QToolButton, QDialog, QDesktopServices, QFileDialog, \
                     QSystemTrayIcon, QApplication, QKeySequence, QAction, \
                     QMessageBox, QStackedLayout, QHelpEvent, QInputDialog
from PyQt4.QtSvg import QSvgRenderer

from calibre import  prints, patheq
from calibre.constants import __version__, __appname__, isfrozen, islinux, \
                    iswindows, isosx, filesystem_encoding
from calibre.utils.filenames import ascii_filename
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import prefs, dynamic
from calibre.utils.ipc.server import Server
from calibre.gui2 import warning_dialog, choose_files, error_dialog, \
                            question_dialog,\
                           pixmap_to_data, choose_dir, \
                           Dispatcher, \
                           available_height, \
                           max_available_height, config, info_dialog, \
                           available_width, GetMetadata
from calibre.gui2.cover_flow import CoverFlow, DatabaseImages, pictureflowerror
from calibre.gui2.widgets import ProgressIndicator, IMAGE_EXTENSIONS
from calibre.gui2.wizard import move_library
from calibre.gui2.dialogs.scheduler import Scheduler
from calibre.gui2.update import CheckForUpdates
from calibre.gui2.main_window import MainWindow
from calibre.gui2.main_ui import Ui_MainWindow
from calibre.gui2.device import DeviceManager, DeviceMenu, DeviceGUI, Emailer
from calibre.gui2.status import StatusBar
from calibre.gui2.jobs import JobManager, JobsDialog
from calibre.gui2.dialogs.metadata_single import MetadataSingleDialog
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.gui2.tools import convert_single_ebook, convert_bulk_ebook, \
    fetch_scheduled_recipe
from calibre.gui2.dialogs.config import ConfigDialog
from calibre.gui2.dialogs.search import SearchDialog
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2.dialogs.book_info import BookInfo
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.library.database2 import LibraryDatabase2, CoverCache
from calibre.gui2.dialogs.confirm_delete import confirm

class SaveMenu(QMenu):

    def __init__(self, parent):
        QMenu.__init__(self, _('Save single format to disk...'), parent)
        for ext in sorted(BOOK_EXTENSIONS):
            action = self.addAction(ext.upper())
            setattr(self, 'do_'+ext, partial(self.do, ext))
            self.connect(action, SIGNAL('triggered(bool)'),
                    getattr(self, 'do_'+ext))

    def do(self, ext, *args):
        self.emit(SIGNAL('save_fmt(PyQt_PyObject)'), ext)

class Listener(Thread):

    def __init__(self, listener):
        Thread.__init__(self)
        self.daemon = True
        self.listener, self.queue = listener, Queue()
        self._run = True
        self.start()

    def run(self):
        while self._run:
            try:
                conn = self.listener.accept()
                msg = conn.recv()
                self.queue.put(msg)
            except:
                continue

    def close(self):
        self._run = False
        try:
            self.listener.close()
        except:
            pass

class SystemTrayIcon(QSystemTrayIcon):

    def __init__(self, icon, parent):
        QSystemTrayIcon.__init__(self, icon, parent)

    def event(self, ev):
        if ev.type() == ev.ToolTip:
            evh = QHelpEvent(ev)
            self.emit(SIGNAL('tooltip_requested(PyQt_PyObject)'),
                    (self, evh.globalPos()))
            return True
        return QSystemTrayIcon.event(self, ev)

class Main(MainWindow, Ui_MainWindow, DeviceGUI):
    'The main GUI'

    def set_default_thumbnail(self, height):
        r = QSvgRenderer(I('book.svg'))
        pixmap = QPixmap(height, height)
        pixmap.fill(QColor(255,255,255))
        p = QPainter(pixmap)
        r.render(p)
        p.end()
        self.default_thumbnail = (pixmap.width(), pixmap.height(),
                pixmap_to_data(pixmap))

    def __init__(self, listener, opts, actions, parent=None):
        self.preferences_action, self.quit_action = actions
        self.spare_servers = []
        MainWindow.__init__(self, opts, parent)
        # Initialize fontconfig in a separate thread as this can be a lengthy
        # process if run for the first time on this machine
        from calibre.utils.fonts import fontconfig
        self.fc = fontconfig
        self.listener = Listener(listener)
        self.check_messages_timer = QTimer()
        self.connect(self.check_messages_timer, SIGNAL('timeout()'),
                self.another_instance_wants_to_talk)
        self.check_messages_timer.start(1000)

        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(__appname__)
        self.search.initialize('main_search_history', colorize=True,
                help_text=_('Search (For Advanced Search click the button to the left)'))
        self.connect(self.clear_button, SIGNAL('clicked()'), self.search.clear)
        self.progress_indicator = ProgressIndicator(self)
        self.verbose = opts.verbose
        self.get_metadata = GetMetadata()
        self.read_settings()
        self.job_manager = JobManager()
        self.emailer = Emailer()
        self.emailer.start()
        self.jobs_dialog = JobsDialog(self, self.job_manager)
        self.upload_memory = {}
        self.delete_memory = {}
        self.conversion_jobs = {}
        self.persistent_files = []
        self.metadata_dialogs = []
        self.default_thumbnail = None
        self.device_error_dialog = error_dialog(self, _('Error'),
                _('Error communicating with device'), ' ')
        self.device_error_dialog.setModal(Qt.NonModal)
        self.tb_wrapper = textwrap.TextWrapper(width=40)
        self.device_connected = False
        self.viewers = collections.deque()
        self.content_server = None
        self.system_tray_icon = SystemTrayIcon(QIcon(I('library.png')), self)
        self.system_tray_icon.setToolTip('calibre')
        self.connect(self.system_tray_icon,
                SIGNAL('tooltip_requested(PyQt_PyObject)'),
                self.job_manager.show_tooltip)
        if not config['systray_icon']:
            self.system_tray_icon.hide()
        else:
            self.system_tray_icon.show()
        self.system_tray_menu = QMenu(self)
        self.restore_action = self.system_tray_menu.addAction(
                QIcon(I('page.svg')), _('&Restore'))
        self.donate_action  = self.system_tray_menu.addAction(
                QIcon(I('donate.svg')), _('&Donate to support calibre'))
        self.donate_button.setDefaultAction(self.donate_action)
        if not config['show_donate_button']:
            self.donate_button.setVisible(False)
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
        self.connect(self.restore_action, SIGNAL('triggered()'),
                self.show_windows)
        self.connect(self.action_show_book_details,
                SIGNAL('triggered(bool)'), self.show_book_info)
        self.connect(self.action_restart, SIGNAL('triggered()'),
                     self.restart)
        self.connect(self.system_tray_icon,
                SIGNAL('activated(QSystemTrayIcon::ActivationReason)'),
                self.system_tray_icon_activated)
        self.tool_bar.contextMenuEvent = self.no_op

        ####################### Start spare job server ########################
        QTimer.singleShot(1000, self.add_spare_server)

        ####################### Setup device detection ########################
        self.device_manager = DeviceManager(Dispatcher(self.device_detected),
                self.job_manager)
        self.device_manager.start()


        ####################### Location View ########################
        QObject.connect(self.location_view,
                SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        QObject.connect(self.location_view,
                SIGNAL('umount_device()'),
                        self.device_manager.umount_device)

        ####################### Vanity ########################
        self.vanity_template  = _('<p>For help see the: <a href="%s">User Manual</a>'
                '<br>')%'http://calibre-ebook.com/user_manual'
        self.vanity_template += _('<b>%s</b>: %s by <b>Kovid Goyal '
            '%%(version)s</b><br>%%(device)s</p>')%(__appname__, __version__)
        self.latest_version = ' '
        self.vanity.setText(self.vanity_template%dict(version=' ', device=' '))
        self.device_info = ' '
        if not opts.no_update_check:
            self.update_checker = CheckForUpdates(self)
            QObject.connect(self.update_checker,
                    SIGNAL('update_found(PyQt_PyObject)'), self.update_found)
            self.update_checker.start(2000)
        ####################### Status Bar #####################
        self.status_bar = StatusBar(self.jobs_dialog, self.system_tray_icon)
        self.setStatusBar(self.status_bar)
        QObject.connect(self.job_manager, SIGNAL('job_added(int)'),
                self.status_bar.job_added, Qt.QueuedConnection)
        QObject.connect(self.job_manager, SIGNAL('job_done(int)'),
                self.status_bar.job_done, Qt.QueuedConnection)
        QObject.connect(self.status_bar, SIGNAL('show_book_info()'),
                self.show_book_info)
        QObject.connect(self.status_bar, SIGNAL('files_dropped(PyQt_PyObject,PyQt_PyObject)'),
                self.files_dropped_on_book)
        ####################### Setup Toolbar #####################
        md = QMenu()
        md.addAction(_('Edit metadata individually'))
        md.addSeparator()
        md.addAction(_('Edit metadata in bulk'))
        md.addSeparator()
        md.addAction(_('Download metadata and covers'))
        md.addAction(_('Download only metadata'))
        md.addAction(_('Download only covers'))
        md.addAction(_('Download only social metadata'))
        self.metadata_menu = md
        self.add_menu = QMenu()
        self.add_menu.addAction(_('Add books from a single directory'))
        self.add_menu.addAction(_('Add books from directories, including '
            'sub-directories (One book per directory, assumes every ebook '
            'file is the same book in a different format)'))
        self.add_menu.addAction(_('Add books from directories, including '
            'sub directories (Multiple books per directory, assumes every '
            'ebook file is a different book)'))
        self.add_menu.addAction(_('Add Empty book. (Book entry with no '
            'formats)'))
        self.action_add.setMenu(self.add_menu)
        QObject.connect(self.action_add, SIGNAL("triggered(bool)"),
                self.add_books)
        QObject.connect(self.add_menu.actions()[0], SIGNAL("triggered(bool)"),
                self.add_books)
        QObject.connect(self.add_menu.actions()[1], SIGNAL("triggered(bool)"),
                self.add_recursive_single)
        QObject.connect(self.add_menu.actions()[2], SIGNAL("triggered(bool)"),
                self.add_recursive_multiple)
        QObject.connect(self.add_menu.actions()[3], SIGNAL('triggered(bool)'),
                self.add_empty)
        QObject.connect(self.action_del, SIGNAL("triggered(bool)"),
                self.delete_books)
        QObject.connect(self.action_edit, SIGNAL("triggered(bool)"),
                self.edit_metadata)
        self.__em1__ = partial(self.edit_metadata, bulk=False)
        QObject.connect(md.actions()[0], SIGNAL('triggered(bool)'),
                self.__em1__)
        self.__em2__ = partial(self.edit_metadata, bulk=True)
        QObject.connect(md.actions()[2], SIGNAL('triggered(bool)'),
                self.__em2__)
        self.__em3__ = partial(self.download_metadata, covers=True)
        QObject.connect(md.actions()[4], SIGNAL('triggered(bool)'),
                self.__em3__)
        self.__em4__ = partial(self.download_metadata, covers=False)
        QObject.connect(md.actions()[5], SIGNAL('triggered(bool)'),
                self.__em4__)
        self.__em5__ = partial(self.download_metadata, covers=True,
                    set_metadata=False)
        QObject.connect(md.actions()[6], SIGNAL('triggered(bool)'),
                self.__em5__)
        self.__em6__ = partial(self.download_metadata, covers=False,
                    set_metadata=False, set_social_metadata=True)
        QObject.connect(md.actions()[7], SIGNAL('triggered(bool)'),
                self.__em6__)


        self.save_menu = QMenu()
        self.save_menu.addAction(_('Save to disk'))
        self.save_menu.addAction(_('Save to disk in a single directory'))
        self.save_menu.addAction(_('Save only %s format to disk')%
                prefs['output_format'].upper())
        self.save_sub_menu = SaveMenu(self)
        self.save_menu.addMenu(self.save_sub_menu)
        self.connect(self.save_sub_menu, SIGNAL('save_fmt(PyQt_PyObject)'),
                self.save_specific_format_disk)

        self.view_menu = QMenu()
        self.view_menu.addAction(_('View'))
        self.view_menu.addAction(_('View specific format'))
        self.action_view.setMenu(self.view_menu)

        self.delete_menu = QMenu()
        self.delete_menu.addAction(_('Remove selected books'))
        self.delete_menu.addAction(
                _('Remove files of a specific format from selected books..'))
        self.delete_menu.addAction(
                _('Remove all formats from selected books, except...'))
        self.delete_menu.addAction(
                _('Remove covers from selected books'))
        self.action_del.setMenu(self.delete_menu)
        QObject.connect(self.action_save, SIGNAL("triggered(bool)"),
                self.save_to_disk)
        QObject.connect(self.save_menu.actions()[0], SIGNAL("triggered(bool)"),
                self.save_to_disk)
        QObject.connect(self.save_menu.actions()[1], SIGNAL("triggered(bool)"),
                self.save_to_single_dir)
        QObject.connect(self.save_menu.actions()[2], SIGNAL("triggered(bool)"),
                self.save_single_format_to_disk)
        QObject.connect(self.action_view, SIGNAL("triggered(bool)"),
                self.view_book)
        QObject.connect(self.view_menu.actions()[0],
                SIGNAL("triggered(bool)"), self.view_book)
        QObject.connect(self.view_menu.actions()[1],
                SIGNAL("triggered(bool)"), self.view_specific_format)
        self.connect(self.action_open_containing_folder,
                SIGNAL('triggered(bool)'), self.view_folder)
        self.delete_menu.actions()[0].triggered.connect(self.delete_books)
        self.delete_menu.actions()[1].triggered.connect(self.delete_selected_formats)
        self.delete_menu.actions()[2].triggered.connect(self.delete_all_but_selected_formats)
        self.delete_menu.actions()[3].triggered.connect(self.delete_covers)

        self.action_open_containing_folder.setShortcut(Qt.Key_O)
        self.addAction(self.action_open_containing_folder)
        self.action_sync.setShortcut(Qt.Key_D)
        self.action_sync.setEnabled(True)
        self.create_device_menu()
        self.action_edit.setMenu(md)
        self.action_save.setMenu(self.save_menu)
        cm = QMenu()
        cm.addAction(_('Convert individually'))
        cm.addAction(_('Bulk convert'))
        self.action_convert.setMenu(cm)
        self._convert_single_hook = partial(self.convert_ebook, bulk=False)
        QObject.connect(cm.actions()[0],
                SIGNAL('triggered(bool)'), self._convert_single_hook)
        self._convert_bulk_hook = partial(self.convert_ebook, bulk=True)
        QObject.connect(cm.actions()[1],
                SIGNAL('triggered(bool)'), self._convert_bulk_hook)
        QObject.connect(self.action_convert,
                SIGNAL('triggered(bool)'), self.convert_ebook)
        self.convert_menu = cm

        pm = QMenu()
        ap = self.action_preferences
        pm.addAction(ap.icon(), ap.text())
        pm.addAction(QIcon(I('wizard.svg')), _('Run welcome wizard'))
        self.connect(pm.actions()[0], SIGNAL('triggered(bool)'),
                self.do_config)
        self.connect(pm.actions()[1], SIGNAL('triggered(bool)'),
                self.run_wizard)
        self.action_preferences.setMenu(pm)
        self.preferences_menu = pm

        self.tool_bar.widgetForAction(self.action_news).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_edit).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_sync).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_convert).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_save).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_add).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_view).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_del).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.widgetForAction(self.action_preferences).\
                setPopupMode(QToolButton.MenuButtonPopup)
        self.tool_bar.setContextMenuPolicy(Qt.PreventContextMenu)

        self.connect(self.preferences_action, SIGNAL('triggered(bool)'),
                self.do_config)
        self.connect(self.action_preferences, SIGNAL('triggered(bool)'),
                self.do_config)
        QObject.connect(self.advanced_search_button, SIGNAL('clicked(bool)'),
                self.do_advanced_search)

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
        self.connect(self.action_books_with_the_same_tags,
                     SIGNAL('triggered()'),
                     lambda : self.show_similar_books('tag'))
        self.connect(self.action_books_by_this_publisher, SIGNAL('triggered()'),
                     lambda : self.show_similar_books('publisher'))
        self.library_view.set_context_menu(self.action_edit, self.action_sync,
                                        self.action_convert, self.action_view,
                                        self.action_save,
                                        self.action_open_containing_folder,
                                        self.action_show_book_details,
                                        self.action_del,
                                        similar_menu=similar_menu)
        self.memory_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del)
        self.card_a_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del)
        self.card_b_view.set_context_menu(None, None, None,
                self.action_view, self.action_save, None, None, self.action_del)
        QObject.connect(self.library_view,
                SIGNAL('files_dropped(PyQt_PyObject)'),
                        self.files_dropped, Qt.QueuedConnection)
        for func, args in [
                             ('connect_to_search_box', (self.search,
                                 self.search_done)),
                             ('connect_to_book_display',
                                 (self.status_bar.book_info.show_data,)),
                             ]:
            for view in (self.library_view, self.memory_view, self.card_a_view, self.card_b_view):
                getattr(view, func)(*args)

        self.memory_view.connect_dirtied_signal(self.upload_booklists)
        self.card_a_view.connect_dirtied_signal(self.upload_booklists)
        self.card_b_view.connect_dirtied_signal(self.upload_booklists)

        self.show()
        if self.system_tray_icon.isVisible() and opts.start_in_tray:
            self.hide_windows()
        self.stack.setCurrentIndex(0)
        try:
            db = LibraryDatabase2(self.library_path)
        except Exception:
            import traceback
            error_dialog(self, _('Bad database location'),
                    _('Bad database location')+':'+self.library_path,
                    det_msg=traceback.format_exc()).exec_()
            fname = _('Calibre Library')
            if isinstance(fname, unicode):
                try:
                    fname = fname.encode(filesystem_encoding)
                except:
                    fname = 'Calibre Library'
            x = os.path.expanduser('~'+os.sep+fname)
            if not os.path.exists(x):
                os.makedirs(x)
            dir = unicode(QFileDialog.getExistingDirectory(self,
                            _('Choose a location for your ebook library.'),
                            x))
            if not dir:
                QCoreApplication.exit(1)
                raise SystemExit(1)
            else:
                self.library_path = dir
                db = LibraryDatabase2(self.library_path)
        self.library_view.set_database(db)
        prefs['library_path'] = self.library_path
        self.library_view.sortByColumn(*dynamic.get('sort_column',
            ('timestamp', Qt.DescendingOrder)))
        if not self.library_view.restore_column_widths():
            self.library_view.resizeColumnsToContents()
        self.library_view.resizeRowsToContents()
        self.search.setFocus(Qt.OtherFocusReason)
        self.cover_cache = CoverCache(self.library_path)
        self.cover_cache.start()
        self.library_view.model().cover_cache = self.cover_cache
        self.tags_view.setVisible(False)
        self.tag_match.setVisible(False)
        self.popularity.setVisible(False)
        self.tags_view.set_database(db, self.tag_match, self.popularity)
        self.connect(self.tags_view,
                SIGNAL('tags_marked(PyQt_PyObject, PyQt_PyObject)'),
                     self.search.search_from_tags)
        self.connect(self.status_bar.tag_view_button,
                SIGNAL('toggled(bool)'), self.toggle_tags_view)
        self.connect(self.search,
                SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'),
                     self.tags_view.model().reinit)
        self.connect(self.library_view.model(),
                SIGNAL('count_changed(int)'), self.location_view.count_changed)
        self.connect(self.library_view.model(), SIGNAL('count_changed(int)'),
                     self.tags_view.recount)
        self.connect(self.search, SIGNAL('cleared()'), self.tags_view.clear)
        self.library_view.model().count_changed()
        ########################### Cover Flow ################################
        self.cover_flow = None
        if CoverFlow is not None:
            self.cf_last_updated_at = None
            self.cover_flow_sync_timer = QTimer(self)
            self.cover_flow_sync_timer.timeout.connect(self.cover_flow_do_sync)
            self.cover_flow_sync_flag = True
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
            self.cover_flow.currentChanged.connect(self.sync_listview_to_cf)
            self.connect(self.status_bar.cover_flow_button,
                         SIGNAL('toggled(bool)'), self.toggle_cover_flow)
            self.connect(self.cover_flow, SIGNAL('stop()'),
                         self.status_bar.cover_flow_button.toggle)
            self.library_view.selectionModel().currentRowChanged.connect(
                    self.sync_cf_to_listview)
            self.db_images = DatabaseImages(self.library_view.model())
            self.cover_flow.setImages(self.db_images)
        else:
            self.status_bar.cover_flow_button.disable(pictureflowerror)

        self._calculated_available_height = min(max_available_height()-15,
                self.height())
        self.resize(self.width(), self._calculated_available_height)
        self.search.setMaximumWidth(self.width()-150)


        if config['autolaunch_server']:
            from calibre.library.server import start_threaded_server
            from calibre.library import server_config
            self.content_server = start_threaded_server(
                    db, server_config().parse())
            self.test_server_timer = QTimer.singleShot(10000, self.test_server)


        self.scheduler = Scheduler(self, self.library_view.model().db)
        self.action_news.setMenu(self.scheduler.news_menu)
        self.connect(self.action_news, SIGNAL('triggered(bool)'),
                self.scheduler.show_dialog)
        self.connect(self.scheduler, SIGNAL('delete_old_news(PyQt_PyObject)'),
                self.library_view.model().delete_books_by_id,
                Qt.QueuedConnection)
        self.connect(self.scheduler,
                SIGNAL('start_recipe_fetch(PyQt_PyObject)'),
                self.download_scheduled_recipe, Qt.QueuedConnection)
        self.library_view.verticalHeader().sectionClicked.connect(self.view_specific_book)

        for view in ('library', 'memory', 'card_a', 'card_b'):
            view = getattr(self, view+'_view')
            view.verticalHeader().sectionDoubleClicked.connect(self.view_specific_book)

        self.location_view.setCurrentIndex(self.location_view.model().index(0))

    def resizeEvent(self, ev):
        MainWindow.resizeEvent(self, ev)
        self.search.setMaximumWidth(self.width()-150)


    def create_device_menu(self):
        self._sync_menu = DeviceMenu(self)
        self.action_sync.setMenu(self._sync_menu)
        self.connect(self._sync_menu,
                SIGNAL('sync(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                self.dispatch_sync_event)
        self.connect(self.action_sync, SIGNAL('triggered(bool)'),
                self._sync_menu.trigger_default)

    def add_spare_server(self, *args):
        self.spare_servers.append(Server(limit=int(config['worker_limit']/2.0)))

    @property
    def spare_server(self):
        # Because of the use of the property decorator, we're called one
        # extra time. Ignore.
        if not hasattr(self, '__spare_server_property_limiter'):
            self.__spare_server_property_limiter = True
            return None
        try:
            QTimer.singleShot(1000, self.add_spare_server)
            return self.spare_servers.pop()
        except:
            pass

    def no_op(self, *args):
        pass

    def system_tray_icon_activated(self, r):
        if r == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide_windows()
            else:
                self.show_windows()

    def hide_windows(self):
        for window in QApplication.topLevelWidgets():
            if isinstance(window, (MainWindow, QDialog)) and \
                    window.isVisible():
                window.hide()
                setattr(window, '__systray_minimized', True)

    def show_windows(self):
        for window in QApplication.topLevelWidgets():
            if getattr(window, '__systray_minimized', False):
                window.show()
                setattr(window, '__systray_minimized', False)

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
                search = ['author:'+a.strip().replace('|', ',') \
                                for a in authors.split(',')]
                join = ' or '
        if search:
            self.search.set_search_string(join.join(search))



    def uncheck_cover_button(self, *args):
        self.status_bar.cover_flow_button.setChecked(False)

    def toggle_cover_flow(self, show):
        if config['separate_cover_flow']:
            if show:
                self.cover_flow.setCurrentSlide(self.library_view.currentIndex().row())
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
                    self.uncheck_cover_button)
                self.cf_dialog = d
                self.cover_flow_sync_timer.start(500)
            else:
                self.cover_flow_sync_timer.stop()
                idx = self.library_view.model().index(self.cover_flow.currentSlide(), 0)
                if idx.isValid():
                    sm = self.library_view.selectionModel()
                    sm.select(idx, sm.ClearAndSelect|sm.Rows)
                    self.library_view.setCurrentIndex(idx)
                cfd = getattr(self, 'cf_dialog', None)
                if cfd is not None:
                    self.cover_flow.setVisible(False)
                    cfd.hide()
                    self.cf_dialog = None
        else:
            if show:
                self.cover_flow.setCurrentSlide(self.library_view.currentIndex().row())
                self.library_view.setCurrentIndex(
                        self.library_view.currentIndex())
                self.cover_flow.setVisible(True)
                self.cover_flow.setFocus(Qt.OtherFocusReason)
                #self.status_bar.book_info.book_data.setMaximumHeight(100)
                #self.status_bar.setMaximumHeight(120)
                self.library_view.scrollTo(self.library_view.currentIndex())
                self.cover_flow_sync_timer.start(500)
            else:
                self.cover_flow_sync_timer.stop()
                self.cover_flow.setVisible(False)
                idx = self.library_view.model().index(self.cover_flow.currentSlide(), 0)
                if idx.isValid():
                    sm = self.library_view.selectionModel()
                    sm.select(idx, sm.ClearAndSelect|sm.Rows)
                    self.library_view.setCurrentIndex(idx)
                #self.status_bar.book_info.book_data.setMaximumHeight(1000)
            #self.resize(self.width(), self._calculated_available_height)
            #self.setMaximumHeight(available_height())

    def toggle_tags_view(self, show):
        if show:
            self.tags_view.setVisible(True)
            self.tag_match.setVisible(True)
            self.popularity.setVisible(True)
            self.tags_view.setFocus(Qt.OtherFocusReason)
        else:
            self.tags_view.setVisible(False)
            self.tag_match.setVisible(False)
            self.popularity.setVisible(False)

    def search_done(self, view, ok):
        if view is self.current_view():
            self.search.search_done(ok)

    def sync_cf_to_listview(self, current, previous):
        if self.cover_flow_sync_flag and self.cover_flow.isVisible() and \
                self.cover_flow.currentSlide() != current.row():
            self.cover_flow.setCurrentSlide(current.row())
        self.cover_flow_sync_flag = True

    def cover_flow_do_sync(self):
        self.cover_flow_sync_flag = True
        try:
            if self.cover_flow.isVisible() and self.cf_last_updated_at is not None and \
                time.time() - self.cf_last_updated_at > 0.5:
                self.cf_last_updated_at = None
                row = self.cover_flow.currentSlide()
                m = self.library_view.model()
                index = m.index(row, 0)
                if self.library_view.currentIndex().row() != row and index.isValid():
                    self.cover_flow_sync_flag = False
                    sm = self.library_view.selectionModel()
                    sm.select(index, sm.ClearAndSelect|sm.Rows)
                    self.library_view.setCurrentIndex(index)
        except:
            pass


    def sync_listview_to_cf(self, row):
        self.cf_last_updated_at = time.time()

    def another_instance_wants_to_talk(self):
        try:
            msg = self.listener.queue.get_nowait()
        except Empty:
            return
        if msg.startswith('launched:'):
            argv = eval(msg[len('launched:'):])
            if len(argv) > 1:
                path = os.path.abspath(argv[1])
                if os.access(path, os.R_OK):
                    self.add_filesystem_book(path)
            self.setWindowState(self.windowState() & \
                    ~Qt.WindowMinimized|Qt.WindowActive)
            self.show_windows()
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
            return self.card_a_view
        if idx == 3:
            return self.card_b_view

    def booklists(self):
        return self.memory_view.model().db, self.card_a_view.model().db, self.card_b_view.model().db



    ########################## Connect to device ##############################

    def save_device_view_settings(self):
        model = self.location_view.model()
        self.memory_view.write_settings()
        for x in range(model.rowCount()):
            if x > 1:
                if model.location_for_row(x) == 'carda':
                    self.card_a_view.write_settings()
                elif model.location_for_row(x) == 'cardb':
                    self.card_b_view.write_settings()

    def device_detected(self, connected):
        '''
        Called when a device is connected to the computer.
        '''
        if connected:
            self.device_manager.get_device_information(\
                    Dispatcher(self.info_read))
            self.set_default_thumbnail(\
                    self.device_manager.device.THUMBNAIL_HEIGHT)
            self.status_bar.showMessage(_('Device: ')+\
                self.device_manager.device.__class__.get_gui_name()+\
                        _(' detected.'), 3000)
            self.device_connected = True
            self._sync_menu.enable_device_actions(True, self.device_manager.device.card_prefix())
            self.location_view.model().device_connected(self.device_manager.device)
        else:
            self.save_device_view_settings()
            self.device_connected = False
            self._sync_menu.enable_device_actions(False)
            self.location_view.model().update_devices()
            self.vanity.setText(self.vanity_template%\
                    dict(version=self.latest_version, device=' '))
            self.device_info = ' '
            if self.current_view() != self.library_view:
                self.status_bar.reset_info()
                self.location_view.setCurrentIndex(self.location_view.model().index(0))

    def info_read(self, job):
        '''
        Called once device information has been read.
        '''
        if job.failed:
            return self.device_job_exception(job)
        info, cp, fs = job.result
        self.location_view.model().update_devices(cp, fs)
        self.device_info = _('Connected ')+info[0]
        self.vanity.setText(self.vanity_template%\
                dict(version=self.latest_version, device=self.device_info))

        self.device_manager.books(Dispatcher(self.metadata_downloaded))

    def metadata_downloaded(self, job):
        '''
        Called once metadata has been read for all books on the device.
        '''
        if job.failed:
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
        mainlist, cardalist, cardblist = job.result
        self.memory_view.set_database(mainlist)
        self.memory_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.card_a_view.set_database(cardalist)
        self.card_a_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.card_b_view.set_database(cardblist)
        self.card_b_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        for view in (self.memory_view, self.card_a_view, self.card_b_view):
            view.sortByColumn(3, Qt.DescendingOrder)
            view.read_settings()
            if not view.restore_column_widths():
                view.resizeColumnsToContents()
            view.resizeRowsToContents()
            view.resize_on_select = not view.isVisible()
        self.sync_news()
    ############################################################################



    ################################# Add books ################################

    def add_recursive(self, single):
        root = choose_dir(self, 'recursive book import root dir dialog',
                          'Select root folder')
        if not root:
            return
        from calibre.gui2.add import Adder
        self._adder = Adder(self,
                self.library_view.model().db,
                Dispatcher(self._files_added), spare_server=self.spare_server)
        self._adder.add_recursive(root, single)

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

    def add_empty(self, checked):
        '''
        Add an empty book item to the library. This does not import any formats
        from a book file.
        '''
        num, ok = QInputDialog.getInt(self, _('How many empty books?'),
                _('How many empty books should be added?'), 1, 1, 100)
        if ok:
            from calibre.ebooks.metadata import MetaInformation
            for x in xrange(num):
                self.library_view.model().db.import_book(MetaInformation(None), [])
            self.library_view.model().books_added(num)

    def files_dropped(self, paths):
        to_device = self.stack.currentIndex() != 0
        self._add_books(paths, to_device)

    def files_dropped_on_book(self, event, paths):
        accept = False
        if self.current_view() is not self.library_view:
            return
        db = self.library_view.model().db
        current_idx = self.library_view.currentIndex()
        if not current_idx.isValid(): return
        cid = db.id(current_idx.row())
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext:
                ext = ext[1:]
            if ext in IMAGE_EXTENSIONS:
                pmap = QPixmap()
                pmap.load(path)
                if not pmap.isNull():
                    accept = True
                    db.set_cover(cid, pmap)
            elif ext in BOOK_EXTENSIONS:
                db.add_format_with_hooks(cid, ext, path, index_is_id=True)
                accept = True
        if accept:
            event.accept()
            self.cover_cache.refresh([cid])
            self.library_view.model().current_changed(current_idx, current_idx)

    def add_filesystem_book(self, path):
        if os.access(path, os.R_OK):
            books = [os.path.abspath(path)]
            to_device = self.stack.currentIndex() != 0
            self._add_books(books, to_device)
            if to_device:
                self.status_bar.showMessage(\
                        _('Uploading books to device.'), 2000)

    def add_books(self, checked):
        '''
        Add books from the local filesystem to either the library or the device.
        '''
        filters = [
                        (_('Books'), BOOK_EXTENSIONS),
                        (_('EPUB Books'), ['epub']),
                        (_('LRF Books'), ['lrf']),
                        (_('HTML Books'), ['htm', 'html', 'xhtm', 'xhtml']),
                        (_('LIT Books'), ['lit']),
                        (_('MOBI Books'), ['mobi', 'prc', 'azw']),
                        (_('Text books'), ['txt', 'rtf']),
                        (_('PDF Books'), ['pdf']),
                        (_('Comics'), ['cbz', 'cbr', 'cbc']),
                        (_('Archives'), ['zip', 'rar']),
                        ]
        to_device = self.stack.currentIndex() != 0
        if to_device:
            filters = [(_('Supported books'), self.device_manager.device.FORMATS)]

        books = choose_files(self, 'add books dialog dir', 'Select books',
                             filters=filters)
        if not books:
            return
        self._add_books(books, to_device)


    def _add_books(self, paths, to_device, on_card=None):
        if on_card is None:
            on_card = 'carda' if self.stack.currentIndex() == 2 else 'cardb' if self.stack.currentIndex() == 3 else None
        if not paths:
            return
        from calibre.gui2.add import Adder
        self.__adder_func = partial(self._files_added, on_card=on_card)
        self._adder = Adder(self,
                None if to_device else self.library_view.model().db,
                Dispatcher(self.__adder_func), spare_server=self.spare_server)
        self._adder.add(paths)

    def _files_added(self, paths=[], names=[], infos=[], on_card=None):
        if paths:
            self.upload_books(paths,
                                list(map(ascii_filename, names)),
                                infos, on_card=on_card)
            self.status_bar.showMessage(
                    _('Uploading books to device.'), 2000)
        if self._adder.number_of_books_added > 0:
            self.library_view.model().books_added(self._adder.number_of_books_added)
            if hasattr(self, 'db_images'):
                self.db_images.reset()
        if self._adder.critical:
            det_msg = []
            for name, log in self._adder.critical.items():
                det_msg.append(name+'\n'+log)
            warning_dialog(self, _('Failed to read metadata'),
                    _('Failed to read metadata from the following')+':',
                    det_msg='\n\n'.join(det_msg), show=True)

        self._adder.cleanup()
        self._adder = None


    ############################################################################

    ############################### Delete books ###############################

    def _get_selected_formats(self, msg):
        from calibre.gui2.dialogs.select_formats import SelectFormats
        fmts = self.library_view.model().db.all_formats()
        d = SelectFormats([x.lower() for x in fmts], msg, parent=self)
        if d.exec_() != d.Accepted:
            return None
        return d.selected_formats

    def _get_selected_ids(self, err_title=_('Cannot delete')):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, err_title, _('No book selected'))
            d.exec_()
            return set([])
        return set(map(self.library_view.model().id, rows))

    def delete_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            _('Choose formats to be deleted'))
        if not fmts:
            return
        for id in ids:
            for fmt in fmts:
                self.library_view.model().db.remove_format(id, fmt,
                        index_is_id=True, notify=False)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())

    def delete_all_but_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            '<p>'+_('Choose formats <b>not</b> to be deleted'))
        if fmts is None:
            return
        for id in ids:
            bfmts = self.library_view.model().db.formats(id, index_is_id=True)
            if bfmts is None:
                continue
            bfmts = set([x.lower() for x in bfmts.split(',')])
            rfmts = bfmts - set(fmts)
            for fmt in rfmts:
                self.library_view.model().db.remove_format(id, fmt,
                        index_is_id=True, notify=False)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())


    def delete_covers(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        for id in ids:
            self.library_view.model().db.remove_cover(id)
        self.library_view.model().refresh_ids(ids)
        self.library_view.model().current_changed(self.library_view.currentIndex(),
                self.library_view.currentIndex())

    def delete_books(self, *args):
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
            ci = view.currentIndex()
            row = None
            if ci.isValid():
                row = ci.row()
            view.model().delete_books(rows)
            if row is not None:
                ci = view.model().index(row, 0)
                if ci.isValid():
                    view.setCurrentIndex(ci)
                    sm = view.selectionModel()
                    sm.select(ci, sm.Select)
        else:
            if self.stack.currentIndex() == 1:
                view = self.memory_view
            elif self.stack.currentIndex() == 2:
                view = self.card_a_view
            else:
                view = self.card_b_view
            paths = view.model().paths(rows)
            job = self.remove_paths(paths)
            self.delete_memory[job] = (paths, view.model())
            view.model().mark_for_deletion(job, rows)
            self.status_bar.showMessage(_('Deleting books from device.'), 1000)

    def remove_paths(self, paths):
        return self.device_manager.delete_books(\
                Dispatcher(self.books_deleted), paths)

    def books_deleted(self, job):
        '''
        Called once deletion is done on the device
        '''
        for view in (self.memory_view, self.card_a_view, self.card_b_view):
            view.model().deletion_done(job, job.failed)
        if job.failed:
            self.device_job_exception(job)
            return

        if self.delete_memory.has_key(job):
            paths, model = self.delete_memory.pop(job)
            self.device_manager.remove_books_from_metadata(paths,
                    self.booklists())
            model.paths_deleted(paths)
            self.upload_booklists()

    ############################################################################

    ############################### Edit metadata ##############################

    def download_metadata(self, checked, covers=True, set_metadata=True,
            set_social_metadata=None):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot download metadata'),
                             _('No books selected'))
            d.exec_()
            return
        db = self.library_view.model().db
        ids = [db.id(row.row()) for row in rows]
        if set_social_metadata is None:
            get_social_metadata = config['get_social_metadata']
        else:
            get_social_metadata = set_social_metadata
        from calibre.gui2.metadata import DownloadMetadata
        self._download_book_metadata = DownloadMetadata(db, ids,
                get_covers=covers, set_metadata=set_metadata,
                get_social_metadata=get_social_metadata)
        self._download_book_metadata.start()
        if set_social_metadata is not None and set_social_metadata:
            x = _('social metadata')
        else:
            x = _('covers') if covers and not set_metadata else _('metadata')
        self.progress_indicator.start(
            _('Downloading %s for %d book(s)')%(x, len(ids)))
        self._book_metadata_download_check = QTimer(self)
        self.connect(self._book_metadata_download_check,
                SIGNAL('timeout()'), self.book_metadata_download_check,
                Qt.QueuedConnection)
        self._book_metadata_download_check.start(100)

    def book_metadata_download_check(self):
        if self._download_book_metadata.is_alive():
            return
        self._book_metadata_download_check.stop()
        self.progress_indicator.stop()
        cr = self.library_view.currentIndex().row()
        x = self._download_book_metadata
        self._download_book_metadata = None
        if x.exception is None:
            self.library_view.model().refresh_ids(
                x.updated, cr)
            if x.failures:
                details = ['%s: %s'%(title, reason) for title,
                        reason in x.failures.values()]
                details = '%s\n'%('\n'.join(details))
                warning_dialog(self, _('Failed to download some metadata'),
                    _('Failed to download metadata for the following:'),
                    det_msg=details).exec_()
        else:
            err = _('Failed to download metadata:')
            error_dialog(self, _('Error'), err, det_msg=x.tb).exec_()


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
            self._metadata_view_id = self.library_view.model().db.id(row.row())
            d = MetadataSingleDialog(self, row.row(),
                                    self.library_view.model().db,
                                    accepted_callback=accepted,
                                    cancel_all=rows.index(row) < len(rows)-1)
            self.connect(d, SIGNAL('view_format(PyQt_PyObject)'),
                    self.metadata_view_format)
            d.exec_()
            if d.cancel_all:
                break
        if rows:
            current = self.library_view.currentIndex()
            self.library_view.model().current_changed(current, previous)

    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in \
                self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot edit metadata'),
                    _('No books selected'))
            d.exec_()
            return
        if MetadataBulkDialog(self, rows,
                self.library_view.model().db).changed:
            self.library_view.model().resort(reset=False)
            self.library_view.model().research()

    ############################################################################


    ############################## Save to disk ################################
    def save_single_format_to_disk(self, checked):
        self.save_to_disk(checked, False, prefs['output_format'])

    def save_specific_format_disk(self, fmt):
        self.save_to_disk(False, False, fmt)

    def save_to_single_dir(self, checked):
        self.save_to_disk(checked, True)

    def save_to_disk(self, checked, single_dir=False, single_format=None):
        rows = self.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self, _('Cannot save to disk'),
                    _('No books selected'), show=True)
        path = choose_dir(self, 'save to disk dialog',
                _('Choose destination directory'))
        if not path:
            return

        if self.current_view() is self.library_view:
            from calibre.gui2.add import Saver
            from calibre.library.save_to_disk import config
            opts = config().parse()
            if single_format is not None:
                opts.formats = single_format
            if single_dir:
                opts.template = opts.template.split('/')[-1].strip()
                if not opts.template:
                    opts.template = '{title} - {authors}'
            self._saver = Saver(self, self.library_view.model().db,
                    Dispatcher(self._books_saved), rows, path, opts,
                    spare_server=self.spare_server)

        else:
            paths = self.current_view().model().paths(rows)
            self.device_manager.save_books(
                    Dispatcher(self.books_saved), paths, path)


    def _books_saved(self, path, failures, error):
        self._saver = None
        if error:
            return error_dialog(self, _('Error while saving'),
                    _('There was an error while saving.'),
                    error, show=True)
        if failures:
            failures = [u'%s\n\t%s'%
                    (title, '\n\t'.join(err.splitlines())) for title, err in
                    failures]

            warning_dialog(self, _('Could not save some books'),
            _('Could not save some books') + ', ' +
            _('Click the show details button to see which ones.'),
            u'\n\n'.join(failures), show=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def books_saved(self, job):
        if job.failed:
            return self.device_job_exception(job)

    ############################################################################

    ############################### Fetch news #################################

    def download_scheduled_recipe(self, arg):
        func, args, desc, fmt, temp_files = \
                fetch_scheduled_recipe(arg)
        job = self.job_manager.run_job(
                Dispatcher(self.scheduled_recipe_fetched), func, args=args,
                           description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, arg)
        self.status_bar.showMessage(_('Fetching news from ')+arg['title'], 2000)

    def scheduled_recipe_fetched(self, job):
        temp_files, fmt, arg = self.conversion_jobs.pop(job)
        pt = temp_files[0]
        if job.failed:
            self.scheduler.recipe_download_failed(arg)
            return self.job_exception(job)
        id = self.library_view.model().add_news(pt.name, arg)
        self.library_view.model().reset()
        sync = dynamic.get('news_to_be_synced', set([]))
        sync.add(id)
        dynamic.set('news_to_be_synced', sync)
        self.scheduler.recipe_downloaded(arg)
        self.status_bar.showMessage(arg['title'] + _(' fetched.'), 3000)
        self.email_news(id)
        self.sync_news()

    ############################################################################

    ############################### Convert ####################################

    def auto_convert(self, book_ids, on_card, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted, extra_job_args=[on_card])

    def auto_convert_mail(self, to, fmts, delete_from_library, book_ids, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_mail,
                extra_job_args=[delete_from_library, to, fmts])

    def auto_convert_news(self, book_ids, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_news)

    def get_books_for_conversion(self):
        rows = [r.row() for r in \
                self.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot convert'),
                    _('No books selected'))
            d.exec_()
            return None
        return [self.library_view.model().db.id(r) for r in rows]

    def convert_ebook(self, checked, bulk=None):
        book_ids = self.get_books_for_conversion()
        if book_ids is None: return
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        num = 0
        if bulk or (bulk is None and len(book_ids) > 1):
            self.__bulk_queue = convert_bulk_ebook(self, self.queue_convert_jobs,
                self.library_view.model().db, book_ids,
                out_format=prefs['output_format'], args=(rows, previous,
                    self.book_converted))
            if self.__bulk_queue is None:
                return
            num = len(self.__bulk_queue.book_ids)
        else:
            jobs, changed, bad = convert_single_ebook(self,
                self.library_view.model().db, book_ids, out_format=prefs['output_format'])
            self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                    self.book_converted)
            num = len(jobs)

        if num > 0:
            self.status_bar.showMessage(_('Starting conversion of %d book(s)') %
                num, 2000)

    def queue_convert_jobs(self, jobs, changed, bad, rows, previous,
            converted_func, extra_job_args=[]):
        for func, args, desc, fmt, id, temp_files in jobs:
            if id not in bad:
                job = self.job_manager.run_job(Dispatcher(converted_func),
                                            func, args=args, description=desc)
                args = [temp_files, fmt, id]+extra_job_args
                self.conversion_jobs[job] = tuple(args)

        if changed:
            self.library_view.model().refresh_rows(rows)
            current = self.library_view.currentIndex()
            self.library_view.model().current_changed(current, previous)

    def book_auto_converted(self, job):
        temp_files, fmt, book_id, on_card = self.conversion_jobs[job]
        self.book_converted(job)
        self.sync_to_device(on_card, False, specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_mail(self, job):
        temp_files, fmt, book_id, delete_from_library, to, fmts = self.conversion_jobs[job]
        self.book_converted(job)
        self.send_by_mail(to, fmts, delete_from_library, specific_format=fmt, send_ids=[book_id], do_auto_convert=False)

    def book_auto_converted_news(self, job):
        temp_files, fmt, book_id = self.conversion_jobs[job]
        self.book_converted(job)
        self.sync_news(send_ids=[book_id], do_auto_convert=False)

    def book_converted(self, job):
        temp_files, fmt, book_id = self.conversion_jobs.pop(job)[:3]
        try:
            if job.failed:
                self.job_exception(job)
                return
            data = open(temp_files[-1].name, 'rb')
            self.library_view.model().db.add_format(book_id, \
                    fmt, data, index_is_id=True)
            data.close()
            self.status_bar.showMessage(job.description + \
                    (' completed'), 2000)
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
        fmt_path = self.library_view.model().db.format_abspath(row, format)
        if fmt_path:
            self._view_file(fmt_path)

    def metadata_view_format(self, fmt):
        fmt_path = self.library_view.model().db.\
                format_abspath(self._metadata_view_id,
                        fmt, index_is_id=True)
        if fmt_path:
            self._view_file(fmt_path)


    def book_downloaded_for_viewing(self, job):
        if job.failed:
            self.device_job_exception(job)
            return
        self._view_file(job.result)

    def _launch_viewer(self, name=None, viewer='ebook-viewer', internal=True):
        self.setCursor(Qt.BusyCursor)
        try:
            if internal:
                args = [viewer]
                if isosx and 'ebook' in viewer:
                    args.append('--raise-window')
                if name is not None:
                    args.append(name)
                self.job_manager.launch_gui_app(viewer,
                        kwargs=dict(args=args))
            else:
                paths = os.environ.get('LD_LIBRARY_PATH',
                            '').split(os.pathsep)
                paths = [x for x in paths if x]
                if isfrozen and islinux and paths:
                    npaths = [x for x in paths if x != sys.frozen_path]
                    os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(npaths)
                QDesktopServices.openUrl(QUrl.fromLocalFile(name))#launch(name)
                if isfrozen and islinux and paths:
                    os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(paths)
                time.sleep(2) # User feedback
        finally:
            self.unsetCursor()

    def _view_file(self, name):
        ext = os.path.splitext(name)[1].upper().replace('.', '')
        viewer = 'lrfviewer' if ext == 'LRF' else 'ebook-viewer'
        internal = ext in config['internally_viewed_formats']
        self._launch_viewer(name, viewer, internal)

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
                d = error_dialog(self, _('Cannot open folder'),
                        _('No book selected'))
                d.exec_()
                return
        for row in rows:
            path = self.library_view.model().db.abspath(row.row())
            QDesktopServices.openUrl(QUrl('file:'+path))


    def view_book(self, triggered):
        rows = self.current_view().selectionModel().selectedRows()
        self._view_books(rows)

    def view_specific_book(self, index):
        self._view_books([index])

    def _view_books(self, rows):
        if not rows or len(rows) == 0:
            self._launch_viewer()
            return

        if len(rows) >= 3:
            if not question_dialog(self, _('Multiple Books Selected'),
                _('You are attempting to open %d books. Opening too many '
                'books at once can be slow and have a negative effect on the '
                'responsiveness of your computer. Once started the process '
                'cannot be stopped until complete. Do you wish to continue?'
                )% len(rows)):
                    return

        if self.current_view() is self.library_view:
            for row in rows:
                if hasattr(row, 'row'):
                    row = row.row()

                formats = self.library_view.model().db.formats(row)
                title   = self.library_view.model().db.title(row)
                if not formats:
                    error_dialog(self, _('Cannot view'),
                        _('%s has no available formats.')%(title,), show=True)
                    continue

                formats = formats.upper().split(',')


                in_prefs = False
                for format in prefs['input_format_order']:
                    if format in formats:
                        in_prefs = True
                        self.view_format(row, format)
                        break
                if not in_prefs:
                    self.view_format(row, formats[0])
        else:
            paths = self.current_view().model().paths(rows)
            for path in paths:
                pt = PersistentTemporaryFile('_viewer_'+\
                        os.path.splitext(path)[1])
                self.persistent_files.append(pt)
                pt.close()
                self.device_manager.view_book(\
                        Dispatcher(self.book_downloaded_for_viewing),
                                              path, pt.name)


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
            d = error_dialog(self, _('Cannot configure'),
                    _('Cannot configure while there are running jobs.'))
            d.exec_()
            return
        d = ConfigDialog(self, self.library_view.model().db,
                server=self.content_server)
        d.exec_()
        self.content_server = d.server
        if d.result() == d.Accepted:
            self.tool_bar.setIconSize(config['toolbar_icon_size'])
            self.search.search_as_you_type(config['search_as_you_type'])
            self.tool_bar.setToolButtonStyle(
                    Qt.ToolButtonTextUnderIcon if \
                            config['show_text_in_toolbar'] else \
                            Qt.ToolButtonIconOnly)
            self.save_menu.actions()[2].setText(
                _('Save only %s format to disk')%
                prefs['output_format'].upper())
            self.library_view.model().read_config()
            self.create_device_menu()


            if not patheq(self.library_path, d.database_location):
                newloc = d.database_location
                move_library(self.library_path, newloc, self,
                        self.library_moved)


    def library_moved(self, newloc):
        if newloc is None: return
        db = LibraryDatabase2(newloc)
        self.library_view.set_database(db)
        self.status_bar.clearMessage()
        self.search.clear_to_help()
        self.status_bar.reset_info()
        self.library_view.sortByColumn(3, Qt.DescendingOrder)
        self.library_view.model().count_changed()

    ############################################################################

    ################################ Book info #################################

    def show_book_info(self, *args):
        if self.current_view() is not self.library_view:
            error_dialog(self, _('No detailed info available'),
                _('No detailed information is available for books '
                  'on the device.')).exec_()
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
        page = 0 if location == 'library' else 1 if location == 'main' else 2 if location == 'carda' else 3
        self.stack.setCurrentIndex(page)
        view = self.memory_view if page == 1 else \
                self.card_a_view if page == 2 else \
                self.card_b_view if page == 3 else None
        if view:
            if view.resize_on_select:
                view.resizeRowsToContents()
                if not view.restore_column_widths():
                    view.resizeColumnsToContents()
                view.resize_on_select = False
        self.status_bar.reset_info()
        if location == 'library':
            self.action_edit.setEnabled(True)
            self.action_convert.setEnabled(True)
            self.view_menu.actions()[1].setEnabled(True)
            self.action_open_containing_folder.setEnabled(True)
            self.action_sync.setEnabled(True)
            self.status_bar.tag_view_button.setEnabled(True)
            self.status_bar.cover_flow_button.setEnabled(True)
            for action in list(self.delete_menu.actions())[1:]:
                action.setEnabled(True)
        else:
            self.action_edit.setEnabled(False)
            self.action_convert.setEnabled(False)
            self.view_menu.actions()[1].setEnabled(False)
            self.action_open_containing_folder.setEnabled(False)
            self.action_sync.setEnabled(False)
            self.status_bar.tag_view_button.setEnabled(False)
            self.status_bar.cover_flow_button.setEnabled(False)
            for action in list(self.delete_menu.actions())[1:]:
                action.setEnabled(False)


    def device_job_exception(self, job):
        '''
        Handle exceptions in threaded device jobs.
        '''
        try:
            if 'Could not read 32 bytes on the control bus.' in \
                    unicode(job.details):
                error_dialog(self, _('Error talking to device'),
                             _('There was a temporary error talking to the '
                             'device. Please unplug and reconnect the device '
                             'and or reboot.')).show()
                return
        except:
            pass
        try:
            prints(job.details, file=sys.stderr)
        except:
            pass
        if not self.device_error_dialog.isVisible():
            self.device_error_dialog.setDetailedText(job.details)
            self.device_error_dialog.show()

    def job_exception(self, job):
        if not hasattr(self, '_modeless_dialogs'):
            self._modeless_dialogs = []
        if self.isVisible():
            for x in list(self._modeless_dialogs):
                if not x.isVisible():
                    self._modeless_dialogs.remove(x)
        try:
            if 'calibre.ebooks.DRMError' in job.details:
                d = error_dialog(self, _('Conversion Error'),
                    _('<p>Could not convert: %s<p>It is a '
                      '<a href="%s">DRM</a>ed book. You must first remove the '
                      'DRM using third party tools.')%\
                        (job.description.split(':')[-1],
                            'http://wiki.mobileread.com/wiki/DRM'))
                d.setModal(False)
                d.show()
                self._modeless_dialogs.append(d)
                return
            if 'calibre.web.feeds.input.RecipeDisabled' in job.details:
                msg = job.details
                msg = msg[msg.find('calibre.web.feeds.input.RecipeDisabled:'):]
                msg = msg.partition(':')[-1]
                d = error_dialog(self, _('Recipe Disabled'),
                    '<p>%s</p>'%msg)
                d.setModal(False)
                d.show()
                self._modeless_dialogs.append(d)
                return
        except:
            pass
        if job.killed:
            return
        try:
            prints(job.details, file=sys.stderr)
        except:
            pass
        d = error_dialog(self, _('Conversion Error'),
                _('<b>Failed</b>')+': '+unicode(job.description),
                det_msg=job.details)
        d.setModal(False)
        d.show()
        self._modeless_dialogs.append(d)


    def initialize_database(self):
        self.library_path = prefs['library_path']
        if self.library_path is None: # Need to migrate to new database layout
            base = os.path.expanduser('~')
            if iswindows:
                from calibre import plugins
                from PyQt4.Qt import QDir
                base = plugins['winutil'][0].special_folder_path(
                        plugins['winutil'][0].CSIDL_PERSONAL)
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
                self.library_path = os.path.expanduser('~/CalibreLibrary')
                error_dialog(self, _('Invalid library location'),
                     _('Could not access %s. Using %s as the library.')%
                     (repr(self.library_path), repr(self.library_path))
                             ).exec_()
                if not os.path.exists(self.library_path):
                    os.makedirs(self.library_path)


    def read_settings(self):
        self.initialize_database()
        geometry = config['main_window_geometry']
        if geometry is not None:
            self.restoreGeometry(geometry)
        self.tool_bar.setIconSize(config['toolbar_icon_size'])
        self.tool_bar.setToolButtonStyle(
                Qt.ToolButtonTextUnderIcon if \
                    config['show_text_in_toolbar'] else \
                    Qt.ToolButtonIconOnly)


    def write_settings(self):
        config.set('main_window_geometry', self.saveGeometry())
        dynamic.set('sort_column', self.library_view.model().sorted_on)
        self.library_view.write_settings()
        if self.device_connected:
            self.save_device_view_settings()

    def restart(self):
        self.quit(restart=True)

    def quit(self, checked=True, restart=False):
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
        MSG = _('is the result of the efforts of many volunteers from all '
                'over the world. If you find it useful, please consider '
                'donating to support its development.')
        HTML = u'''
        <html>
            <head>
                <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
                <title>Donate to support calibre</title>
            </head>
            <body style="background:white">
                <div><a href="http://calibre-ebook.com"><img style="border:0px"
                src="file://%s" alt="calibre" /></a></div>
                <p>Calibre %s</p>
                %s
            </body>
        </html>
        '''%(P('content_server/calibre_banner.png').replace(os.sep, '/'), MSG, BUTTON)
        pt = PersistentTemporaryFile('_donate.htm')
        pt.write(HTML.encode('utf-8'))
        pt.close()
        QDesktopServices.openUrl(QUrl.fromLocalFile(pt.name))


    def confirm_quit(self):
        if self.job_manager.has_jobs():
            msg = _('There are active jobs. Are you sure you want to quit?')
            if self.job_manager.has_device_jobs():
                msg = '<p>'+__appname__ + \
                      _(''' is communicating with the device!<br>
                      Quitting may cause corruption on the device.<br>
                      Are you sure you want to quit?''')+'</p>'

            d = QMessageBox(QMessageBox.Warning, _('WARNING: Active jobs'), msg,
                            QMessageBox.Yes|QMessageBox.No, self)
            d.setIconPixmap(QPixmap(I('dialog_warning.svg')))
            d.setDefaultButton(QMessageBox.No)
            if d.exec_() != QMessageBox.Yes:
                return False
        return True


    def shutdown(self, write_settings=True):
        if write_settings:
            self.write_settings()
        self.check_messages_timer.stop()
        self.update_checker.stop()
        self.listener.close()
        self.job_manager.server.close()
        while self.spare_servers:
            self.spare_servers.pop().close()
        self.device_manager.keep_going = False
        self.cover_cache.stop()
        self.hide_windows()
        self.cover_cache.terminate()
        self.emailer.stop()
        try:
            try:
                if self.content_server is not None:
                    self.content_server.exit()
            except:
                pass
            time.sleep(2)
        except KeyboardInterrupt:
            pass
        self.hide_windows()
        return True

    def run_wizard(self, *args):
        if self.confirm_quit():
            self.run_wizard_b4_shutdown = True
            self.restart_after_quit = True
            try:
                self.shutdown(write_settings=False)
            except:
                pass
            QApplication.instance().quit()



    def closeEvent(self, e):
        self.write_settings()
        if self.system_tray_icon.isVisible():
            if not dynamic['systray_msg'] and not isosx:
                info_dialog(self, 'calibre', 'calibre '+\
                        _('will keep running in the system tray. To close it, '
                        'choose <b>Quit</b> in the context menu of the '
                        'system tray.')).exec_()
                dynamic['systray_msg'] = True
            self.hide_windows()
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
        url = 'http://calibre-ebook.com/download_%s'%os
        self.latest_version = '<br>' + _('<span style="color:red; font-weight:bold">'
                'Latest version: <a href="%s">%s</a></span>')%(url, version)
        self.vanity.setText(self.vanity_template%\
                (dict(version=self.latest_version,
                      device=self.device_info)))
        self.vanity.update()
        if config.get('new_version_notification') and \
                dynamic.get('update to version %s'%version, True):
            if question_dialog(self, _('Update available'),
                    _('%s has been updated to version %s. '
                    'See the <a href="http://calibre-ebook.com/whats-new'
                    '">new features</a>. Visit the download pa'
                    'ge?')%(__appname__, version)):
                url = 'http://calibre-ebook.com/download_'+\
                    ('windows' if iswindows else 'osx' if isosx else 'linux')
                QDesktopServices.openUrl(QUrl(url))
            dynamic.set('update to version %s'%version, False)



