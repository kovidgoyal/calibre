#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, os, shutil
from future_builtins import map

class BaseTest(unittest.TestCase):

    def create_db(self, library_path):
        from calibre.library.database2 import LibraryDatabase2
        if LibraryDatabase2.exists_at(library_path):
            raise ValueError('A library already exists at %r'%library_path)
        src = os.path.join(os.path.dirname(__file__), 'metadata.db')
        db = os.path.join(library_path, 'metadata.db')
        shutil.copyfile(src, db)
        return db

    def init_cache(self, library_path):
        from calibre.db.backend import DB
        from calibre.db.cache import Cache
        backend = DB(library_path)
        cache = Cache(backend)
        cache.init()
        return cache

    def compare_metadata(self, mi1, mi2):
        allfk1 = mi1.all_field_keys()
        allfk2 = mi2.all_field_keys()
        self.assertEqual(allfk1, allfk2)

        all_keys = {'format_metadata', 'id', 'application_id',
                'author_sort_map', 'author_link_map', 'book_size',
                'ondevice_col', 'last_modified'}.union(allfk1)
        for attr in all_keys:
            if attr == 'user_metadata': continue
            if attr == 'format_metadata': continue # TODO: Not implemented yet
            attr1, attr2 = getattr(mi1, attr), getattr(mi2, attr)
            if attr == 'formats':
                attr1, attr2 = map(lambda x:tuple(x) if x else (), (attr1, attr2))
            self.assertEqual(attr1, attr2,
                    '%s not the same: %r != %r'%(attr, attr1, attr2))
            if attr.startswith('#'):
                attr1, attr2 = mi1.get_extra(attr), mi2.get_extra(attr)
                self.assertEqual(attr1, attr2,
                    '%s {#extra} not the same: %r != %r'%(attr, attr1, attr2))


