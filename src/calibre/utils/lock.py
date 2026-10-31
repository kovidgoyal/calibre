#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import errno
import os
import stat
import time
from collections.abc import Callable
from functools import partial
from io import BufferedRandom
from types import TracebackType
from typing import IO

from calibre.constants import __appname__, filesystem_encoding, islinux, ismacos, iswindows
from calibre.ptempfile import base_dir, get_default_tempdir
from calibre.utils.monotonic import monotonic
from calibre_extensions import speedup

if iswindows:
    import msvcrt

    from calibre.constants import get_windows_username
    from calibre_extensions import winutil

    excl_file_mode = stat.S_IREAD | stat.S_IWRITE
else:
    excl_file_mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
    import fcntl


def unix_open(path: str | bytes) -> BufferedRandom:
    flags = os.O_RDWR | os.O_CREAT
    has_cloexec = False
    if hasattr(speedup, 'O_CLOEXEC'):
        try:
            fd = os.open(path, flags | speedup.O_CLOEXEC, excl_file_mode)
            has_cloexec = True
        except OSError as err:
            # Kernel may not support O_CLOEXEC
            if err.errno != errno.EINVAL:
                raise

    if not has_cloexec:
        fd = os.open(path, flags, excl_file_mode)
        fcntl.fcntl(fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
    return os.fdopen(fd, 'r+b')


def unix_retry(err: OSError) -> bool:
    return err.errno in (errno.EACCES, errno.EAGAIN, errno.ENOLCK, errno.EINTR)


def windows_open(path: str | bytes) -> BufferedRandom:
    if isinstance(path, bytes):
        path = os.fsdecode(path)
    h = winutil.create_file(
        path,
        winutil.GENERIC_READ | winutil.GENERIC_WRITE,  # Open for reading and writing
        0,  # Open exclusive
        winutil.OPEN_ALWAYS,  # If file does not exist, create it
        winutil.FILE_ATTRIBUTE_NORMAL,  # Normal attributes
    )
    fd = msvcrt.open_osfhandle(int(h), 0)
    ans = os.fdopen(fd, 'r+b')
    h.detach()
    return ans


def windows_retry(err: OSError) -> bool:
    return err.winerror in (winutil.ERROR_SHARING_VIOLATION, winutil.ERROR_LOCK_VIOLATION)


def retry_for_a_time[*Ts, R](timeout: float, sleep_time: float, func: Callable[[*Ts], R], error_retry: Callable[[OSError], bool], *args: *Ts) -> R:
    limit = monotonic() + timeout
    while True:
        try:
            return func(*args)
        except OSError as err:
            if not error_retry(err) or monotonic() > limit:
                raise
        time.sleep(sleep_time)


def lock_file(path: str | bytes, timeout: float = 15, sleep_time: float = 0.2) -> BufferedRandom:
    if iswindows:
        return retry_for_a_time(timeout, sleep_time, windows_open, windows_retry, path)
    f = unix_open(path)
    try:
        retry_for_a_time(timeout, sleep_time, fcntl.flock, unix_retry, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        f.close()
        raise
    return f


class ExclusiveFile:
    def __init__(self, path: str | bytes, timeout: float = 15, sleep_time: float = 0.2) -> None:
        if iswindows and isinstance(path, bytes):
            path = path.decode(filesystem_encoding)
        self.path = path
        self.timeout = timeout
        self.sleep_time = sleep_time

    def __enter__(self) -> BufferedRandom:
        self.file = lock_file(self.path, self.timeout, self.sleep_time)
        return self.file

    def __exit__(self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None) -> None:
        self.file.close()


def _clean_lock_file(file_obj: IO[str]) -> None:
    try:
        os.remove(file_obj.name)
    except OSError:
        pass
    try:
        file_obj.close()
    except OSError:
        pass


if iswindows:

    def create_single_instance_mutex(name: str, per_user: bool = True) -> Callable[[], None] | None:
        mutexname = '{}-singleinstance-{}-{}'.format(__appname__, (get_windows_username() if per_user else ''), name)
        try:
            mutex = winutil.create_mutex(mutexname, False)
        except FileExistsError:
            return
        return mutex.close

elif islinux:

    def create_single_instance_mutex(name: str, per_user: bool = True) -> Callable[[], None] | None:
        import socket

        from calibre.utils.ipc import eintr_retry_call

        name = '{}-singleinstance-{}-{}'.format(__appname__, (os.geteuid() if per_user else ''), name)
        address = '\0' + name.replace(' ', '_')
        sock = socket.socket(family=socket.AF_UNIX)
        try:
            eintr_retry_call(sock.bind, address)
        except OSError as err:
            sock.close()
            if getattr(err, 'errno', None) == errno.EADDRINUSE:
                return
            raise
        fd = sock.fileno()
        old_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, old_flags | fcntl.FD_CLOEXEC)
        return sock.close

else:

    def singleinstance_path(name: str, per_user: bool = True) -> str:
        name = '{}-singleinstance-{}-{}.lock'.format(__appname__, (os.geteuid() if per_user else ''), name)
        home = os.path.expanduser('~')
        base_dir()  # initialize get_default_tempdir()
        locs = ['/var/lock', home, get_default_tempdir()]
        if ismacos:
            locs.insert(0, '/Library/Caches')
        for loc in locs:
            if os.access(loc, os.W_OK | os.R_OK | os.X_OK):
                return os.path.join(loc, ('.' if loc is home else '') + name)
        raise OSError('Failed to find a suitable filesystem location for the lock file')

    def create_single_instance_mutex(name: str, per_user: bool = True) -> Callable[[], None] | None:
        from calibre.utils.ipc import eintr_retry_call

        path = singleinstance_path(name, per_user)
        f = open(path, 'w')  # ruff: ignore[open-file-with-context-handler]
        try:
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return partial(_clean_lock_file, f)
        except OSError as err:
            f.close()
            if err.errno not in (errno.EAGAIN, errno.EACCES):
                raise


class SingleInstance:
    def __init__(self, name: str) -> None:
        self.name = name
        self.release_mutex: Callable[[], None] | None = None

    def __enter__(self) -> bool:
        self.release_mutex = create_single_instance_mutex(self.name)
        return self.release_mutex is not None

    def __exit__(self, *a: object) -> None:
        if self.release_mutex is not None:
            self.release_mutex()
            self.release_mutex = None


def singleinstance(name: str) -> bool:
    "Ensure that only a single process exists with the specified mutex key"
    release_mutex = create_single_instance_mutex(name)
    if release_mutex is None:
        return False
    atexit.register(release_mutex)
    return True
