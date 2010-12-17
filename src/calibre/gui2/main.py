__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, time, socket, traceback
from functools import partial

from PyQt4.Qt import QCoreApplication, QIcon, QMessageBox, QObject, QTimer, \
        QThread, pyqtSignal, Qt, QProgressDialog, QString, QPixmap, \
        QSplashScreen, QApplication

from calibre import prints, plugins
from calibre.constants import iswindows, __appname__, isosx, DEBUG, \
        filesystem_encoding
from calibre.utils.ipc import ADDRESS, RC
from calibre.gui2 import ORG_NAME, APP_UID, initialize_file_icon_provider, \
    Application, choose_dir, error_dialog, question_dialog, gprefs
from calibre.gui2.main_window import option_parser as _option_parser
from calibre.utils.config import prefs, dynamic
from calibre.library.database2 import LibraryDatabase2
from calibre.library.sqlite import sqlite, DatabaseException

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
    parser.add_option('--no-update-check', default=False, action='store_true',
            help=_('Do not check for updates'))
    return parser

def init_qt(args):
    from calibre.gui2.ui import Main
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if opts.with_library is not None:
        if not os.path.exists(opts.with_library):
            os.makedirs(opts.with_library)
        if os.path.isdir(opts.with_library):
            prefs.set('library_path', os.path.abspath(opts.with_library))
            prints('Using library at', prefs['library_path'])
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationName(APP_UID)
    app = Application(args)
    actions = tuple(Main.create_application_menubar())
    app.setWindowIcon(QIcon(I('library.png')))
    return app, opts, args, actions


def get_default_library_path():
    fname = _('Calibre Library')
    if iswindows:
        fname = 'Calibre Library'
    if isinstance(fname, unicode):
        try:
            fname = fname.encode(filesystem_encoding)
        except:
            fname = 'Calibre Library'
    x = os.path.expanduser('~'+os.sep+fname)
    if not os.path.exists(x):
        try:
            os.makedirs(x)
        except:
            x = os.path.expanduser('~')
    return x


def get_library_path(parent=None):
    library_path = prefs['library_path']
    if library_path is None: # Need to migrate to new database layout
        base = os.path.expanduser('~')
        if iswindows:
            base = plugins['winutil'][0].special_folder_path(
                    plugins['winutil'][0].CSIDL_PERSONAL)
            if not base or not os.path.exists(base):
                from PyQt4.Qt import QDir
                base = unicode(QDir.homePath()).replace('/', os.sep)
        candidate = choose_dir(None, 'choose calibre library',
                _('Choose a location for your calibre e-book library'),
                default_dir=base)
        if not candidate:
            candidate = os.path.join(base, 'Calibre Library')
        library_path = os.path.abspath(candidate)
    if not os.path.exists(library_path):
        try:
            os.makedirs(library_path)
        except:
            error_dialog(parent, _('Failed to create library'),
                    _('Failed to create calibre library at: %r.')%library_path,
                    det_msg=traceback.format_exc(), show=True)
            library_path = choose_dir(parent, 'choose calibre library',
                _('Choose a location for your new calibre e-book library'),
                default_dir=get_default_library_path())
    return library_path

class DBRepair(QThread):

    repair_done = pyqtSignal(object, object)
    progress = pyqtSignal(object, object)

    def __init__(self, library_path, parent, pd):
        QThread.__init__(self, parent)
        self.library_path = library_path
        self.pd = pd
        self.progress.connect(self._callback, type=Qt.QueuedConnection)

    def _callback(self, num, is_length):
        if is_length:
            self.pd.setRange(0, num-1)
            num = 0
        self.pd.setValue(num)

    def callback(self, num, is_length):
        self.progress.emit(num, is_length)

    def run(self):
        from calibre.debug import reinit_db
        try:
            reinit_db(os.path.join(self.library_path, 'metadata.db'),
                    self.callback)
            db = LibraryDatabase2(self.library_path)
            tb = None
        except:
            db, tb = None, traceback.format_exc()
        self.repair_done.emit(db, tb)

