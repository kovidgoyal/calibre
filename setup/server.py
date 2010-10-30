#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, tempfile, os, time

from setup import Command

class Server(Command):

    description = 'Run the calibre server in development mode conveniently'

    MONOCLE_PATH = '../monocle'

    def rebuild_monocole(self):
        subprocess.check_call(['sprocketize', '-C', self.MONOCLE_PATH,
            '-I', 'src', 'src/monocle.js'],
            stdout=open('resources/content_server/monocle.js', 'wb'))

    def launch_server(self, log):
        self.rebuild_monocole()
        p = subprocess.Popen(['calibre-server', '--develop'],
                stderr=subprocess.STDOUT, stdout=log)
        return p

    def run(self, opts):
        tdir = tempfile.gettempdir()
        logf = os.path.join(tdir, 'calibre-server.log')
        log = open(logf, 'ab')
        print 'Server log available at:', logf

        while True:
            print 'Starting server...'
            p = self.launch_server(log)
            try:
                raw_input('Press Enter to kill/restart server. Ctrl+C to quit: ')
            except:
                break
            else:
                while p.returncode is None:
                    p.terminate()
                    time.sleep(0.1)
                    p.kill()
        print

