#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import namedtuple
from functools import partial
from io import BytesIO

from calibre.ebooks.metadata import author_to_author_sort
from calibre.utils.date import UNDEFINED_DATE
from calibre.db.tests.base import BaseTest

class WritingTest(BaseTest):

    # Utils {{{
    def create_getter(self, name, getter=None):
        if getter is None:
            if name.endswith('_index'):
                ans = lambda db:partial(db.get_custom_extra, index_is_id=True,
                                        label=name[1:].replace('_index', ''))
            else:
                ans = lambda db:partial(db.get_custom, label=name[1:],
                                       index_is_id=True)
        else:
            ans = lambda db:partial(getattr(db, getter), index_is_id=True)
        return ans

    def create_setter(self, name, setter=None):
        if setter is None:
            ans = lambda db:partial(db.set_custom, label=name[1:], commit=True)
        else:
            ans = lambda db:partial(getattr(db, setter), commit=True)
        return ans

    def create_test(self, name, vals, getter=None, setter=None):
        T = namedtuple('Test', 'name vals getter setter')
        return T(name, vals, self.create_getter(name, getter),
                 self.create_setter(name, setter))

    def run_tests(self, tests):
        results = {}
        for test in tests:
            results[test] = []
            for val in test.vals:
                cl = self.cloned_library
                cache = self.init_cache(cl)
                cache.set_field(test.name, {1: val})
                cached_res = cache.field_for(test.name, 1)
                del cache
                db = self.init_old(cl)
                getter = test.getter(db)
                sqlite_res = getter(1)
                if test.name.endswith('_index'):
                    val = float(val) if val is not None else 1.0
                    self.assertEqual(sqlite_res, val,
                        'Failed setting for %s with value %r, sqlite value not the same. val: %r != sqlite_val: %r'%(
                            test.name, val, val, sqlite_res))
                else:
                    test.setter(db)(1, val)
                    old_cached_res = getter(1)
                    self.assertEqual(old_cached_res, cached_res,
                                    'Failed setting for %s with value %r, cached value not the same. Old: %r != New: %r'%(
                            test.name, val, old_cached_res, cached_res))
                    db.refresh()
                    old_sqlite_res = getter(1)
                    self.assertEqual(old_sqlite_res, sqlite_res,
                        'Failed setting for %s, sqlite value not the same: %r != %r'%(
                            test.name, old_sqlite_res, sqlite_res))
                del db
    # }}}

    def test_one_one(self):  # {{{
        'Test setting of values in one-one fields'
        tests = [self.create_test('#yesno', (True, False, 'true', 'false', None))]
        for name, getter, setter in (
            ('#series_index', None, None),
            ('series_index', 'series_index', 'set_series_index'),
            ('#float', None, None),
        ):
            vals = ['1.5', None, 0, 1.0]
            tests.append(self.create_test(name, tuple(vals), getter, setter))

        for name, getter, setter in (
            ('pubdate', 'pubdate', 'set_pubdate'),
            ('timestamp', 'timestamp', 'set_timestamp'),
            ('#date', None, None),
        ):
            tests.append(self.create_test(
                name, ('2011-1-12', UNDEFINED_DATE, None), getter, setter))

        for name, getter, setter in (
            ('title', 'title', 'set_title'),
            ('uuid', 'uuid', 'set_uuid'),
            ('author_sort', 'author_sort', 'set_author_sort'),
            ('sort', 'title_sort', 'set_title_sort'),
            ('#comments', None, None),
            ('comments', 'comments', 'set_comment'),
        ):
            vals = ['something', None]
            if name not in {'comments', '#comments'}:
                # Setting text column to '' returns None in the new backend
                # and '' in the old. I think None is more correct.
                vals.append('')
            if name == 'comments':
                # Again new behavior of deleting comment rather than setting
                # empty string is more correct.
                vals.remove(None)
            tests.append(self.create_test(name, tuple(vals), getter, setter))

        self.run_tests(tests)
    # }}}

    def test_many_one_basic(self):  # {{{
        'Test the different code paths for writing to a many-one field'
        cl = self.cloned_library
        cache = self.init_cache(cl)
        f = cache.fields['publisher']
        item_ids = {f.ids_for_book(1)[0], f.ids_for_book(2)[0]}
        val = 'Changed'
        self.assertEqual(cache.set_field('publisher', {1:val, 2:val}), {1, 2})
        cache2 = self.init_cache(cl)
        for book_id in (1, 2):
            for c in (cache, cache2):
                self.assertEqual(c.field_for('publisher', book_id), val)
                self.assertFalse(item_ids.intersection(set(c.fields['publisher'].table.id_map)))
        del cache2
        self.assertFalse(cache.set_field('publisher', {1:val, 2:val}))
        val = val.lower()
        self.assertFalse(cache.set_field('publisher', {1:val, 2:val},
                                         allow_case_change=False))
        self.assertEqual(cache.set_field('publisher', {1:val, 2:val}), {1, 2})
        cache2 = self.init_cache(cl)
        for book_id in (1, 2):
            for c in (cache, cache2):
                self.assertEqual(c.field_for('publisher', book_id), val)
        del cache2
        self.assertEqual(cache.set_field('publisher', {1:'new', 2:'New'}), {1, 2})
        self.assertEqual(cache.field_for('publisher', 1).lower(), 'new')
        self.assertEqual(cache.field_for('publisher', 2).lower(), 'new')
        self.assertEqual(cache.set_field('publisher', {1:None, 2:'NEW'}), {1, 2})
        self.assertEqual(len(f.table.id_map), 1)
        self.assertEqual(cache.set_field('publisher', {2:None}), {2})
        self.assertEqual(len(f.table.id_map), 0)
        cache2 = self.init_cache(cl)
        self.assertEqual(len(cache2.fields['publisher'].table.id_map), 0)
        del cache2
        self.assertEqual(cache.set_field('publisher', {1:'one', 2:'two',
                                                       3:'three'}), {1, 2, 3})
        self.assertEqual(cache.set_field('publisher', {1:''}), set([1]))
        self.assertEqual(cache.set_field('publisher', {1:'two'}), set([1]))
        self.assertEqual(tuple(map(f.for_book, (1,2,3))), ('two', 'two', 'three'))
        self.assertEqual(cache.set_field('publisher', {1:'Two'}), {1, 2})
        cache2 = self.init_cache(cl)
        self.assertEqual(tuple(map(f.for_book, (1,2,3))), ('Two', 'Two', 'three'))
        del cache2

        # Enum
        self.assertFalse(cache.set_field('#enum', {1:'Not allowed'}))
        self.assertEqual(cache.set_field('#enum', {1:'One', 2:'One', 3:'Three'}), {1, 3})
        self.assertEqual(cache.set_field('#enum', {1:None}), set([1]))
        cache2 = self.init_cache(cl)
        for c in (cache, cache2):
            for i, val in {1:None, 2:'One', 3:'Three'}.iteritems():
                self.assertEqual(c.field_for('#enum', i), val)
        del cache2

        # Rating
        self.assertFalse(cache.set_field('rating', {1:6, 2:4}))
        self.assertEqual(cache.set_field('rating', {1:0, 3:2}), {1, 3})
        self.assertEqual(cache.set_field('#rating', {1:None, 2:4, 3:8}), {1, 2, 3})
        cache2 = self.init_cache(cl)
        for c in (cache, cache2):
            for i, val in {1:None, 2:4, 3:2}.iteritems():
                self.assertEqual(c.field_for('rating', i), val)
            for i, val in {1:None, 2:4, 3:8}.iteritems():
                self.assertEqual(c.field_for('#rating', i), val)
        del cache2

        # Series
        self.assertFalse(cache.set_field('series',
                {1:'a series one', 2:'a series one'}, allow_case_change=False))
        self.assertEqual(cache.set_field('series', {3:'Series [3]'}), set([3]))
        self.assertEqual(cache.set_field('#series', {1:'Series', 3:'Series'}),
                                         {1, 3})
        self.assertEqual(cache.set_field('#series', {2:'Series [0]'}), set([2]))
        cache2 = self.init_cache(cl)
        for c in (cache, cache2):
            for i, val in {1:'A Series One', 2:'A Series One', 3:'Series'}.iteritems():
                self.assertEqual(c.field_for('series', i), val)
            for i in (1, 2, 3):
                self.assertEqual(c.field_for('#series', i), 'Series')
            for i, val in {1:2, 2:1, 3:3}.iteritems():
                self.assertEqual(c.field_for('series_index', i), val)
            for i, val in {1:1, 2:0, 3:1}.iteritems():
                self.assertEqual(c.field_for('#series_index', i), val)
        del cache2

    # }}}

    def test_many_many_basic(self):  # {{{
        'Test the different code paths for writing to a many-many field'
        cl = self.cloned_library
        cache = self.init_cache(cl)
        ae, af, sf = self.assertEqual, self.assertFalse, cache.set_field

        # Tags
        ae(sf('#tags', {1:cache.field_for('tags', 1), 2:cache.field_for('tags', 2)}),
            {1, 2})
        for name in ('tags', '#tags'):
            f = cache.fields[name]
            af(sf(name, {1:('News', 'tag one')}, allow_case_change=False))
            ae(sf(name, {1:'tag one, News'}), {1, 2})
            ae(sf(name, {3:('tag two', 'sep,sep2')}), {2, 3})
            ae(len(f.table.id_map), 4)
            ae(sf(name, {1:None}), set([1]))
            cache2 = self.init_cache(cl)
            for c in (cache, cache2):
                ae(c.field_for(name, 3), ('tag two', 'sep;sep2'))
                ae(len(c.fields[name].table.id_map), 3)
                ae(len(c.fields[name].table.id_map), 3)
                ae(c.field_for(name, 1), ())
                ae(c.field_for(name, 2), ('tag two', 'tag one'))
            del cache2

        # Authors
        ae(sf('#authors', {k:cache.field_for('authors', k) for k in (1,2,3)}),
           {1,2,3})

        for name in ('authors', '#authors'):
            f = cache.fields[name]
            ae(len(f.table.id_map), 3)
            af(cache.set_field(name, {3:None if name == 'authors' else 'Unknown'}))
            ae(cache.set_field(name, {3:'Kovid Goyal & Divok Layog'}), set([3]))
            ae(cache.set_field(name, {1:'', 2:'An, Author'}), {1,2})
            cache2 = self.init_cache(cl)
            for c in (cache, cache2):
                ae(len(c.fields[name].table.id_map), 4 if name =='authors' else 3)
                ae(c.field_for(name, 3), ('Kovid Goyal', 'Divok Layog'))
                ae(c.field_for(name, 2), ('An, Author',))
                ae(c.field_for(name, 1), ('Unknown',) if name=='authors' else ())
                if name == 'authors':
                    ae(c.field_for('author_sort', 1), author_to_author_sort('Unknown'))
                    ae(c.field_for('author_sort', 2), author_to_author_sort('An, Author'))
                    ae(c.field_for('author_sort', 3), author_to_author_sort('Kovid Goyal') + ' & ' + author_to_author_sort('Divok Layog'))
            del cache2
        ae(cache.set_field('authors', {1:'KoviD GoyaL'}), {1, 3})
        ae(cache.field_for('author_sort', 1), 'GoyaL, KoviD')
        ae(cache.field_for('author_sort', 3), 'GoyaL, KoviD & Layog, Divok')

        # Languages
        f = cache.fields['languages']
        ae(f.table.id_map, {1: 'eng', 2: 'deu'})
        ae(sf('languages', {1:''}), set([1]))
        ae(cache.field_for('languages', 1), ())
        ae(sf('languages', {2:('und',)}), set([2]))
        af(f.table.id_map)
        ae(sf('languages', {1:'eng,fra,deu', 2:'es,Dutch', 3:'English'}), {1, 2, 3})
        ae(cache.field_for('languages', 1), ('eng', 'fra', 'deu'))
        ae(cache.field_for('languages', 2), ('spa', 'nld'))
        ae(cache.field_for('languages', 3), ('eng',))
        ae(sf('languages', {3:None}), set([3]))
        ae(cache.field_for('languages', 3), ())
        ae(sf('languages', {1:'deu,fra,eng'}), set([1]), 'Changing order failed')
        ae(sf('languages', {2:'deu,eng,eng'}), set([2]))
        cache2 = self.init_cache(cl)
        for c in (cache, cache2):
            ae(cache.field_for('languages', 1), ('deu', 'fra', 'eng'))
            ae(cache.field_for('languages', 2), ('deu', 'eng'))
        del cache2

        # Identifiers
        f = cache.fields['identifiers']
        ae(sf('identifiers', {3: 'one:1,two:2'}), set([3]))
        ae(sf('identifiers', {2:None}), set([2]))
        ae(sf('identifiers', {1: {'test':'1', 'two':'2'}}), set([1]))
        cache2 = self.init_cache(cl)
        for c in (cache, cache2):
            ae(c.field_for('identifiers', 3), {'one':'1', 'two':'2'})
            ae(c.field_for('identifiers', 2), {})
            ae(c.field_for('identifiers', 1), {'test':'1', 'two':'2'})
        del cache2

        # Test setting of title sort
        ae(sf('title', {1:'The Moose', 2:'Cat'}), {1, 2})
        cache2 = self.init_cache(cl)
        for c in (cache, cache2):
            ae(c.field_for('sort', 1), 'Moose, The')
            ae(c.field_for('sort', 2), 'Cat')

    # }}}

    def test_dirtied(self):  # {{{
        'Test the setting of the dirtied flag and the last_modified column'
        cl = self.cloned_library
        cache = self.init_cache(cl)
        ae, af, sf = self.assertEqual, self.assertFalse, cache.set_field
        # First empty dirtied
        cache.dump_metadata()
        af(cache.dirtied_cache)
        af(self.init_cache(cl).dirtied_cache)

        prev = cache.field_for('last_modified', 3)
        import calibre.db.cache as c
        from datetime import timedelta
        utime = prev+timedelta(days=1)
        onowf = c.nowf
        c.nowf = lambda: utime
        try:
            ae(sf('title', {3:'xxx'}), set([3]))
            self.assertTrue(3 in cache.dirtied_cache)
            ae(cache.field_for('last_modified', 3), utime)
            cache.dump_metadata()
            raw = cache.read_backup(3)
            from calibre.ebooks.metadata.opf2 import OPF
            opf = OPF(BytesIO(raw))
            ae(opf.title, 'xxx')
        finally:
            c.nowf = onowf
    # }}}

    def test_backup(self):  # {{{
        'Test the automatic backup of changed metadata'
        cl = self.cloned_library
        cache = self.init_cache(cl)
        ae, af, sf, ff = self.assertEqual, self.assertFalse, cache.set_field, cache.field_for
        # First empty dirtied
        cache.dump_metadata()
        af(cache.dirtied_cache)
        from calibre.db.backup import MetadataBackup
        interval = 0.01
        mb = MetadataBackup(cache, interval=interval, scheduling_interval=0)
        mb.start()
        try:
            ae(sf('title', {1:'title1', 2:'title2', 3:'title3'}), {1,2,3})
            ae(sf('authors', {1:'author1 & author2', 2:'author1 & author2', 3:'author1 & author2'}), {1,2,3})
            count = 6
            while cache.dirty_queue_length() and count > 0:
                mb.join(interval)
                count -= 1
            af(cache.dirty_queue_length())
        finally:
            mb.stop()
        mb.join(interval)
        af(mb.is_alive())
        from calibre.ebooks.metadata.opf2 import OPF
        for book_id in (1, 2, 3):
            raw = cache.read_backup(book_id)
            opf = OPF(BytesIO(raw))
            ae(opf.title, 'title%d'%book_id)
            ae(opf.authors, ['author1', 'author2'])
    # }}}

    def test_set_cover(self):  # {{{
        ' Test setting of cover '
        cache = self.init_cache()
        ae = self.assertEqual

        # Test removing a cover
        ae(cache.field_for('cover', 1), 1)
        ae(cache.set_cover({1:None}), set([1]))
        ae(cache.field_for('cover', 1), 0)

        img = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xe1\x00\x16Exif\x00\x00II*\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xdb\x00C\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xdb\x00C\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\n\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x11\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xbf\x80\x01\xff\xd9'  # noqa {{{ }}}
        # Test setting a cover
        ae(cache.set_cover({bid:img for bid in (1, 2, 3)}), {1, 2, 3})
        old = self.init_old()
        for book_id in (1, 2, 3):
            ae(cache.cover(book_id), img, 'Cover was not set correctly for book %d' % book_id)
            ae(cache.field_for('cover', book_id), 1)
            ae(old.cover(book_id, index_is_id=True), img, 'Cover was not set correctly for book %d' % book_id)
            self.assertTrue(old.has_cover(book_id))
    # }}}

    def test_set_metadata(self):  # {{{
        ' Test setting of metadata '
        ae = self.assertEqual
        cache = self.init_cache(self.cloned_library)

        # Check that changing title/author updates the path
        mi = cache.get_metadata(1)
        old_path = cache.field_for('path', 1)
        old_title, old_author = mi.title, mi.authors[0]
        ae(old_path, '%s/%s (1)' % (old_author, old_title))
        mi.title, mi.authors = 'New Title', ['New Author']
        cache.set_metadata(1, mi)
        ae(cache.field_for('path', 1), '%s/%s (1)' % (mi.authors[0], mi.title))
        p = cache.format_abspath(1, 'FMT1')
        self.assertTrue(mi.authors[0] in p and mi.title in p)

        # Compare old and new set_metadata()
        db = self.init_old(self.cloned_library)
        mi = db.get_metadata(1, index_is_id=True, get_cover=True, cover_as_data=True)
        mi2 = db.get_metadata(3, index_is_id=True, get_cover=True, cover_as_data=True)
        db.set_metadata(2, mi)
        db.set_metadata(1, mi2, force_changes=True)
        oldmi = db.get_metadata(2, index_is_id=True, get_cover=True, cover_as_data=True)
        oldmi2 = db.get_metadata(1, index_is_id=True, get_cover=True, cover_as_data=True)
        db.close()
        del db
        cache = self.init_cache(self.cloned_library)
        cache.set_metadata(2, mi)
        nmi = cache.get_metadata(2, get_cover=True, cover_as_data=True)
        ae(oldmi.cover_data, nmi.cover_data)
        self.compare_metadata(nmi, oldmi, exclude={'last_modified', 'format_metadata'})
        cache.set_metadata(1, mi2, force_changes=True)
        nmi2 = cache.get_metadata(1, get_cover=True, cover_as_data=True)
        # The new code does not allow setting of #series_index to None, instead
        # it is reset to 1.0
        ae(nmi2.get_extra('#series'), 1.0)
        self.compare_metadata(nmi2, oldmi2, exclude={'last_modified', 'format_metadata', '#series_index'})

    # }}}

