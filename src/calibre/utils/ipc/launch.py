#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, os, sys, time, binascii, cPickle
from functools import partial

from calibre.constants import iswindows, isosx, isfrozen, filesystem_encoding
from calibre.utils.config import prefs
from calibre.ptempfile import PersistentTemporaryFile, base_dir

if iswindows:
    import win32process
    try:
        _windows_null_file = open(os.devnull, 'wb')
    except:
        raise RuntimeError('NUL file missing in windows. This indicates a'
                ' corrupted windows. You should contact Microsoft'
                ' for assistance.')

def renice(niceness):
    try:
        os.nice(niceness)
    except:
        pass

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

        if hasattr(sys, 'executables_location'):
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
        # We use this inefficient method of copying the environment variables
        # because of non ascii env vars on windows. See https://bugs.launchpad.net/bugs/811191
        env = {}
        for key in os.environ:
            try:
                val = os.environ[key]
                if isinstance(val, unicode):
                    # On windows subprocess cannot handle unicode env vars
                    try:
                        val = val.encode(filesystem_encoding)
                    except ValueError:
                        val = val.encode('utf-8')
                if isinstance(key, unicode):
                    key = key.encode('ascii')
                env[key] = val
            except:
                pass
        env[b'CALIBRE_WORKER'] = b'1'
        td = binascii.hexlify(cPickle.dumps(base_dir()))
        env[b'CALIBRE_WORKER_TEMP_DIR'] = bytes(td)
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

    def close_log_file(self):
        try:
            self._file.close()
        except:
            pass

    def kill(self):
        self.close_log_file()
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
        # Windows cannot handle unicode env vars
        for k, v in env.iteritems():
            try:
                if isinstance(k, unicode):
                    k = k.encode('ascii')
                if isinstance(v, unicode):
                    try:
                        v = v.encode(filesystem_encoding)
                    except:
                        v = v.encode('utf-8')
                self._env[k] = v
            except:
                pass

    def __call__(self, redirect_output=True, cwd=None, priority=None):
        '''
        If redirect_output is True, output from the child is redirected
        to a file on disk and this method returns the path to that file.
        '''
        exe = self.gui_executable if self.gui else self.executable
        env = self.env
        env[b'ORIGWD'] = binascii.hexlify(cPickle.dumps(cwd or
                                    os.path.abspath(os.getcwdu())))
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
        else:
            niceness = {
                    'normal' : 0,
                    'low'    : 10,
                    'high'   : 20,
            }[priority]
            args['preexec_fn'] = partial(renice, niceness)
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



