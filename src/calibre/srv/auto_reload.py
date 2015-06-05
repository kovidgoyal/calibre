#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, subprocess, signal, time
from threading import Thread

from calibre.constants import islinux

class NoAutoReload(EnvironmentError):
    pass

EXTENSIONS_TO_WATCH = frozenset('py pyj css js xml'.split())
BOUNCE_INTERVAL = 2  # seconds

if islinux:
    import select
    from calibre.utils.inotify import INotifyTreeWatcher

    def ignore_event(path, name):
        return name and name.rpartition('.')[-1] not in EXTENSIONS_TO_WATCH

    class Watcher(object):

        def __init__(self, root_dirs, server, log):
            self.server, self.log = server, log
            self.fd_map = {}
            for d in frozenset(root_dirs):
                w = INotifyTreeWatcher(d, ignore_event)
                self.fd_map[w._inotify_fd] = w
            self.last_restart_time = time.time()
            fpath = os.path.abspath(__file__)
            d = os.path.dirname
            self.base = d(d(d(d(fpath))))

        def loop(self):
            while True:
                r = select.select(list(self.fd_map.iterkeys()), [], [])[0]
                modified = set()
                for fd in r:
                    w = self.fd_map[fd]
                    modified |= w()
                if modified:
                    if time.time() - self.last_restart_time > BOUNCE_INTERVAL:
                        modified = {os.path.relpath(x, self.base) if x.startswith(self.base) else x for x in modified if x}
                        changed = os.pathsep.join(sorted(modified))
                        self.log('')
                        self.log('Restarting server because of changed files:', changed)
                        self.log('')
                        self.server.restart()
                        self.last_restart_time = time.time()
else:
    Watcher = None


def find_dirs_to_watch(fpath, dirs, add_default_dirs):
    dirs = {os.path.abspath(x) for x in dirs}
    def add(x):
        if os.path.isdir(x):
            dirs.add(x)
    if add_default_dirs:
        d = os.path.dirname
        srv = d(fpath)
        add(srv)
        base = d(d(d(srv)))
        add(os.path.join(base, 'resources', 'server'))
        add(os.path.join(base, 'src', 'calibre', 'db'))
    return dirs

def join_process(p, timeout=5):
    t = Thread(target=p.wait, name='JoinProcess')
    t.daemon = True
    t.start()
    t.join(timeout)
    return p.poll()

class Worker(object):

    def __init__(self, cmd, timeout=5):
        self.cmd = cmd
        self.p = None
        self.timeout = timeout

    def __enter__(self):
        self.restart()
        return self

    def __exit__(self, *args):
        if self.p and self.p.poll() is None:
            # SIGINT will already have been sent to the child process
            self.clean_kill(send_signal=False)

    def clean_kill(self, send_signal=True):
        if self.p is not None:
            if send_signal:
                self.p.send_signal(getattr(signal, 'CTRL_BREAK_EVENT', signal.SIGINT))
            if join_process(self.p) is None:
                self.p.kill()
                self.p.wait()
            self.p = None

    def restart(self):
        self.clean_kill()
        self.p = subprocess.Popen(self.cmd, creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))

def auto_reload(log, dirs=frozenset(), cmd=None, add_default_dirs=True):
    if Watcher is None:
        raise NoAutoReload('Auto-reload is not supported on this operating system')
    fpath = os.path.abspath(__file__)
    if not os.access(fpath, os.R_OK):
        raise NoAutoReload('Auto-reload can only be used when running from source')
    if cmd is None:
        cmd = list(sys.argv)
        cmd.remove('--auto-reload')
    dirs = find_dirs_to_watch(fpath, dirs, add_default_dirs)
    log('Auto-restarting server on changes press Ctrl-C to quit')
    log('Watching %d directory trees for changes' % len(dirs))
    with Worker(cmd) as server:
        w = Watcher(dirs, server, log)
        try:
            w.loop()
        except KeyboardInterrupt:
            pass
