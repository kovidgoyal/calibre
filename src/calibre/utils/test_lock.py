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

from calibre.constants import fcntl, iswindows
from calibre.utils.lock import ExclusiveFile, unix_open


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
        exe = [os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'calibre-parallel' + ('.exe' if iswindows else ''))]
    env = kw.get('env', os.environ.copy())
    env['CALIBRE_SIMPLE_WORKER'] = mod + ':' + func
    if iswindows:
        import win32process
        kw['creationflags'] = win32process.CREATE_NO_WINDOW
    kw['env'] = {str(k):str(v) for k, v in env.iteritems()}  # windows needs bytes in env
    return subprocess.Popen(exe, **kw)


class IPCLockTest(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tdir = tempfile.mkdtemp()
        os.chdir(self.tdir)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tdir)

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


def other1():
    e = ExclusiveFile('test')
    with e:
        os.mkdir('ready')
        while not os.path.exists('quit'):
            time.sleep(0.02)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(IPCLockTest)


if __name__ == '__main__':
    suite = find_tests()
    unittest.TextTestRunner(verbosity=4).run(suite)
