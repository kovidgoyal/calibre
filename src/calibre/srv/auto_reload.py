#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, subprocess, signal, time, errno
from threading import Thread

from calibre.constants import islinux, iswindows, isosx

class NoAutoReload(EnvironmentError):
    pass


class WatcherBase(object):

    EXTENSIONS_TO_WATCH = frozenset('py pyj'.split())
    BOUNCE_INTERVAL = 2  # seconds

    def __init__(self, server, log):
        self.server, self.log = server, log
        fpath = os.path.abspath(__file__)
        d = os.path.dirname
        self.base = d(d(d(d(fpath))))
        self.last_restart_time = time.time()

    def handle_modified(self, modified):
        if modified:
            if time.time() - self.last_restart_time > self.BOUNCE_INTERVAL:
                modified = {os.path.relpath(x, self.base) if x.startswith(self.base) else x for x in modified if x}
                changed = os.pathsep.join(sorted(modified))
                self.log('')
                self.log('Restarting server because of changed files:', changed)
                self.log('')
                self.server.restart()
                self.last_restart_time = time.time()

    def file_is_watched(self, fname):
        return fname and fname.rpartition('.')[-1] in self.EXTENSIONS_TO_WATCH

if islinux:
    import select
    from calibre.utils.inotify import INotifyTreeWatcher

    class Watcher(WatcherBase):

        def __init__(self, root_dirs, server, log):
            WatcherBase.__init__(self, server, log)
            self.fd_map = {}
            for d in frozenset(root_dirs):
                w = INotifyTreeWatcher(d, self.ignore_event)
                self.fd_map[w._inotify_fd] = w

        def loop(self):
            while True:
                r = select.select(list(self.fd_map.iterkeys()), [], [])[0]
                modified = set()
                for fd in r:
                    w = self.fd_map[fd]
                    modified |= w()
                self.handle_modified(modified)

        def ignore_event(self, path, name):
            return not self.file_is_watched(name)

elif iswindows:
    import win32file, win32con
    from Queue import Queue
    FILE_LIST_DIRECTORY = 0x0001
    from calibre.srv.utils import HandleInterrupt

    class TreeWatcher(Thread):
        daemon = True

        def __init__(self, path_to_watch, modified_queue):
            Thread.__init__(self, name='TreeWatcher')
            self.modified_queue = modified_queue
            self.path_to_watch = path_to_watch
            self.dir_handle = win32file.CreateFileW(
                path_to_watch,
                FILE_LIST_DIRECTORY,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS,
                None
            )

        def run(self):
            try:
                while True:
                    results = win32file.ReadDirectoryChangesW(
                        self.dir_handle,
                        8192,  # Buffer size for storing events
                        True,  # Watch sub-directories as well
                        win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                        win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                        win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                        win32con.FILE_NOTIFY_CHANGE_SIZE |
                        win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                        win32con.FILE_NOTIFY_CHANGE_SECURITY,
                        None, None
                    )
                    for action, filename in results:
                        if self.file_is_watched(filename):
                            self.modified_queue.put(os.path.join(self.path_to_watch, filename))
            except Exception:
                import traceback
                traceback.print_exc()

    class Watcher(WatcherBase):

        def __init__(self, root_dirs, server, log):
            WatcherBase.__init__(self, server, log)
            self.watchers = []
            self.modified_queue = Queue()
            for d in frozenset(root_dirs):
                self.watchers.append(TreeWatcher(d, self.modified_queue))

        def loop(self):
            for w in self.watchers:
                w.start()
            with HandleInterrupt(lambda : self.modified_queue.put(None)):
                while True:
                    path = self.modified_queue.get()
                    if path is None:
                        break
                    self.handle_modified({path})

elif isosx:
    from fsevents import Observer, Stream

    class Watcher(WatcherBase):

        def __init__(self, root_dirs, server, log):
            WatcherBase.__init__(self, server, log)
            self.stream = Stream(self.notify, *(x.encode('utf-8') for x in root_dirs), file_events=True)

        def loop(self):
            observer = Observer()
            observer.schedule(self.stream)
            observer.daemon = True
            observer.start()
            try:
                while True:
                    # Cannot use observer.join() as it is not interrupted by
                    # Ctrl-C
                    time.sleep(10000)
            finally:
                observer.unschedule(self.stream)
                observer.stop()

        def notify(self, ev):
            name = ev.name
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            if self.file_is_watched(name):
                self.handle_modified({name})

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
        add(os.path.join(base, 'src', 'pyj'))
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
        from calibre.utils.rapydscript import compile_srv
        self.clean_kill()
        try:
            compile_srv()
        except EnvironmentError as e:
            # Happens if the editor deletes and replaces a file being edited
            if e.errno != errno.ENOENT or not getattr(e, 'filename', False):
                raise
            st = time.time()
            while not os.path.exists(e.filename) and time.time() - st < 3:
                time.sleep(0.01)
            compile_srv()
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
