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

    @unittest.skipUnless(iswindows, 'Windows only')
    def test_windows_atomic_move(self):
        'Test book file open in another process when changing metadata'
        cl = self.cloned_library
        cache = self.init_cache(cl)
        fpath = cache.format_abspath(1, 'FMT1')
        f = open(fpath, 'rb')
        with self.assertRaises(IOError):
            cache.set_field('title', {1:'Moved'})
        f.close()
        self.assertNotEqual(cache.field_for('title', 1), 'Moved', 'Title was changed despite file lock')


