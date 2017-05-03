__license__ = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
'''
Secure access to locked files from multiple processes.
'''

import atexit
import errno
import os
import stat
import time

from calibre.constants import (
    __appname__, fcntl, filesystem_encoding, ishaiku, islinux, iswindows, win32api,
    win32event
)
from calibre.utils.monotonic import monotonic

if iswindows:
    excl_file_mode = stat.S_IREAD | stat.S_IWRITE
    import msvcrt, win32file, pywintypes, winerror
else:
    excl_file_mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH


def unix_open(path):
    flags = os.O_RDWR | os.O_CREAT
    from calibre.constants import plugins
    speedup = plugins['speedup'][0]
    has_cloexec = False
    if hasattr(speedup, 'O_CLOEXEC'):
        try:
            fd = os.open(path, flags | speedup.O_CLOEXEC, excl_file_mode)
            has_cloexec = True
        except EnvironmentError as err:
            # Kernel may not support O_CLOEXEC
            if err.errno != errno.EINVAL:
                raise

    if not has_cloexec:
        fd = os.open(path, flags, excl_file_mode)
        fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
    return os.fdopen(fd, 'r+b')


def unix_retry(err):
    return err.errno in (errno.EACCES, errno.EAGAIN, errno.ENOLCK, errno.EINTR)


def windows_open(path):
    try:
        h = win32file.CreateFile(
            path,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,  # Open for reading and writing
            0,  # Open exclusive
            None,  # No security attributes, ensures handle is not inherited by children
            win32file.OPEN_ALWAYS,  # If file does not exist, create it
            win32file.FILE_ATTRIBUTE_NORMAL,  # Normal attributes
            None,  # No template file
        )
    except pywintypes.error as err:
        raise WindowsError(err[0], err[2], path)
    fd = msvcrt.open_osfhandle(h.Detach(), 0)
    return os.fdopen(fd, 'r+b')


def windows_retry(err):
    return err.winerror in (winerror.ERROR_SHARING_VIOLATION, winerror.ERROR_LOCK_VIOLATION)


def retry_for_a_time(timeout, sleep_time, func, error_retry, *args):
    limit = monotonic() + timeout
    while True:
        try:
            return func(*args)
        except EnvironmentError as err:
            if not error_retry(err) or monotonic() > limit:
                raise
        time.sleep(sleep_time)


class ExclusiveFile(object):

    def __init__(self, path, timeout=15, sleep_time=0.2):
        if iswindows:
            if isinstance(path, bytes):
                path = path.decode(filesystem_encoding)
        self.path = path
        self.timeout = timeout
        self.sleep_time = sleep_time

    def __enter__(self):
        if iswindows:
            self.file = retry_for_a_time(
                self.timeout, self.sleep_time, windows_open, windows_retry, self.path
            )
        else:
            f = unix_open(self.path)
            retry_for_a_time(
                self.timeout, self.sleep_time, fcntl.flock, unix_retry,
                f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
            )
            self.file = f
        return self.file

    def __exit__(self, type, value, traceback):
        self.file.close()


def _clean_lock_file(file):
    try:
        file.close()
    except:
        pass
    try:
        os.remove(file.name)
    except:
        pass


if iswindows:

    def singleinstance(name):
        mutexname = 'mutexforsingleinstanceof' + __appname__ + name
        mutex = win32event.CreateMutex(None, False, mutexname)
        err = win32api.GetLastError()
        if err == winerror.ERROR_ALREADY_EXISTS:
            # Close this handle other wise this handle will prevent the mutex
            # from being deleted when the process that created it exits.
            win32api.CloseHandle(mutex)
        elif mutex and err != winerror.ERROR_INVALID_HANDLE:
            atexit.register(win32api.CloseHandle, mutex)
        return not err == winerror.ERROR_ALREADY_EXISTS
elif islinux:

    def singleinstance(name):
        import socket
        from calibre.utils.ipc import eintr_retry_call
        name = '%s-singleinstance-%s-%d' % (__appname__, name, os.geteuid())
        if not isinstance(name, bytes):
            name = name.encode('utf-8')
        address = b'\0' + name.replace(b' ', b'_')
        sock = socket.socket(family=socket.AF_UNIX)
        try:
            eintr_retry_call(sock.bind, address)
        except socket.error as err:
            if getattr(err, 'errno', None) == errno.EADDRINUSE:
                return False
            raise
        fd = sock.fileno()
        old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)
        atexit.register(sock.close)
        return True
elif ishaiku:

    def singleinstance(name):
        # Somebody should fix this.
        return True
else:

    def singleinstance_path(name):
        home = os.path.expanduser('~')
        if os.access(home, os.W_OK | os.R_OK | os.X_OK):
            basename = __appname__ + '_' + name + '.lock'
            return os.path.expanduser('~/.' + basename)
        import tempfile
        tdir = tempfile.gettempdir()
        return os.path.join(
            tdir, '%s_%s_%s.lock' % (__appname__, name, os.geteuid())
        )

    def singleinstance(name):
        '''
        Return True if no other instance of the application identified by name is running,
        False otherwise.
        @param name: The name to lock.
        @type name: string
        '''
        from calibre.utils.ipc import eintr_retry_call
        path = singleinstance_path(name)
        f = open(path, 'w')
        old_flags = fcntl.fcntl(f.fileno(), fcntl.F_GETFD)
        fcntl.fcntl(f.fileno(), fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)
        try:
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            atexit.register(_clean_lock_file, f)
            return True
        except IOError as err:
            if err.errno == errno.EAGAIN:
                return False
            raise
        return False
