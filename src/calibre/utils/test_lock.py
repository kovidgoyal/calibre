#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from threading import Thread

from calibre.constants import cache_dir, fcntl, iswindows
from calibre.utils.lock import ExclusiveFile, create_single_instance_mutex, unix_open
from calibre.utils.tdir_in_cache import (
    clean_tdirs_in, is_tdir_locked, retry_lock_tdir, tdir_in_cache, tdirs_in,
    unlock_file
)


def FastFailEF(name):
    return ExclusiveFile(name, sleep_time=0.01, timeout=0.05)


class Other(Thread):
    daemon = True
    locked = None

    def run(self):
        try:
            with FastFailEF('testsp'):
                self.locked = True
        except EnvironmentError:
            self.locked = False


def run_worker(mod, func, **kw):
    try:
        exe = [sys.executable, os.path.join(sys.setup_dir, 'run-calibre-worker.py')]
    except AttributeError:
        exe = [
            os.path.join(
                os.path.dirname(os.path.abspath(sys.executable)),
                'calibre-parallel' + ('.exe' if iswindows else '')
            )
        ]
    env = kw.get('env', os.environ.copy())
    env['CALIBRE_SIMPLE_WORKER'] = mod + ':' + func
    if iswindows:
        import win32process
        kw['creationflags'] = win32process.CREATE_NO_WINDOW
    kw['env'] = {str(k): str(v)
                 for k, v in env.iteritems()}  # windows needs bytes in env
    return subprocess.Popen(exe, **kw)


class IPCLockTest(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tdir = tempfile.mkdtemp()
        os.chdir(self.tdir)
        self.original_cache_dir = cache_dir()
        cache_dir.ans = self.tdir

    def tearDown(self):
        cache_dir.ans = self.original_cache_dir
        os.chdir(self.cwd)
        for i in range(100):
            try:
                shutil.rmtree(self.tdir)
                break
            except EnvironmentError:
                time.sleep(0.1)

    def test_exclusive_file_same_process(self):
        fname = 'testsp'
        with ExclusiveFile(fname):
            ef = FastFailEF(fname)
            self.assertRaises(EnvironmentError, ef.__enter__)
            t = Other()
            t.start(), t.join()
            self.assertIs(t.locked, False)
        if not iswindows:
            with unix_open(fname) as f:
                self.assertEqual(
                    1, fcntl.fcntl(f.fileno(), fcntl.F_GETFD) & fcntl.FD_CLOEXEC
                )

    def run_other_ef_op(self, clean_exit):
        child = run_worker('calibre.utils.test_lock', 'other1')
        try:
            while child.poll() is None:
                if os.path.exists('ready'):
                    break
                time.sleep(0.01)
            self.assertIsNone(child.poll(), 'child died without creating ready dir')
            ef = FastFailEF('test')
            self.assertRaises(EnvironmentError, ef.__enter__)
            if clean_exit:
                os.mkdir('quit')
            else:
                child.kill()
            self.assertIsNotNone(child.wait())
            with ExclusiveFile('test', timeout=3):
                pass
        finally:
            if child.poll() is None:
                child.kill()

    def test_exclusive_file_other_process_clean(self):
        self.run_other_ef_op(True)

    def test_exclusive_file_other_process_kill(self):
        self.run_other_ef_op(False)

    def test_single_instance(self):
        release_mutex = create_single_instance_mutex('test')
        for i in range(5):
            child = run_worker('calibre.utils.test_lock', 'other2')
            self.assertEqual(child.wait(), 0)
        release_mutex()
        for i in range(5):
            child = run_worker('calibre.utils.test_lock', 'other2')
            self.assertEqual(child.wait(), 1)
        child = run_worker('calibre.utils.test_lock', 'other3')
        while not os.path.exists('ready'):
            time.sleep(0.01)
        child.kill()
        release_mutex = create_single_instance_mutex('test')
        self.assertIsNotNone(release_mutex)
        release_mutex()

    def test_tdir_in_cache_dir(self):
        child = run_worker('calibre.utils.test_lock', 'other4')
        tdirs = []
        while not tdirs:
            time.sleep(0.05)
            gl = retry_lock_tdir('t', sleep=0.05)
            try:
                tdirs = list(tdirs_in('t'))
            finally:
                unlock_file(gl)
        self.assertTrue(is_tdir_locked(tdirs[0]))
        c2 = run_worker('calibre.utils.test_lock', 'other5')
        self.assertEqual(c2.wait(), 0)
        self.assertTrue(is_tdir_locked(tdirs[0]))
        child.kill(), child.wait()
        self.assertTrue(os.path.exists(tdirs[0]))
        self.assertFalse(is_tdir_locked(tdirs[0]))
        clean_tdirs_in('t')
        self.assertFalse(os.path.exists(tdirs[0]))
        self.assertEqual(os.listdir('t'), [u'tdir-lock'])


def other1():
    e = ExclusiveFile('test')
    with e:
        os.mkdir('ready')
        while not os.path.exists('quit'):
            time.sleep(0.02)


def other2():
    release_mutex = create_single_instance_mutex('test')
    raise SystemExit(0 if release_mutex is None else 1)


def other3():
    create_single_instance_mutex('test')
    os.mkdir('ready')
    time.sleep(30)


def other4():
    cache_dir.ans = os.getcwdu()
    tdir_in_cache('t')
    time.sleep(30)


def other5():
    cache_dir.ans = os.getcwdu()
    if not os.path.isdir(tdir_in_cache('t')):
        raise SystemExit(1)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(IPCLockTest)


if __name__ == '__main__':
    suite = find_tests()
    unittest.TextTestRunner(verbosity=4).run(suite)
