#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys

# For some reason Qt 5 crashes on some linux systems if the fork() is done
# after the Qt modules are loaded in calibre.gui2. We also cannot do a fork()
# while python is importing a module. So we use this simple launcher module to
# launch all the GUI apps, forking before Qt is loaded and not during a
# python import.

def do_detach(fork=True, setsid=True, redirect=True):
    if fork:
        # Detach from the controlling process.
        if os.fork() != 0:
            raise SystemExit(0)
    if setsid:
        os.setsid()
    if redirect:
        from calibre.constants import plugins
        try:
            plugins['speedup'][0].detach(os.devnull)
        except AttributeError:
            pass  # people running from source without updated binaries

def detach_gui():
    from calibre.constants import islinux, isbsd, DEBUG
    if (islinux or isbsd) and not DEBUG and '--detach' in sys.argv:
        do_detach()


def calibre():
    detach_gui()
    from calibre.gui2.main import main
    main()

def ebook_viewer():
    detach_gui()
    from calibre.gui2.viewer.main import main
    main()

def ebook_edit():
    detach_gui()
    from calibre.gui2.tweak_book.main import main
    main()

def option_parser(basename):
    if basename == 'calibre':
        from calibre.gui2.main import option_parser
    elif basename == 'ebook-viewer':
        from calibre.gui2.viewer.main import option_parser
    elif basename == 'ebook-edit':
        from calibre.gui2.tweak_book.main import option_parser
    return option_parser()
