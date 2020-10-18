#!/usr/bin/env python
# vim:fileencoding=utf-8


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


def detach_gui():
    from calibre.constants import islinux, isbsd, DEBUG
    if (islinux or isbsd) and not DEBUG and '--detach' in sys.argv:
        do_detach()


def init_dbus():
    from calibre.constants import islinux, isbsd
    if islinux or isbsd:
        from dbus.mainloop.glib import DBusGMainLoop, threads_init
        threads_init()
        DBusGMainLoop(set_as_default=True)


def register_with_default_programs():
    from calibre.constants import iswindows
    if iswindows:
        from calibre.utils.winreg.default_programs import Register
        from calibre.gui2 import gprefs
        return Register(gprefs)
    else:
        class Dummy(object):

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
    init_dbus()
    with register_with_default_programs():
        from calibre.gui2.main import main
        main(args)


def ebook_viewer(args=sys.argv):
    detach_gui()
    init_dbus()
    with register_with_default_programs():
        from calibre.gui2.viewer.main import main
        main(args)


def store_dialog(args=sys.argv):
    detach_gui()
    init_dbus()
    from calibre.gui2.store.web_store import main
    main(args)


def webengine_dialog(**kw):
    detach_gui()
    init_dbus()
    from calibre.debug import load_user_plugins
    load_user_plugins()
    import importlib
    m = importlib.import_module(kw.pop('module'))
    getattr(m, kw.pop('entry_func', 'main'))(**kw)


def toc_dialog(**kw):
    detach_gui()
    init_dbus()
    from calibre.gui2.toc.main import main
    main(**kw)


def gui_ebook_edit(path=None, notify=None):
    ' For launching the editor from inside calibre '
    init_dbus()
    from calibre.gui2.tweak_book.main import gui_main
    gui_main(path, notify)


def ebook_edit(args=sys.argv):
    detach_gui()
    init_dbus()
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
