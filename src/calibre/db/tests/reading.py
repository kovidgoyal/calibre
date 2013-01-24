#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import shutil, unittest, tempfile, datetime
from cStringIO import StringIO

from calibre.utils.date import utc_tz
from calibre.db.tests.base import BaseTest

class ReadingTest(BaseTest):

    def setUp(self):
        self.library_path = tempfile.mkdtemp()
        self.create_db(self.library_path)

    def tearDown(self):
        shutil.rmtree(self.library_path)

    def test_read(self): # {{{
        'Test the reading of data from the database'
        cache = self.init_cache(self.library_path)
        tests = {
                3  : {
                    'title': 'Unknown',
                    'sort': 'Unknown',
                    'authors': ('Unknown',),
                    'author_sort': 'Unknown',
                    'series' : None,
                    'series_index': 1.0,
                    'rating': None,
                    'tags': (),
                    'formats':(),
                    'identifiers': {},
                    'timestamp': datetime.datetime(2011, 9, 7, 19, 54, 41,
                        tzinfo=utc_tz),
                    'pubdate': datetime.datetime(2011, 9, 7, 19, 54, 41,
                        tzinfo=utc_tz),
                    'last_modified': datetime.datetime(2011, 9, 7, 19, 54, 41,
                        tzinfo=utc_tz),
                    'publisher': None,
                    'languages': (),
                    'comments': None,
                    '#enum': None,
                    '#authors':(),
                    '#date':None,
                    '#rating':None,
                    '#series':None,
                    '#series_index': None,
                    '#tags':(),
                    '#yesno':None,
                    '#comments': None,

                },

                2 : {
                    'title': 'Title One',
                    'sort': 'One',
                    'authors': ('Author One',),
                    'author_sort': 'One, Author',
                    'series' : 'A Series One',
                    'series_index': 1.0,
                    'tags':('Tag One', 'Tag Two'),
                    'formats': (),
                    'rating': 4.0,
                    'identifiers': {'test':'one'},
                    'timestamp': datetime.datetime(2011, 9, 5, 21, 6,
                        tzinfo=utc_tz),
                    'pubdate': datetime.datetime(2011, 9, 5, 21, 6,
                        tzinfo=utc_tz),
                    'publisher': 'Publisher One',
                    'languages': ('eng',),
                    'comments': '<p>Comments One</p>',
                    '#enum':'One',
                    '#authors':('Custom One', 'Custom Two'),
                    '#date':datetime.datetime(2011, 9, 5, 6, 0,
                        tzinfo=utc_tz),
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
                    'series' : 'A Series One',
                    'series_index': 2.0,
                    'rating': 6.0,
                    'tags': ('Tag One',),
                    'formats':(),
                    'identifiers': {'test':'two'},
                    'timestamp': datetime.datetime(2011, 9, 6, 6, 0,
                        tzinfo=utc_tz),
                    'pubdate': datetime.datetime(2011, 8, 5, 6, 0,
                        tzinfo=utc_tz),
                    'publisher': 'Publisher Two',
                    'languages': ('deu',),
                    'comments': '<p>Comments Two</p>',
                    '#enum':'Two',
                    '#authors':('My Author Two',),
                    '#date':datetime.datetime(2011, 9, 1, 6, 0,
                        tzinfo=utc_tz),
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
                val = cache.field_for(field, book_id)
                self.assertEqual(expected_val, val,
                        'Book id: %d Field: %s failed: %r != %r'%(
                            book_id, field, expected_val, val))
        # }}}

    def test_sorting(self): # {{{
        'Test sorting'
        cache = self.init_cache(self.library_path)
        for field, order in {
            'title'  : [2, 1, 3],
            'authors': [2, 1, 3],
            'series' : [3, 1, 2],
            'tags'   : [3, 1, 2],
            'rating' : [3, 2, 1],
            # 'identifiers': [3, 2, 1], There is no stable sort since 1 and
            # 2 have the same identifier keys
            # 'last_modified': [3, 2, 1], There is no stable sort as two
            # records have the exact same value
            'timestamp': [2, 1, 3],
            'pubdate'  : [1, 2, 3],
            'publisher': [3, 2, 1],
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
            # TODO: Add an empty book to the db and ensure that empty
            # fields sort the same as they do in db2
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

    def test_get_metadata(self): # {{{
        'Test get_metadata() returns the same data for both backends'
        from calibre.library.database2 import LibraryDatabase2
        old = LibraryDatabase2(self.library_path)
        for i in xrange(1, 3):
            old.add_format(i, 'txt%d'%i, StringIO(b'random%d'%i),
                    index_is_id=True)
            old.add_format(i, 'text%d'%i, StringIO(b'random%d'%i),
                    index_is_id=True)

        old_metadata = {i:old.get_metadata(i, index_is_id=True) for i in
                xrange(1, 4)}
        old = None

        cache = self.init_cache(self.library_path)

        new_metadata = {i:cache.get_metadata(i) for i in xrange(1, 4)}
        cache = None
        for mi2, mi1 in zip(new_metadata.values(), old_metadata.values()):
            self.compare_metadata(mi1, mi2)

    # }}}

    def test_searching(self): # {{{
        'Test searching returns the same data for both backends'
        from calibre.library.database2 import LibraryDatabase2
        old = LibraryDatabase2(self.library_path)
        oldvals = {query:set(old.search_getting_ids(query, '')) for query in (
            # Date tests
            'date:9/6/2011', 'date:true', 'date:false', 'pubdate:9/2011',
            '#date:true', 'date:<100daysago', 'date:>9/6/2011',
            '#date:>9/1/2011', '#date:=2011',

            # Number tests
            'rating:3', 'rating:>2', 'rating:=2', 'rating:true',
            'rating:false', 'rating:>4', 'tags:#<2', 'tags:#>7',
            'cover:false', 'cover:true', '#float:>11', '#float:<1k',
            '#float:10.01', 'series_index:1', 'series_index:<3', 'id:1',
            'id:>2',

            # Bool tests
            '#yesno:true', '#yesno:false', '#yesno:yes', '#yesno:no',
            '#yesno:empty',

            # Keypair tests
            'identifiers:true', 'identifiers:false', 'identifiers:test',
            'identifiers:test:false', 'identifiers:test:one',
            'identifiers:t:n', 'identifiers:=test:=two', 'identifiers:x:y',
            'identifiers:z',

            # Text tests
            'title:="Title One"', 'title:~title', '#enum:=one', '#enum:tw',
            '#enum:false', '#enum:true', 'series:one', 'tags:one', 'tags:true',
            'tags:false', '2', 'one', '20.02', '"publisher one"',
            '"my comments one"',

            # User categories
            '@Good Authors:One', '@Good Series.good tags:two',

            # TODO: Tests for searching the size and #formats columns and
            # cover:true|false
        )}
        old = None

        cache = self.init_cache(self.library_path)
        for query, ans in oldvals.iteritems():
            nr = cache.search(query, '')
            self.assertEqual(ans, nr,
                'Old result: %r != New result: %r for search: %s'%(
                    ans, nr, query))

    # }}}

    def test_get_categories(self): # {{{
        'Check that get_categories() returns the same data for both backends'
        from calibre.library.database2 import LibraryDatabase2
        old = LibraryDatabase2(self.library_path)
        old_categories = old.get_categories()
        cache = self.init_cache(self.library_path)
        import pprint
        pprint.pprint(old_categories)
        pprint.pprint(cache.get_categories())

    # }}}

def tests():
    return unittest.TestLoader().loadTestsFromTestCase(ReadingTest)

def run():
    unittest.TextTestRunner(verbosity=2).run(tests())

if __name__ == '__main__':
    run()

