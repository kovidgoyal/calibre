#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys

# For some reason Qt 5 crashes on some linux systems if the fork() is done
# after the Qt modules are loaded in calibre.gui2. We also cannot do a fork()
# while python is importing a module. So we use this simple launcher module to
# launch all the GUI apps, forking before Qt is loaded and not during a
# python import.

is_detached = False


def do_detach(fork=True, setsid=True, redirect=True):
    global is_detached
    if fork:
        # Detach from the controlling process.
        if os.fork() != 0:
            raise SystemExit(0)
    if setsid:
        os.setsid()
    if redirect:
        from calibre_extensions.speedup import detach
        detach(os.devnull)
    is_detached = True


def setup_qt_logging():
    from calibre.constants import DEBUG
    if not DEBUG:
        from qt.core import QLoggingCategory
        QLoggingCategory.setFilterRules('''\
qt.webenginecontext.info=false
''')


def detach_gui():
    from calibre.constants import islinux, isbsd, DEBUG
    if (islinux or isbsd) and not DEBUG and '--detach' in sys.argv:
        do_detach()


def register_with_default_programs():
    from calibre.constants import iswindows
    if iswindows:
        from calibre.utils.winreg.default_programs import Register
        from calibre.gui2 import gprefs
        return Register(gprefs)
    else:
        class Dummy:

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass
        return Dummy()


def calibre(args=sys.argv):
    from calibre.constants import DEBUG
    if DEBUG:
        from calibre.debug import print_basic_debug_info
        print_basic_debug_info()
    detach_gui()
    setup_qt_logging()
    with register_with_default_programs():
        from calibre.gui2.main import main
        main(args)


def is_possible_media_pack_error(e):
    from calibre.constants import iswindows
    from ctypes.util import find_library
    if iswindows and 'QtWebEngine' in str(e):
        if not find_library('MFTranscode.dll'):
            return True
    return False


def show_media_pack_error():
    import traceback
    from calibre.gui2 import error_dialog, Application
    app = Application([])
    error_dialog(None, _('Required component missing'), '<p>' + _(
        'This computer is missing the Windows MediaPack, which is needed for calibre. Instructions'
        ' for installing it are <a href="{0}">available here</a>.').format(
            'https://support.medal.tv/support/solutions/articles/48001157311-windows-is-missing-media-pack'),
                 det_msg=traceback.format_exc()).exec()
    del app


def media_pack_error_check(func):

    def wrapper(*a, **kw):
        try:
            return func(*a, **kw)
        except ImportError as e:
            if is_possible_media_pack_error(e):
                show_media_pack_error()
            else:
                raise
    return wrapper


@media_pack_error_check
def ebook_viewer(args=sys.argv):
    detach_gui()
    setup_qt_logging()
    with register_with_default_programs():
        try:
            from calibre.gui2.viewer.main import main
            main(args)
        except ImportError as e:
            if is_possible_media_pack_error(e):
                show_media_pack_error()
            else:
                raise


@media_pack_error_check
def store_dialog(args=sys.argv):
    detach_gui()
    setup_qt_logging()
    from calibre.gui2.store.web_store import main
    main(args)


@media_pack_error_check
def webengine_dialog(**kw):
    detach_gui()
    setup_qt_logging()
    from calibre.debug import load_user_plugins
    load_user_plugins()
    import importlib
    m = importlib.import_module(kw.pop('module'))
    getattr(m, kw.pop('entry_func', 'main'))(**kw)


@media_pack_error_check
def toc_dialog(**kw):
    detach_gui()
    setup_qt_logging()
    from calibre.gui2.toc.main import main
    main(**kw)


@media_pack_error_check
def gui_ebook_edit(path=None, notify=None):
    ' For launching the editor from inside calibre '
    from calibre.gui2.tweak_book.main import gui_main
    setup_qt_logging()
    gui_main(path, notify)


@media_pack_error_check
def ebook_edit(args=sys.argv):
    detach_gui()
    setup_qt_logging()
    with register_with_default_programs():
        from calibre.gui2.tweak_book.main import main
        main(args)


def option_parser(basename):
    if basename == 'calibre':
        from calibre.gui2.main import option_parser
    elif basename == 'ebook-viewer':
        from calibre.gui2.viewer.main import option_parser
    elif basename == 'ebook-edit':
        from calibre.gui2.tweak_book.main import option_parser
    return option_parser()
