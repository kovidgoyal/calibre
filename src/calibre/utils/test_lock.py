#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import shutil
import subprocess
import tempfile
import unittest
from threading import Thread

from calibre.constants import iswindows, fcntl
from calibre.debug import run_calibre_debug
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
        child = run_calibre_debug(
            '-c',
            'from calibre.utils.test_lock import other1; other1()',
            stdout=subprocess.PIPE
        )
        ready = child.stdout.readline()
        self.assertEqual(ready.strip(), b'ready')
        ef = FastFailEF('test')
        self.assertRaises(EnvironmentError, ef.__enter__)
        child.kill()
        self.assertIsNotNone(child.wait())
        with ExclusiveFile('test'):
            pass


def other1():
    import sys, time
    e = ExclusiveFile('test')
    with e:
        print('ready')
        sys.stdout.close()
        sys.stderr.close()
        time.sleep(30)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(IPCLockTest)
