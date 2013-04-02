#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, os, shutil, tempfile, atexit, gc
from functools import partial
from io import BytesIO
from future_builtins import map

rmtree = partial(shutil.rmtree, ignore_errors=True)

class BaseTest(unittest.TestCase):

    def setUp(self):
        self.library_path = self.mkdtemp()
        self.create_db(self.library_path)

    def tearDown(self):
        gc.collect(), gc.collect()
        shutil.rmtree(self.library_path)

    def create_db(self, library_path):
        from calibre.library.database2 import LibraryDatabase2
        if LibraryDatabase2.exists_at(library_path):
            raise ValueError('A library already exists at %r'%library_path)
        src = os.path.join(os.path.dirname(__file__), 'metadata.db')
        dest = os.path.join(library_path, 'metadata.db')
        shutil.copyfile(src, dest)
        db = LibraryDatabase2(library_path)
        db.set_cover(1, I('lt.png', data=True))
        db.set_cover(2, I('polish.png', data=True))
        db.add_format(1, 'FMT1', BytesIO(b'book1fmt1'), index_is_id=True)
        db.add_format(1, 'FMT2', BytesIO(b'book1fmt2'), index_is_id=True)
        db.add_format(2, 'FMT1', BytesIO(b'book2fmt1'), index_is_id=True)
        db.conn.close()
        return dest

    def init_cache(self, library_path):
        from calibre.db.backend import DB
        from calibre.db.cache import Cache
        backend = DB(library_path)
        cache = Cache(backend)
        cache.init()
        return cache

    def mkdtemp(self):
        ans = tempfile.mkdtemp(prefix='db_test_')
        atexit.register(rmtree, ans)
        return ans

    def init_old(self, library_path):
        from calibre.library.database2 import LibraryDatabase2
        return LibraryDatabase2(library_path)

    def clone_library(self, library_path):
        if not hasattr(self, 'clone_dir'):
            self.clone_dir = tempfile.mkdtemp()
            atexit.register(rmtree, self.clone_dir)
            self.clone_count = 0
        self.clone_count += 1
        dest = os.path.join(self.clone_dir, str(self.clone_count))
        shutil.copytree(library_path, dest)
        return dest

    @property
    def cloned_library(self):
        return self.clone_library(self.library_path)

    def compare_metadata(self, mi1, mi2):
        allfk1 = mi1.all_field_keys()
        allfk2 = mi2.all_field_keys()
        self.assertEqual(allfk1, allfk2)

        all_keys = {'format_metadata', 'id', 'application_id',
                    'author_sort_map', 'author_link_map', 'book_size',
                    'ondevice_col', 'last_modified', 'has_cover',
                    'cover_data'}.union(allfk1)
        for attr in all_keys:
            if attr == 'user_metadata': continue
            attr1, attr2 = getattr(mi1, attr), getattr(mi2, attr)
            if attr == 'formats':
                attr1, attr2 = map(lambda x:tuple(x) if x else (), (attr1, attr2))
            if isinstance(attr1, (tuple, list)) and 'authors' not in attr and 'languages' not in attr:
                attr1, attr2 = set(attr1), set(attr2)
            self.assertEqual(attr1, attr2,
                    '%s not the same: %r != %r'%(attr, attr1, attr2))
            if attr.startswith('#'):
                attr1, attr2 = mi1.get_extra(attr), mi2.get_extra(attr)
                self.assertEqual(attr1, attr2,
                    '%s {#extra} not the same: %r != %r'%(attr, attr1, attr2))


