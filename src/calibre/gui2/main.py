#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
import socket
import sys
import time
import traceback
from functools import partial

import apsw
from PyQt5.Qt import QCoreApplication, QIcon, QObject, QTimer

from calibre import force_unicode, plugins, prints
from calibre.constants import (
    DEBUG, __appname__, filesystem_encoding, get_portable_base, islinux, isosx,
    iswindows, MAIN_APP_UID
)
from calibre.gui2 import (
    Application, choose_dir, error_dialog, gprefs, initialize_file_icon_provider,
    question_dialog, setup_gui_option_parser
)
from calibre.gui2.main_window import option_parser as _option_parser
from calibre.gui2.splash_screen import SplashScreen
from calibre.utils.config import dynamic, prefs
from calibre.utils.ipc import RC, gui_socket_address

if iswindows:
    winutil = plugins['winutil'][0]


class AbortInit(Exception):
    pass


def option_parser():
    parser = _option_parser(_('''\
%prog [options] [path_to_ebook]

Launch the main calibre Graphical User Interface and optionally add the e-book at
path_to_ebook to the database.
'''))
    parser.add_option('--with-library', default=None, action='store',
                      help=_('Use the library located at the specified path.'))
    parser.add_option('--start-in-tray', default=False, action='store_true',
                      help=_('Start minimized to system tray.'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help=_('Ignored, do not use. Present only for legacy reasons'))
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
    setup_gui_option_parser(parser)
    return parser


def find_portable_library():
    base = get_portable_base()
    if base is None:
        return
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
    parser = option_parser()
    opts, args = parser.parse_args(args)
    find_portable_library()
    if opts.with_library is not None:
        libpath = os.path.expanduser(opts.with_library)
        if not os.path.exists(libpath):
            os.makedirs(libpath)
        if os.path.isdir(libpath):
            prefs.set('library_path', os.path.abspath(libpath))
            prints('Using library at', prefs['library_path'])
    override = 'calibre-gui' if islinux else None
    app = Application(args, override_program_name=override)
    app.file_event_hook = EventAccumulator()
    try:
        from PyQt5.Qt import QX11Info
        is_x11 = QX11Info.isPlatformX11()
    except Exception:
        is_x11 = False
    # Ancient broken VNC servers cannot handle icons of size greater than 256
    # https://www.mobileread.com/forums/showthread.php?t=278447
    ic = 'lt.png' if is_x11 else 'library.png'
    app.setWindowIcon(QIcon(I(ic, allow_user_override=False)))
    return app, opts, args


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


def get_library_path(gui_runner):
    library_path = prefs['library_path']
    if library_path is None:  # Need to migrate to new database layout
        base = os.path.expanduser('~')
        if iswindows:
            try:
                base = winutil.special_folder_path(winutil.CSIDL_PERSONAL)
            except ValueError:
                base = None
            if not base or not os.path.exists(base):
                from PyQt5.Qt import QDir
                base = unicode(QDir.homePath()).replace('/', os.sep)
        candidate = gui_runner.choose_dir(base)
        if not candidate:
            candidate = os.path.join(base, 'Calibre Library')
        library_path = os.path.abspath(candidate)
    if not os.path.exists(library_path):
        try:
            os.makedirs(library_path)
        except:
            gui_runner.show_error(_('Failed to create library'),
                    _('Failed to create calibre library at: %r.\n'
                      'You will be asked to choose a new library location.')%library_path,
                    det_msg=traceback.format_exc())
            library_path = gui_runner.choose_dir(get_default_library_path())
    return library_path


def repair_library(library_path):
    from calibre.gui2.dialogs.restore_library import repair_library_at
    return repair_library_at(library_path)


def windows_repair(library_path=None):
    from binascii import hexlify, unhexlify
    import cPickle, subprocess
    if library_path:
        library_path = hexlify(cPickle.dumps(library_path, -1))
        winutil.prepare_for_restart()
        os.environ['CALIBRE_REPAIR_CORRUPTED_DB'] = library_path
        subprocess.Popen([sys.executable])
    else:
        try:
            app = Application([])
            from calibre.gui2.dialogs.restore_library import repair_library_at
            library_path = cPickle.loads(unhexlify(os.environ.pop('CALIBRE_REPAIR_CORRUPTED_DB')))
            done = repair_library_at(library_path, wait_time=4)
        except Exception:
            done = False
            error_dialog(None, _('Failed to repair library'), _(
                'Could not repair library. Click "Show details" for more information.'), det_msg=traceback.format_exc(), show=True)
        if done:
            subprocess.Popen([sys.executable])
        app.quit()


class EventAccumulator(object):

    def __init__(self):
        self.events = []

    def __call__(self, ev):
        self.events.append(ev)


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
        main = self.main = Main(self.opts, gui_debug=self.gui_debug)
        if self.splash_screen is not None:
            self.splash_screen.show_message(_('Initializing user interface...'))
        try:
            with gprefs:  # Only write gui.json after initialization is complete
                main.initialize(self.library_path, db, self.listener, self.actions)
        finally:
            if self.splash_screen is not None:
                self.splash_screen.finish(main)
            self.splash_screen = None
        if DEBUG:
            prints('Started up in %.2f seconds'%(time.time() -
                self.startup_time), 'with', len(db.data), 'books')
        add_filesystem_book = partial(main.iactions['Add Books'].add_filesystem_book, allow_device=False)
        main.set_exception_handler()
        if len(self.args) > 1:
            files = [os.path.abspath(p) for p in self.args[1:] if not
                    os.path.isdir(p)]
            if len(files) < len(sys.argv[1:]):
                prints('Ignoring directories passed as command line arguments')
            if files:
                add_filesystem_book(files)
        for event in self.app.file_event_hook.events:
            add_filesystem_book(event)
        self.app.file_event_hook = add_filesystem_book

    def choose_dir(self, initial_dir):
        self.hide_splash_screen()
        return choose_dir(self.splash_screen, 'choose calibre library',
                _('Choose a location for your new calibre e-book library'),
                default_dir=initial_dir)

    def show_error(self, title, msg, det_msg=''):
        self.hide_splash_screen()
        with self.app:
            error_dialog(self.splash_screen, title, msg, det_msg=det_msg, show=True)

    def initialization_failed(self):
        print 'Catastrophic failure initializing GUI, bailing out...'
        QCoreApplication.exit(1)
        raise SystemExit(1)

    def initialize_db_stage2(self, db, tb):
        from calibre.db.legacy import LibraryDatabase

        if db is None and tb is not None:
            # DB Repair failed
            self.show_error(_('Repairing failed'), _(
                'The database repair failed. Starting with a new empty library.'),
                            det_msg=tb)
        if db is None:
            candidate = self.choose_dir(get_default_library_path())
            if not candidate:
                self.initialization_failed()

            try:
                self.library_path = candidate
                db = LibraryDatabase(candidate)
            except:
                self.show_error(_('Bad database location'), _(
                    'Bad database location %r. calibre will now quit.')%self.library_path,
                    det_msg=traceback.format_exc())
                self.initialization_failed()

        try:
            self.start_gui(db)
        except Exception:
            self.show_error(_('Startup error'), _(
                'There was an error during {0} startup. Parts of {0} may not function.'
                ' Click Show details to learn more.').format(__appname__),
                         det_msg=traceback.format_exc())

    def initialize_db(self):
        from calibre.db.legacy import LibraryDatabase
        db = None
        try:
            db = LibraryDatabase(self.library_path)
        except apsw.Error:
            with self.app:
                self.hide_splash_screen()
                repair = question_dialog(self.splash_screen, _('Corrupted database'),
                        _('The library database at %s appears to be corrupted. Do '
                        'you want calibre to try and rebuild it automatically? '
                        'The rebuild may not be completely successful. '
                        'If you say No, a new empty calibre library will be created.')
                        % force_unicode(self.library_path, filesystem_encoding),
                        det_msg=traceback.format_exc()
                        )
            if repair:
                if iswindows:
                    # On some windows systems the existing db file gets locked
                    # by something when running restore from the main process.
                    # So run the restore in a separate process.
                    windows_repair(self.library_path)
                    self.app.quit()
                    return
                if repair_library(self.library_path):
                    db = LibraryDatabase(self.library_path)
        except:
            self.show_error(_('Bad database location'),
                    _('Bad database location %r. Will start with '
                    ' a new, empty calibre library')%self.library_path,
                    det_msg=traceback.format_exc())

        self.initialize_db_stage2(db, None)

    def show_splash_screen(self):
        self.splash_screen = SplashScreen()
        self.splash_screen.show()
        self.splash_screen.show_message(_('Starting %s: Loading books...') % __appname__)

    def hide_splash_screen(self):
        if self.splash_screen is not None:
            self.splash_screen.hide()
        self.splash_screen = None

    def initialize(self, *args):
        if gprefs['show_splash_screen'] and not self.opts.start_in_tray:
            self.show_splash_screen()
        self.library_path = get_library_path(self)
        if not self.library_path:
            self.initialization_failed()

        self.initialize_db()


def get_debug_executable():
    e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    if hasattr(sys, 'frameworks_dir'):
        base = os.path.dirname(sys.frameworks_dir)
        if 'calibre-debug.app' not in base:
            base = os.path.join(base, 'calibre-debug.app', 'Contents')
        exe = os.path.basename(e)
        if '-debug' not in exe:
            exe += '-debug'
        exe = os.path.join(base, 'MacOS', exe)
    else:
        exe = e
        if '-debug' not in exe:
            base, ext = os.path.splitext(e)
            exe = base + '-debug' + ext
    return exe


def run_in_debug_mode(logpath=None):
    import tempfile, subprocess
    fd, logpath = tempfile.mkstemp('.txt')
    os.close(fd)

    exe = get_debug_executable()
    print 'Starting debug executable:', exe
    creationflags = 0
    if iswindows:
        import win32process
        creationflags = win32process.CREATE_NO_WINDOW
    subprocess.Popen([exe, '--gui-debug', logpath], stdout=open(logpath, 'w'),
            stderr=subprocess.STDOUT, stdin=open(os.devnull, 'r'),
            creationflags=creationflags)


def shellquote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def run_gui(opts, args, listener, app, gui_debug=None):
    initialize_file_icon_provider()
    app.load_builtin_fonts(scan_for_fonts=True)
    if not dynamic.get('welcome_wizard_was_run', False):
        from calibre.gui2.wizard import wizard
        wizard().exec_()
        dynamic.set('welcome_wizard_was_run', True)
    from calibre.gui2.ui import Main
    if isosx:
        actions = tuple(Main.create_application_menubar())
    else:
        actions = tuple(Main.get_menubar_actions())
    runner = GuiRunner(opts, args, actions, listener, app, gui_debug=gui_debug)
    ret = app.exec_()
    if getattr(runner.main, 'run_wizard_b4_shutdown', False):
        from calibre.gui2.wizard import wizard
        wizard().exec_()
    if getattr(runner.main, 'restart_after_quit', False):
        e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        if getattr(runner.main, 'debug_on_restart', False) or gui_debug is not None:
            run_in_debug_mode()
        else:
            import subprocess
            if hasattr(sys, 'frameworks_dir'):
                app = os.path.dirname(os.path.dirname(os.path.realpath(sys.frameworks_dir)))
                prints('Restarting with:', app)
                subprocess.Popen('sleep 3s; open ' + shellquote(app), shell=True)
            else:
                if iswindows and hasattr(winutil, 'prepare_for_restart'):
                    winutil.prepare_for_restart()
                args = ['-g'] if os.path.splitext(e)[0].endswith('-debug') else []
                prints('Restarting with:', ' '.join([e] + args))
                subprocess.Popen([e] + args)
    else:
        if iswindows:
            try:
                runner.main.system_tray_icon.hide()
            except:
                pass
    if getattr(runner.main, 'gui_debug', None) is not None:
        e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        debugfile = runner.main.gui_debug
        from calibre.gui2 import open_local_file
        if iswindows:
            with open(debugfile, 'r+b') as f:
                raw = f.read()
                raw = re.sub(b'(?<!\r)\n', b'\r\n', raw)
                f.seek(0)
                f.truncate()
                f.write(raw)
        open_local_file(debugfile)
    return ret


singleinstance_name = 'calibre_GUI'


def cant_start(msg=_('If you are sure it is not running')+', ',
               det_msg=_('Timed out waiting for response from running calibre'),
               listener_failed=False):
    base = '<p>%s</p><p>%s %s'
    where = __appname__ + ' '+_('may be running in the system tray, in the')+' '
    if isosx:
        where += _('upper right region of the screen.')
    else:
        where += _('lower right region of the screen.')
    if iswindows or islinux:
        what = _('try rebooting your computer.')
    else:
        if listener_failed:
            path = gui_socket_address()
        else:
            from calibre.utils.lock import singleinstance_path
            path = singleinstance_path(singleinstance_name)
        what = _('try deleting the file: "%s"') % path

    info = base%(where, msg, what)
    error_dialog(None, _('Cannot Start ')+__appname__,
        '<p>'+(_('%s is already running.')%__appname__)+'</p>'+info, det_msg=det_msg, show=True)

    raise SystemExit(1)


def build_pipe(print_error=True):
    t = RC(print_error=print_error)
    t.start()
    t.join(3.0)
    if t.is_alive():
        cant_start()
        raise SystemExit(1)
    return t


def shutdown_other(rc=None):
    if rc is None:
        rc = build_pipe(print_error=False)
        if rc.conn is None:
            prints(_('No running calibre found'))
            return  # No running instance found
    from calibre.utils.lock import singleinstance
    rc.conn.send('shutdown:')
    prints(_('Shutdown command sent, waiting for shutdown...'))
    for i in xrange(50):
        if singleinstance(singleinstance_name):
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
            args[1:] = [os.path.abspath(x) if os.path.exists(x) else x for x in args[1:]]
        import json
        t.conn.send('launched:'+json.dumps(args))
    t.conn.close()
    raise SystemExit(0)


def create_listener():
    if islinux:
        from calibre.utils.ipc.server import LinuxListener as Listener
    else:
        from multiprocessing.connection import Listener
    return Listener(address=gui_socket_address())


def main(args=sys.argv):
    if iswindows and 'CALIBRE_REPAIR_CORRUPTED_DB' in os.environ:
        windows_repair()
        return 0
    gui_debug = None
    if args[0] == '__CALIBRE_GUI_DEBUG__':
        gui_debug = args[1]
        args = ['calibre']

    if iswindows:
        # Ensure that all ebook editor instances are grouped together in the task
        # bar. This prevents them from being grouped with viewer process when
        # launched from within calibre, as both use calibre-parallel.exe
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(MAIN_APP_UID)
        except Exception:
            pass  # Only available on windows 7 and newer

    try:
        app, opts, args = init_qt(args)
    except AbortInit:
        return 1
    try:
        from calibre.utils.lock import singleinstance
        si = singleinstance(singleinstance_name)
    except Exception:
        error_dialog(None, _('Cannot start calibre'), _(
            'Failed to start calibre, single instance locking failed. Click "Show Details" for more information'),
                     det_msg=traceback.format_exc(), show=True)
        return 1
    if si and opts.shutdown_running_calibre:
        return 0
    if si:
        try:
            listener = create_listener()
        except socket.error:
            if iswindows or islinux:
                cant_start(det_msg=traceback.format_exc(), listener_failed=True)
            if os.path.exists(gui_socket_address()):
                os.remove(gui_socket_address())
            try:
                listener = create_listener()
            except socket.error:
                cant_start(det_msg=traceback.format_exc(), listener_failed=True)
            else:
                return run_gui(opts, args, listener, app,
                        gui_debug=gui_debug)
        else:
            return run_gui(opts, args, listener, app,
                    gui_debug=gui_debug)
    otherinstance = False
    try:
        listener = create_listener()
    except socket.error:  # Good singleinstance is correct (on UNIX)
        otherinstance = True
    else:
        # On windows only singleinstance can be trusted
        otherinstance = True if iswindows else False
    if not otherinstance and not opts.shutdown_running_calibre:
        return run_gui(opts, args, listener, app, gui_debug=gui_debug)

    communicate(opts, args)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as err:
        if not iswindows:
            raise
        tb = traceback.format_exc()
        from PyQt5.Qt import QErrorMessage
        logfile = os.path.join(os.path.expanduser('~'), 'calibre.log')
        if os.path.exists(logfile):
            log = open(logfile).read().decode('utf-8', 'ignore')
            d = QErrorMessage()
            d.showMessage(('<b>Error:</b>%s<br><b>Traceback:</b><br>'
                '%s<b>Log:</b><br>%s')%(unicode(err),
                    unicode(tb).replace('\n', '<br>'),
                    log.replace('\n', '<br>')))
