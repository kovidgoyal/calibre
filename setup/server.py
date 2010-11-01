#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, tempfile, os, time, sys
from threading import RLock

from setup import Command

try:
    from pyinotify import WatchManager, ThreadedNotifier, EventsCodes, ProcessEvent
except:
    wm = None
else:
    wm = WatchManager()
    flags = EventsCodes.ALL_FLAGS
    mask = flags['IN_MODIFY']

    class ProcessEvents(ProcessEvent):

        def __init__(self, command):
            ProcessEvent.__init__(self)
            self.command = command

        def process_default(self, event):
            name = getattr(event,
                    'name', None)
            if name and os.path.splitext(name)[1] == '.py':
                print
                print name, 'changed'
                self.command.kill_server()
                self.command.launch_server()
                print self.command.prompt,
                sys.stdout.flush()


class Server(Command):

    description = 'Run the calibre server in development mode conveniently'

    MONOCLE_PATH = '../monocle'

    def rebuild_monocole(self):
        subprocess.check_call(['sprocketize', '-C', self.MONOCLE_PATH,
            '-I', 'src', 'src/monocle.js'],
            stdout=open('resources/content_server/read/monocle.js', 'wb'))

    def launch_server(self):
        print 'Starting server...\n'
        with self.lock:
            self.rebuild_monocole()
            self.server_proc = p = subprocess.Popen(['calibre-server', '--develop'],
                    stderr=subprocess.STDOUT, stdout=self.server_log)
            time.sleep(0.2)
            if p.poll() is not None:
                print 'Starting server failed'
                raise SystemExit(1)
            return p

    def kill_server(self):
        print 'Killing server...\n'
        if self.server_proc is not None:
            with self.lock:
                if self.server_proc.poll() is None:
                    self.server_proc.terminate()
                while self.server_proc.poll() is None:
                    time.sleep(0.1)

    def watch(self):
        if wm is not None:
            self.notifier = ThreadedNotifier(wm, ProcessEvents(self))
            self.notifier.start()
            self.wdd = wm.add_watch(os.path.abspath('src'), mask, rec=True)

    def run(self, opts):
        self.lock = RLock()
        tdir = tempfile.gettempdir()
        logf = os.path.join(tdir, 'calibre-server.log')
        self.server_log = open(logf, 'ab')
        self.prompt = 'Press Enter to kill/restart server. Ctrl+C to quit: '
        print 'Server log available at:', logf
        print
        self.watch()

        first = True
        while True:
            self.launch_server()
            if first:
                pass
            first = False

            try:
                raw_input(self.prompt)
            except:
                print
                self.kill_server()
                break
            else:
                self.kill_server()
        print

        if hasattr(self, 'notifier'):
            self.notifier.stop()

