__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, time, socket, traceback
from functools import partial

from PyQt4.Qt import (QCoreApplication, QIcon, QObject, QTimer,
        QPixmap, QSplashScreen, QApplication)

from calibre import prints, plugins, force_unicode
from calibre.constants import (iswindows, __appname__, isosx, DEBUG, islinux,
        filesystem_encoding, get_portable_base)
from calibre.utils.ipc import gui_socket_address, RC
from calibre.gui2 import (ORG_NAME, APP_UID, initialize_file_icon_provider,
    Application, choose_dir, error_dialog, question_dialog, gprefs)
from calibre.gui2.main_window import option_parser as _option_parser
from calibre.utils.config import prefs, dynamic
from calibre.library.database2 import LibraryDatabase2
from calibre.library.sqlite import sqlite, DatabaseException

if iswindows:
    winutil = plugins['winutil'][0]

class AbortInit(Exception):
    pass

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
    parser.add_option('--ignore-plugins', default=False, action='store_true',
            help=_('Ignore custom plugins, useful if you installed a plugin'
                ' that is preventing calibre from starting'))
    parser.add_option('-s', '--shutdown-running-calibre', default=False,
            action='store_true',
            help=_('Cause a running calibre instance, if any, to be'
                ' shutdown. Note that if there are running jobs, they '
                'will be silently aborted, so use with care.'))
    return parser

def find_portable_library():
    base = get_portable_base()
    if base is None: return
    import glob
    candidates = [os.path.basename(os.path.dirname(x)) for x in glob.glob(
        os.path.join(base, u'*%smetadata.db'%os.sep))]
    if not candidates:
        candidates = [u'Calibre Library']
    lp = prefs['library_path']
    if not lp:
        lib = os.path.join(base, candidates[0])
    else:
        lib = None
        q = os.path.basename(lp)
        for c in candidates:
            c = c
            if c.lower() == q.lower():
                lib = os.path.join(base, c)
                break
        if lib is None:
            lib = os.path.join(base, candidates[0])

    if len(lib) > 74:
        error_dialog(None, _('Path too long'),
            _("Path to Calibre Portable (%s) "
                'too long. Must be less than 59 characters.')%base, show=True)
        raise AbortInit()

    prefs.set('library_path', lib)
    if not os.path.exists(lib):
        os.mkdir(lib)

def init_qt(args):
    from calibre.gui2.ui import Main
    parser = option_parser()
    opts, args = parser.parse_args(args)
    find_portable_library()
    if opts.with_library is not None:
        if not os.path.exists(opts.with_library):
            os.makedirs(opts.with_library)
        if os.path.isdir(opts.with_library):
            prefs.set('library_path', os.path.abspath(opts.with_library))
            prints('Using library at', prefs['library_path'])
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationName(APP_UID)
    override = 'calibre-gui' if islinux else None
    app = Application(args, override_program_name=override, scan_for_fonts=True)
    actions = tuple(Main.create_application_menubar())
    app.setWindowIcon(QIcon(I('lt.png')))
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
            base = winutil.special_folder_path(winutil.CSIDL_PERSONAL)
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

