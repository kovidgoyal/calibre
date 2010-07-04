#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''The main GUI'''

import collections, os, sys, textwrap, time
from Queue import Queue, Empty
from threading import Thread
from PyQt4.Qt import Qt, SIGNAL, QObject, QTimer, \
                     QPixmap, QMenu, QIcon, pyqtSignal, \
                     QDialog, \
                     QSystemTrayIcon, QApplication, QKeySequence, QAction, \
                     QMessageBox, QHelpEvent

from calibre import  prints, patheq
from calibre.constants import __appname__, isosx
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import prefs, dynamic
from calibre.utils.ipc.server import Server
from calibre.gui2 import error_dialog, GetMetadata, open_local_file, \
        gprefs, max_available_height, config, info_dialog
from calibre.gui2.cover_flow import CoverFlowMixin
from calibre.gui2.widgets import ProgressIndicator
from calibre.gui2.wizard import move_library
from calibre.gui2.dialogs.scheduler import Scheduler
from calibre.gui2.update import UpdateMixin
from calibre.gui2.main_window import MainWindow
from calibre.gui2.main_ui import Ui_MainWindow
from calibre.gui2.device import DeviceMixin
from calibre.gui2.jobs import JobManager, JobsDialog, JobsButton
from calibre.gui2.dialogs.config import ConfigDialog

from calibre.gui2.dialogs.book_info import BookInfo
from calibre.library.database2 import LibraryDatabase2
from calibre.gui2.init import ToolbarMixin, LibraryViewMixin, LayoutMixin
from calibre.gui2.search_box import SearchBoxMixin, SavedSearchBoxMixin
from calibre.gui2.search_restriction_mixin import SearchRestrictionMixin
from calibre.gui2.tag_view import TagBrowserMixin
from calibre.gui2.actions import AnnotationsAction, AddAction, DeleteAction, \
    EditMetadataAction, SaveToDiskAction, GenerateCatalogAction, FetchNewsAction, \
    ConvertAction, ViewAction


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

    tooltip_requested = pyqtSignal(object)

    def __init__(self, icon, parent):
        QSystemTrayIcon.__init__(self, icon, parent)

    def event(self, ev):
        if ev.type() == ev.ToolTip:
            evh = QHelpEvent(ev)
            self.tooltip_requested.emit(
                    (self, evh.globalPos()))
            return True
        return QSystemTrayIcon.event(self, ev)

# }}}

class Main(MainWindow, Ui_MainWindow, DeviceMixin, ToolbarMixin, # {{{
        TagBrowserMixin, CoverFlowMixin, LibraryViewMixin, SearchBoxMixin,
        SavedSearchBoxMixin, SearchRestrictionMixin, LayoutMixin, UpdateMixin,
        AnnotationsAction, AddAction, DeleteAction,
        EditMetadataAction, SaveToDiskAction, GenerateCatalogAction, FetchNewsAction,
        ConvertAction, ViewAction):
    'The main GUI'


    def __init__(self, opts, parent=None):
        MainWindow.__init__(self, opts, parent)
        self.opts = opts

    def initialize(self, library_path, db, listener, actions):
        opts = self.opts
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
        self.jobs_button = JobsButton(horizontal=True)
        self.jobs_button.initialize(self.jobs_dialog, self.job_manager)
        # }}}

        LayoutMixin.__init__(self)
        DeviceMixin.__init__(self)

        self.restriction_count_of_books_in_view = 0
        self.restriction_count_of_books_in_library = 0
        self.restriction_in_effect = False

        self.progress_indicator = ProgressIndicator(self)
        self.progress_indicator.pos = (0, 20)
        self.verbose = opts.verbose
        self.get_metadata = GetMetadata()
        self.upload_memory = {}
        self.delete_memory = {}
        self.conversion_jobs = {}
        self.persistent_files = []
        self.metadata_dialogs = []
        self.default_thumbnail = None
        self.tb_wrapper = textwrap.TextWrapper(width=40)
        self.viewers = collections.deque()
        self.content_server = None
        self.system_tray_icon = SystemTrayIcon(QIcon(I('library.png')), self)
        self.system_tray_icon.setToolTip('calibre')
        self.system_tray_icon.tooltip_requested.connect(
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
        self.donate_button.setStatusTip(self.donate_button.toolTip())
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


        ####################### Start spare job server ########################
        QTimer.singleShot(1000, self.add_spare_server)

        ####################### Location View ########################
        QObject.connect(self.location_view,
                SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        QObject.connect(self.location_view,
                SIGNAL('umount_device()'),
                        self.device_manager.umount_device)
        self.eject_action.triggered.connect(self.device_manager.umount_device)

        #################### Update notification ###################
        UpdateMixin.__init__(self, opts)

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

        self.keyboard_interrupt.connect(self.quit, type=Qt.QueuedConnection)
        AddAction.__init__(self)

        self.read_settings()
        self.finalize_layout()

    def resizeEvent(self, ev):
        MainWindow.resizeEvent(self, ev)
        self.search.setMaximumWidth(self.width()-150)

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
            self.set_device_menu_items_state(bool(self.device_connected))
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
        self.tags_view.set_database(db, self.tag_match, self.sort_by)
        self.library_view.model().set_book_on_device_func(self.book_on_device)
        self.status_bar.clear_message()
        self.search.clear_to_help()
        self.book_details.reset_info()
        self.library_view.model().count_changed()
        prefs['library_path'] = self.library_path

    def show_book_info(self, *args):
        if self.current_view() is not self.library_view:
            error_dialog(self, _('No detailed info available'),
                _('No detailed information is available for books '
                  'on the device.')).exec_()
            return
        index = self.library_view.currentIndex()
        if index.isValid():
            BookInfo(self, self.library_view, index).show()

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
            # Reset the view in case something changed while it was invisible
            self.current_view().reset()
        self.set_number_of_books_shown()



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
        open_local_file(pt.name)


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
        cc = self.library_view.model().cover_cache
        if cc is not None:
            cc.stop()
        self.hide_windows()
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

    # }}}

