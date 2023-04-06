#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import shutil
import tempfile
import unittest


class TestCopyFiles(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def setUp(self):
        self.tdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tdir)

    def test_copy_files(self):
        pass


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCopyFiles)