class GuiRunner(QObject):
    '''Make sure an event loop is running before starting the main work of
    initialization'''

    def __init__(self, opts, args, actions, listener, app, gui_debug=None):
        self.startup_time = time.time()
        self.opts, self.args, self.listener, self.app = opts, args, listener, app
        self.gui_debug = gui_debug
        self.actions = actions
        self.main = None
        QObject.__init__(self)
        self.splash_screen = None
        self.timer = QTimer.singleShot(1, self.initialize)
        if DEBUG:
            prints('Starting up...')

    def start_gui(self):
        from calibre.gui2.ui import Main
        main = Main(self.opts, gui_debug=self.gui_debug)
        if self.splash_screen is not None:
            self.splash_screen.showMessage(_('Initializing user interface...'))
            self.splash_screen.finish(main)
        main.initialize(self.library_path, self.db, self.listener, self.actions)
        if DEBUG:
            prints('Started up in', time.time() - self.startup_time)
        add_filesystem_book = partial(main.iactions['Add Books'].add_filesystem_book, allow_device=False)
        sys.excepthook = main.unhandled_exception
        if len(self.args) > 1:
            p = os.path.abspath(self.args[1])
            add_filesystem_book(p)
        self.app.file_event_hook = add_filesystem_book
        self.main = main

    def initialization_failed(self):
        print 'Catastrophic failure initializing GUI, bailing out...'
        QCoreApplication.exit(1)
        raise SystemExit(1)

    def initialize_db_stage2(self, db, tb):
        repair_pd = getattr(self, 'repair_pd', None)
        if repair_pd is not None:
            repair_pd.cancel()

        if db is None and tb is not None:
            # DB Repair failed
            error_dialog(self.splash_screen, _('Repairing failed'),
                    _('The database repair failed. Starting with '
                        'a new empty library.'),
                    det_msg=tb, show=True)
        if db is None:
            candidate = choose_dir(self.splash_screen, 'choose calibre library',
                _('Choose a location for your new calibre e-book library'),
                default_dir=get_default_library_path())
            if not candidate:
                self.initialization_failed()

            try:
                self.library_path = candidate
                db = LibraryDatabase2(candidate)
            except:
                error_dialog(self.splash_screen, _('Bad database location'),
                    _('Bad database location %r. calibre will now quit.'
                     )%self.library_path,
                    det_msg=traceback.format_exc(), show=True)
                self.initialization_failed()

        self.db = db
        self.start_gui()

    def initialize_db(self):
        db = None
        try:
            db = LibraryDatabase2(self.library_path)
        except (sqlite.Error, DatabaseException):
            repair = question_dialog(self.splash_screen, _('Corrupted database'),
                    _('Your calibre database appears to be corrupted. Do '
                    'you want calibre to try and repair it automatically? '
                    'If you say No, a new empty calibre library will be created.'),
                    det_msg=traceback.format_exc()
                    )
            if repair:
                self.repair_pd = QProgressDialog(_('Repairing database. This '
                    'can take a very long time for a large collection'), QString(),
                    0, 0)
                self.repair_pd.setWindowModality(Qt.WindowModal)
                self.repair_pd.show()

                self.repair = DBRepair(self.library_path, self, self.repair_pd)
                self.repair.repair_done.connect(self.initialize_db_stage2,
                        type=Qt.QueuedConnection)
                self.repair.start()
                return
        except:
            error_dialog(self.splash_screen, _('Bad database location'),
                    _('Bad database location %r. Will start with '
                    ' a new, empty calibre library')%self.library_path,
                    det_msg=traceback.format_exc(), show=True)

        self.initialize_db_stage2(db, None)

    def show_splash_screen(self):
        self.splash_pixmap = QPixmap()
        self.splash_pixmap.load(I('library.png'))
        self.splash_screen = QSplashScreen(self.splash_pixmap)
        self.splash_screen.showMessage(_('Starting %s: Loading books...') %
                __appname__)
        self.splash_screen.show()
        QApplication.instance().processEvents()

    def initialize(self, *args):
        if gprefs['show_splash_screen']:
            self.show_splash_screen()

        self.library_path = get_library_path(parent=self.splash_screen)
        if not self.library_path:
            self.initialization_failed()

        self.initialize_db()

def run_in_debug_mode(logpath=None):
    e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    import tempfile, subprocess
    fd, logpath = tempfile.mkstemp('.txt')

    if hasattr(sys, 'frameworks_dir'):
        base = os.path.dirname(sys.frameworks_dir)
        if 'console.app' not in base:
            base = os.path.join(base, 'console.app', 'Contents')
        exe = os.path.basename(e)
        exe = os.path.join(base, 'MacOS', exe+'-debug')
    else:
        base, ext = os.path.splitext(e)
        exe = base + '-debug' + ext
    print 'Starting debug executable:', exe
    subprocess.Popen([exe, '--gui-debug', logpath], stdout=fd, stderr=fd)
    time.sleep(1) # Give subprocess a change to launch, before fd is closed

