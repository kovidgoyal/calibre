#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, os, sys, time, binascii, cPickle

from calibre.constants import iswindows, isosx, isfrozen
from calibre.utils.config import prefs
from calibre.ptempfile import PersistentTemporaryFile, base_dir

if iswindows:
    import win32process
    try:
        _windows_null_file = open(os.devnull, 'wb')
    except:
        raise RuntimeError('NUL %r file missing in windows'%os.devnull)

class Worker(object):
    '''
    Platform independent object for launching child processes. All processes
    have the environment variable :envvar:`CALIBRE_WORKER` set.

    Useful attributes: ``is_alive``, ``returncode``, ``pid``
    Useful methods: ``kill``

    To launch child simply call the Worker object. By default, the child's
    output is redirected to an on disk file, the path to which is returned by
    the call.
    '''

    exe_name = 'calibre-parallel'

    @property
    def osx_interpreter(self):
        exe = os.path.basename(sys.executable)
        return exe if 'python' in exe else 'python'

    @property
    def osx_contents_dir(self):
        fd = os.path.realpath(getattr(sys, 'frameworks_dir'))
        return os.path.dirname(fd)

    @property
    def executable(self):
        e = self.exe_name
        if iswindows:
            return os.path.join(os.path.dirname(sys.executable),
                   e+'.exe' if isfrozen else \
                           'Scripts\\%s.exe'%e)
        if isosx:
            return os.path.join(sys.console_binaries_path, e)

        if isfrozen:
            return os.path.join(sys.executables_location, e)

        c = os.path.join(sys.executables_location, e)
        if os.access(c, os.X_OK):
            return c
        return e


    @property
    def gui_executable(self):
        if isosx:
           return os.path.join(sys.binaries_path, self.exe_name)

        return self.executable

    @property
    def env(self):
        env = dict(os.environ)
        env['CALIBRE_WORKER'] = '1'
        td = binascii.hexlify(cPickle.dumps(base_dir()))
        env['CALIBRE_WORKER_TEMP_DIR'] = td
        env.update(self._env)
        return env

    @property
    def is_alive(self):
        return hasattr(self, 'child') and self.child.poll() is None

    @property
    def returncode(self):
        if not hasattr(self, 'child'): return None
        self.child.poll()
        return self.child.returncode

    @property
    def pid(self):
        if not hasattr(self, 'child'): return None
        return getattr(self.child, 'pid', None)

    def kill(self):
        try:
            if self.is_alive:
                if iswindows:
                    return self.child.kill()
                try:
                    self.child.terminate()
                    st = time.time()
                    while self.is_alive and time.time()-st < 2:
                        time.sleep(0.2)
                finally:
                    if self.is_alive:
                        self.child.kill()
        except:
            pass

    def __init__(self, env, gui=False):
        self._env = {}
        self.gui = gui
        self._env.update(env)

    def __call__(self, redirect_output=True, cwd=None, priority=None):
        '''
        If redirect_output is True, output from the child is redirected
        to a file on disk and this method returns the path to that file.
        '''
        exe = self.gui_executable if self.gui else self.executable
        env = self.env
        env['ORIGWD'] = cwd or os.path.abspath(os.getcwd())
        _cwd = cwd
        if priority is None:
            priority = prefs['worker_process_priority']
        cmd = [exe]
        args = {
                'env' : env,
                'cwd' : _cwd,
                }
        if iswindows:
            priority = {
                    'high'   : win32process.HIGH_PRIORITY_CLASS,
                    'normal' : win32process.NORMAL_PRIORITY_CLASS,
                    'low'    : win32process.IDLE_PRIORITY_CLASS}[priority]
            args['creationflags'] = win32process.CREATE_NO_WINDOW|priority
        ret = None
        if redirect_output:
            self._file = PersistentTemporaryFile('_worker_redirect.log')
            args['stdout'] = self._file._fd
            args['stderr'] = subprocess.STDOUT
            if iswindows:
                args['stdin'] = subprocess.PIPE
            ret = self._file.name

        if iswindows and 'stdin' not in args:
            # On windows when using the pythonw interpreter,
            # stdout, stderr and stdin may not be valid
            args['stdin'] = subprocess.PIPE
            args['stdout'] = _windows_null_file
            args['stderr'] = subprocess.STDOUT

        if not iswindows:
            # Close inherited file descriptors in worker
            # On windows, this is done in the worker process
            # itself
            args['close_fds'] = True

        self.child = subprocess.Popen(cmd, **args)
        if 'stdin' in args:
            self.child.stdin.close()

        self.log_path = ret
        return ret



