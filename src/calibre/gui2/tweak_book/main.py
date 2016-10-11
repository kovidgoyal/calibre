#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, importlib, time

from PyQt5.Qt import QIcon

from calibre.constants import islinux, iswindows
from calibre.gui2 import Application, setup_gui_option_parser, decouple, set_gui_prefs
from calibre.ptempfile import reset_base_dir
from calibre.utils.config import OptionParser


def option_parser():
    parser =  OptionParser(_('''\
%prog [opts] [path_to_ebook] [name_of_file_inside_book ...]

Launch the calibre edit book tool. You can optionally also specify the names of
files inside the book which will be opened for editing automatically.
'''))
    setup_gui_option_parser(parser)
    return parser


class EventAccumulator(object):

    def __init__(self):
        self.events = []

    def __call__(self, ev):
        self.events.append(ev)


def gui_main(path=None, notify=None):
    _run(['ebook-edit', path], notify=notify)


def _run(args, notify=None):
    # Ensure we can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()

    if iswindows:
        # Ensure that all ebook editor instances are grouped together in the task
        # bar. This prevents them from being grouped with viewer process when
        # launched from within calibre, as both use calibre-parallel.exe
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('com.calibre-ebook.edit-book')
        except Exception:
            pass  # Only available on windows 7 and newer

    # The following two lines are needed to prevent circular imports causing
    # errors during initialization of plugins that use the polish container
    # infrastructure.
    importlib.import_module('calibre.customize.ui')
    from calibre.gui2.tweak_book import tprefs
    from calibre.gui2.tweak_book.ui import Main

    parser = option_parser()
    opts, args = parser.parse_args(args)
    decouple('edit-book-'), set_gui_prefs(tprefs)
    override = 'calibre-edit-book' if islinux else None
    app = Application(args, override_program_name=override, color_prefs=tprefs)
    app.file_event_hook = EventAccumulator()
    app.load_builtin_fonts()
    app.setWindowIcon(QIcon(I('tweak.png')))
    main = Main(opts, notify=notify)
    main.set_exception_handler()
    main.show()
    app.shutdown_signal_received.connect(main.boss.quit)
    if len(args) > 1:
        main.boss.open_book(args[1], edit_file=args[2:], clear_notify_data=False)
    else:
        for path in reversed(app.file_event_hook.events):
            main.boss.open_book(path)
            break
        app.file_event_hook = main.boss.open_book
    app.exec_()
    # Ensure that the parse worker has quit so that temp files can be deleted
    # on windows
    st = time.time()
    from calibre.gui2.tweak_book.preview import parse_worker
    while parse_worker.is_alive() and time.time() - st < 120:
        time.sleep(0.1)


def main(args=sys.argv):
    _run(args)

if __name__ == '__main__':
    main()

