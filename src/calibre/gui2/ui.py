#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''The main GUI'''

import collections, os, sys, textwrap, time, gc, errno, re
from Queue import Queue, Empty
from threading import Thread
from collections import OrderedDict
from io import BytesIO

import apsw
from PyQt5.Qt import (
    Qt, QTimer, QAction, QMenu, QIcon, pyqtSignal, QUrl, QFont, QDialog,
    QApplication, QSystemTrayIcon)

from calibre import prints, force_unicode, detect_ncpus
from calibre.constants import (
        __appname__, isosx, iswindows, filesystem_encoding, DEBUG, config_dir)
from calibre.utils.config import prefs, dynamic
from calibre.utils.ipc.pool import Pool
from calibre.db.legacy import LibraryDatabase
from calibre.customize.ui import interface_actions, available_store_plugins
from calibre.gui2 import (error_dialog, GetMetadata, open_url,
        gprefs, max_available_height, config, info_dialog, Dispatcher,
        question_dialog, warning_dialog)
from calibre.gui2.cover_flow import CoverFlowMixin
from calibre.gui2.changes import handle_changes
from calibre.gui2.widgets import ProgressIndicator
from calibre.gui2.update import UpdateMixin
from calibre.gui2.main_window import MainWindow
from calibre.gui2.layout import MainWindowMixin
from calibre.gui2.device import DeviceMixin
from calibre.gui2.email import EmailMixin
from calibre.gui2.ebook_download import EbookDownloadMixin
from calibre.gui2.jobs import JobManager, JobsDialog, JobsButton
from calibre.gui2.init import LibraryViewMixin, LayoutMixin
from calibre.gui2.search_box import SearchBoxMixin, SavedSearchBoxMixin
from calibre.gui2.search_restriction_mixin import SearchRestrictionMixin
from calibre.gui2.tag_browser.ui import TagBrowserMixin
from calibre.gui2.keyboard import Manager
from calibre.gui2.auto_add import AutoAdder
from calibre.gui2.proceed import ProceedQuestion
from calibre.gui2.dialogs.message_box import JobError
from calibre.gui2.job_indicator import Pointer
from calibre.gui2.dbus_export.widgets import factory
from calibre.gui2.open_with import register_keyboard_shortcuts
from calibre.library import current_library_name
from calibre.srv.library_broker import GuiLibraryBroker


class Listener(Thread):  # {{{

    def __init__(self, listener):
        Thread.__init__(self)
        self.daemon = True
        self.listener, self.queue = listener, Queue()
        self._run = True
        self.start()

    def run(self):
        if self.listener is None:
            return
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
            if self.listener is not None:
                self.listener.close()
        except:
            import traceback
            traceback.print_exc()

# }}}


_gui = None


def get_gui():
    return _gui


def add_quick_start_guide(library_view, refresh_cover_browser=None):
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.ebooks.covers import calibre_cover2
    from calibre.utils.zipfile import safe_replace
    from calibre.utils.localization import get_lang, canonicalize_lang
    from calibre.ptempfile import PersistentTemporaryFile
    l = canonicalize_lang(get_lang()) or 'eng'
    gprefs['quick_start_guide_added'] = True
    imgbuf = BytesIO(calibre_cover2(_('Quick Start Guide'), ''))
    try:
        with lopen(P('quick_start/%s.epub' % l), 'rb') as src:
            buf = BytesIO(src.read())
    except EnvironmentError as err:
        if err.errno != errno.ENOENT:
            raise
        with lopen(P('quick_start/eng.epub'), 'rb') as src:
            buf = BytesIO(src.read())
    safe_replace(buf, 'images/cover.jpg', imgbuf)
    buf.seek(0)
    mi = get_metadata(buf, 'epub')
    with PersistentTemporaryFile('.epub') as tmp:
        tmp.write(buf.getvalue())
    library_view.model().add_books([tmp.name], ['epub'], [mi])
    os.remove(tmp.name)
    library_view.model().books_added(1)
    if refresh_cover_browser is not None:
        refresh_cover_browser()
    if library_view.model().rowCount(None) < 3:
        library_view.resizeColumnsToContents()


