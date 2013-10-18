#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, os
from io import BytesIO

from calibre.constants import iswindows
from calibre.db.tests.base import BaseTest

class FilesystemTest(BaseTest):

    def get_filesystem_data(self, cache, book_id):
        fmts = cache.field_for('formats', book_id)
        ans = {}
        for fmt in fmts:
            buf = BytesIO()
            if cache.copy_format_to(book_id, fmt, buf):
                ans[fmt] = buf.getvalue()
        buf = BytesIO()
        if cache.copy_cover_to(book_id, buf):
            ans['cover'] = buf.getvalue()
        return ans

    def test_metadata_move(self):
        'Test the moving of files when title/author change'
        cl = self.cloned_library
        cache = self.init_cache(cl)
        ae, af, sf = self.assertEqual, self.assertFalse, cache.set_field

        # Test that changing metadata on a book with no formats/cover works
        ae(sf('title', {3:'moved1'}), set([3]))
        ae(sf('authors', {3:'moved1'}), set([3]))
        ae(sf('title', {3:'Moved1'}), set([3]))
        ae(sf('authors', {3:'Moved1'}), set([3]))
        ae(cache.field_for('title', 3), 'Moved1')
        ae(cache.field_for('authors', 3), ('Moved1',))

        # Now try with a book that has covers and formats
        orig_data = self.get_filesystem_data(cache, 1)
        orig_fpath = cache.format_abspath(1, 'FMT1')
        ae(sf('title', {1:'moved'}), set([1]))
        ae(sf('authors', {1:'moved'}), set([1]))
        ae(sf('title', {1:'Moved'}), set([1]))
        ae(sf('authors', {1:'Moved'}), set([1]))
        ae(cache.field_for('title', 1), 'Moved')
        ae(cache.field_for('authors', 1), ('Moved',))
        cache2 = self.init_cache(cl)
        for c in (cache, cache2):
            data = self.get_filesystem_data(c, 1)
            ae(set(orig_data.iterkeys()), set(data.iterkeys()))
            ae(orig_data, data, 'Filesystem data does not match')
            ae(c.field_for('path', 1), 'Moved/Moved (1)')
            ae(c.field_for('path', 3), 'Moved1/Moved1 (3)')
        fpath = c.format_abspath(1, 'FMT1').replace(os.sep, '/').split('/')
        ae(fpath[-3:], ['Moved', 'Moved (1)', 'Moved - Moved.fmt1'])
        af(os.path.exists(os.path.dirname(orig_fpath)), 'Original book folder still exists')
        # Check that the filesystem reflects fpath (especially on
        # case-insensitive systems).
        for x in range(1, 4):
            base = os.sep.join(fpath[:-x])
            part = fpath[-x:][0]
            self.assertIn(part, os.listdir(base))

    @unittest.skipUnless(iswindows, 'Windows only')
    def test_windows_atomic_move(self):
        'Test book file open in another process when changing metadata'
        cl = self.cloned_library
        cache = self.init_cache(cl)
        fpath = cache.format_abspath(1, 'FMT1')
        f = open(fpath, 'rb')
        with self.assertRaises(IOError):
            cache.set_field('title', {1:'Moved'})
        with self.assertRaises(IOError):
            cache.remove_books({1})
        f.close()
        self.assertNotEqual(cache.field_for('title', 1), 'Moved', 'Title was changed despite file lock')

        # Test on folder with hardlinks
        from calibre.ptempfile import TemporaryDirectory
        from calibre.utils.filenames import hardlink_file, WindowsAtomicFolderMove
        raw = b'xxx'
        with TemporaryDirectory() as tdir1, TemporaryDirectory() as tdir2:
            a, b = os.path.join(tdir1, 'a'), os.path.join(tdir1, 'b')
            a = os.path.join(tdir1, 'a')
            with open(a, 'wb') as f:
                f.write(raw)
            hardlink_file(a, b)
            wam = WindowsAtomicFolderMove(tdir1)
            wam.copy_path_to(a, os.path.join(tdir2, 'a'))
            wam.copy_path_to(b, os.path.join(tdir2, 'b'))
            wam.delete_originals()
            self.assertEqual([], os.listdir(tdir1))
            self.assertEqual({'a', 'b'}, set(os.listdir(tdir2)))
            self.assertEqual(raw, open(os.path.join(tdir2, 'a'), 'rb').read())
            self.assertEqual(raw, open(os.path.join(tdir2, 'b'), 'rb').read())

    def test_library_move(self):
        ' Test moving of library '
        from calibre.ptempfile import TemporaryDirectory
        cache = self.init_cache()
        self.assertIn('metadata.db', cache.get_top_level_move_items()[0])
        all_ids = cache.all_book_ids()
        fmt1 = cache.format(1, 'FMT1')
        cov = cache.cover(1)
        with TemporaryDirectory('moved_lib') as tdir:
            cache.move_library_to(tdir)
            self.assertIn('moved_lib', cache.backend.library_path)
            self.assertIn('moved_lib', cache.backend.dbpath)
            self.assertEqual(fmt1, cache.format(1, 'FMT1'))
            self.assertEqual(cov, cache.cover(1))
            cache.reload_from_db()
            self.assertEqual(all_ids, cache.all_book_ids())
            cache.backend.close()

    def test_long_filenames(self):
        ' Test long file names '
        cache = self.init_cache()
        cache.set_field('title', {1:'a'*10000})
        self.assertLessEqual(len(cache.field_for('path', 1)), cache.backend.PATH_LIMIT * 2)
        cache.set_field('authors', {1:'b'*10000})
        self.assertLessEqual(len(cache.field_for('path', 1)), cache.backend.PATH_LIMIT * 2)
        fpath = cache.format_abspath(1, cache.formats(1)[0])
        self.assertLessEqual(len(fpath), len(cache.backend.library_path) + cache.backend.PATH_LIMIT * 4)

    def test_fname_change(self):
        ' Test the changing of the filename but not the folder name '
        cache = self.init_cache()
        title = 'a'*30 + 'bbb'
        cache.backend.PATH_LIMIT = 100
        cache.set_field('title', {3:title})
        cache.add_format(3, 'TXT', BytesIO(b'xxx'))
        cache.backend.PATH_LIMIT = 40
        cache.set_field('title', {3:title})
        fpath = cache.format_abspath(3, 'TXT')
        self.assertEqual(sorted([os.path.basename(fpath)]), sorted(os.listdir(os.path.dirname(fpath))))
