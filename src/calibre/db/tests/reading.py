#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import os, shutil, unittest, tempfile, datetime

from calibre.utils.date import local_tz

def create_db(library_path):
    from calibre.library.database2 import LibraryDatabase2
    if LibraryDatabase2.exists_at(library_path):
        raise ValueError('A library already exists at %r'%library_path)
    src = os.path.join(os.path.dirname(__file__), 'metadata.db')
    db = os.path.join(library_path, 'metadata.db')
    shutil.copyfile(src, db)
    return db

def init_cache(library_path):
    from calibre.db.backend import DB
    from calibre.db.cache import Cache
    backend = DB(library_path)
    cache = Cache(backend)
    cache.init()
    return cache

class ReadingTest(unittest.TestCase):

    def setUp(self):
        self.library_path = tempfile.mkdtemp()
        create_db(self.library_path)

    def tearDown(self):
        shutil.rmtree(self.library_path)

    def test_read(self): # {{{
        cache = init_cache(self.library_path)
        tests = {
                2 : {
                    'title': 'Title One',
                    'sort': 'One',
                    'authors': ('Author One',),
                    'author_sort': 'One, Author',
                    'series' : 'Series One',
                    'series_index': 1.0,
                    'tags':('Tag Two', 'Tag One'),
                    'rating': 4.0,
                    'identifiers': {'test':'one'},
                    'timestamp': datetime.datetime(2011, 9, 5, 15, 6,
                        tzinfo=local_tz),
                    'pubdate': datetime.datetime(2011, 9, 5, 15, 6,
                        tzinfo=local_tz),
                    'publisher': 'Publisher One',
                    'languages': ('eng',),
                    'comments': '<p>Comments One</p>',
                    '#enum':'One',
                    '#authors':('Custom One', 'Custom Two'),
                    '#date':datetime.datetime(2011, 9, 5, 0, 0,
                        tzinfo=local_tz),
                    '#rating':2.0,
                    '#series':'My Series One',
                    '#series_index': 1.0,
                    '#tags':('My Tag One', 'My Tag Two'),
                    '#yesno':True,
                    '#comments': '<div>My Comments One<p></p></div>',
                },
                1  : {
                    'title': 'Title Two',
                    'sort': 'Title Two',
                    'authors': ('Author Two', 'Author One'),
                    'author_sort': 'Two, Author & One, Author',
                    'series' : 'Series Two',
                    'series_index': 2.0,
                    'rating': 6.0,
                    'tags': ('Tag Two',),
                    'identifiers': {'test':'two'},
                    'timestamp': datetime.datetime(2011, 9, 6, 0, 0,
                        tzinfo=local_tz),
                    'pubdate': datetime.datetime(2011, 8, 5, 0, 0,
                        tzinfo=local_tz),
                    'publisher': 'Publisher Two',
                    'languages': ('deu',),
                    'comments': '<p>Comments Two</p>',
                    '#enum':'Two',
                    '#authors':('My Author Two',),
                    '#date':datetime.datetime(2011, 9, 1, 0, 0,
                        tzinfo=local_tz),
                    '#rating':4.0,
                    '#series':'My Series Two',
                    '#series_index': 3.0,
                    '#tags':('My Tag Two',),
                    '#yesno':False,
                    '#comments': '<div>My Comments Two<p></p></div>',

                },
        }
        for book_id, test in tests.iteritems():
            for field, expected_val in test.iteritems():
                self.assertEqual(expected_val,
                        cache.field_for(field, book_id))
        # }}}

def tests():
    return unittest.TestLoader().loadTestsFromTestCase(ReadingTest)

def run():
    unittest.TextTestRunner(verbosity=2).run(tests())

if __name__ == '__main__':
    run()

