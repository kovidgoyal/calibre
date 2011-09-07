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
        'Test the reading of data from the database'
        cache = init_cache(self.library_path)
        tests = {
                3  : {
                    'title': 'Unknown',
                    'sort': 'Unknown',
                    'authors': ('Unknown',),
                    'author_sort': 'Unknown',
                    'series' : None,
                    'series_index': 1.0,
                    'rating': None,
                    'tags': None,
                    'identifiers': None,
                    'timestamp': datetime.datetime(2011, 9, 7, 13, 54, 41,
                        tzinfo=local_tz),
                    'pubdate': datetime.datetime(2011, 9, 7, 13, 54, 41,
                        tzinfo=local_tz),
                    'last_modified': datetime.datetime(2011, 9, 7, 13, 54, 41,
                        tzinfo=local_tz),
                    'publisher': None,
                    'languages': None,
                    'comments': None,
                    '#enum': None,
                    '#authors':None,
                    '#date':None,
                    '#rating':None,
                    '#series':None,
                    '#series_index': None,
                    '#tags':None,
                    '#yesno':None,
                    '#comments': None,

                },

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
                    'series' : 'Series One',
                    'series_index': 2.0,
                    'rating': 6.0,
                    'tags': ('Tag One',),
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

    def test_sorting(self): # {{{
        'Test sorting'
        cache = init_cache(self.library_path)
        for field, order in {
                'title'  : [2, 1, 3],
                'authors': [2, 1, 3],
                'series' : [3, 2, 1],
                'tags'   : [3, 1, 2],
                'rating' : [3, 2, 1],
                # 'identifiers': [3, 2, 1], There is no stable sort since 1 and
                # 2 have the same identifier keys
                # TODO: Add an empty book to the db and ensure that empty
                # fields sort the same as they do in db2
                'timestamp': [2, 1, 3],
                'pubdate'  : [1, 2, 3],
                'publisher': [3, 2, 1],
                'last_modified': [2, 1, 3],
                'languages': [3, 2, 1],
                'comments': [3, 2, 1],
                '#enum' : [3, 2, 1],
                '#authors' : [3, 2, 1],
                '#date': [3, 1, 2],
                '#rating':[3, 2, 1],
                '#series':[3, 2, 1],
                '#tags':[3, 2, 1],
                '#yesno':[3, 1, 2],
                '#comments':[3, 2, 1],
            }.iteritems():
            x = list(reversed(order))
            self.assertEqual(order, cache.multisort([(field, True)],
                ids_to_sort=x),
                    'Ascending sort of %s failed'%field)
            self.assertEqual(x, cache.multisort([(field, False)],
                ids_to_sort=order),
                    'Descending sort of %s failed'%field)

        # Test subsorting
        self.assertEqual([3, 2, 1], cache.multisort([('identifiers', True),
            ('title', True)]), 'Subsort failed')
    # }}}


def tests():
    return unittest.TestLoader().loadTestsFromTestCase(ReadingTest)

def run():
    unittest.TextTestRunner(verbosity=2).run(tests())

if __name__ == '__main__':
    run()

