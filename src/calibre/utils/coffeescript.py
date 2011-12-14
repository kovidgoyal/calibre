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
import time, SimpleHTTPServer, SocketServer, threading, os, subprocess

class Server(threading.Thread):

    def __init__(self, port=8000):
        threading.Thread.__init__(self)
        self.port = port
        self.daemon = True
        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        self.httpd = SocketServer.TCPServer(("localhost", port), Handler)

    def run(self):
        print('serving at localhost:%d'%self.port)
        self.httpd.serve_forever()

    def end(self):
        self.httpd.shutdown()
        self.join()

class Compiler(threading.Thread):

    def __init__(self, coffee_files):
        threading.Thread.__init__(self)
        self.daemon = True
        if not isinstance(coffee_files, dict):
            coffee_files = {x:os.path.splitext(os.path.basename(x))[0]+'.js'
                    for x in coffee_files}
        a = os.path.abspath
        self.src_map = {a(x):a(y) for x, y in coffee_files.iteritems()}
        self.keep_going = True

    def run(self):
        while self.keep_going:
            for src, dest in self.src_map.iteritems():
                if self.newer(src, dest):
                    self.compile(src, dest)
            time.sleep(0.1)

    def newer(self, src, dest):
        try:
            sstat = os.stat(src)
        except:
            time.sleep(0.01)
            sstat = os.stat(src)
        return (not os.access(dest, os.R_OK) or sstat.st_mtime >
                os.stat(dest).st_mtime)

    def compile(self, src, dest):
        with open(dest, 'wb') as f:
            try:
                subprocess.check_call(['coffee', '-c', '-p', src], stdout=f)
            except:
                print('Compilation of %s failed'%src)
                f.seek(0)
                f.truncate()
                f.write('// Compilation of cofeescript failed')

    def end(self):
        self.keep_going = False
        self.join()
        for x in self.src_map.itervalues():
            try:
                os.remove(x)
            except:
                pass

def serve(coffee_files, port=8000):
    ws = Server(port=port)
    comp = Compiler(coffee_files)
    comp.start()
    ws.start()

    try:
        while True:
            time.sleep(1)
            if not comp.is_alive() or not ws.is_alive():
                print ('Worker failed')
                raise SystemExit(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            comp.end()
        except:
            pass
        ws.end()
