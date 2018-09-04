#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, tempfile
import SimpleHTTPServer
import SocketServer


def run_devel_server():
    base = os.path.dirname(os.path.abspath(__file__))
    tdir = tempfile.gettempdir()
    dest = os.path.join(tdir, os.path.basename(base))
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(base, dest)
    for i in range(5):
        base = os.path.dirname(base)
    shutil.copy(os.path.join(base, 'pyj', 'read_book', 'cfi.pyj'), dest)
    os.chdir(dest)
    from calibre.utils.rapydscript import compile_pyj
    with lopen('cfi-test.pyj', 'rb') as f, lopen('cfi-test.js', 'wb') as js:
        js.write(compile_pyj(f.read()).encode('utf-8'))
    PORT = 8000
    Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
    httpd = SocketServer.TCPServer(("", PORT), Handler)
    print('Serving CFI test at http://localhost:%d' % PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    run_devel_server()

