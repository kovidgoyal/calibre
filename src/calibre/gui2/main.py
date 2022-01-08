#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
import sys
import time
import traceback

import apsw
from qt.core import QCoreApplication, QIcon, QObject, QTimer

from calibre import force_unicode, prints
from calibre.constants import (
    DEBUG, MAIN_APP_UID, __appname__, filesystem_encoding, get_portable_base,
    islinux, ismacos, iswindows
)
from calibre.gui2 import (
    Application, choose_dir, error_dialog, gprefs, initialize_file_icon_provider,
    question_dialog, setup_gui_option_parser
)
from calibre.gui2.listener import send_message_in_process
from calibre.gui2.main_window import option_parser as _option_parser
from calibre.gui2.splash_screen import SplashScreen
from calibre.utils.config import dynamic, prefs
from calibre.utils.lock import SingleInstance
from calibre.utils.monotonic import monotonic
from polyglot.builtins import as_bytes, environ_item

after_quit_actions = {'debug_on_restart': False, 'restart_after_quit': False, 'no_plugins_on_restart': False}
if iswindows:
    from calibre_extensions import winutil


class AbortInit(Exception):
    pass


def option_parser():
    parser = _option_parser(_('''\
%prog [options] [path_to_ebook or calibre url ...]

Launch the main calibre Graphical User Interface and optionally add the e-book at
path_to_ebook to the database. You can also specify calibre URLs to perform various
different actions, than just adding books. For example:

calibre://view-book/test_library/1842/epub

Will open the book with id 1842 in the EPUB format from the library
"test_library" in the calibre E-book viewer. Library names are the folder names of the
libraries with spaces replaced by underscores. A full description of the
various URL based actions is in the User Manual.
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
        os.path.join(base, '*%smetadata.db'%os.sep))]
    if not candidates:
        candidates = ['Calibre Library']
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
                'too long. It must be less than 59 characters.')%base, show=True)
        raise AbortInit()

    prefs.set('library_path', lib)
    if not os.path.exists(lib):
        os.mkdir(lib)


def init_qt(args):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if os.environ.pop('CALIBRE_IGNORE_PLUGINS_ON_RESTART', '') == '1':
        opts.ignore_plugins = True
    find_portable_library()
    if opts.with_library is not None:
        libpath = os.path.expanduser(opts.with_library)
        if not os.path.exists(libpath):
            os.makedirs(libpath)
        if os.path.isdir(libpath):
            prefs.set('library_path', os.path.abspath(libpath))
            prints('Using library at', prefs['library_path'])
    override = 'calibre-gui' if islinux else None
    app = Application(args, override_program_name=override, windows_app_uid=MAIN_APP_UID)

    app.file_event_hook = EventAccumulator()
    try:
        is_x11 = app.platformName() == 'xcb'
    except Exception:
        import traceback
        traceback.print_exc()
        is_x11 = False
    # Ancient broken VNC servers cannot handle icons of size greater than 256
    # https://www.mobileread.com/forums/showthread.php?t=278447
    ic = 'lt.png' if is_x11 else 'library.png'
    app.setWindowIcon(QIcon.ic(ic))
    return app, opts, args


def get_default_library_path():
    fname = _('Calibre Library')
    if iswindows:
        fname = 'Calibre Library'
    if isinstance(fname, str):
        try:
            fname.encode(filesystem_encoding)
        except Exception:
            fname = 'Calibre Library'
    x = os.path.expanduser(os.path.join('~', fname))
    if not os.path.exists(x):
        try:
            os.makedirs(x)
        except Exception:
            x = os.path.expanduser('~')
    return x


def try_other_known_library_paths():
    stats = gprefs.get('library_usage_stats', {})
    if stats:
        for candidate in sorted(stats.keys(), key=stats.__getitem__, reverse=True):
            candidate = os.path.abspath(candidate)
            if os.path.exists(candidate):
                return candidate


def get_library_path(gui_runner):
    library_path = prefs['library_path']
    if library_path is None:  # Need to migrate to new database layout
        base = os.path.expanduser('~')
        if not base or not os.path.exists(base):
            from qt.core import QDir
            base = str(QDir.homePath()).replace('/', os.sep)
        candidate = gui_runner.choose_dir(base)
        if not candidate:
            candidate = os.path.join(base, 'Calibre Library')
        library_path = os.path.abspath(candidate)
    elif not os.path.exists(library_path):
        q = try_other_known_library_paths()
        if q:
            library_path = q
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
    import subprocess
    from calibre.utils.serialize import json_dumps, json_loads
    from polyglot.binary import as_hex_unicode, from_hex_bytes
    if library_path:
        library_path = as_hex_unicode(json_dumps(library_path))
        winutil.prepare_for_restart()
        os.environ['CALIBRE_REPAIR_CORRUPTED_DB'] = environ_item(library_path)
        subprocess.Popen([sys.executable])
    else:
        try:
            app = Application([])
            from calibre.gui2.dialogs.restore_library import repair_library_at
            library_path = json_loads(from_hex_bytes(os.environ.pop('CALIBRE_REPAIR_CORRUPTED_DB')))
            done = repair_library_at(library_path, wait_time=4)
        except Exception:
            done = False
            error_dialog(None, _('Failed to repair library'), _(
                'Could not repair library. Click "Show details" for more information.'), det_msg=traceback.format_exc(), show=True)
        if done:
            subprocess.Popen([sys.executable])
        app.quit()


class EventAccumulator:

    def __init__(self):
        self.events = []

    def __call__(self, ev):
        self.events.append(ev)


class GuiRunner(QObject):
    '''Make sure an event loop is running before starting the main work of
    initialization'''

    def __init__(self, opts, args, actions, app, gui_debug=None):
        self.startup_time = monotonic()
        self.timed_print('Starting up...')
        self.opts, self.args, self.app = opts, args, app
        self.gui_debug = gui_debug
        self.actions = actions
        self.main = None
        QObject.__init__(self)
        self.splash_screen = None
        self.timer = QTimer.singleShot(1, self.initialize)

    def timed_print(self, *a, **kw):
        if DEBUG:
            prints(f'[{monotonic() - self.startup_time:.2f}]', *a, **kw)

    def start_gui(self, db):
        from calibre.gui2.ui import Main
        self.timed_print('Constructing main UI...')
        main = self.main = Main(self.opts, gui_debug=self.gui_debug)
        if self.splash_screen is not None:
            self.splash_screen.show_message(_('Initializing user interface...'))
        try:
            with gprefs:  # Only write gui.json after initialization is complete
                main.initialize(self.library_path, db, self.actions)
        finally:
            self.timed_print('main UI initialized...')
            if self.splash_screen is not None:
                self.timed_print('Hiding splash screen')
                self.splash_screen.finish(main)
                self.timed_print('splash screen hidden')
            self.splash_screen = None
        self.timed_print('Started up in %.2f seconds'%(monotonic() - self.startup_time), 'with', len(db.data), 'books')
        main.set_exception_handler()
        if len(self.args) > 1:
            main.handle_cli_args(self.args[1:])
        for event in self.app.file_event_hook.events:
            main.handle_cli_args(event)
        self.app.file_event_hook = main.handle_cli_args

    def choose_dir(self, initial_dir):
        self.hide_splash_screen()
        return choose_dir(self.splash_screen, 'choose calibre library',
                _('Choose a location for your new calibre e-book library'),
                default_dir=initial_dir)

    def show_error(self, title, msg, det_msg=''):
        print(det_msg, file=sys.stderr)
        self.hide_splash_screen()
        with self.app:
            error_dialog(self.splash_screen, title, msg, det_msg=det_msg, show=True)

    def initialization_failed(self):
        print('Catastrophic failure initializing GUI, bailing out...')
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

        self.timed_print('db initialized')
        try:
            self.start_gui(db)
        except Exception:
            try:
                details = traceback.format_exc()
            except Exception:
                details = ''
            self.show_error(_('Startup error'), _(
                'There was an error during {0} startup. Parts of {0} may not function.'
                ' Click "Show details" to learn more.').format(__appname__), det_msg=details)

    def initialize_db(self):
        from calibre.db.legacy import LibraryDatabase
        db = None
        self.timed_print('Initializing db...')
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
        self.timed_print('Showing splash screen...')
        self.splash_screen = SplashScreen()
        self.splash_screen.show()
        self.splash_screen.show_message(_('Starting %s: Loading books...') % __appname__)
        self.timed_print('splash screen shown')

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


def run_in_debug_mode():
    from calibre.debug import run_calibre_debug
    import tempfile, subprocess
    fd, logpath = tempfile.mkstemp('.txt')
    os.close(fd)
    run_calibre_debug(
        '--gui-debug', logpath, stdout=lopen(logpath, 'wb'),
        stderr=subprocess.STDOUT, stdin=lopen(os.devnull, 'rb'))


def run_gui(opts, args, app, gui_debug=None):
    with SingleInstance('db') as si:
        if not si:
            ext = '.exe' if iswindows else ''
            error_dialog(None, _('Cannot start calibre'), _(
                'Another calibre program that can modify calibre libraries, such as,'
                ' {0} or {1} is already running. You must first shut it down, before'
                ' starting the main calibre program. If you are sure no such'
                ' program is running, try restarting your computer.').format(
                    'calibre-server' + ext, 'calibredb' + ext), show=True)
            return 1
        run_gui_(opts, args, app, gui_debug)


def run_gui_(opts, args, app, gui_debug=None):
    initialize_file_icon_provider()
    app.load_builtin_fonts(scan_for_fonts=True)
    if not dynamic.get('welcome_wizard_was_run', False):
        from calibre.gui2.wizard import wizard
        wizard().exec()
        dynamic.set('welcome_wizard_was_run', True)
    from calibre.gui2.ui import Main
    if ismacos:
        actions = tuple(Main.create_application_menubar())
    else:
        actions = tuple(Main.get_menubar_actions())
    runner = GuiRunner(opts, args, actions, app, gui_debug=gui_debug)
    ret = app.exec()
    if getattr(runner.main, 'run_wizard_b4_shutdown', False):
        from calibre.gui2.wizard import wizard
        wizard().exec()
    if getattr(runner.main, 'restart_after_quit', False):
        after_quit_actions['restart_after_quit'] = True
        after_quit_actions['debug_on_restart'] = getattr(runner.main, 'debug_on_restart', False) or gui_debug is not None
        after_quit_actions['no_plugins_on_restart'] = getattr(runner.main, 'no_plugins_on_restart', False)
    else:
        if iswindows:
            try:
                runner.main.system_tray_icon.hide()
            except:
                pass
    if getattr(runner.main, 'gui_debug', None) is not None:
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


singleinstance_name = 'GUI'


def send_message(msg):
    try:
        send_message_in_process(msg)
    except Exception:
        time.sleep(2)
        try:
            send_message_in_process(msg)
        except Exception as err:
            print(_('Failed to contact running instance of calibre'), file=sys.stderr, flush=True)
            print(err, file=sys.stderr, flush=True)
            if Application.instance():
                error_dialog(None, _('Contacting calibre failed'), _(
                    'Failed to contact running instance of calibre, try restarting calibre'),
                    det_msg=str(err) + '\n\n' + repr(msg), show=True)
            return False
    return True


def shutdown_other():
    if send_message('shutdown:'):
        print(_('Shutdown command sent, waiting for shutdown...'), flush=True)
        for i in range(50):
            with SingleInstance(singleinstance_name) as si:
                if si:
                    return
            time.sleep(0.1)
        raise SystemExit(_('Failed to shutdown running calibre instance'))


def communicate(opts, args):
    if opts.shutdown_running_calibre:
        shutdown_other()
    else:
        if len(args) > 1:
            args[1:] = [os.path.abspath(x) if os.path.exists(x) else x for x in args[1:]]
        import json
        if not send_message(b'launched:'+as_bytes(json.dumps(args))):
            raise SystemExit(_('Failed to contact running instance of calibre'))
    raise SystemExit(0)


def restart_after_quit():
    e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    is_calibre_debug_exe = os.path.splitext(e)[0].endswith('-debug')
    if iswindows and not is_calibre_debug_exe:
        # detach the stdout/stderr/stdin handles
        winutil.prepare_for_restart()
    if after_quit_actions['no_plugins_on_restart']:
        os.environ['CALIBRE_IGNORE_PLUGINS_ON_RESTART'] = '1'
    if after_quit_actions['debug_on_restart']:
        run_in_debug_mode()
        return
    if hasattr(sys, 'frameworks_dir'):
        app = os.path.dirname(os.path.dirname(os.path.realpath(sys.frameworks_dir)))
        from calibre.debug import run_calibre_debug
        prints('Restarting with:', app)
        run_calibre_debug('-c', 'import sys, os, time; time.sleep(3); os.execlp("open", "open", sys.argv[-1])', app)
    else:
        import subprocess
        if hasattr(sys, 'run_local'):
            cmd = [sys.run_local]
            if DEBUG:
                cmd += ['calibre-debug', '-g']
            else:
                cmd.append('calibre')
        else:
            cmd = [e]
            if is_calibre_debug_exe:
                cmd.append('-g')
        prints('Restarting with:', ' '.join(cmd))
        subprocess.Popen(cmd)


def main(args=sys.argv):
    if iswindows and 'CALIBRE_REPAIR_CORRUPTED_DB' in os.environ:
        windows_repair()
        return 0
    gui_debug = None
    if args[0] == '__CALIBRE_GUI_DEBUG__':
        gui_debug = args[1]
        args = ['calibre']

    try:
        app, opts, args = init_qt(args)
    except AbortInit:
        return 1
    with SingleInstance(singleinstance_name) as si:
        if si and opts.shutdown_running_calibre:
            return 0
        run_main(app, opts, args, gui_debug, si)
    if after_quit_actions['restart_after_quit']:
        restart_after_quit()


def run_main(app, opts, args, gui_debug, si):
    if si:
        return run_gui(opts, args, app, gui_debug=gui_debug)
    communicate(opts, args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as err:
        if not iswindows:
            raise
        tb = traceback.format_exc()
        from qt.core import QErrorMessage
        logfile = os.path.join(os.path.expanduser('~'), 'calibre.log')
        if os.path.exists(logfile):
            with open(logfile) as f:
                log = f.read().decode('utf-8', 'ignore')
            d = QErrorMessage()
            d.showMessage(('<b>Error:</b>%s<br><b>Traceback:</b><br>'
                '%s<b>Log:</b><br>%s')%(str(err),
                    str(tb).replace('\n', '<br>'),
                    log.replace('\n', '<br>')))