class Main(MainWindow, MainWindowMixin, DeviceMixin, EmailMixin,  # {{{
        TagBrowserMixin, CoverFlowMixin, LibraryViewMixin, SearchBoxMixin,
        SavedSearchBoxMixin, SearchRestrictionMixin, LayoutMixin, UpdateMixin,
        EbookDownloadMixin
        ):

    'The main GUI'

    proceed_requested = pyqtSignal(object, object)
    book_converted = pyqtSignal(object, object)
    shutting_down = False

    def __init__(self, opts, parent=None, gui_debug=None):
        global _gui
        MainWindow.__init__(self, opts, parent=parent, disable_automatic_gc=True)
        self.setWindowIcon(QApplication.instance().windowIcon())
        self.jobs_pointer = Pointer(self)
        self.proceed_requested.connect(self.do_proceed,
                type=Qt.QueuedConnection)
        self.proceed_question = ProceedQuestion(self)
        self.job_error_dialog = JobError(self)
        self.keyboard = Manager(self)
        _gui = self
        self.opts = opts
        self.device_connected = None
        self.gui_debug = gui_debug
        self.iactions = OrderedDict()
        # Actions
        for action in interface_actions():
            if opts.ignore_plugins and action.plugin_path is not None:
                continue
            try:
                ac = self.init_iaction(action)
            except:
                # Ignore errors in loading user supplied plugins
                import traceback
                traceback.print_exc()
                if action.plugin_path is None:
                    raise
                continue
            ac.plugin_path = action.plugin_path
            ac.interface_action_base_plugin = action
            self.add_iaction(ac)
        self.load_store_plugins()

    def init_iaction(self, action):
        ac = action.load_actual_plugin(self)
        ac.plugin_path = action.plugin_path
        ac.interface_action_base_plugin = action
        action.actual_iaction_plugin_loaded = True
        return ac

    def add_iaction(self, ac):
        acmap = self.iactions
        if ac.name in acmap:
            if ac.priority >= acmap[ac.name].priority:
                acmap[ac.name] = ac
        else:
            acmap[ac.name] = ac

    def load_store_plugins(self):
        from calibre.gui2.store.loader import Stores
        self.istores = Stores()
        for store in available_store_plugins():
            if self.opts.ignore_plugins and store.plugin_path is not None:
                continue
            try:
                st = self.init_istore(store)
                self.add_istore(st)
            except:
                # Ignore errors in loading user supplied plugins
                import traceback
                traceback.print_exc()
                if store.plugin_path is None:
                    raise
                continue
        self.istores.builtins_loaded()

    def init_istore(self, store):
        st = store.load_actual_plugin(self)
        st.plugin_path = store.plugin_path
        st.base_plugin = store
        store.actual_istore_plugin_loaded = True
        return st

    def add_istore(self, st):
        stmap = self.istores
        if st.name in stmap:
            if st.priority >= stmap[st.name].priority:
                stmap[st.name] = st
        else:
            stmap[st.name] = st

    def initialize(self, library_path, db, listener, actions, show_gui=True):
        opts = self.opts
        self.preferences_action, self.quit_action = actions
        self.library_path = library_path
        self.library_broker = GuiLibraryBroker(db)
        self.content_server = None
        self.server_change_notification_timer = t = QTimer(self)
        self.server_changes = Queue()
        t.setInterval(1000), t.timeout.connect(self.handle_changes_from_server_debounced), t.setSingleShot(True)
        self._spare_pool = None
        self.must_restart_before_config = False
        self.listener = Listener(listener)
        self.check_messages_timer = QTimer()
        self.check_messages_timer.timeout.connect(self.another_instance_wants_to_talk)
        self.check_messages_timer.start(1000)

        for ac in self.iactions.values():
            try:
                ac.do_genesis()
            except Exception:
                # Ignore errors in third party plugins
                import traceback
                traceback.print_exc()
                if getattr(ac, 'plugin_path', None) is None:
                    raise
        self.donate_action = QAction(QIcon(I('donate.png')),
                _('&Donate to support calibre'), self)
        for st in self.istores.values():
            st.do_genesis()
        MainWindowMixin.init_main_window_mixin(self, db)

        # Jobs Button {{{
        self.job_manager = JobManager()
        self.jobs_dialog = JobsDialog(self, self.job_manager)
        self.jobs_button = JobsButton(parent=self)
        self.jobs_button.initialize(self.jobs_dialog, self.job_manager)
        # }}}

        LayoutMixin.init_layout_mixin(self)
        DeviceMixin.init_device_mixin(self)

        self.progress_indicator = ProgressIndicator(self)
        self.progress_indicator.pos = (0, 20)
        self.verbose = opts.verbose
        self.get_metadata = GetMetadata()
        self.upload_memory = {}
        self.metadata_dialogs = []
        self.default_thumbnail = None
        self.tb_wrapper = textwrap.TextWrapper(width=40)
        self.viewers = collections.deque()
        self.system_tray_icon = None
        if config['systray_icon']:
            self.system_tray_icon = factory(app_id='com.calibre-ebook.gui').create_system_tray_icon(parent=self, title='calibre')
        if self.system_tray_icon is not None:
            self.system_tray_icon.setIcon(QIcon(I('lt.png', allow_user_override=False)))
            if not (iswindows or isosx):
                self.system_tray_icon.setIcon(QIcon.fromTheme('calibre-gui', self.system_tray_icon.icon()))
            self.system_tray_icon.setToolTip(self.jobs_button.tray_tooltip())
            self.system_tray_icon.setVisible(True)
            self.jobs_button.tray_tooltip_updated.connect(self.system_tray_icon.setToolTip)
        elif config['systray_icon']:
            prints('Failed to create system tray icon, your desktop environment probably does not support the StatusNotifier spec')
        self.system_tray_menu = QMenu(self)
        self.toggle_to_tray_action = self.system_tray_menu.addAction(QIcon(I('page.png')), '')
        self.toggle_to_tray_action.triggered.connect(self.system_tray_icon_activated)
        self.system_tray_menu.addAction(self.donate_action)
        self.eject_action = self.system_tray_menu.addAction(
                QIcon(I('eject.png')), _('&Eject connected device'))
        self.eject_action.setEnabled(False)
        self.addAction(self.quit_action)
        self.system_tray_menu.addAction(self.quit_action)
        self.keyboard.register_shortcut('quit calibre', _('Quit calibre'),
                default_keys=('Ctrl+Q',), action=self.quit_action)
        if self.system_tray_icon is not None:
            self.system_tray_icon.setContextMenu(self.system_tray_menu)
            self.system_tray_icon.activated.connect(self.system_tray_icon_activated)
        self.quit_action.triggered[bool].connect(self.quit)
        self.donate_action.triggered[bool].connect(self.donate)
        self.minimize_action = QAction(_('Minimize the calibre window'), self)
        self.addAction(self.minimize_action)
        self.keyboard.register_shortcut('minimize calibre', self.minimize_action.text(),
                default_keys=(), action=self.minimize_action)
        self.minimize_action.triggered.connect(self.showMinimized)

        self.esc_action = QAction(self)
        self.addAction(self.esc_action)
        self.keyboard.register_shortcut('clear current search',
                _('Clear the current search'), default_keys=('Esc',),
                action=self.esc_action)
        self.esc_action.triggered.connect(self.esc)

        self.shift_esc_action = QAction(self)
        self.addAction(self.shift_esc_action)
        self.keyboard.register_shortcut('focus book list',
                _('Focus the book list'), default_keys=('Shift+Esc',),
                action=self.shift_esc_action)
        self.shift_esc_action.triggered.connect(self.shift_esc)

        self.ctrl_esc_action = QAction(self)
        self.addAction(self.ctrl_esc_action)
        self.keyboard.register_shortcut('clear virtual library',
                _('Clear the virtual library'), default_keys=('Ctrl+Esc',),
                action=self.ctrl_esc_action)
        self.ctrl_esc_action.triggered.connect(self.ctrl_esc)

        self.alt_esc_action = QAction(self)
        self.addAction(self.alt_esc_action)
        self.keyboard.register_shortcut('clear additional restriction',
                _('Clear the additional restriction'), default_keys=('Alt+Esc',),
                action=self.alt_esc_action)
        self.alt_esc_action.triggered.connect(self.clear_additional_restriction)

        # ###################### Start spare job server ########################
        QTimer.singleShot(1000, self.create_spare_pool)

        # ###################### Location Manager ########################
        self.location_manager.location_selected.connect(self.location_selected)
        self.location_manager.unmount_device.connect(self.device_manager.umount_device)
        self.location_manager.configure_device.connect(self.configure_connected_device)
        self.location_manager.update_device_metadata.connect(self.update_metadata_on_device)
        self.eject_action.triggered.connect(self.device_manager.umount_device)

        # ################### Update notification ###################
        UpdateMixin.init_update_mixin(self, opts)

        # ###################### Search boxes ########################
        SearchRestrictionMixin.init_search_restriction_mixin(self)
        SavedSearchBoxMixin.init_saved_seach_box_mixin(self)

        # ###################### Library view ########################
        LibraryViewMixin.init_library_view_mixin(self, db)
        SearchBoxMixin.init_search_box_mixin(self)  # Requires current_db

        self.library_view.model().count_changed_signal.connect(
                self.iactions['Choose Library'].count_changed)
        if not gprefs.get('quick_start_guide_added', False):
            try:
                add_quick_start_guide(self.library_view)
            except:
                import traceback
                traceback.print_exc()
        for view in ('library', 'memory', 'card_a', 'card_b'):
            v = getattr(self, '%s_view' % view)
            v.selectionModel().selectionChanged.connect(self.update_status_bar)
            v.model().count_changed_signal.connect(self.update_status_bar)

        self.library_view.model().count_changed()
        self.bars_manager.database_changed(self.library_view.model().db)
        self.library_view.model().database_changed.connect(self.bars_manager.database_changed,
                type=Qt.QueuedConnection)

        # ########################## Tags Browser ##############################
        TagBrowserMixin.init_tag_browser_mixin(self, db)
        self.library_view.model().database_changed.connect(self.populate_tb_manage_menu, type=Qt.QueuedConnection)

        # ######################## Search Restriction ##########################
        if db.prefs['virtual_lib_on_startup']:
            self.apply_virtual_library(db.prefs['virtual_lib_on_startup'])
        self.rebuild_vl_tabs()

        # ########################## Cover Flow ################################

        CoverFlowMixin.init_cover_flow_mixin(self)

        self._calculated_available_height = min(max_available_height()-15,
                self.height())
        self.resize(self.width(), self._calculated_available_height)

        self.build_context_menus()

        for ac in self.iactions.values():
            try:
                ac.gui_layout_complete()
            except:
                import traceback
                traceback.print_exc()
                if ac.plugin_path is None:
                    raise

        if config['autolaunch_server']:
            self.start_content_server()

        self.read_settings()

        self.finalize_layout()
        self.bars_manager.start_animation()
        self.set_window_title()

        for ac in self.iactions.values():
            try:
                ac.initialization_complete()
            except:
                import traceback
                traceback.print_exc()
                if ac.plugin_path is None:
                    raise
        self.set_current_library_information(current_library_name(), db.library_id,
                                             db.field_metadata)

        register_keyboard_shortcuts()
        self.keyboard.finalize()
        if show_gui:
            # Note this has to come after restoreGeometry() because of
            # https://bugreports.qt.io/browse/QTBUG-56831
            self.show()
        if self.system_tray_icon is not None and self.system_tray_icon.isVisible() and opts.start_in_tray:
            self.hide_windows()
        self.auto_adder = AutoAdder(gprefs['auto_add_path'], self)
        self.save_layout_state()

        # Collect cycles now
        gc.collect()

        QApplication.instance().shutdown_signal_received.connect(self.quit)
        if show_gui and self.gui_debug is not None:
            QTimer.singleShot(10, self.show_gui_debug_msg)

        self.iactions['Connect Share'].check_smartdevice_menus()
        QTimer.singleShot(1, self.start_smartdevice)
        QTimer.singleShot(100, self.update_toggle_to_tray_action)

    def show_gui_debug_msg(self):
        info_dialog(self, _('Debug mode'), '<p>' +
                _('You have started calibre in debug mode. After you '
                    'quit calibre, the debug log will be available in '
                    'the file: %s<p>The '
                    'log will be displayed automatically.')%self.gui_debug, show=True)

    def esc(self, *args):
        self.search.clear()

    def shift_esc(self):
        self.current_view().setFocus(Qt.OtherFocusReason)

    def ctrl_esc(self):
        self.apply_virtual_library()
        self.current_view().setFocus(Qt.OtherFocusReason)

    def start_smartdevice(self):
        message = None
        if self.device_manager.get_option('smartdevice', 'autostart'):
            try:
                message = self.device_manager.start_plugin('smartdevice')
            except:
                message = 'start smartdevice unknown exception'
                prints(message)
                import traceback
                traceback.print_exc()
        if message:
            if not self.device_manager.is_running('Wireless Devices'):
                error_dialog(self, _('Problem starting the wireless device'),
                             _('The wireless device driver had problems starting. '
                               'It said "%s"')%message, show=True)
        self.iactions['Connect Share'].set_smartdevice_action_state()

    def start_content_server(self, check_started=True):
        from calibre.srv.embedded import Server
        if not gprefs.get('server3_warning_done', False):
            gprefs.set('server3_warning_done', True)
            if os.path.exists(os.path.join(config_dir, 'server.py')):
                try:
                    os.remove(os.path.join(config_dir, 'server.py'))
                except EnvironmentError:
                    pass
                warning_dialog(self, _('Content server changed!'), _(
                    'calibre 3 comes with a completely re-written content server.'
                    ' As such any custom configuration you have for the content'
                    ' server no longer applies. You should check and refresh your'
                    ' settings in Preferences->Sharing->Sharing over the net'), show=True)
        self.content_server = Server(self.library_broker, Dispatcher(self.handle_changes_from_server))
        self.content_server.state_callback = Dispatcher(
                self.iactions['Connect Share'].content_server_state_changed)
        if check_started:
            self.content_server.start_failure_callback = \
                Dispatcher(self.content_server_start_failed)
        self.content_server.start()

    def handle_changes_from_server(self, library_path, change_event):
        if DEBUG:
            prints('Received server change event: {} for {}'.format(change_event, library_path))
        if self.library_broker.is_gui_library(library_path):
            self.server_changes.put((library_path, change_event))
            self.server_change_notification_timer.start()

    def handle_changes_from_server_debounced(self):
        if self.shutting_down:
            return
        changes = []
        while True:
            try:
                library_path, change_event = self.server_changes.get_nowait()
            except Empty:
                break
            if self.library_broker.is_gui_library(library_path):
                changes.append(change_event)
        if changes:
            handle_changes(changes, self)

    def content_server_start_failed(self, msg):
        self.content_server = None
        error_dialog(self, _('Failed to start Content server'),
                _('Could not start the Content server. Error:\n\n%s')%msg,
                show=True)

    def resizeEvent(self, ev):
        MainWindow.resizeEvent(self, ev)
        self.search.setMaximumWidth(self.width()-150)

    def create_spare_pool(self, *args):
        if self._spare_pool is None:
            num = min(detect_ncpus(), int(config['worker_limit']/2.0))
            self._spare_pool = Pool(max_workers=num, name='GUIPool')

    def spare_pool(self):
        ans, self._spare_pool = self._spare_pool, None
        QTimer.singleShot(1000, self.create_spare_pool)
        return ans

    def do_proceed(self, func, payload):
        if callable(func):
            func(payload)

    def no_op(self, *args):
        pass

    def system_tray_icon_activated(self, r=False):
        if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.MiddleClick, False):
            if self.isVisible():
                if self.isMinimized():
                    self.showNormal()
                else:
                    self.hide_windows()
            else:
                self.show_windows()
                if self.isMinimized():
                    self.showNormal()

    @property
    def is_minimized_to_tray(self):
        return getattr(self, '__systray_minimized', False)

    def ask_a_yes_no_question(self, title, msg, det_msg='',
            show_copy_button=False, ans_when_user_unavailable=True,
            skip_dialog_name=None, skipped_value=True):
        if self.is_minimized_to_tray:
            return ans_when_user_unavailable
        return question_dialog(self, title, msg, det_msg=det_msg,
                show_copy_button=show_copy_button,
                skip_dialog_name=skip_dialog_name,
                skip_dialog_skipped_value=skipped_value)

    def update_toggle_to_tray_action(self, *args):
        if hasattr(self, 'toggle_to_tray_action'):
            self.toggle_to_tray_action.setText(
                _('Hide main window') if self.isVisible() else _('Show main window'))

    def hide_windows(self):
        for window in QApplication.topLevelWidgets():
            if isinstance(window, (MainWindow, QDialog)) and \
                    window.isVisible():
                window.hide()
                setattr(window, '__systray_minimized', True)
        self.update_toggle_to_tray_action()

    def show_windows(self, *args):
        for window in QApplication.topLevelWidgets():
            if getattr(window, '__systray_minimized', False):
                window.show()
                setattr(window, '__systray_minimized', False)
        self.update_toggle_to_tray_action()

    def test_server(self, *args):
        if self.content_server is not None and \
                self.content_server.exception is not None:
            error_dialog(self, _('Failed to start Content server'),
                         unicode(self.content_server.exception)).exec_()

    @property
    def current_db(self):
        return self.library_view.model().db

    def refresh_all(self):
        m = self.library_view.model()
        m.db.data.refresh(clear_caches=False, do_search=False)
        self.saved_searches_changed(recount=False)
        m.resort()
        m.research()
        self.tags_view.recount()

    def another_instance_wants_to_talk(self):
        try:
            msg = self.listener.queue.get_nowait()
        except Empty:
            return
        if msg.startswith('launched:'):
            import json
            try:
                argv = json.loads(msg[len('launched:'):])
            except ValueError:
                prints('Failed to decode message from other instance: %r' % msg)
                if DEBUG:
                    error_dialog(self, 'Invalid message',
                                 'Received an invalid message from other calibre instance.'
                                 ' Do you have multiple versions of calibre installed?',
                                 det_msg='Invalid msg: %r' % msg, show=True)
                argv = ()
            if isinstance(argv, (list, tuple)) and len(argv) > 1:
                files = [os.path.abspath(p) for p in argv[1:] if not os.path.isdir(p) and os.access(p, os.R_OK)]
                if files:
                    self.iactions['Add Books'].add_filesystem_book(files)
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized|Qt.WindowActive)
            self.show_windows()
            self.raise_()
            self.activateWindow()
        elif msg.startswith('refreshdb:'):
            m = self.library_view.model()
            m.db.new_api.reload_from_db()
            self.refresh_all()
        elif msg.startswith('shutdown:'):
            self.quit(confirm_quit=False)
        elif msg.startswith('bookedited:'):
            parts = msg.split(':')[1:]
            try:
                book_id, fmt, library_id = parts[:3]
                book_id = int(book_id)
                m = self.library_view.model()
                db = m.db.new_api
                if m.db.library_id == library_id and db.has_id(book_id):
                    db.format_metadata(book_id, fmt, allow_cache=False, update_db=True)
                    db.update_last_modified((book_id,))
                    m.refresh_ids((book_id,))
            except Exception:
                import traceback
                traceback.print_exc()
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

    def library_moved(self, newloc, copy_structure=False, allow_rebuild=False):
        if newloc is None:
            return
        with self.library_broker:
            default_prefs = None
            try:
                olddb = self.library_view.model().db
                if copy_structure:
                    default_prefs = olddb.prefs
            except:
                olddb = None
            if copy_structure and olddb is not None and default_prefs is not None:
                default_prefs['field_metadata'] = olddb.new_api.field_metadata.all_metadata()
            db = self.library_broker.prepare_for_gui_library_change(newloc)
            if db is None:
                try:
                    db = LibraryDatabase(newloc, default_prefs=default_prefs)
                except apsw.Error:
                    if not allow_rebuild:
                        raise
                    import traceback
                    repair = question_dialog(self, _('Corrupted database'),
                            _('The library database at %s appears to be corrupted. Do '
                            'you want calibre to try and rebuild it automatically? '
                            'The rebuild may not be completely successful.')
                            % force_unicode(newloc, filesystem_encoding),
                            det_msg=traceback.format_exc()
                            )
                    if repair:
                        from calibre.gui2.dialogs.restore_library import repair_library_at
                        if repair_library_at(newloc, parent=self):
                            db = LibraryDatabase(newloc, default_prefs=default_prefs)
                        else:
                            return
                    else:
                        return
            self.library_path = newloc
            prefs['library_path'] = self.library_path
            self.book_on_device(None, reset=True)
            db.set_book_on_device_func(self.book_on_device)
            self.library_view.set_database(db)
            self.tags_view.set_database(db, self.alter_tb)
            self.library_view.model().set_book_on_device_func(self.book_on_device)
            self.status_bar.clear_message()
            self.search.clear()
            self.saved_search.clear()
            self.book_details.reset_info()
            # self.library_view.model().count_changed()
            db = self.library_view.model().db
            self.iactions['Choose Library'].count_changed(db.count())
            self.set_window_title()
            self.apply_named_search_restriction('')  # reset restriction to null
            self.saved_searches_changed(recount=False)  # reload the search restrictions combo box
            if db.prefs['virtual_lib_on_startup']:
                self.apply_virtual_library(db.prefs['virtual_lib_on_startup'])
            self.rebuild_vl_tabs()
            for action in self.iactions.values():
                action.library_changed(db)
            self.library_broker.gui_library_changed(db, olddb)
            if self.device_connected:
                self.set_books_in_library(self.booklists(), reset=True)
                self.refresh_ondevice()
                self.memory_view.reset()
                self.card_a_view.reset()
                self.card_b_view.reset()
            self.set_current_library_information(current_library_name(), db.library_id,
                                                db.field_metadata)
            self.library_view.set_current_row(0)
        # Run a garbage collection now so that it does not freeze the
        # interface later
        gc.collect()

    def set_window_title(self):
        db = self.current_db
        restrictions = [x for x in (db.data.get_base_restriction_name(),
                        db.data.get_search_restriction_name()) if x]
        restrictions = ' :: '.join(restrictions)
        font = QFont()
        if restrictions:
            restrictions = ' :: ' + restrictions
            font.setBold(True)
            font.setItalic(True)
        self.virtual_library.setFont(font)
        title = u'{0} - || {1}{2} ||'.format(
                __appname__, self.iactions['Choose Library'].library_name(), restrictions)
        self.setWindowTitle(title)

    def location_selected(self, location):
        '''
        Called when a location icon is clicked (e.g. Library)
        '''
        page = 0 if location == 'library' else 1 if location == 'main' else 2 if location == 'carda' else 3
        self.stack.setCurrentIndex(page)
        self.book_details.reset_info()
        for x in ('tb', 'cb'):
            splitter = getattr(self, x+'_splitter')
            splitter.button.setEnabled(location == 'library')
        for action in self.iactions.values():
            action.location_selected(location)
        if location == 'library':
            self.virtual_library_menu.setEnabled(True)
            self.highlight_only_button.setEnabled(True)
            self.vl_tabs.setEnabled(True)
        else:
            self.virtual_library_menu.setEnabled(False)
            self.highlight_only_button.setEnabled(False)
            self.vl_tabs.setEnabled(False)
            # Reset the view in case something changed while it was invisible
            self.current_view().reset()
        self.set_number_of_books_shown()
        self.update_status_bar()

    def job_exception(self, job, dialog_title=_('Conversion error'), retry_func=None):
        if not hasattr(self, '_modeless_dialogs'):
            self._modeless_dialogs = []
        minz = self.is_minimized_to_tray
        if self.isVisible():
            for x in list(self._modeless_dialogs):
                if not x.isVisible():
                    self._modeless_dialogs.remove(x)
        try:
            if 'calibre.ebooks.DRMError' in job.details:
                if not minz:
                    from calibre.gui2.dialogs.drm_error import DRMErrorMessage
                    d = DRMErrorMessage(self, _('Cannot convert') + ' ' +
                        job.description.split(':')[-1].partition('(')[-1][:-1])
                    d.setModal(False)
                    d.show()
                    self._modeless_dialogs.append(d)
                return

            if 'calibre.ebooks.oeb.transforms.split.SplitError' in job.details:
                title = job.description.split(':')[-1].partition('(')[-1][:-1]
                msg = _('<p><b>Failed to convert: %s')%title
                msg += '<p>'+_('''
                Many older e-book reader devices are incapable of displaying
                EPUB files that have internal components over a certain size.
                Therefore, when converting to EPUB, calibre automatically tries
                to split up the EPUB into smaller sized pieces.  For some
                files that are large undifferentiated blocks of text, this
                splitting fails.
                <p>You can <b>work around the problem</b> by either increasing the
                maximum split size under <i>EPUB output</i> in the conversion dialog,
                or by turning on Heuristic Processing, also in the conversion
                dialog. Note that if you make the maximum split size too large,
                your e-book reader may have trouble with the EPUB.
                        ''')
                if not minz:
                    d = error_dialog(self, _('Conversion Failed'), msg,
                            det_msg=job.details)
                    d.setModal(False)
                    d.show()
                    self._modeless_dialogs.append(d)
                return

            if 'calibre.ebooks.mobi.reader.mobi6.KFXError:' in job.details:
                if not minz:
                    title = job.description.split(':')[-1].partition('(')[-1][:-1]
                    msg = _('<p><b>Failed to convert: %s') % title
                    idx = job.details.index('calibre.ebooks.mobi.reader.mobi6.KFXError:')
                    msg += '<p>' + re.sub(r'(https:\S+)', r'<a href="\1">{}</a>'.format(_('here')),
                                          job.details[idx:].partition(':')[2].strip())
                    d = error_dialog(self, _('Conversion failed'), msg, det_msg=job.details)
                    d.setModal(False)
                    d.show()
                    self._modeless_dialogs.append(d)
                return

            if 'calibre.web.feeds.input.RecipeDisabled' in job.details:
                if not minz:
                    msg = job.details
                    msg = msg[msg.find('calibre.web.feeds.input.RecipeDisabled:'):]
                    msg = msg.partition(':')[-1]
                    d = error_dialog(self, _('Recipe Disabled'),
                        '<p>%s</p>'%msg)
                    d.setModal(False)
                    d.show()
                    self._modeless_dialogs.append(d)
                return

            if 'calibre.ebooks.conversion.ConversionUserFeedBack:' in job.details:
                if not minz:
                    import json
                    payload = job.details.rpartition(
                        'calibre.ebooks.conversion.ConversionUserFeedBack:')[-1]
                    payload = json.loads('{' + payload.partition('{')[-1])
                    d = {'info':info_dialog, 'warn':warning_dialog,
                            'error':error_dialog}.get(payload['level'],
                                    error_dialog)
                    d = d(self, payload['title'],
                            '<p>%s</p>'%payload['msg'],
                            det_msg=payload['det_msg'])
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
        if not minz:
            self.job_error_dialog.show_error(dialog_title,
                    _('<b>Failed</b>')+': '+unicode(job.description),
                    det_msg=job.details, retry_func=retry_func)

    def read_settings(self):
        geometry = config['main_window_geometry']
        if geometry is not None:
            self.restoreGeometry(geometry)
        self.read_layout_settings()

    def write_settings(self):
        with gprefs:  # Only write to gprefs once
            config.set('main_window_geometry', self.saveGeometry())
            dynamic.set('sort_history', self.library_view.model().sort_history)
            self.save_layout_state()
            self.stack.tb_widget.save_state()

    def quit(self, checked=True, restart=False, debug_on_restart=False,
            confirm_quit=True):
        if self.shutting_down:
            return
        if confirm_quit and not self.confirm_quit():
            return
        try:
            self.shutdown()
        except:
            pass
        self.restart_after_quit = restart
        self.debug_on_restart = debug_on_restart
        QApplication.instance().quit()

    def donate(self, *args):
        open_url(QUrl('https://calibre-ebook.com/donate'))

    def confirm_quit(self):
        if self.job_manager.has_jobs():
            msg = _('There are active jobs. Are you sure you want to quit?')
            if self.job_manager.has_device_jobs():
                msg = '<p>'+__appname__ + \
                      _(''' is communicating with the device!<br>
                      Quitting may cause corruption on the device.<br>
                      Are you sure you want to quit?''')+'</p>'

            if not question_dialog(self, _('Active jobs'), msg):
                return False

        if self.proceed_question.questions:
            msg = _('There are library updates waiting. Are you sure you want to quit?')
            if not question_dialog(self, _('Library updates waiting'), msg):
                return False

        from calibre.db.delete_service import has_jobs
        if has_jobs():
            msg = _('Some deleted books are still being moved to the Recycle '
                    'Bin, if you quit now, they will be left behind. Are you '
                    'sure you want to quit?')
            if not question_dialog(self, _('Active jobs'), msg):
                return False

        return True

    def shutdown(self, write_settings=True):
        self.shutting_down = True
        self.show_shutdown_message()
        self.server_change_notification_timer.stop()

        from calibre.customize.ui import has_library_closed_plugins
        if has_library_closed_plugins():
            self.show_shutdown_message(
                _('Running database shutdown plugins. This could take a few seconds...'))

        self.grid_view.shutdown()
        db = None
        try:
            db = self.library_view.model().db
            cf = db.clean
        except:
            pass
        else:
            cf()
            # Save the current field_metadata for applications like calibre2opds
            # Goes here, because if cf is valid, db is valid.
            db.new_api.set_pref('field_metadata', db.field_metadata.all_metadata())
            db.commit_dirty_cache()
            db.prefs.write_serialized(prefs['library_path'])
        for action in self.iactions.values():
            if not action.shutting_down():
                return
        if write_settings:
            self.write_settings()
        self.check_messages_timer.stop()
        if hasattr(self, 'update_checker'):
            self.update_checker.shutdown()
        self.listener.close()
        self.job_manager.server.close()
        self.job_manager.threaded_server.close()
        self.device_manager.keep_going = False
        self.auto_adder.stop()
        # Do not report any errors that happen after the shutdown
        # We cannot restore the original excepthook as that causes PyQt to
        # call abort() on unhandled exceptions
        import traceback

        def eh(t, v, tb):
            try:
                traceback.print_exception(t, v, tb, file=sys.stderr)
            except:
                pass
        sys.excepthook = eh

        mb = self.library_view.model().metadata_backup
        if mb is not None:
            mb.stop()

        self.library_view.model().close()

        try:
            try:
                if self.content_server is not None:
                    # If the Content server has any sockets being closed then
                    # this can take quite a long time (minutes). Tell the user that it is
                    # happening.
                    self.show_shutdown_message(
                        _('Shutting down the Content server. This could take a while...'))
                    s = self.content_server
                    self.content_server = None
                    s.exit()
            except:
                pass
        except KeyboardInterrupt:
            pass
        self.hide_windows()
        if self._spare_pool is not None:
            self._spare_pool.shutdown()
        from calibre.db.delete_service import shutdown
        shutdown()
        time.sleep(2)
        self.istores.join()
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
        if self.shutting_down:
            return
        self.write_settings()
        if self.system_tray_icon is not None and self.system_tray_icon.isVisible():
            if not dynamic['systray_msg'] and not isosx:
                info_dialog(self, 'calibre', 'calibre '+
                        _('will keep running in the system tray. To close it, '
                        'choose <b>Quit</b> in the context menu of the '
                        'system tray.'), show_copy_button=False).exec_()
                dynamic['systray_msg'] = True
            self.hide_windows()
            e.ignore()
        else:
            if self.confirm_quit():
                try:
                    self.shutdown(write_settings=False)
                except:
                    import traceback
                    traceback.print_exc()
                e.accept()
            else:
                e.ignore()

    # }}}
