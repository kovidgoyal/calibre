#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, os, sys, time

from calibre.constants import iswindows, ismacos, isfrozen
from calibre.utils.config import prefs
from calibre.ptempfile import PersistentTemporaryFile, base_dir
from calibre.utils.serialize import msgpack_dumps
from polyglot.builtins import string_or_bytes, environ_item, native_string_type, getcwd
from polyglot.binary import as_hex_unicode

if iswindows:
    try:
        windows_null_file = open(os.devnull, 'wb')
    except:
        raise RuntimeError('NUL file missing in windows. This indicates a'
                ' corrupted windows. You should contact Microsoft'
                ' for assistance and/or follow the steps described here: https://bytes.com/topic/net/answers/264804-compile-error-null-device-missing')


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
    def executable(self):
        if hasattr(sys, 'running_from_setup'):
            return [sys.executable, os.path.join(sys.setup_dir, 'run-calibre-worker.py')]
        if getattr(sys, 'run_local', False):
            return [sys.executable, sys.run_local, self.exe_name]
        e = self.exe_name
        if iswindows:
            return os.path.join(os.path.dirname(sys.executable),
                   e+'.exe' if isfrozen else 'Scripts\\%s.exe'%e)
        if ismacos:
            return os.path.join(sys.executables_location, e)

        if isfrozen:
            return os.path.join(sys.executables_location, e)

        if hasattr(sys, 'executables_location'):
            c = os.path.join(sys.executables_location, e)
            if os.access(c, os.X_OK):
                return c
        return e

    @property
    def gui_executable(self):
        if ismacos and not hasattr(sys, 'running_from_setup'):
            if self.job_name == 'ebook-viewer':
                base = os.path.dirname(sys.executables_location)
                return os.path.join(base, 'ebook-viewer.app/Contents/MacOS/', self.exe_name)
            if self.job_name == 'ebook-edit':
                base = os.path.dirname(sys.executables_location)
                return os.path.join(base, 'ebook-viewer.app/Contents/ebook-edit.app/Contents/MacOS/', self.exe_name)

            return os.path.join(sys.executables_location, self.exe_name)

        return self.executable

    @property
    def env(self):
        env = os.environ.copy()
        env[native_string_type('CALIBRE_WORKER')] = environ_item('1')
        td = as_hex_unicode(msgpack_dumps(base_dir()))
        env[native_string_type('CALIBRE_WORKER_TEMP_DIR')] = environ_item(td)
        env.update(self._env)
        return env

    @property
    def is_alive(self):
        return hasattr(self, 'child') and self.child.poll() is None

    @property
    def returncode(self):
        if not hasattr(self, 'child'):
            return None
        self.child.poll()
        return self.child.returncode

    @property
    def pid(self):
        if not hasattr(self, 'child'):
            return None
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

    def __init__(self, env, gui=False, job_name=None):
        self._env = {}
        self.gui = gui
        self.job_name = job_name
        self._env = env.copy()

    def __call__(self, redirect_output=True, cwd=None, priority=None):
        '''
        If redirect_output is True, output from the child is redirected
        to a file on disk and this method returns the path to that file.
        '''
        exe = self.gui_executable if self.gui else self.executable
        env = self.env
        try:
            origwd = cwd or os.path.abspath(getcwd())
        except EnvironmentError:
            # cwd no longer exists
            origwd = cwd or os.path.expanduser('~')
        env[native_string_type('ORIGWD')] = environ_item(as_hex_unicode(msgpack_dumps(origwd)))
        _cwd = cwd
        if priority is None:
            priority = prefs['worker_process_priority']
        cmd = [exe] if isinstance(exe, string_or_bytes) else exe
        args = {
                'env' : env,
                'cwd' : _cwd,
                }
        if iswindows:
            priority = {
                    'high'   : subprocess.HIGH_PRIORITY_CLASS,
                    'normal' : subprocess.NORMAL_PRIORITY_CLASS,
                    'low'    : subprocess.IDLE_PRIORITY_CLASS}[priority]
            args['creationflags'] = subprocess.CREATE_NO_WINDOW|priority
        else:
            niceness = {
                    'normal' : 0,
                    'low'    : 10,
                    'high'   : 20,
            }[priority]
            args['env']['CALIBRE_WORKER_NICENESS'] = str(niceness)
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
            args['stdout'] = windows_null_file
            args['stderr'] = subprocess.STDOUT

        self.child = subprocess.Popen(cmd, **args)
        if 'stdin' in args:
            self.child.stdin.close()

        self.log_path = ret
        return ret
