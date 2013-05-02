#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.db.tests.base import BaseTest

class LegacyTest(BaseTest):

    ''' Test the emulation of the legacy interface. '''

    def test_library_wide_properties(self):  # {{{
        'Test library wide properties'
        def get_props(db):
            props = ('user_version', 'is_second_db', 'library_id', 'field_metadata',
                    'custom_column_label_map', 'custom_column_num_map', 'library_path', 'dbpath')
            fprops = ('last_modified', )
            ans = {x:getattr(db, x) for x in props}
            ans.update({x:getattr(db, x)() for x in fprops})
            ans['all_ids'] = frozenset(db.all_ids())
            return ans

        old = self.init_old()
        oldvals = get_props(old)
        old.close()
        del old
        db = self.init_legacy()
        newvals = get_props(db)
        self.assertEqual(oldvals, newvals)
        db.close()
    # }}}

    def test_get_property(self):  # {{{
        'Test the get_property interface for reading data'
        def get_values(db):
            ans = {}
            for label, loc in db.FIELD_MAP.iteritems():
                if isinstance(label, int):
                    label = '#'+db.custom_column_num_map[label]['label']
                label = type('')(label)
                ans[label] = tuple(db.get_property(i, index_is_id=True, loc=loc)
                                   for i in db.all_ids())
                if label in ('id', 'title', '#tags'):
                    with self.assertRaises(IndexError):
                        db.get_property(9999, loc=loc)
                    with self.assertRaises(IndexError):
                        db.get_property(9999, index_is_id=True, loc=loc)
                if label in {'tags', 'formats'}:
                    # Order is random in the old db for these
                    ans[label] = tuple(set(x.split(',')) if x else x for x in ans[label])
                if label == 'series_sort':
                    # The old db code did not take book language into account
                    # when generating series_sort values (the first book has
                    # lang=deu)
                    ans[label] = ans[label][1:]
            return ans

        old = self.init_old()
        old_vals = get_values(old)
        old.close()
        old = None
        db = self.init_legacy()
        new_vals = get_values(db)
        db.close()
        self.assertEqual(old_vals, new_vals)

    # }}}

    def test_refresh(self):  # {{{
        ' Test refreshing the view after a change to metadata.db '
        db = self.init_legacy()
        db2 = self.init_legacy()
        self.assertEqual(db2.data.cache.set_field('title', {1:'xxx'}), set([1]))
        db2.close()
        del db2
        self.assertNotEqual(db.title(1, index_is_id=True), 'xxx')
        db.check_if_modified()
        self.assertEqual(db.title(1, index_is_id=True), 'xxx')
    # }}}

    def test_legacy_getters(self):  # {{{
        ' Test various functions to get individual bits of metadata '
        old = self.init_old()
        getters = ('path', 'abspath', 'title', 'authors', 'series',
                   'publisher', 'author_sort', 'authors', 'comments',
                   'comment', 'publisher', 'rating', 'series_index', 'tags',
                   'timestamp', 'uuid', 'pubdate', 'ondevice',
                   'metadata_last_modified', 'languages')
        oldvals = {g:tuple(getattr(old, g)(x) for x in xrange(3)) + tuple(getattr(old, g)(x, True) for x in (1,2,3)) for g in getters}
        old_rows = {tuple(r)[:5] for r in old}
        old.close()
        db = self.init_legacy()
        newvals = {g:tuple(getattr(db, g)(x) for x in xrange(3)) + tuple(getattr(db, g)(x, True) for x in (1,2,3)) for g in getters}
        new_rows = {tuple(r)[:5] for r in db}
        for x in (oldvals, newvals):
            x['tags'] = tuple(set(y.split(',')) if y else y for y in x['tags'])
        self.assertEqual(oldvals, newvals)
        self.assertEqual(old_rows, new_rows)

    # }}}

    def test_legacy_coverage(self):  # {{{
        ' Check that the emulation of the legacy interface is (almost) total '
        cl = self.cloned_library
        db = self.init_old(cl)
        ndb = self.init_legacy()

        SKIP_ATTRS = {'TCat_Tag'}

        for attr in dir(db):
            if attr in SKIP_ATTRS:
                continue
            self.assertTrue(hasattr(ndb, attr), 'The attribute %s is missing' % attr)
            # obj = getattr(db, attr)
    # }}}
