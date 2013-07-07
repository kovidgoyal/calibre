#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from io import BytesIO
from tempfile import NamedTemporaryFile
from datetime import timedelta

from calibre.db.tests.base import BaseTest, IMG
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import now, UNDEFINED_DATE

def import_test(replacement_data, replacement_fmt=None):
    def func(path, fmt):
        if not path.endswith('.'+fmt.lower()):
            raise AssertionError('path extension does not match format')
        ext = (replacement_fmt or fmt).lower()
        with PersistentTemporaryFile('.'+ext) as f:
            f.write(replacement_data)
        return f.name
    return func

class AddRemoveTest(BaseTest):

    def test_add_format(self):  # {{{
        'Test adding formats to an existing book record'
        af, ae, at = self.assertFalse, self.assertEqual, self.assertTrue

        cache = self.init_cache()
        table = cache.fields['formats'].table
        NF = b'test_add_formatxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

        # Test that replace=False works
        previous = cache.format(1, 'FMT1')
        af(cache.add_format(1, 'FMT1', BytesIO(NF), replace=False))
        ae(previous, cache.format(1, 'FMT1'))

        # Test that replace=True works
        lm = cache.field_for('last_modified', 1)
        at(cache.add_format(1, 'FMT1', BytesIO(NF), replace=True))
        ae(NF, cache.format(1, 'FMT1'))
        ae(cache.format_metadata(1, 'FMT1')['size'], len(NF))
        at(cache.field_for('size', 1) >= len(NF))
        at(cache.field_for('last_modified', 1) > lm)
        ae(('FMT2','FMT1'), cache.formats(1))
        at(1 in table.col_book_map['FMT1'])

        # Test adding a format to a record with no formats
        at(cache.add_format(3, 'FMT1', BytesIO(NF), replace=True))
        ae(NF, cache.format(3, 'FMT1'))
        ae(cache.format_metadata(3, 'FMT1')['size'], len(NF))
        ae(('FMT1',), cache.formats(3))
        at(3 in table.col_book_map['FMT1'])
        at(cache.add_format(3, 'FMTX', BytesIO(NF), replace=True))
        at(3 in table.col_book_map['FMTX'])
        ae(('FMT1','FMTX'), cache.formats(3))

        # Test running on import plugins
        import calibre.db.cache as c
        orig = c.run_plugins_on_import
        try:
            c.run_plugins_on_import = import_test(b'replacement data')
            at(cache.add_format(3, 'REPL', BytesIO(NF)))
            ae(b'replacement data', cache.format(3, 'REPL'))
            c.run_plugins_on_import = import_test(b'replacement data2', 'REPL2')
            with NamedTemporaryFile(suffix='_test_add_format.repl') as f:
                f.write(NF)
                f.seek(0)
                at(cache.add_format(3, 'REPL', BytesIO(NF)))
                ae(b'replacement data', cache.format(3, 'REPL'))
                ae(b'replacement data2', cache.format(3, 'REPL2'))

        finally:
            c.run_plugins_on_import = orig

        # Test adding FMT with path
        with NamedTemporaryFile(suffix='_test_add_format.fmt9') as f:
            f.write(NF)
            f.seek(0)
            at(cache.add_format(2, 'FMT9', f))
            ae(NF, cache.format(2, 'FMT9'))
            ae(cache.format_metadata(2, 'FMT9')['size'], len(NF))
            at(cache.field_for('size', 2) >= len(NF))
            at(2 in table.col_book_map['FMT9'])

        del cache
        # Test that the old interface also shows correct format data
        db = self.init_old()
        ae(db.formats(3, index_is_id=True), ','.join(['FMT1', 'FMTX', 'REPL', 'REPL2']))
        ae(db.format(3, 'FMT1', index_is_id=True), NF)
        ae(db.format(1, 'FMT1', index_is_id=True), NF)

        db.close()
        del db

    # }}}

    def test_remove_formats(self):  # {{{
        'Test removal of formats from book records'
        af, ae, at = self.assertFalse, self.assertEqual, self.assertTrue

        cache = self.init_cache()

        # Test removal of non-existing format does nothing
        formats = {bid:tuple(cache.formats(bid)) for bid in (1, 2, 3)}
        cache.remove_formats({1:{'NF'}, 2:{'NF'}, 3:{'NF'}})
        nformats = {bid:tuple(cache.formats(bid)) for bid in (1, 2, 3)}
        ae(formats, nformats)

        # Test full removal of format
        af(cache.format(1, 'FMT1') is None)
        at(cache.has_format(1, 'FMT1'))
        cache.remove_formats({1:{'FMT1'}})
        at(cache.format(1, 'FMT1') is None)
        af(bool(cache.format_metadata(1, 'FMT1')))
        af(bool(cache.format_metadata(1, 'FMT1', allow_cache=False)))
        af('FMT1' in cache.formats(1))
        af(cache.has_format(1, 'FMT1'))

        # Test db only removal
        at(cache.has_format(1, 'FMT2'))
        ap = cache.format_abspath(1, 'FMT2')
        if ap and os.path.exists(ap):
            cache.remove_formats({1:{'FMT2'}})
            af(bool(cache.format_metadata(1, 'FMT2')))
            af(cache.has_format(1, 'FMT2'))
            at(os.path.exists(ap))

        # Test that the old interface agrees
        db = self.init_old()
        at(db.format(1, 'FMT1', index_is_id=True) is None)

        db.close()
        del db
    # }}}

    def test_create_book_entry(self):  # {{{
        'Test the creation of new book entries'
        from calibre.ebooks.metadata.book.base import Metadata
        cache = self.init_cache()
        mi = Metadata('Created One', authors=('Creator One', 'Creator Two'))

        book_id = cache.create_book_entry(mi)
        self.assertIsNot(book_id, None)

        def do_test(cache, book_id):
            for field in ('path', 'uuid', 'author_sort', 'timestamp', 'pubdate', 'title', 'authors', 'series_index', 'sort'):
                self.assertTrue(cache.field_for(field, book_id))
            for field in ('size', 'cover'):
                self.assertFalse(cache.field_for(field, book_id))
            self.assertEqual(book_id, cache.fields['uuid'].table.uuid_to_id_map[cache.field_for('uuid', book_id)])
            self.assertLess(now() - cache.field_for('timestamp', book_id), timedelta(seconds=30))
            self.assertEqual(('Created One', ('Creator One', 'Creator Two')), (cache.field_for('title', book_id), cache.field_for('authors', book_id)))
            self.assertEqual(cache.field_for('series_index', book_id), 1.0)
            self.assertEqual(cache.field_for('pubdate', book_id), UNDEFINED_DATE)

        do_test(cache, book_id)
        # Test that the db contains correct data
        cache = self.init_cache()
        do_test(cache, book_id)

        self.assertIs(None, cache.create_book_entry(mi, add_duplicates=False), 'Duplicate added incorrectly')
        book_id = cache.create_book_entry(mi, cover=IMG)
        self.assertIsNot(book_id, None)
        self.assertEqual(IMG, cache.cover(book_id))

        import calibre.db.cache as c
        orig = c.prefs
        c.prefs = {'new_book_tags':('newbook', 'newbook2')}
        try:
            book_id = cache.create_book_entry(mi)
            self.assertEqual(('newbook', 'newbook2'), cache.field_for('tags', book_id))
            mi.tags = ('one', 'two')
            book_id = cache.create_book_entry(mi)
            self.assertEqual(('one', 'two') + ('newbook', 'newbook2'), cache.field_for('tags', book_id))
            mi.tags = ()
        finally:
            c.prefs = orig

        mi.uuid = 'a preserved uuid'
        book_id = cache.create_book_entry(mi, preserve_uuid=True)
        self.assertEqual(mi.uuid, cache.field_for('uuid', book_id))
    # }}}

    def test_add_books(self):  # {{{
        'Test the adding of new books'
        from calibre.ebooks.metadata.book.base import Metadata
        cache = self.init_cache()
        mi = Metadata('Created One', authors=('Creator One', 'Creator Two'))
        FMT1, FMT2 = b'format1', b'format2'
        format_map = {'FMT1':BytesIO(FMT1), 'FMT2':BytesIO(FMT2)}
        ids, duplicates = cache.add_books([(mi, format_map)])
        self.assertTrue(len(ids) == 1)
        self.assertFalse(duplicates)
        book_id = ids[0]
        self.assertEqual(set(cache.formats(book_id)), {'FMT1', 'FMT2'})
        self.assertEqual(cache.format(book_id, 'FMT1'), FMT1)
        self.assertEqual(cache.format(book_id, 'FMT2'), FMT2)
    # }}}

    def test_remove_books(self):  # {{{
        'Test removal of books'
        cache = self.init_cache()
        af, ae, at = self.assertFalse, self.assertEqual, self.assertTrue
        authors = cache.fields['authors'].table

        # Delete a single book, with no formats and check cleaning
        self.assertIn(_('Unknown'), set(authors.id_map.itervalues()))
        olen = len(authors.id_map)
        item_id = {v:k for k, v in authors.id_map.iteritems()}[_('Unknown')]
        cache.remove_books((3,))
        for c in (cache, self.init_cache()):
            table = c.fields['authors'].table
            self.assertNotIn(3, c.all_book_ids())
            self.assertNotIn(_('Unknown'), set(table.id_map.itervalues()))
            self.assertNotIn(item_id, table.asort_map)
            self.assertNotIn(item_id, table.alink_map)
            ae(len(table.id_map), olen-1)

        # Check that files are removed
        fmtpath = cache.format_abspath(1, 'FMT1')
        bookpath = os.path.dirname(fmtpath)
        authorpath = os.path.dirname(bookpath)
        item_id = {v:k for k, v in cache.fields['#series'].table.id_map.iteritems()}['My Series Two']
        cache.remove_books((1,), permanent=True)
        for x in (fmtpath, bookpath, authorpath):
            af(os.path.exists(x))
        for c in (cache, self.init_cache()):
            table = c.fields['authors'].table
            self.assertNotIn(1, c.all_book_ids())
            self.assertNotIn('Author Two', set(table.id_map.itervalues()))
            self.assertNotIn(6, set(c.fields['rating'].table.id_map.itervalues()))
            self.assertIn('A Series One', set(c.fields['series'].table.id_map.itervalues()))
            self.assertNotIn('My Series Two', set(c.fields['#series'].table.id_map.itervalues()))
            self.assertNotIn(item_id, c.fields['#series'].table.col_book_map)
            self.assertNotIn(1, c.fields['#series'].table.book_col_map)

        # Test emptying the db
        cache.remove_books(cache.all_book_ids(), permanent=True)
        for f in ('authors', 'series', '#series', 'tags'):
            table = cache.fields[f].table
            self.assertFalse(table.id_map)
            self.assertFalse(table.book_col_map)
            self.assertFalse(table.col_book_map)

    # }}}


