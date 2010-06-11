#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''The main GUI'''

import collections, datetime, os, shutil, sys, textwrap, time
from xml.parsers.expat import ExpatError
from Queue import Queue, Empty
from threading import Thread
from functools import partial
from PyQt4.Qt import Qt, SIGNAL, QObject, QUrl, QTimer, \
                     QModelIndex, QPixmap, QColor, QPainter, QMenu, QIcon, \
                     QDialog, QDesktopServices, \
                     QSystemTrayIcon, QApplication, QKeySequence, QAction, \
                     QMessageBox, QHelpEvent, QInputDialog,\
                     QThread, pyqtSignal
from PyQt4.QtSvg import QSvgRenderer

from calibre import  prints, patheq, strftime
from calibre.constants import __version__, __appname__, isfrozen, islinux, \
                    iswindows, isosx, filesystem_encoding, preferred_encoding
from calibre.utils.filenames import ascii_filename
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import prefs, dynamic
from calibre.utils.ipc.server import Server
from calibre.devices.errors import UserFeedback
from calibre.gui2 import warning_dialog, choose_files, error_dialog, \
                           question_dialog,\
                           pixmap_to_data, choose_dir, \
                           Dispatcher, gprefs, \
                           max_available_height, config, info_dialog, \
                           GetMetadata
from calibre.gui2.cover_flow import CoverFlowMixin
from calibre.gui2.widgets import ProgressIndicator, IMAGE_EXTENSIONS
from calibre.gui2.wizard import move_library
from calibre.gui2.dialogs.scheduler import Scheduler
from calibre.gui2.update import CheckForUpdates
from calibre.gui2.main_window import MainWindow
from calibre.gui2.main_ui import Ui_MainWindow
from calibre.gui2.device import DeviceManager, DeviceMenu, DeviceMixin, Emailer
from calibre.gui2.jobs import JobManager, JobsDialog, JobsButton
from calibre.gui2.dialogs.metadata_single import MetadataSingleDialog
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.gui2.tools import convert_single_ebook, convert_bulk_ebook, \
    fetch_scheduled_recipe, generate_catalog
from calibre.gui2.dialogs.config import ConfigDialog
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2.dialogs.book_info import BookInfo
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag, NavigableString
from calibre.library.database2 import LibraryDatabase2
from calibre.library.caches import CoverCache
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.init import ToolbarMixin, LibraryViewMixin, LayoutMixin
from calibre.gui2.search_box import SearchBoxMixin, SavedSearchBoxMixin
from calibre.gui2.search_restriction_mixin import SearchRestrictionMixin
from calibre.gui2.tag_view import TagBrowserMixin

class Listener(Thread): # {{{

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

# }}}

class SystemTrayIcon(QSystemTrayIcon): # {{{

    def __init__(self, icon, parent):
        QSystemTrayIcon.__init__(self, icon, parent)

    def event(self, ev):
        if ev.type() == ev.ToolTip:
            evh = QHelpEvent(ev)
            self.emit(SIGNAL('tooltip_requested(PyQt_PyObject)'),
                    (self, evh.globalPos()))
            return True
        return QSystemTrayIcon.event(self, ev)

# }}}

