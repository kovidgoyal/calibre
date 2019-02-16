#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

# TODO: --open-at and --continue command line options

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
from threading import Thread

from PyQt5.Qt import QIcon, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWebEngineCore import QWebEngineUrlScheme

from calibre import as_unicode, prints
from calibre.constants import FAKE_PROTOCOL, VIEWER_APP_UID, islinux, iswindows
from calibre.gui2 import (
    Application, error_dialog, set_app_uid, setup_gui_option_parser
)
from calibre.gui2.viewer2.ui import EbookViewer
from calibre.ptempfile import reset_base_dir
from calibre.utils.config import JSONConfig
from calibre.utils.ipc import RC, viewer_socket_address

vprefs = JSONConfig('viewer')
vprefs.defaults['singleinstance'] = False
singleinstance_name = 'calibre_viewer'


class EventAccumulator(QObject):

    got_file = pyqtSignal(object)

    def __init__(self, parent):
        QObject.__init__(self, parent)
        self.events = []

    def __call__(self, paths):
        for path in paths:
            if os.path.exists(path):
                self.events.append(path)
                self.got_file.emit(path)

    def flush(self):
        if self.events:
            self.got_file.emit(self.events[-1])
            self.events = []


def listen(listener, msg_from_anotherinstance):
    while True:
        try:
            conn = listener.accept()
        except Exception:
            break
        try:
            msg_from_anotherinstance.emit(conn.recv())
            conn.close()
        except Exception as e:
            prints('Failed to read message from other instance with error: %s' % as_unicode(e))


def create_listener():
    if islinux:
        from calibre.utils.ipc.server import LinuxListener as Listener
    else:
        from multiprocessing.connection import Listener
    return Listener(address=viewer_socket_address())


def ensure_single_instance(args, open_at):
    try:
        from calibre.utils.lock import singleinstance
        si = singleinstance(singleinstance_name)
    except Exception:
        import traceback
        error_dialog(None, _('Cannot start viewer'), _(
            'Failed to start viewer, could not insure only a single instance of the viewer is running. Click "Show Details" for more information'),
                    det_msg=traceback.format_exc(), show=True)
        raise SystemExit(1)
    if not si:
        if len(args) > 1:
            t = RC(print_error=True, socket_address=viewer_socket_address())
            t.start()
            t.join(3.0)
            if t.is_alive() or t.conn is None:
                error_dialog(None, _('Connect to viewer failed'), _(
                    'Unable to connect to existing viewer window, try restarting the viewer.'), show=True)
                raise SystemExit(1)
            t.conn.send((os.path.abspath(args[1]), open_at))
            t.conn.close()
            prints('Opened book in existing viewer instance')
        raise SystemExit(0)
    listener = create_listener()
    return listener


def option_parser():
    from calibre.gui2.main_window import option_parser
    parser = option_parser(_('''\
%prog [options] file

View an e-book.
'''))
    a = parser.add_option
    a('--raise-window', default=False, action='store_true',
        help=_('If specified, viewer window will try to come to the '
               'front when started.'))
    a('--full-screen', '--fullscreen', '-f', default=False, action='store_true',
        help=_('If specified, viewer window will try to open '
               'full screen when started.'))
    a('--open-at', default=None, help=_(
        'The position at which to open the specified book. The position is '
        'a location as displayed in the top left corner of the viewer. '
        'Alternately, you can use the form toc:something and it will open '
        'at the location of the first Table of Contents entry that contains the string "something".'))
    a('--continue', default=False, action='store_true', dest='continue_reading',
        help=_('Continue reading at the previously opened book'))

    setup_gui_option_parser(parser)
    return parser


def main(args=sys.argv):
    # Ensure viewer can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()
    scheme = QWebEngineUrlScheme(FAKE_PROTOCOL.encode('ascii'))
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(QWebEngineUrlScheme.SecureScheme)
    QWebEngineUrlScheme.registerScheme(scheme)
    if iswindows:
        # Ensure that all ebook viewer instances are grouped together in the task
        # bar. This prevents them from being grouped with the editor process when
        # launched from within calibre, as both use calibre-parallel.exe
        set_app_uid(VIEWER_APP_UID)
    override = 'calibre-ebook-viewer' if islinux else None
    app = Application(args, override_program_name=override, color_prefs=vprefs)

    parser = option_parser()
    opts, args = parser.parse_args(args)

    open_at = None
    if opts.open_at is not None:
        if opts.open_at.startswith('toc:'):
            open_at = opts.open_at
        else:
            open_at = float(opts.open_at.replace(',', '.'))

    listener = None
    if vprefs['singleinstance']:
        try:
            listener = ensure_single_instance(args, open_at)
        except Exception as e:
            import traceback
            error_dialog(None, _('Failed to start viewer'), as_unicode(e), det_msg=traceback.format_exc(), show=True)
            raise SystemExit(1)

    acc = EventAccumulator(app)
    app.file_event_hook = acc
    app.load_builtin_fonts()
    app.setWindowIcon(QIcon(I('viewer.png')))
    main = EbookViewer()
    main.set_exception_handler()
    if args:
        acc.events.append(args[-1])
    acc.got_file.connect(main.handle_commandline_arg)
    main.show()
    main.msg_from_anotherinstance.connect(main.another_instance_wants_to_talk, type=Qt.QueuedConnection)
    if listener is not None:
        t = Thread(name='ConnListener', target=listen, args=(listener, main.msg_from_anotherinstance))
        t.daemon = True
        t.start()
    QTimer.singleShot(0, acc.flush)
    if opts.raise_window:
        main.raise_()
    if opts.full_screen:
        main.showFullScreen()

    app.exec_()
    if listener is not None:
        listener.close()


if __name__ == '__main__':
    sys.exit(main())
