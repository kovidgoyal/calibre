#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import atexit
import errno
import os
import tempfile
import time

from calibre.constants import cache_dir, iswindows
from calibre.ptempfile import remove_dir
from calibre.utils.monotonic import monotonic

TDIR_LOCK = u'tdir-lock'

if iswindows:
    from calibre.utils.lock import windows_open

    def lock_tdir(path):
        return windows_open(os.path.join(path, TDIR_LOCK))

    def unlock_file(fobj):
        fobj.close()

    def remove_tdir(path, lock_file):
        lock_file.close()
        remove_dir(path)

    def is_tdir_locked(path):
        try:
            with windows_open(os.path.join(path, TDIR_LOCK)):
                pass
        except EnvironmentError:
            return True
        return False
else:
    import fcntl
    from calibre.utils.ipc import eintr_retry_call

    def lock_tdir(path):
        lf = os.path.join(path, TDIR_LOCK)
        f = lopen(lf, 'w')
        eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f

    def unlock_file(fobj):
        from calibre.utils.ipc import eintr_retry_call
        eintr_retry_call(fcntl.lockf, fobj.fileno(), fcntl.LOCK_UN)
        fobj.close()

    def remove_tdir(path, lock_file):
        lock_file.close()
        remove_dir(path)

    def is_tdir_locked(path):
        lf = os.path.join(path, TDIR_LOCK)
        f = lopen(lf, 'w')
        try:
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            eintr_retry_call(fcntl.lockf, f.fileno(), fcntl.LOCK_UN)
            return False
        except EnvironmentError:
            return True
        finally:
            f.close()


def tdirs_in(b):
    try:
        tdirs = os.listdir(b)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        tdirs = ()
    for x in tdirs:
        x = os.path.join(b, x)
        if os.path.isdir(x):
            yield x


def clean_tdirs_in(b):
    # Remove any stale tdirs left by previous program crashes
    for q in tdirs_in(b):
        if not is_tdir_locked(q):
            remove_dir(q)


def retry_lock_tdir(path, timeout=30, sleep=0.1):
    st = monotonic()
    while True:
        try:
            return lock_tdir(path)
        except Exception:
            if monotonic() - st > timeout:
                raise
            time.sleep(sleep)


def tdir_in_cache(base):
    ''' Create a temp dir inside cache_dir/base. The created dir is robust
    against application crashes. i.e. it will be cleaned up the next time the
    application starts, even if it was left behind by a previous crash. '''
    b = os.path.join(os.path.realpath(cache_dir()), base)
    try:
        os.makedirs(b)
    except EnvironmentError as e:
        if e.errno != errno.EEXIST:
            raise
    global_lock = retry_lock_tdir(b)
    try:
        if b not in tdir_in_cache.scanned:
            tdir_in_cache.scanned.add(b)
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


tdir_in_cache.scanned = set()