def repair_library(library_path):
    from calibre.gui2.dialogs.restore_library import repair_library_at
    return repair_library_at(library_path)

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

    def start_gui(self, db):
        from calibre.gui2.ui import Main
        main = Main(self.opts, gui_debug=self.gui_debug)
        if self.splash_screen is not None:
            self.splash_screen.showMessage(_('Initializing user interface...'))
        with gprefs: # Only write gui.json after initialization is complete
            main.initialize(self.library_path, db, self.listener, self.actions)
        if self.splash_screen is not None:
            self.splash_screen.finish(main)
        if DEBUG:
            prints('Started up in %.2f seconds'%(time.time() -
                self.startup_time), 'with', len(db.data), 'books')
        add_filesystem_book = partial(main.iactions['Add Books'].add_filesystem_book, allow_device=False)
        sys.excepthook = main.unhandled_exception
        if len(self.args) > 1:
            files = [os.path.abspath(p) for p in self.args[1:] if not
                    os.path.isdir(p)]
            if len(files) < len(sys.argv[1:]):
                prints('Ignoring directories passed as command line arguments')
            if files:
                add_filesystem_book(files)
        self.app.file_event_hook = add_filesystem_book
        self.main = main

    def initialization_failed(self):
        print 'Catastrophic failure initializing GUI, bailing out...'
        QCoreApplication.exit(1)
        raise SystemExit(1)

    def initialize_db_stage2(self, db, tb):

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

        self.start_gui(db)

    def initialize_db(self):
        db = None
        try:
            db = LibraryDatabase2(self.library_path)
        except (sqlite.Error, DatabaseException):
            repair = question_dialog(self.splash_screen, _('Corrupted database'),
                    _('The library database at %s appears to be corrupted. Do '
                    'you want calibre to try and rebuild it automatically? '
                    'The rebuild may not be completely successful. '
                    'If you say No, a new empty calibre library will be created.')
                    % force_unicode(self.library_path, filesystem_encoding),
                    det_msg=traceback.format_exc()
                    )
            if repair:
                if repair_library(self.library_path):
                    db = LibraryDatabase2(self.library_path)
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
    os.close(fd)

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
    creationflags = 0
    if iswindows:
        import win32process
        creationflags = win32process.CREATE_NO_WINDOW
    subprocess.Popen([exe, '--gui-debug', logpath], stdout=open(logpath, 'w'),
            stderr=subprocess.STDOUT, stdin=open(os.devnull, 'r'),
            creationflags=creationflags)

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
            import subprocess
            print 'Restarting with:', e, sys.argv
            if hasattr(sys, 'frameworks_dir'):
                app = os.path.dirname(os.path.dirname(sys.frameworks_dir))
                subprocess.Popen('sleep 3s; open '+app, shell=True)
            else:
                subprocess.Popen([e] + sys.argv[1:])
    else:
        if iswindows:
            try:
                runner.main.system_tray_icon.hide()
            except:
                pass
    if getattr(runner.main, 'gui_debug', None) is not None:
        e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        import subprocess
        creationflags = 0
        if iswindows:
            import win32process
            creationflags = win32process.CREATE_NO_WINDOW
        subprocess.Popen([e, '--show-gui-debug', runner.main.gui_debug],
            creationflags=creationflags, stdout=open(os.devnull, 'w'),
            stderr=subprocess.PIPE, stdin=open(os.devnull, 'r'))
    return ret

def cant_start(msg=_('If you are sure it is not running')+', ',
        what=None):
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
            what = _('try deleting the file')+': '+ gui_socket_address()

    info = base%(where, msg, what)
    error_dialog(None, _('Cannot Start ')+__appname__,
        '<p>'+(_('%s is already running.')%__appname__)+'</p>'+info, show=True)

    raise SystemExit(1)

def build_pipe(print_error=True):
    t = RC(print_error=print_error)
    t.start()
    t.join(3.0)
    if t.is_alive():
        if iswindows():
            cant_start()
        else:
            f = os.path.expanduser('~/.calibre_calibre GUI.lock')
            cant_start(what=_('try deleting the file')+': '+f)
        raise SystemExit(1)
    return t

def shutdown_other(rc=None):
    if rc is None:
        rc = build_pipe(print_error=False)
        if rc.conn is None:
            prints(_('No running calibre found'))
            return # No running instance found
    from calibre.utils.lock import singleinstance
    rc.conn.send('shutdown:')
    prints(_('Shutdown command sent, waiting for shutdown...'))
    for i in xrange(50):
        if singleinstance('calibre GUI'):
            return
        time.sleep(0.1)
    prints(_('Failed to shutdown running calibre instance'))
    raise SystemExit(1)

def communicate(opts, args):
    t = build_pipe()
    if opts.shutdown_running_calibre:
        shutdown_other(t)
    else:
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

    try:
        app, opts, args, actions = init_qt(args)
    except AbortInit:
        return 1
    from calibre.utils.lock import singleinstance
    from multiprocessing.connection import Listener
    si = singleinstance('calibre GUI')
    if si and opts.shutdown_running_calibre:
        return 0
    if si:
        try:
            listener = Listener(address=gui_socket_address())
        except socket.error:
            if iswindows:
                cant_start()
            if os.path.exists(gui_socket_address()):
                os.remove(gui_socket_address())
            try:
                listener = Listener(address=gui_socket_address())
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
        listener = Listener(address=gui_socket_address())
    except socket.error: # Good si is correct (on UNIX)
        otherinstance = True
    else:
        # On windows only singleinstance can be trusted
        otherinstance = True if iswindows else False
    if not otherinstance and not opts.shutdown_running_calibre:
        return run_gui(opts, args, actions, listener, app, gui_debug=gui_debug)

    communicate(opts, args)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as err:
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

