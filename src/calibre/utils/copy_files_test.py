#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
import tempfile
import time
import unittest

from calibre import walk
from calibre.constants import iswindows

from .copy_files import copy_tree
from .filenames import nlinks_file


class TestCopyFiles(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def setUp(self):
        self.tdir = t = tempfile.mkdtemp()
        def wf(*parts):
            d = os.path.join(t, *parts)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            with open(d, 'w') as f:
                f.write(' '.join(parts))
        wf('base'), wf('src/one'), wf('src/sub/a')
        if not iswindows:
            os.symlink('sub/a', os.path.join(t, 'src/link'))

    def tearDown(self):
        if self.tdir:
            try:
                shutil.rmtree(self.tdir)
            except OSError:
                time.sleep(1)
                shutil.rmtree(self.tdir)
        self.tdir = ''

    def s(self, *path):
        return os.path.abspath(os.path.join(self.tdir, 'src', *path))

    def d(self, *path):
        return os.path.abspath(os.path.join(self.tdir, 'dest', *path))

    def file_data_eq(self, path):
        with open(self.s(path)) as src, open(self.d(path)) as dest:
            self.ae(src.read(), dest.read())

    def reset(self):
        self.tearDown()
        self.setUp()

    def test_copying_of_trees(self):
        src, dest = self.s(), self.d()
        copy_tree(src, dest)
        eq = self.file_data_eq
        eq('one')
        eq('sub/a')
        if not iswindows:
            eq('link')
            self.ae(os.readlink(self.d('link')), 'sub/a')
        self.ae(nlinks_file(self.s('one')), 2)
        self.ae(set(os.listdir(self.tdir)), {'src', 'dest', 'base'})
        self.reset()
        src, dest = self.s(), self.d()
        copy_tree(src, dest, delete_source=True)
        self.ae(set(os.listdir(self.tdir)), {'dest', 'base'})
        self.ae(nlinks_file(self.d('one')), 1)

        def transform_destination_filename(src, dest):
            return dest + '.extra'

        self.reset()
        src, dest = self.s(), self.d()
        copy_tree(src, dest, transform_destination_filename=transform_destination_filename)
        with open(self.d('sub/a.extra')) as d:
            self.ae(d.read(), 'src/sub/a')
        if not iswindows:
            self.ae(os.readlink(self.d('link.extra')), 'sub/a')

        self.reset()
        src, dest = self.s(), self.d()
        if iswindows:
            with open(self.s('sub/a')) as locked:
                locked
                self.assertRaises(IOError, copy_tree, src, dest)
                self.ae(os.listdir(self.d()), ['sub'])
                self.assertFalse(tuple(walk(self.d())))

def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCopyFiles)