class Main(MainWindow, Ui_MainWindow, DeviceMixin, ToolbarMixin,
        TagBrowserMixin, CoverFlowMixin, LibraryViewMixin, SearchBoxMixin,
        SavedSearchBoxMixin, SearchRestrictionMixin, LayoutMixin):
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

        self.last_time = datetime.datetime.now()

    def __init__(self, opts, parent=None):
        MainWindow.__init__(self, opts, parent)
        self.opts = opts

    def initialize(self, library_path, db, listener, actions):
        opts = self.opts
        self.last_time = datetime.datetime.now()
        self.preferences_action, self.quit_action = actions
        self.library_path = library_path
        self.spare_servers = []
        self.must_restart_before_config = False
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

        # Jobs Button {{{
        self.job_manager = JobManager()
        self.jobs_dialog = JobsDialog(self, self.job_manager)
        self.jobs_button = JobsButton()
        self.jobs_button.initialize(self.jobs_dialog, self.job_manager)
        # }}}

        LayoutMixin.__init__(self)

        self.restriction_count_of_books_in_view = 0
        self.restriction_count_of_books_in_library = 0
        self.restriction_in_effect = False

        self.progress_indicator = ProgressIndicator(self)
        self.verbose = opts.verbose
        self.get_metadata = GetMetadata()
        self.emailer = Emailer()
        self.emailer.start()
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
        self.device_connected = None
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
        self.eject_action = self.system_tray_menu.addAction(
                QIcon(I('eject.svg')), _('&Eject connected device'))
        self.eject_action.setEnabled(False)
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

        DeviceMixin.__init__(self)

        ####################### Start spare job server ########################
        QTimer.singleShot(1000, self.add_spare_server)

        ####################### Setup device detection ########################
        self.device_manager = DeviceManager(Dispatcher(self.device_detected),
                self.job_manager, Dispatcher(self.status_bar.show_message))
        self.device_manager.start()


        ####################### Location View ########################
        QObject.connect(self.location_view,
                SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        QObject.connect(self.location_view,
                SIGNAL('umount_device()'),
                        self.device_manager.umount_device)
        self.eject_action.triggered.connect(self.device_manager.umount_device)

        ####################### Vanity ########################
        self.vanity_template  = _('<p>For help see the: <a href="%s">User Manual</a>'
                '<br>')%'http://calibre-ebook.com/user_manual'
        dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        v = __version__
        if getattr(sys, 'frozen', False) and dv and os.path.abspath(dv) in sys.path:
            v += '*'
        self.vanity_template += _('<b>%s</b>: %s by <b>Kovid Goyal '
            '%%(version)s</b><br>%%(device)s</p>')%(__appname__, v)
        self.latest_version = ' '
        self.vanity.setText(self.vanity_template%dict(version=' ', device=' '))
        self.device_info = ' '
        if not opts.no_update_check:
            self.update_checker = CheckForUpdates(self)
            self.update_checker.update_found.connect(self.update_found,
                    type=Qt.QueuedConnection)
            self.update_checker.start()

        ####################### Status Bar #####################
        self.status_bar.initialize(self.system_tray_icon)
        self.status_bar.show_book_info.connect(self.show_book_info)
        self.status_bar.files_dropped.connect(self.files_dropped_on_book)

        ####################### Setup Toolbar #####################
        ToolbarMixin.__init__(self)

        ####################### Search boxes ########################
        SavedSearchBoxMixin.__init__(self)
        SearchBoxMixin.__init__(self)

        ####################### Library view ########################
        LibraryViewMixin.__init__(self, db)

        self.show()

        if self.system_tray_icon.isVisible() and opts.start_in_tray:
            self.hide_windows()
        self.cover_cache = CoverCache(self.library_path)
        self.cover_cache.start()
        self.library_view.model().cover_cache = self.cover_cache
        self.library_view.model().count_changed_signal.connect \
                                            (self.location_view.count_changed)
        if not gprefs.get('quick_start_guide_added', False):
            from calibre.ebooks.metadata import MetaInformation
            mi = MetaInformation(_('Calibre Quick Start Guide'), ['John Schember'])
            mi.author_sort = 'Schember, John'
            mi.comments = "A guide to get you up and running with calibre"
            mi.publisher = 'calibre'
            self.library_view.model().add_books([P('quick_start.epub')], ['epub'],
                    [mi])
            gprefs['quick_start_guide_added'] = True
            self.library_view.model().books_added(1)
            if hasattr(self, 'db_images'):
                self.db_images.reset()

        self.library_view.model().count_changed()
        self.location_view.model().database_changed(self.library_view.model().db)
        self.library_view.model().database_changed.connect(self.location_view.model().database_changed,
                type=Qt.QueuedConnection)

        ########################### Tags Browser ##############################
        TagBrowserMixin.__init__(self, db)

        ######################### Search Restriction ##########################
        SearchRestrictionMixin.__init__(self)

        ########################### Cover Flow ################################

        CoverFlowMixin.__init__(self)

        self._calculated_available_height = min(max_available_height()-15,
                self.height())
        self.resize(self.width(), self._calculated_available_height)


        if config['autolaunch_server']:
            from calibre.library.server.main import start_threaded_server
            from calibre.library.server import server_config
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

        self.location_view.setCurrentIndex(self.location_view.model().index(0))

        self._add_filesystem_book = Dispatcher(self.__add_filesystem_book)
        self.keyboard_interrupt.connect(self.quit, type=Qt.QueuedConnection)

        self.read_settings()
        self.finalize_layout()

    def resizeEvent(self, ev):
        MainWindow.resizeEvent(self, ev)
        self.search.setMaximumWidth(self.width()-150)

    def connect_to_folder(self):
        dir = choose_dir(self, 'Select Device Folder',
                _('Select folder to open as device'))
        if dir is not None:
            self.device_manager.connect_to_folder(dir)

    def disconnect_from_folder(self):
        self.device_manager.disconnect_folder()

    def _sync_action_triggered(self, *args):
        m = getattr(self, '_sync_menu', None)
        if m is not None:
            m.trigger_default()

    def create_device_menu(self):
        self._sync_menu = DeviceMenu(self)
        self.action_sync.setMenu(self._sync_menu)
        self.connect(self._sync_menu,
                SIGNAL('sync(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                self.dispatch_sync_event)
        self._sync_menu.fetch_annotations.connect(self.fetch_annotations)
        self._sync_menu.connect_to_folder.connect(self.connect_to_folder)
        self._sync_menu.disconnect_from_folder.connect(self.disconnect_from_folder)
        if self.device_connected:
            self._sync_menu.connect_to_folder_action.setEnabled(False)
            if self.device_connected == 'folder':
                self._sync_menu.disconnect_from_folder_action.setEnabled(True)
            else:
                self._sync_menu.disconnect_from_folder_action.setEnabled(False)
        else:
            self._sync_menu.connect_to_folder_action.setEnabled(True)
            self._sync_menu.disconnect_from_folder_action.setEnabled(False)

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
        return
        #self.memory_view.write_settings()
        for x in range(model.rowCount()):
            if x > 1:
                if model.location_for_row(x) == 'carda':
                    self.card_a_view.write_settings()
                elif model.location_for_row(x) == 'cardb':
                    self.card_b_view.write_settings()

    def device_detected(self, connected, is_folder_device):
        '''
        Called when a device is connected to the computer.
        '''
        if connected:
            self._sync_menu.connect_to_folder_action.setEnabled(False)
            if is_folder_device:
                self._sync_menu.disconnect_from_folder_action.setEnabled(True)
            self.device_manager.get_device_information(\
                    Dispatcher(self.info_read))
            self.set_default_thumbnail(\
                    self.device_manager.device.THUMBNAIL_HEIGHT)
            self.status_bar.show_message(_('Device: ')+\
                self.device_manager.device.__class__.get_gui_name()+\
                        _(' detected.'), 3000)
            self.device_connected = 'device' if not is_folder_device else 'folder'
            self._sync_menu.enable_device_actions(True,
                    self.device_manager.device.card_prefix(),
                    self.device_manager.device)
            self.location_view.model().device_connected(self.device_manager.device)
            self.eject_action.setEnabled(True)
            self.refresh_ondevice_info (device_connected = True, reset_only = True)
        else:
            self._sync_menu.connect_to_folder_action.setEnabled(True)
            self._sync_menu.disconnect_from_folder_action.setEnabled(False)
            self.save_device_view_settings()
            self.device_connected = None
            self._sync_menu.enable_device_actions(False)
            self.location_view.model().update_devices()
            self.vanity.setText(self.vanity_template%\
                    dict(version=self.latest_version, device=' '))
            self.device_info = ' '
            if self.current_view() != self.library_view:
                self.status_bar.reset_info()
                self.location_view.setCurrentIndex(self.location_view.model().index(0))
            self.eject_action.setEnabled(False)
            self.refresh_ondevice_info (device_connected = False)

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
        self.set_books_in_library(job.result, reset=True)
        mainlist, cardalist, cardblist = job.result
        self.memory_view.set_database(mainlist)
        self.memory_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.card_a_view.set_database(cardalist)
        self.card_a_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.card_b_view.set_database(cardblist)
        self.card_b_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.sync_news()
        self.sync_catalogs()
        self.refresh_ondevice_info(device_connected = True)

    ############################################################################
    ### Force the library view to refresh, taking into consideration books information
    def refresh_ondevice_info(self, device_connected, reset_only = False):
        self.book_on_device(None, reset=True)
        if reset_only:
            return
        self.library_view.set_device_connected(device_connected)
    ############################################################################

    ######################### Fetch annotations ################################

    def fetch_annotations(self, *args):
        # Generate a path_map from selected ids
        def get_ids_from_selected_rows():
            rows = self.library_view.selectionModel().selectedRows()
            if not rows or len(rows) < 2:
                rows = xrange(self.library_view.model().rowCount(QModelIndex()))
            ids = map(self.library_view.model().id, rows)
            return ids

        def get_formats(id):
            formats = db.formats(id, index_is_id=True)
            fmts = []
            if formats:
                for format in formats.split(','):
                    fmts.append(format.lower())
            return fmts

        def generate_annotation_paths(ids, db, device):
            # Generate path templates
            # Individual storage mount points scanned/resolved in driver.get_annotations()
            path_map = {}
            for id in ids:
                mi = db.get_metadata(id, index_is_id=True)
                a_path = device.create_upload_path(os.path.abspath('/<storage>'), mi, 'x.bookmark', create_dirs=False)
                path_map[id] = dict(path=a_path, fmts=get_formats(id))
            return path_map

        device = self.device_manager.device

        if self.current_view() is not self.library_view:
            return error_dialog(self, _('Use library only'),
                    _('User annotations generated from main library only'),
                    show=True)
        db = self.library_view.model().db

        # Get the list of ids
        ids = get_ids_from_selected_rows()
        if not ids:
            return error_dialog(self, _('No books selected'),
                    _('No books selected to fetch annotations from'),
                    show=True)

        # Map ids to paths
        path_map = generate_annotation_paths(ids, db, device)

        # Dispatch to devices.kindle.driver.get_annotations()
        self.device_manager.annotations(Dispatcher(self.annotations_fetched),
                path_map)

    def annotations_fetched(self, job):
        from calibre.devices.usbms.device import Device
        from calibre.ebooks.metadata import MetaInformation
        from calibre.gui2.dialogs.progress import ProgressDialog
        from calibre.library.cli import do_add_format

        class Updater(QThread):

            update_progress = pyqtSignal(int)
            update_done     = pyqtSignal()
            FINISHED_READING_PCT_THRESHOLD = 96

            def __init__(self, parent, db, annotation_map, done_callback):
                QThread.__init__(self, parent)
                self.db = db
                self.pd = ProgressDialog(_('Merging user annotations into database'), '',
                        0, len(job.result), parent=parent)

                self.am = annotation_map
                self.done_callback = done_callback
                self.connect(self.pd, SIGNAL('canceled()'), self.canceled)
                self.pd.setModal(True)
                self.pd.show()
                self.update_progress.connect(self.pd.set_value,
                        type=Qt.QueuedConnection)
                self.update_done.connect(self.pd.hide, type=Qt.QueuedConnection)

            def generate_annotation_html(self, bookmark):
                # Returns <div class="user_annotations"> ... </div>
                last_read_location = bookmark.last_read_location
                timestamp = datetime.datetime.utcfromtimestamp(bookmark.timestamp)
                percent_read = bookmark.percent_read

                ka_soup = BeautifulSoup()
                dtc = 0
                divTag = Tag(ka_soup,'div')
                divTag['class'] = 'user_annotations'

                # Add the last-read location
                spanTag = Tag(ka_soup, 'span')
                spanTag['style'] = 'font-weight:bold'
                if bookmark.book_format == 'pdf':
                    spanTag.insert(0,NavigableString(
                        _("%s<br />Last Page Read: %d (%d%%)") % \
                                    (strftime(u'%x', timestamp.timetuple()),
                                    last_read_location,
                                    percent_read)))
                else:
                    spanTag.insert(0,NavigableString(
                        _("%s<br />Last Page Read: Location %d (%d%%)") % \
                                    (strftime(u'%x', timestamp.timetuple()),
                                    last_read_location,
                                    percent_read)))

                divTag.insert(dtc, spanTag)
                dtc += 1
                divTag.insert(dtc, Tag(ka_soup,'br'))
                dtc += 1

                if bookmark.user_notes:
                    user_notes = bookmark.user_notes
                    annotations = []

                    # Add the annotations sorted by location
                    # Italicize highlighted text
                    for location in sorted(user_notes):
                        if user_notes[location]['text']:
                            annotations.append(
                                    _('<b>Location %d &bull; %s</b><br />%s<br />') % \
                                                (user_notes[location]['displayed_location'],
                                                    user_notes[location]['type'],
                                                    user_notes[location]['text'] if \
                                                    user_notes[location]['type'] == 'Note' else \
                                                    '<i>%s</i>' % user_notes[location]['text']))
                        else:
                            if bookmark.book_format == 'pdf':
                                annotations.append(
                                        _('<b>Page %d &bull; %s</b><br />') % \
                                                    (user_notes[location]['displayed_location'],
                                                     user_notes[location]['type']))
                            else:
                                annotations.append(
                                        _('<b>Location %d &bull; %s</b><br />') % \
                                                    (user_notes[location]['displayed_location'],
                                                     user_notes[location]['type']))

                    for annotation in annotations:
                        divTag.insert(dtc, annotation)
                        dtc += 1

                ka_soup.insert(0,divTag)
                return ka_soup

            def mark_book_as_read(self,id):
                read_tag = gprefs.get('catalog_epub_mobi_read_tag')
                self.db.set_tags(id, [read_tag], append=True)

            def canceled(self):
                self.pd.hide()

            def run(self):
                ignore_tags = set(['Catalog','Clippings'])
                for (i, id) in enumerate(self.am):
                    bm = Device.UserAnnotation(self.am[id][0],self.am[id][1])
                    if bm.type == 'kindle_bookmark':
                        mi = self.db.get_metadata(id, index_is_id=True)
                        user_notes_soup = self.generate_annotation_html(bm.value)
                        if mi.comments:
                            a_offset = mi.comments.find('<div class="user_annotations">')
                            ad_offset = mi.comments.find('<hr class="annotations_divider" />')

                            if a_offset >= 0:
                                mi.comments = mi.comments[:a_offset]
                            if ad_offset >= 0:
                                mi.comments = mi.comments[:ad_offset]
                            if set(mi.tags).intersection(ignore_tags):
                                continue
                            if mi.comments:
                                hrTag = Tag(user_notes_soup,'hr')
                                hrTag['class'] = 'annotations_divider'
                                user_notes_soup.insert(0,hrTag)

                            mi.comments += user_notes_soup.prettify()
                        else:
                            mi.comments = unicode(user_notes_soup.prettify())
                        # Update library comments
                        self.db.set_comment(id, mi.comments)

                        # Update 'read' tag except for Catalogs/Clippings
                        if bm.value.percent_read >= self.FINISHED_READING_PCT_THRESHOLD:
                            if not set(mi.tags).intersection(ignore_tags):
                                self.mark_book_as_read(id)

                        # Add bookmark file to id
                        self.db.add_format_with_hooks(id, bm.value.bookmark_extension,
                                                      bm.value.path, index_is_id=True)
                        self.update_progress.emit(i)
                    elif bm.type == 'kindle_clippings':
                        # Find 'My Clippings' author=Kindle in database, or add
                        last_update = 'Last modified %s' % strftime(u'%x %X',bm.value['timestamp'].timetuple())
                        mc_id = list(db.data.parse('title:"My Clippings"'))
                        if mc_id:
                            do_add_format(self.db, mc_id[0], 'TXT', bm.value['path'])
                            mi = self.db.get_metadata(mc_id[0], index_is_id=True)
                            mi.comments = last_update
                            self.db.set_metadata(mc_id[0], mi)
                        else:
                            mi = MetaInformation('My Clippings', authors = ['Kindle'])
                            mi.tags = ['Clippings']
                            mi.comments = last_update
                            self.db.add_books([bm.value['path']], ['txt'], [mi])

                self.update_done.emit()
                self.done_callback(self.am.keys())

        if not job.result: return

        if self.current_view() is not self.library_view:
            return error_dialog(self, _('Use library only'),
                    _('User annotations generated from main library only'),
                    show=True)
        db = self.library_view.model().db

        self.__annotation_updater = Updater(self, db, job.result,
                Dispatcher(self.library_view.model().refresh_ids))
        self.__annotation_updater.start()


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

    def add_recursive_single(self, *args):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming one book per folder.
        '''
        self.add_recursive(True)

    def add_recursive_multiple(self, *args):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming multiple books per folder.
        '''
        self.add_recursive(False)

    def add_empty(self, *args):
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

    def __add_filesystem_book(self, paths, allow_device=True):
        if isinstance(paths, basestring):
            paths = [paths]
        books = [path for path in map(os.path.abspath, paths) if os.access(path,
            os.R_OK)]

        if books:
            to_device = allow_device and self.stack.currentIndex() != 0
            self._add_books(books, to_device)
            if to_device:
                self.status_bar.show_message(\
                        _('Uploading books to device.'), 2000)


    def add_filesystem_book(self, paths, allow_device=True):
        self._add_filesystem_book(paths, allow_device=allow_device)

    def add_books(self, *args):
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
                        (_('Topaz books'), ['tpz','azw1']),
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
            self.status_bar.show_message(
                    _('Uploading books to device.'), 2000)
        if getattr(self._adder, 'number_of_books_added', 0) > 0:
            self.library_view.model().books_added(self._adder.number_of_books_added)
            if hasattr(self, 'db_images'):
                self.db_images.reset()
        if getattr(self._adder, 'merged_books', False):
            books = u'\n'.join([x if isinstance(x, unicode) else
                    x.decode(preferred_encoding, 'replace') for x in
                    self._adder.merged_books])
            info_dialog(self, _('Merged some books'),
                    _('Some duplicates were found and merged into the '
                        'following existing books:'), det_msg=books, show=True)
        if getattr(self._adder, 'critical', None):
            det_msg = []
            for name, log in self._adder.critical.items():
                if isinstance(name, str):
                    name = name.decode(filesystem_encoding, 'replace')
                det_msg.append(name+'\n'+log)

            warning_dialog(self, _('Failed to read metadata'),
                    _('Failed to read metadata from the following')+':',
                    det_msg='\n\n'.join(det_msg), show=True)

        if hasattr(self._adder, 'cleanup'):
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
        if ids:
            self.tags_view.recount()

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
        if ids:
            self.tags_view.recount()


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
            ids_deleted = view.model().delete_books(rows)
            for v in (self.memory_view, self.card_a_view, self.card_b_view):
                if v is None:
                    continue
                v.model().clear_ondevice(ids_deleted)
            if row is not None:
                ci = view.model().index(row, 0)
                if ci.isValid():
                    view.setCurrentIndex(ci)
                    sm = view.selectionModel()
                    sm.select(ci, sm.Select)
        else:
            if not confirm('<p>'+_('The selected books will be '
                                   '<b>permanently deleted</b> '
                                   'from your device. Are you sure?')
                                +'</p>', 'device_delete_books', self):
                return
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
            self.status_bar.show_message(_('Deleting books from device.'), 1000)

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
        # Clear the ondevice info so it will be recomputed
        self.book_on_device(None, None, reset=True)
        # We want to reset all the ondevice flags in the library. Use a big
        # hammer, so we don't need to worry about whether some succeeded or not
        self.library_view.model().refresh()

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
            m = self.library_view.model()
            m.refresh_cover_cache(map(m.id, rows))
            if self.cover_flow:
                self.cover_flow.dataChanged()
            m.current_changed(current, previous)
            self.tags_view.recount()

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
            self.tags_view.recount()

    ############################################################################

    ############################### Merge books ##############################
    def merge_books(self, safe_merge=False):
        '''
        Merge selected books in library.
        '''
        if self.stack.currentIndex() != 0:
            return
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self, _('Cannot merge books'),
                                _('No books selected'), show=True)
        if len(rows) < 2:
            return error_dialog(self, _('Cannot merge books'),
                        _('At least two books must be selected for merging'),
                        show=True)
        dest_id, src_books, src_ids = self.books_to_merge(rows)
        if safe_merge:
            if not confirm('<p>'+_(
                'All book formats and metadata from the selected books '
                'will be added to the <b>first selected book.</b><br><br> '
                'The second and subsequently selected books will not '
                'be deleted or changed.<br><br>'
                'Please confirm you want to proceed.')
            +'</p>', 'merge_books_safe', self):
                return
            self.add_formats(dest_id, src_books)
            self.merge_metadata(dest_id, src_ids)
        else:
            if not confirm('<p>'+_(
                'All book formats and metadata from the selected books will be merged '
                'into the <b>first selected book</b>.<br><br>'
                'After merger the second and '
                'subsequently selected books will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your computer.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')
            +'</p>', 'merge_books', self):
                return
            if len(rows)>5:
                if not confirm('<p>'+_('You are about to merge more than 5 books.  '
                                        'Are you <b>sure</b> you want to proceed?')
                                    +'</p>', 'merge_too_many_books', self):
                    return
            self.add_formats(dest_id, src_books)
            self.merge_metadata(dest_id, src_ids)
            self.delete_books_after_merge(src_ids)
            # leave the selection highlight on first selected book
            dest_row = rows[0].row()
            for row in rows:
                if row.row() < rows[0].row():
                    dest_row -= 1
            ci = self.library_view.model().index(dest_row, 0)
            if ci.isValid():
                self.library_view.setCurrentIndex(ci)

    def add_formats(self, dest_id, src_books, replace=False):
        for src_book in src_books:
            if src_book:
                fmt = os.path.splitext(src_book)[-1].replace('.', '').upper()
                with open(src_book, 'rb') as f:
                    self.library_view.model().db.add_format(dest_id, fmt, f, index_is_id=True,
                            notify=False, replace=replace)

    def books_to_merge(self, rows):
        src_books = []
        src_ids = []
        m = self.library_view.model()
        for i, row in enumerate(rows):
            id_ = m.id(row)
            if i == 0:
                dest_id = id_
            else:
                src_ids.append(id_)
                dbfmts = m.db.formats(id_, index_is_id=True)
                if dbfmts:
                    for fmt in dbfmts.split(','):
                        src_books.append(m.db.format_abspath(id_, fmt,
                            index_is_id=True))
        return [dest_id, src_books, src_ids]

    def delete_books_after_merge(self, ids_to_delete):
        self.library_view.model().delete_books_by_id(ids_to_delete)

    def merge_metadata(self, dest_id, src_ids):
        db = self.library_view.model().db
        dest_mi = db.get_metadata(dest_id, index_is_id=True, get_cover=True)
        orig_dest_comments = dest_mi.comments
        for src_id in src_ids:
            src_mi = db.get_metadata(src_id, index_is_id=True, get_cover=True)
            if src_mi.comments and orig_dest_comments != src_mi.comments:
                if not dest_mi.comments or len(dest_mi.comments) == 0:
                    dest_mi.comments = src_mi.comments
                else:
                    dest_mi.comments = unicode(dest_mi.comments) + u'\n\n' + unicode(src_mi.comments)
            if src_mi.title and src_mi.title and (not dest_mi.title or
                    dest_mi.title == _('Unknown')):
                dest_mi.title = src_mi.title
            if src_mi.title and (not dest_mi.authors or dest_mi.authors[0] ==
                    _('Unknown')):
                dest_mi.authors = src_mi.authors
                dest_mi.author_sort = src_mi.author_sort
            if src_mi.tags:
                if not dest_mi.tags:
                    dest_mi.tags = src_mi.tags
                else:
                    for tag in src_mi.tags:
                        dest_mi.tags.append(tag)
            if src_mi.cover and not dest_mi.cover:
                dest_mi.cover = src_mi.cover
            if not dest_mi.publisher:
                dest_mi.publisher = src_mi.publisher
            if not dest_mi.rating:
                dest_mi.rating = src_mi.rating
            if not dest_mi.series:
                dest_mi.series = src_mi.series
                dest_mi.series_index = src_mi.series_index
        db.set_metadata(dest_id, dest_mi, ignore_errors=False)

    ############################################################################


    ############################## Save to disk ################################
    def save_single_format_to_disk(self, checked):
        self.save_to_disk(checked, False, prefs['output_format'])

    def save_specific_format_disk(self, fmt):
        self.save_to_disk(False, False, fmt)

    def save_to_single_dir(self, checked):
        self.save_to_disk(checked, True)

    def save_single_fmt_to_single_dir(self, *args):
        self.save_to_disk(False, single_dir=True,
                single_format=prefs['output_format'])

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
                # Special case for Kindle annotation files
                if single_format.lower() in ['mbp','pdr','tan']:
                    opts.to_lowercase = False
                    opts.save_cover = False
                    opts.write_opf = False
                    opts.template = opts.send_template
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

    ############################### Generate catalog ###########################

    def generate_catalog(self):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) < 2:
            rows = xrange(self.library_view.model().rowCount(QModelIndex()))
        ids = map(self.library_view.model().id, rows)

        dbspec = None
        if not ids:
            return error_dialog(self, _('No books selected'),
                    _('No books selected to generate catalog for'),
                    show=True)

        # Calling gui2.tools:generate_catalog()
        ret = generate_catalog(self, dbspec, ids, self.device_manager.device)
        if ret is None:
            return

        func, args, desc, out, sync, title = ret

        fmt = os.path.splitext(out)[1][1:].upper()
        job = self.job_manager.run_job(
                Dispatcher(self.catalog_generated), func, args=args,
                    description=desc)
        job.catalog_file_path = out
        job.fmt = fmt
        job.catalog_sync, job.catalog_title = sync, title
        self.status_bar.show_message(_('Generating %s catalog...')%fmt)

    def catalog_generated(self, job):
        if job.result:
            # Search terms nulled catalog results
            return error_dialog(self, _('No books found'),
                    _("No books to catalog\nCheck exclude tags"),
                    show=True)
        if job.failed:
            return self.job_exception(job)
        id = self.library_view.model().add_catalog(job.catalog_file_path, job.catalog_title)
        self.library_view.model().reset()
        if job.catalog_sync:
            sync = dynamic.get('catalogs_to_be_synced', set([]))
            sync.add(id)
            dynamic.set('catalogs_to_be_synced', sync)
        self.status_bar.show_message(_('Catalog generated.'), 3000)
        self.sync_catalogs()
        if job.fmt not in ['EPUB','MOBI']:
            export_dir = choose_dir(self, _('Export Catalog Directory'),
                    _('Select destination for %s.%s') % (job.catalog_title, job.fmt.lower()))
            if export_dir:
                destination = os.path.join(export_dir, '%s.%s' % (job.catalog_title, job.fmt.lower()))
                shutil.copyfile(job.catalog_file_path, destination)

    ############################### Fetch news #################################

    def download_scheduled_recipe(self, arg):
        func, args, desc, fmt, temp_files = \
                fetch_scheduled_recipe(arg)
        job = self.job_manager.run_job(
                Dispatcher(self.scheduled_recipe_fetched), func, args=args,
                           description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, arg)
        self.status_bar.show_message(_('Fetching news from ')+arg['title'], 2000)

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
        self.status_bar.show_message(arg['title'] + _(' fetched.'), 3000)
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

    def auto_convert_catalogs(self, book_ids, format):
        previous = self.library_view.currentIndex()
        rows = [x.row() for x in \
                self.library_view.selectionModel().selectedRows()]
        jobs, changed, bad = convert_single_ebook(self, self.library_view.model().db, book_ids, True, format)
        if jobs == []: return
        self.queue_convert_jobs(jobs, changed, bad, rows, previous,
                self.book_auto_converted_catalogs)



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
            self.status_bar.show_message(_('Starting conversion of %d book(s)') %
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

    def book_auto_converted_catalogs(self, job):
        temp_files, fmt, book_id = self.conversion_jobs[job]
        self.book_converted(job)
        self.sync_catalogs(send_ids=[book_id], do_auto_convert=False)

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
            self.status_bar.show_message(job.description + \
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
        if d.exec_() == QDialog.Accepted:
            format = d.format()
            self.view_format(row, format)

    def _view_check(self, num, max_=3):
        if num <= max_:
            return True
        return question_dialog(self, _('Multiple Books Selected'),
                _('You are attempting to open %d books. Opening too many '
                'books at once can be slow and have a negative effect on the '
                'responsiveness of your computer. Once started the process '
                'cannot be stopped until complete. Do you wish to continue?'
                ) % num)

    def view_folder(self, *args):
        rows = self.current_view().selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self, _('Cannot open folder'),
                    _('No book selected'))
            d.exec_()
            return
        if not self._view_check(len(rows)):
            return
        for row in rows:
            path = self.library_view.model().db.abspath(row.row())
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


    def view_book(self, triggered):
        rows = self.current_view().selectionModel().selectedRows()
        self._view_books(rows)

    def view_specific_book(self, index):
        self._view_books([index])

    def _view_books(self, rows):
        if not rows or len(rows) == 0:
            self._launch_viewer()
            return

        if not self._view_check(len(rows)):
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

    ############################################################################

    ############################### Do config ##################################

    def do_config(self, *args):
        if self.job_manager.has_jobs():
            d = error_dialog(self, _('Cannot configure'),
                    _('Cannot configure while there are running jobs.'))
            d.exec_()
            return
        if self.must_restart_before_config:
            d = error_dialog(self, _('Cannot configure'),
                    _('Cannot configure before calibre is restarted.'))
            d.exec_()
            return
        d = ConfigDialog(self, self.library_view,
                server=self.content_server)

        d.exec_()
        self.content_server = d.server
        if d.result() == d.Accepted:
            self.read_toolbar_settings()
            self.search.search_as_you_type(config['search_as_you_type'])
            self.save_menu.actions()[2].setText(
                _('Save only %s format to disk')%
                prefs['output_format'].upper())
            self.save_menu.actions()[3].setText(
                _('Save only %s format to disk in a single directory')%
                prefs['output_format'].upper())
            self.tags_view.set_new_model() # in case columns changed
            self.tags_view.recount()
            self.create_device_menu()

            if not patheq(self.library_path, d.database_location):
                newloc = d.database_location
                move_library(self.library_path, newloc, self,
                        self.library_moved)

    def library_moved(self, newloc):
        if newloc is None: return
        db = LibraryDatabase2(newloc)
        self.library_path = newloc
        self.book_on_device(None, reset=True)
        db.set_book_on_device_func(self.book_on_device)
        self.library_view.set_database(db)
        self.tags_view.set_database(db, self.tag_match, self.popularity)
        self.library_view.model().set_book_on_device_func(self.book_on_device)
        self.status_bar.clearMessage()
        self.search.clear_to_help()
        self.status_bar.reset_info()
        self.library_view.model().count_changed()
        prefs['library_path'] = self.library_path

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
        self.status_bar.reset_info()
        for x in ('tb', 'cb'):
            splitter = getattr(self, x+'_splitter')
            splitter.button.setEnabled(location == 'library')
        if location == 'library':
            self.action_edit.setEnabled(True)
            self.action_merge.setEnabled(True)
            self.action_convert.setEnabled(True)
            self.view_menu.actions()[1].setEnabled(True)
            self.action_open_containing_folder.setEnabled(True)
            self.action_sync.setEnabled(True)
            self.search_restriction.setEnabled(True)
            for action in list(self.delete_menu.actions())[1:]:
                action.setEnabled(True)
        else:
            self.action_edit.setEnabled(False)
            self.action_merge.setEnabled(False)
            self.action_convert.setEnabled(False)
            self.view_menu.actions()[1].setEnabled(False)
            self.action_open_containing_folder.setEnabled(False)
            self.action_sync.setEnabled(False)
            self.search_restriction.setEnabled(False)
            for action in list(self.delete_menu.actions())[1:]:
                action.setEnabled(False)
        self.set_number_of_books_shown()


    def device_job_exception(self, job):
        '''
        Handle exceptions in threaded device jobs.
        '''
        if isinstance(getattr(job, 'exception', None), UserFeedback):
            ex = job.exception
            func = {UserFeedback.ERROR:error_dialog,
                    UserFeedback.WARNING:warning_dialog,
                    UserFeedback.INFO:info_dialog}[ex.level]
            return func(self, _('Failed'), ex.msg, det_msg=ex.details if
                    ex.details else '', show=True)

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
                            'http://bugs.calibre-ebook.com/wiki/DRM'))
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

    def read_settings(self):
        geometry = config['main_window_geometry']
        if geometry is not None:
            self.restoreGeometry(geometry)
        self.read_toolbar_settings()
        self.read_layout_settings()

    def write_settings(self):
        config.set('main_window_geometry', self.saveGeometry())
        dynamic.set('sort_history', self.library_view.model().sort_history)
        self.save_layout_state()

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
        self.update_checker.terminate()
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



