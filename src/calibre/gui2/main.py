__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, time, socket, traceback
from functools import partial

from PyQt4.Qt import QCoreApplication, QIcon, QMessageBox

from calibre import prints
from calibre.constants import iswindows, __appname__, isosx
from calibre.utils.ipc import ADDRESS, RC
from calibre.gui2 import ORG_NAME, APP_UID, initialize_file_icon_provider, \
    Application
from calibre.gui2.main_window import option_parser as _option_parser
from calibre.utils.config import prefs, dynamic

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
    if opts.with_library is not None and os.path.isdir(opts.with_library):
        prefs.set('library_path', os.path.abspath(opts.with_library))
        prints('Using library at', prefs['library_path'])
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationName(APP_UID)
    app = Application(args)
    actions = tuple(Main.create_application_menubar())
    app.setWindowIcon(QIcon(I('library.png')))
    return app, opts, args, actions

def run_gui(opts, args, actions, listener, app):
    from calibre.gui2.ui import Main
    initialize_file_icon_provider()
    if not dynamic.get('welcome_wizard_was_run', False):
        from calibre.gui2.wizard import wizard
        wizard().exec_()
        dynamic.set('welcome_wizard_was_run', True)
    main = Main(listener, opts, actions)
    add_filesystem_book = partial(main.add_filesystem_book, allow_device=False)
    sys.excepthook = main.unhandled_exception
    if len(args) > 1:
        args[1] = os.path.abspath(args[1])
        add_filesystem_book(args[1])
    app.file_event_hook = add_filesystem_book
    ret = app.exec_()
    if getattr(main, 'run_wizard_b4_shutdown', False):
        from calibre.gui2.wizard import wizard
        wizard().exec_()
    if getattr(main, 'restart_after_quit', False):
        e = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
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
                main.system_tray_icon.hide()
            except:
                pass
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
                return run_gui(opts, args, actions, listener, app)
        else:
            return run_gui(opts, args, actions, listener, app)
    otherinstance = False
    try:
        listener = Listener(address=ADDRESS)
    except socket.error: # Good si is correct (on UNIX)
        otherinstance = True
    else:
        # On windows only singleinstance can be trusted
        otherinstance = True if iswindows else False
    if not otherinstance:
        return run_gui(opts, args, actions, listener, app)

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

