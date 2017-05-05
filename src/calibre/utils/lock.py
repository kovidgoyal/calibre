#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import atexit
import errno
import os
import stat
import tempfile
import time
from functools import partial

from calibre.constants import (
    __appname__, fcntl, filesystem_encoding, islinux, isosx, iswindows, plugins
)
from calibre.utils.monotonic import monotonic

speedup = plugins['speedup'][0]
if iswindows:
    import msvcrt, win32file, pywintypes, winerror, win32api, win32event
    from calibre.constants import get_windows_username
    excl_file_mode = stat.S_IREAD | stat.S_IWRITE
else:
    excl_file_mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH


def unix_open(path):
    flags = os.O_RDWR | os.O_CREAT
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
            win32file.GENERIC_READ |
            win32file.GENERIC_WRITE,  # Open for reading and writing
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
    return err.winerror in (
        winerror.ERROR_SHARING_VIOLATION, winerror.ERROR_LOCK_VIOLATION
    )


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


def _clean_lock_file(file_obj):
    try:
        os.remove(file_obj.name)
    except EnvironmentError:
        pass
    try:
        file_obj.close()
    except EnvironmentError:
        pass


if iswindows:

    def create_single_instance_mutex(name, per_user=True):
        mutexname = '{}-singleinstance-{}-{}'.format(
            __appname__, (get_windows_username() if per_user else ''), name
        )
        mutex = win32event.CreateMutex(None, False, mutexname)
        if not mutex:
            return
        err = win32api.GetLastError()
        if err == winerror.ERROR_ALREADY_EXISTS:
            # Close this handle other wise this handle will prevent the mutex
            # from being deleted when the process that created it exits.
            win32api.CloseHandle(mutex)
            return
        return partial(win32api.CloseHandle, mutex)

elif islinux:

    def create_single_instance_mutex(name, per_user=True):
        import socket
        from calibre.utils.ipc import eintr_retry_call
        name = '%s-singleinstance-%s-%s' % (
            __appname__, (os.geteuid() if per_user else ''), name
        )
        name = name.encode('utf-8')
        address = b'\0' + name.replace(b' ', b'_')
        sock = socket.socket(family=socket.AF_UNIX)
        try:
            eintr_retry_call(sock.bind, address)
        except socket.error as err:
            if getattr(err, 'errno', None) == errno.EADDRINUSE:
                return
            raise
        fd = sock.fileno()
        old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)
        return sock.close

else:

    def singleinstance_path(name, per_user=True):
        name = '%s-singleinstance-%s-%s.lock' % (
            __appname__, (os.geteuid() if per_user else ''), name
        )
        home = os.path.expanduser('~')
        locs = ['/var/lock', home, tempfile.gettempdir()]
        if isosx:
            locs.insert(0, '/Library/Caches')
        for loc in locs:
            if os.access(loc, os.W_OK | os.R_OK | os.X_OK):
                return os.path.join(loc, ('.' if loc is home else '') + name)
        raise EnvironmentError(
            'Failed to find a suitable filesystem location for the lock file'
        )

    def create_single_instance_mutex(name, per_user=True):
        from calibre.utils.ipc import eintr_retry_call
        path = singleinstance_path(name, per_user)
        f = lopen(path, 'w')
        try:
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return partial(_clean_lock_file, f)
        except EnvironmentError as err:
            if err.errno not in (errno.EAGAIN, errno.EACCES):
                raise


def singleinstance(name):
    ' Ensure that only a single process holding exists with the specified mutex key '
    release_mutex = create_single_instance_mutex(name)
    if release_mutex is None:
        return False
    atexit.register(release_mutex)
    return True
