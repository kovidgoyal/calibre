#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


import os
import sys
from threading import Thread

from PyQt5.Qt import QIcon, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtWebEngineCore import QWebEngineUrlScheme

from calibre import as_unicode, prints
from calibre.constants import FAKE_PROTOCOL, VIEWER_APP_UID, islinux
from calibre.gui2 import Application, error_dialog, setup_gui_option_parser
from calibre.gui2.viewer.ui import EbookViewer, is_float
from calibre.ptempfile import reset_base_dir
from calibre.utils.config import JSONConfig
from calibre.utils.ipc import RC, viewer_socket_address
from calibre.gui2.viewer.web_view import vprefs, get_session_pref

singleinstance_name = 'calibre_viewer'


def migrate_previous_viewer_prefs():
    new_prefs = vprefs
    if new_prefs['old_prefs_migrated']:
        return
    old_vprefs = JSONConfig('viewer')
    old_prefs = JSONConfig('viewer.py')
    with new_prefs:
        sd = new_prefs['session_data']
        fs = sd.get('standalone_font_settings', {})
        for k in ('serif', 'sans', 'mono'):
            defval = 'Liberation ' + k.capitalize()
            k += '_family'
            if old_prefs.get(k) and old_prefs[k] != defval:
                fs[k] = old_prefs[k]
        if old_prefs.get('standard_font') in ('serif', 'sans', 'mono'):
            fs['standard_font'] = old_prefs['standard_font']
        if old_prefs.get('minimum_font_size') is not None and old_prefs['minimum_font_size'] != 8:
            fs['minimum_font_size'] = old_prefs['minimum_font_size']
        sd['standalone_font_settings'] = fs

        ms = sd.get('standalone_misc_settings', {})
        ms['remember_window_geometry'] = bool(old_prefs.get('remember_window_size', False))
        ms['remember_last_read'] = bool(old_prefs.get('remember_current_page', True))
        ms['save_annotations_in_ebook'] = bool(old_prefs.get('copy_bookmarks_to_file', True))
        ms['singleinstance'] = bool(old_vprefs.get('singleinstance', False))
        sd['standalone_misc_settings'] = ms

        for k in ('top', 'bottom'):
            v = old_prefs.get(k + '_margin')
            if v != 20 and v is not None:
                sd['margin_' + k] = v
        v = old_prefs.get('side_margin')
        if v is not None and v != 40:
            sd['margin_left'] = sd['margin_right'] = v // 2

        if old_prefs.get('user_css'):
            sd['user_stylesheet'] = old_prefs['user_css']

        cps = {'portrait': 0, 'landscape': 0}
        cp = old_prefs.get('cols_per_screen_portrait')
        if cp and cp > 1:
            cps['portrait'] = cp
        cl = old_prefs.get('cols_per_screen_landscape')
        if cl and cl > 1:
            cps['landscape'] = cp
        if cps['portrait'] or cps['landscape']:
            sd['columns_per_screen'] = cps
        if old_vprefs.get('in_paged_mode') is False:
            sd['read_mode'] = 'flow'

        new_prefs.set('session_data', sd)
        new_prefs.set('old_prefs_migrated', True)


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
    a('--force-reload', default=False, action='store_true',
        help=_('Force reload of all opened books'))
    a('--open-at', default=None, help=_(
        'The position at which to open the specified book. The position is '
        'a location or position you can get by using the Go to->Location action in the viewer controls. '
        'Alternately, you can use the form toc:something and it will open '
        'at the location of the first Table of Contents entry that contains '
        'the string "something". The form toc-href:something will match the '
        'href (internal link destination) of toc nodes. The matching is exact, '
        'If you want to match a substring, use the form toc-href-contains:something. '
        'The form ref:something will use Reference mode references.'))
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
    override = 'calibre-ebook-viewer' if islinux else None
    app = Application(args, override_program_name=override, windows_app_uid=VIEWER_APP_UID)

    parser = option_parser()
    opts, args = parser.parse_args(args)
    oat = opts.open_at
    if oat and not (
            oat.startswith('toc:') or oat.startswith('toc-href:') or oat.startswith('toc-href-contains:') or
            oat.startswith('epubcfi(/') or is_float(oat) or oat.startswith('ref:')):
        raise SystemExit('Not a valid --open-at value: {}'.format(opts.open_at))

    listener = None
    if get_session_pref('singleinstance', False):
        try:
            listener = ensure_single_instance(args, opts.open_at)
        except Exception as e:
            import traceback
            error_dialog(None, _('Failed to start viewer'), as_unicode(e), det_msg=traceback.format_exc(), show=True)
            raise SystemExit(1)

    acc = EventAccumulator(app)
    app.file_event_hook = acc
    app.load_builtin_fonts()
    app.setWindowIcon(QIcon(I('viewer.png')))
    migrate_previous_viewer_prefs()
    main = EbookViewer(open_at=opts.open_at, continue_reading=opts.continue_reading, force_reload=opts.force_reload)
    main.set_exception_handler()
    if len(args) > 1:
        acc.events.append(os.path.abspath(args[-1]))
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
        main.set_full_screen(True)

    app.exec_()
    if listener is not None:
        listener.close()


if __name__ == '__main__':
    sys.exit(main())