def run_gui(opts, args, actions, listener, app, gui_debug=None):
    initialize_file_icon_provider()
    if not dynamic.get('welcome_wizard_was_run', False):
        from calibre.gui2.wizard import wizard
        wizard().exec_()
        dynamic.set('welcome_wizard_was_run', True)
    runner = GuiRunner(opts, args, actions, listener, app, gui_debug=gui_debug)
    ret = app.exec_()
    if getattr(runner.main, 'run_wizard_b4_shutdown', False):
        from calibre.gui2.wizard import wizard
        wizard().exec_()
    if getattr(runner.main, 'restart_after_quit', False):
        e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        if getattr(runner.main, 'debug_on_restart', False):
            run_in_debug_mode()
        else:
            print 'Restarting with:', e, sys.argv
            if hasattr(sys, 'frameworks_dir'):
                app = os.path.dirname(os.path.dirname(sys.frameworks_dir))
                import subprocess
                subprocess.Popen('sleep 3s; open '+app, shell=True)
            else:
                os.execvp(e, sys.argv)
    else:
        if iswindows:
            try:
                runner.main.system_tray_icon.hide()
            except:
                pass
    if runner.main.gui_debug is not None:
        e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        import subprocess
        subprocess.Popen([e, '--show-gui-debug', runner.main.gui_debug])
    return ret

def cant_start(msg=_('If you are sure it is not running')+', ',
        what=None):
    d = QMessageBox(QMessageBox.Critical, _('Cannot Start ')+__appname__,
        '<p>'+(_('%s is already running.')%__appname__)+'</p>',
        QMessageBox.Ok)
    base = '<p>%s</p><p>%s %s'
    where = __appname__ + ' '+_('may be running in the system tray, in the')+' '
    if isosx:
        where += _('upper right region of the screen.')
    else:
        where += _('lower right region of the screen.')
    if what is None:
        if iswindows:
            what = _('try rebooting your computer.')
        else:
            what = _('try deleting the file')+': '+ADDRESS

    d.setInformativeText(base%(where, msg, what))
    d.exec_()
    raise SystemExit(1)

def communicate(args):
    t = RC()
    t.start()
    time.sleep(3)
    if not t.done:
        f = os.path.expanduser('~/.calibre_calibre GUI.lock')
        cant_start(what=_('try deleting the file')+': '+f)
        raise SystemExit(1)

    if len(args) > 1:
        args[1] = os.path.abspath(args[1])
    t.conn.send('launched:'+repr(args))
    t.conn.close()
    raise SystemExit(0)


def main(args=sys.argv):
    gui_debug = None
    if args[0] == '__CALIBRE_GUI_DEBUG__':
        gui_debug = args[1]
        args = ['calibre']

    app, opts, args, actions = init_qt(args)
    from calibre.utils.lock import singleinstance
    from multiprocessing.connection import Listener
    si = singleinstance('calibre GUI')
    if si:
        try:
            listener = Listener(address=ADDRESS)
        except socket.error:
            if iswindows:
                cant_start()
            os.remove(ADDRESS)
            try:
                listener = Listener(address=ADDRESS)
            except socket.error:
                cant_start()
            else:
                return run_gui(opts, args, actions, listener, app,
                        gui_debug=gui_debug)
        else:
            return run_gui(opts, args, actions, listener, app,
                    gui_debug=gui_debug)
    otherinstance = False
    try:
        listener = Listener(address=ADDRESS)
    except socket.error: # Good si is correct (on UNIX)
        otherinstance = True
    else:
        # On windows only singleinstance can be trusted
        otherinstance = True if iswindows else False
    if not otherinstance:
        return run_gui(opts, args, actions, listener, app, gui_debug=gui_debug)

    communicate(args)

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
            d = QErrorMessage()
            d.showMessage(('<b>Error:</b>%s<br><b>Traceback:</b><br>'
                '%s<b>Log:</b><br>%s')%(unicode(err),
                    unicode(tb).replace('\n', '<br>'),
                    log.replace('\n', '<br>')))

