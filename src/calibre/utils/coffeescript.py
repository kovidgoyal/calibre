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
from io import BytesIO

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    special_resources = {}
    compiled_cs = {}

    def send_head(self):
        path = self.path
        if path.endswith('.coffee'):
            path = path[1:] if path.startswith('/') else path
            path = self.special_resources.get(path, path)
            raw, mtime = self.compile_coffeescript(path)
            self.send_response(200)
            self.send_header("Content-type", b'text/javascript')
            self.send_header("Content-Length", bytes(len(raw)))
            self.send_header("Last-Modified", self.date_time_string(int(mtime)))
            self.end_headers()
            return BytesIO(raw)

        return SimpleHTTPServer.SimpleHTTPRequestHandler.send_head(self)

    def translate_path(self, path):
        path = self.special_resources.get(path, path)
        if path.endswith('/jquery.js'):
            return P('content_server/jquery.js')

        return SimpleHTTPServer.SimpleHTTPRequestHandler.translate_path(self,
                path)

    def newer(self, src, dest):
        try:
            sstat = os.stat(src)
        except:
            time.sleep(0.01)
            sstat = os.stat(src)
        return sstat.st_mtime > dest

    def compile_coffeescript(self, src):
        raw, mtime = self.compiled_cs.get(src, (None, 0))
        if self.newer(src, mtime):
            mtime = time.time()
            try:
                raw = subprocess.check_output(['coffee', '-c', '-p', src])
            except:
                print('Compilation of %s failed'%src)
                cs = '''
                // Compilation of coffeescript failed
                alert("Compilation of %s failed");
                '''%src
                raw = cs.encode('utf-8')
            self.compiled_cs[src] = (raw, mtime)
        return raw, mtime

class HTTPD(SocketServer.TCPServer):
    allow_reuse_address = True

def serve(resources={}, port=8000):
    Handler.special_resources = resources
    httpd = HTTPD(('0.0.0.0', port), Handler)
    print('serving at localhost:%d'%port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        raise SystemExit(0)

