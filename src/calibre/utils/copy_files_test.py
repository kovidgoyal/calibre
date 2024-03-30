#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
import tempfile
import time
import unittest
from contextlib import closing

from calibre import walk
from calibre.constants import iswindows

from .copy_files import copy_tree, rename_files
from .filenames import nlinks_file

if iswindows:
    from calibre_extensions import winutil


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

    def test_renaming_of_files(self):
        for name in 'one two'.split():
            with open(os.path.join(self.tdir, name), 'w') as f:
                f.write(name)
        renames = {os.path.join(self.tdir, k): os.path.join(self.tdir, v) for k, v in {'one': 'One', 'two': 'three'}.items()}
        rename_files(renames)
        contents = set(os.listdir(self.tdir)) - {'base', 'src'}
        self.ae(contents, {'One', 'three'})

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
        self.assertFalse(os.path.exists(src))

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
            os.mkdir(self.s('lockdir'))
            open(self.s('lockdir/lockfile'), 'w').close()
            before = frozenset(walk(src))
            with open(self.s('lockdir/lockfile')) as locked:
                locked
                self.assertRaises(IOError, copy_tree, src, dest, delete_source=True)
                self.ae(set(os.listdir(self.d())), {'sub', 'lockdir'})
                self.assertFalse(tuple(walk(self.d())))
            self.ae(before, frozenset(walk(src)), 'Source files were deleted despite there being an error')

            shutil.rmtree(dest)
            os.mkdir(dest)
            h = winutil.create_file(
                self.s('lockdir'), winutil.GENERIC_READ|winutil.GENERIC_WRITE|winutil.DELETE,
                winutil.FILE_SHARE_READ|winutil.FILE_SHARE_WRITE|winutil.FILE_SHARE_DELETE, winutil.OPEN_EXISTING,
                winutil.FILE_FLAG_BACKUP_SEMANTICS)
            with closing(h):
                self.assertRaises(IOError, copy_tree, src, dest, delete_source=True)
                self.ae(set(os.listdir(self.d())), {'sub', 'lockdir'})
                self.assertFalse(tuple(walk(self.d())))
            self.ae(before, frozenset(walk(src)), 'Source files were deleted despite there being an error')

def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCopyFiles)
