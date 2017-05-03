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
            with FastFailEF('test'):
                self.locked = True
        except EnvironmentError:
            self.locked = False


def run_worker(mod, func, **kw):
    exe = [sys.executable, os.path.join(sys.setup_dir, 'run-calibre-worker.py')]
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
        with ExclusiveFile('test'):
            ef = FastFailEF('test')
            self.assertRaises(EnvironmentError, ef.__enter__)
            t = Other()
            t.start(), t.join()
            self.assertIs(t.locked, False)
        if not iswindows:
            with unix_open('test') as f:
                self.assertEqual(
                    1, fcntl.fcntl(f.fileno(), fcntl.F_GETFD) & fcntl.FD_CLOEXEC
                )

    def test_exclusive_file_other_process(self):
        child = run_worker('calibre.utils.test_lock', 'other1')
        print(1111111, child)
        while child.poll() is None:
            if os.path.exists('ready'):
                break
            time.sleep(0.01)
        self.assertIsNone(child.poll(), 'child died without creating ready dir')
        ef = FastFailEF('test')
        self.assertRaises(EnvironmentError, ef.__enter__)
        child.kill()
        self.assertIsNotNone(child.wait())
        with ExclusiveFile('test'):
            pass


def other1():
    e = ExclusiveFile('test')
    with e:
        os.mkdir('ready')
        print(22222222)
        time.sleep(30)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(IPCLockTest)


if __name__ == '__main__':
    suite = find_tests()
    unittest.TextTestRunner(verbosity=4).run(suite)
