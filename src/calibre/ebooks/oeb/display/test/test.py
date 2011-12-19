#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

try:
    from calibre.utils.coffeescript import serve
except ImportError:
    import init_calibre
    if False: init_calibre, serve
    from calibre.utils.coffeescript import serve


def run_devel_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    serve()

if __name__ == '__main__':
    run_devel_server()

