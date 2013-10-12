#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os

from PyQt4.Qt import QIcon

from calibre.constants import islinux
from calibre.gui2 import Application, ORG_NAME, APP_UID
from calibre.ptempfile import reset_base_dir
from calibre.utils.config import OptionParser
from calibre.gui2.tweak_book.ui import Main

def option_parser():
    return OptionParser('''\
%prog [opts] [path_to_ebook]

Launch the calibre tweak book tool.
''')

def main(args=sys.argv):
    # Ensure we can continue to function if GUI is closed
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()

    parser = option_parser()
    opts, args = parser.parse_args(args)
    override = 'calibre-tweak-book' if islinux else None
    app = Application(args, override_program_name=override)
    app.load_builtin_fonts()
    app.setWindowIcon(QIcon(I('tweak.png')))
    Application.setOrganizationName(ORG_NAME)
    Application.setApplicationName(APP_UID)
    main = Main(opts)
    sys.excepthook = main.unhandled_exception
    main.show()
    if len(args) > 1:
        main.boss.open_book(args[1])
    app.exec_()

if __name__ == '__main__':
    main()

