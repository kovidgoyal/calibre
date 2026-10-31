#!/usr/bin/env python
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import errno
import os
import tempfile
import time
from collections.abc import Iterator
from typing import IO

from calibre.constants import cache_dir, iswindows
from calibre.ptempfile import remove_dir
from calibre.utils.monotonic import monotonic

TDIR_LOCK = 'tdir-lock'

if iswindows:
    from calibre.utils.lock import windows_open

    def lock_tdir(path: str) -> IO[bytes]:
        return windows_open(os.path.join(path, TDIR_LOCK))

    def unlock_file(fobj: IO[bytes] | IO[str]) -> None:
        fobj.close()

    def remove_tdir(path: str, lock_file: IO[bytes] | IO[str]) -> None:
        lock_file.close()
        remove_dir(path)

    def is_tdir_locked(path: str) -> bool:
        try:
            with windows_open(os.path.join(path, TDIR_LOCK)):
                pass
        except OSError:
            return True
        return False

else:
    import fcntl

    from calibre.utils.ipc import eintr_retry_call

    def lock_tdir(path: str) -> IO[str]:
        lf = os.path.join(path, TDIR_LOCK)
        f = open(lf, 'w')  # ruff: ignore[open-file-with-context-handler]
        eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f

    def unlock_file(fobj: IO[bytes] | IO[str]) -> None:
        from calibre.utils.ipc import eintr_retry_call

        eintr_retry_call(fcntl.lockf, fobj.fileno(), fcntl.LOCK_UN)
        fobj.close()

    def remove_tdir(path: str, lock_file: IO[bytes] | IO[str]) -> None:
        lock_file.close()
        remove_dir(path)

    def is_tdir_locked(path: str) -> bool:
        lf = os.path.join(path, TDIR_LOCK)
        f = open(lf, 'w')  # ruff: ignore[open-file-with-context-handler]
        try:
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_UN)
            return False
        except OSError:
            return True
        finally:
            f.close()


def tdirs_in(b: str) -> Iterator[str]:
    try:
        tdirs = os.listdir(b)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        tdirs = ()
    for x in tdirs:
        x = os.path.join(b, x)
        if os.path.isdir(x):
            yield x


def clean_tdirs_in(b: str) -> None:
    # Remove any stale tdirs left by previous program crashes
    for q in tdirs_in(b):
        if not is_tdir_locked(q):
            remove_dir(q)


def retry_lock_tdir(path: str, timeout: float = 30, sleep: float = 0.1) -> IO[bytes] | IO[str]:
    st = monotonic()
    while True:
        try:
            return lock_tdir(path)
        except Exception:
            if monotonic() - st > timeout:
                raise
            time.sleep(sleep)


_tdir_in_cache_scanned: set[str] = set()


def tdir_in_cache(base: str) -> str:
    """Create a temp dir inside cache_dir/base. The created dir is robust
    against application crashes. i.e. it will be cleaned up the next time the
    application starts, even if it was left behind by a previous crash."""
    b = os.path.join(os.path.realpath(cache_dir()), base)
    try:
        os.makedirs(b)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    global_lock = retry_lock_tdir(b)
    try:
        if b not in _tdir_in_cache_scanned:
            _tdir_in_cache_scanned.add(b)
            try:
                clean_tdirs_in(b)
            except Exception:
                import traceback

                traceback.print_exc()
        tdir = tempfile.mkdtemp(dir=b)
        lock_data = lock_tdir(tdir)
        atexit.register(remove_tdir, tdir, lock_data)
        tdir = os.path.join(tdir, 'a')
        os.mkdir(tdir)
        return tdir
    finally:
        unlock_file(global_lock)
