#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Utilities to help with developing coffeescript based apps
'''
import time, SimpleHTTPServer, SocketServer, os, subprocess

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    generated_files = set()

    def translate_path(self, path):
        if path.endswith('jquery.js'):
            return P('content_server/jquery.js')
        if path.endswith('.coffee'):
            return self.compile_coffeescript(path[1:])

        return SimpleHTTPServer.SimpleHTTPRequestHandler.translate_path(self,
                path)

    def newer(self, src, dest):
        try:
            sstat = os.stat(src)
        except:
            time.sleep(0.01)
            sstat = os.stat(src)
        return (not os.access(dest, os.R_OK) or sstat.st_mtime >
                os.stat(dest).st_mtime)

    def compile_coffeescript(self, src):
        dest = os.path.splitext(src)[0] + '.js'
        self.generated_files.add(dest)
        if self.newer(src, dest):
            with open(dest, 'wb') as f:
                try:
                    subprocess.check_call(['coffee', '-c', '-p', src], stdout=f)
                except:
                    print('Compilation of %s failed'%src)
                    f.seek(0)
                    f.truncate()
                    f.write('// Compilation of coffeescript failed')
                    f.write('alert("Compilation of %s failed");'%src)
        return dest

def serve(port=8000):
    httpd = SocketServer.TCPServer(('localhost', port), Handler)
    print('serving at localhost:%d'%port)
    try:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            raise SystemExit(0)
    finally:
        for x in Handler.generated_files:
            try:
                os.remove(x)
            except:
                pass

