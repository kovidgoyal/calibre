#!/usr/bin/env python
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import sys
from contextlib import closing
from qt.core import QIcon, QObject, Qt, QTimer, pyqtSignal

from calibre.constants import VIEWER_APP_UID, islinux
from calibre.gui2 import Application, error_dialog, setup_gui_option_parser
from calibre.gui2.listener import send_message_in_process
from calibre.gui2.viewer.config import get_session_pref, vprefs
from calibre.gui2.viewer.ui import EbookViewer, is_float
from calibre.ptempfile import reset_base_dir
from calibre.utils.config import JSONConfig
from calibre.utils.ipc import viewer_socket_address

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


def send_message_to_viewer_instance(args, open_at):
    if len(args) > 1:
        msg = json.dumps((os.path.abspath(args[1]), open_at))
        try:
            send_message_in_process(msg, address=viewer_socket_address())
        except Exception as err:
            error_dialog(None, _('Connecting to E-book viewer failed'), _(
                'Unable to connect to existing E-book viewer window, try restarting the viewer.'), det_msg=str(err), show=True)
            raise SystemExit(1)
        print('Opened book in existing viewer instance')


def option_parser():
    from calibre.gui2.main_window import option_parser
    parser = option_parser(_('''\
%prog [options] file

View an e-book.
'''))
    a = parser.add_option
    a('--raise-window', default=False, action='store_true',
        help=_('If specified, the E-book viewer window will try to come to the '
               'front when started.'))
    a('--full-screen', '--fullscreen', '-f', default=False, action='store_true',
        help=_('If specified, the E-book viewer window will try to open '
               'full screen when started.'))
    a('--force-reload', default=False, action='store_true',
        help=_('Force reload of all opened books'))
    a('--open-at', default=None, help=_(
        'The position at which to open the specified book. The position is '
        'a location or position you can get by using the Go to->Location action in the viewer controls. '
        'Alternately, you can use the form toc:something and it will open '
        'at the location of the first Table of Contents entry that contains '
        'the string "something". The form toc-href:something will match the '
        'href (internal link destination) of toc nodes. The matching is exact. '
        'If you want to match a substring, use the form toc-href-contains:something. '
        'The form ref:something will use Reference mode references. The form search:something will'
        ' search for something after opening the book. The form regex:something will search'
        ' for the regular expression something after opening the book.'
    ))
    a('--continue', default=False, action='store_true', dest='continue_reading',
        help=_('Continue reading the last opened book'))

    setup_gui_option_parser(parser)
    return parser


def run_gui(app, opts, args, internal_book_data, listener=None):
    acc = EventAccumulator(app)
    app.file_event_hook = acc
    app.load_builtin_fonts()
    app.setWindowIcon(QIcon.ic('viewer.png'))
    migrate_previous_viewer_prefs()
    main = EbookViewer(
        open_at=opts.open_at, continue_reading=opts.continue_reading, force_reload=opts.force_reload,
        calibre_book_data=internal_book_data)
    main.set_exception_handler()
    if len(args) > 1:
        acc.events.append(os.path.abspath(args[-1]))
    acc.got_file.connect(main.handle_commandline_arg)
    main.show()
    if listener is not None:
        listener.message_received.connect(main.message_from_other_instance, type=Qt.ConnectionType.QueuedConnection)
    QTimer.singleShot(0, acc.flush)
    if opts.raise_window:
        main.raise_()
    if opts.full_screen:
        main.set_full_screen(True)

    app.exec()


def main(args=sys.argv):
    from calibre.utils.webengine import setup_fake_protocol
    # Ensure viewer can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()
    setup_fake_protocol()
    override = 'calibre-ebook-viewer' if islinux else None
    processed_args = []
    internal_book_data = internal_book_data_path = None
    for arg in args:
        if arg.startswith('--internal-book-data='):
            internal_book_data_path = arg.split('=', 1)[1]
            continue
        processed_args.append(arg)
    if internal_book_data_path:
        try:
            with lopen(internal_book_data_path, 'rb') as f:
                internal_book_data = json.load(f)
        finally:
            try:
                os.remove(internal_book_data_path)
            except OSError:
                pass
    args = processed_args
    app = Application(args, override_program_name=override, windows_app_uid=VIEWER_APP_UID)
    from calibre.utils.webengine import setup_default_profile
    setup_default_profile()

    parser = option_parser()
    opts, args = parser.parse_args(args)
    oat = opts.open_at
    if oat and not (
            oat.startswith('toc:') or oat.startswith('toc-href:') or oat.startswith('toc-href-contains:') or
            oat.startswith('epubcfi(/') or is_float(oat) or oat.startswith('ref:') or oat.startswith('search:') or oat.startswith('regex:')):
        raise SystemExit(f'Not a valid --open-at value: {opts.open_at}')

    if get_session_pref('singleinstance', False):
        from calibre.gui2.listener import Listener
        from calibre.utils.lock import SingleInstance
        with SingleInstance(singleinstance_name) as si:
            if si:
                try:
                    listener = Listener(address=viewer_socket_address(), parent=app)
                    listener.start_listening()
                except Exception as err:
                    error_dialog(None, _('Failed to start listener'), _(
                        'Could not start the listener used for single instance viewers. Try rebooting your computer.'),
                                        det_msg=str(err), show=True)
                else:
                    with closing(listener):
                        run_gui(app, opts, args, internal_book_data, listener=listener)
            else:
                send_message_to_viewer_instance(args, opts.open_at)
    else:
        run_gui(app, opts, args, internal_book_data)


if __name__ == '__main__':
    sys.exit(main())
