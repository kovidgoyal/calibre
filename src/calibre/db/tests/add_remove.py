#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import glob
import os
from contextlib import suppress
from datetime import timedelta
from io import BytesIO
from tempfile import NamedTemporaryFile

from calibre.db.constants import METADATA_FILE_NAME
from calibre.db.tests.base import IMG, BaseTest
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import UNDEFINED_DATE, now, utcnow
from calibre.utils.img import image_from_path
from calibre.utils.resources import get_image_path
from polyglot.builtins import iteritems, itervalues


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
        ap = cache.format_abspath(1, 'FMT1')
        at(os.path.exists(ap))
        cache.remove_formats({1:{'FMT1'}})
        at(cache.format(1, 'FMT1') is None)
        af(bool(cache.format_metadata(1, 'FMT1')))
        af(bool(cache.format_metadata(1, 'FMT1', allow_cache=False)))
        af('FMT1' in cache.formats(1))
        af(cache.has_format(1, 'FMT1'))
        af(os.path.exists(ap))

        # Test db only removal
        at(cache.has_format(1, 'FMT2'))
        ap = cache.format_abspath(1, 'FMT2')
        if ap and os.path.exists(ap):
            cache.remove_formats({1:{'FMT2'}}, db_only=True)
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
        cache.set_field('authors', {1: 'Creator Two'})
        cache.set_link_map('authors', {'Creator Two': 'original'})
        mi = Metadata('Created One', authors=('Creator One', 'Creator Two'))
        mi.link_maps = {'authors': {'Creator One': 'link1', 'Creator Two': 'changed'}}

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
            self.assertEqual(cache.get_all_link_maps_for_book(book_id), {'authors': {'Creator One': 'link1', 'Creator Two': 'original'}})

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
        cl = self.cloned_library
        cl2 = self.cloned_library
        cl3 = self.cloned_library
        cache = self.init_cache()
        af, ae = self.assertFalse, self.assertEqual
        authors = cache.fields['authors'].table

        # Delete a single book, with no formats and check cleaning
        self.assertIn('Unknown', set(itervalues(authors.id_map)))
        olen = len(authors.id_map)
        item_id = {v:k for k, v in iteritems(authors.id_map)}['Unknown']
        cache.remove_books((3,))
        for c in (cache, self.init_cache()):
            table = c.fields['authors'].table
            self.assertNotIn(3, c.all_book_ids())
            self.assertNotIn('Unknown', set(itervalues(table.id_map)))
            self.assertNotIn(item_id, table.asort_map)
            self.assertNotIn(item_id, table.link_map)
            ae(len(table.id_map), olen-1)

        # Check that files are removed
        fmtpath = cache.format_abspath(1, 'FMT1')
        bookpath = os.path.dirname(fmtpath)
        authorpath = os.path.dirname(bookpath)
        os.mkdir(os.path.join(authorpath, '.DS_Store'))
        open(os.path.join(authorpath, 'Thumbs.db'), 'wb').close()
        item_id = {v:k for k, v in iteritems(cache.fields['#series'].table.id_map)}['My Series Two']
        cache.remove_books((1,), permanent=True)
        for x in (fmtpath, bookpath, authorpath):
            af(os.path.exists(x), 'The file %s exists, when it should not' % x)
        for c in (cache, self.init_cache()):
            table = c.fields['authors'].table
            self.assertNotIn(1, c.all_book_ids())
            self.assertNotIn('Author Two', set(itervalues(table.id_map)))
            self.assertNotIn(6, set(itervalues(c.fields['rating'].table.id_map)))
            self.assertIn('A Series One', set(itervalues(c.fields['series'].table.id_map)))
            self.assertNotIn('My Series Two', set(itervalues(c.fields['#series'].table.id_map)))
            self.assertNotIn(item_id, c.fields['#series'].table.col_book_map)
            self.assertNotIn(1, c.fields['#series'].table.book_col_map)

        # Test emptying the db
        cache.remove_books(cache.all_book_ids(), permanent=True)
        for f in ('authors', 'series', '#series', 'tags'):
            table = cache.fields[f].table
            self.assertFalse(table.id_map)
            self.assertFalse(table.book_col_map)
            self.assertFalse(table.col_book_map)

        # Test the delete service
        # test basic delete book and cache expiry
        cache = self.init_cache(cl)
        fmtpath = cache.format_abspath(1, 'FMT1')
        bookpath = os.path.dirname(fmtpath)
        title = cache.field_for('title', 1)
        os.mkdir(os.path.join(bookpath, 'xyz'))
        open(os.path.join(bookpath, 'xyz', 'abc'), 'w').close()
        authorpath = os.path.dirname(bookpath)
        item_id = {v:k for k, v in iteritems(cache.fields['#series'].table.id_map)}['My Series Two']
        cache.remove_books((1,))
        for x in (fmtpath, bookpath, authorpath):
            af(os.path.exists(x), 'The file %s exists, when it should not' % x)
        b, f = cache.list_trash_entries()
        self.assertEqual(len(b), 1)
        self.assertEqual(len(f), 0)
        self.assertEqual(b[0].title, title)
        self.assertTrue(os.path.exists(b[0].cover_path))
        cache.backend.expire_old_trash(1000)
        self.assertTrue(os.path.exists(b[0].cover_path))
        cache.backend.expire_old_trash(0)
        self.assertFalse(os.path.exists(b[0].cover_path))

        # test restoring of books
        cache = self.init_cache(cl2)
        cache.set_cover({1: image_from_path(get_image_path('lt.png', allow_user_override=False))})
        fmtpath = cache.format_abspath(1, 'FMT1')
        bookpath = os.path.dirname(fmtpath)
        cache.set_annotations_for_book(1, 'FMT1', [({'title': 'else', 'type': 'bookmark', 'timestamp': utcnow().isoformat()}, 1)])
        annots_before = cache.all_annotations_for_book(1)
        fm_before = cache.format_metadata(1, 'FMT1', allow_cache=False), cache.format_metadata(1, 'FMT2', allow_cache=False)
        os.mkdir(os.path.join(bookpath, 'xyz'))
        open(os.path.join(bookpath, 'xyz', 'abc'), 'w').close()
        with suppress(FileNotFoundError):
            os.remove(os.path.join(bookpath, METADATA_FILE_NAME))
        cache.remove_books((1,))
        cache.move_book_from_trash(1)
        b, f = cache.list_trash_entries()
        self.assertEqual(len(b), 0)
        self.assertEqual(len(f), 0)
        self.assertEqual(fmtpath, cache.format_abspath(1, 'FMT1'))
        self.assertEqual(fm_before, (cache.format_metadata(1, 'FMT1', allow_cache=False), cache.format_metadata(1, 'FMT2', allow_cache=False)))
        self.assertEqual(annots_before, cache.all_annotations_for_book(1))
        self.assertTrue(cache.cover(1))
        self.assertTrue(os.path.exists(os.path.join(bookpath, 'xyz', 'abc')))

        # test restoring of formats
        cache = self.init_cache(cl3)
        all_formats = cache.formats(1)
        cache.remove_formats({1: all_formats})
        self.assertFalse(cache.formats(1))
        b, f = cache.list_trash_entries()
        self.assertEqual(len(b), 0)
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].title, title)
        self.assertTrue(f[0].cover_path)
        for fmt in all_formats:
            cache.move_format_from_trash(1, fmt)
        self.assertEqual(all_formats, cache.formats(1))
        self.assertFalse(os.listdir(os.path.join(cache.backend.trash_dir, 'f')))
    # }}}

    def test_original_fmt(self):  # {{{
        ' Test management of original fmt '
        af, ae, at = self.assertFalse, self.assertEqual, self.assertTrue
        db = self.init_cache()
        fmts = db.formats(1)
        af(db.has_format(1, 'ORIGINAL_FMT1'))
        at(db.save_original_format(1, 'FMT1'))
        at(db.has_format(1, 'ORIGINAL_FMT1'))
        raw = db.format(1, 'FMT1')
        ae(raw, db.format(1, 'ORIGINAL_FMT1'))
        db.add_format(1, 'FMT1', BytesIO(b'replacedfmt'))
        self.assertNotEqual(db.format(1, 'FMT1'), db.format(1, 'ORIGINAL_FMT1'))
        at(db.restore_original_format(1, 'ORIGINAL_FMT1'))
        ae(raw, db.format(1, 'FMT1'))
        af(db.has_format(1, 'ORIGINAL_FMT1'))
        ae(set(fmts), set(db.formats(1, verify_formats=False)))
    # }}}

    def test_format_orphan(self):  # {{{
        ' Test that adding formats does not create orphans if the file name algorithm changes '
        cache = self.init_cache()
        path = cache.format_abspath(1, 'FMT1')
        base, name = os.path.split(path)
        prefix = 'mushroomxx'
        os.rename(path, os.path.join(base, prefix + name))
        cache.fields['formats'].table.fname_map[1]['FMT1'] = prefix + os.path.splitext(name)[0]
        old = glob.glob(os.path.join(base, '*.fmt1'))
        cache.add_format(1, 'FMT1', BytesIO(b'xxxx'), run_hooks=False)
        new = glob.glob(os.path.join(base, '*.fmt1'))
        self.assertNotEqual(old, new)
        self.assertEqual(len(old), len(new))
        self.assertNotIn(prefix, cache.fields['formats'].format_fname(1, 'FMT1'))
    # }}}

    def test_copy_to_library(self):  # {{{
        from calibre.db.copy_to_library import copy_one_book
        from calibre.ebooks.metadata import authors_to_string
        from calibre.utils.date import EPOCH, utcnow
        src_db = self.init_cache()
        dest_db = self.init_cache(self.cloned_library)

        def read(x, mode='r'):
            with open(x, mode) as f:
                return f.read()

        def a(**kw):
            ts = utcnow()
            kw['timestamp'] = utcnow().isoformat()
            return kw, (ts - EPOCH).total_seconds()

        annot_list = [
            a(type='bookmark', title='bookmark1 changed', seq=1),
            a(type='highlight', highlighted_text='text1', uuid='1', seq=2),
            a(type='highlight', highlighted_text='text2', uuid='2', seq=3, notes='notes2 some word changed again'),
        ]
        src_db.set_annotations_for_book(1, 'FMT1', annot_list)
        bookdir = os.path.dirname(src_db.format_abspath(1, '__COVER_INTERNAL__'))
        with open(os.path.join(bookdir, 'exf'), 'w') as f:
            f.write('exf')
        os.mkdir(os.path.join(bookdir, 'sub'))
        with open(os.path.join(bookdir, 'sub', 'recurse'), 'w') as f:
            f.write('recurse')

        def make_rdata(book_id=1, new_book_id=None, action='add'):
            return {
                    'title': src_db.field_for('title', book_id),
                    'authors': list(src_db.field_for('authors', book_id)),
                    'author': authors_to_string(src_db.field_for('authors', book_id)),
                    'book_id': book_id, 'new_book_id': new_book_id, 'action': action
            }

        def compare_field(field, func=self.assertEqual):
            func(src_db.field_for(field, rdata['book_id']), dest_db.field_for(field, rdata['new_book_id']))

        def assert_has_extra_files(book_id):
            bookdir = os.path.dirname(dest_db.format_abspath(book_id, '__COVER_INTERNAL__'))
            self.assertEqual('exf', read(os.path.join(bookdir, 'exf')))
            self.assertEqual('recurse', read(os.path.join(bookdir, 'sub', 'recurse')))

        def assert_does_not_have_extra_files(book_id):
            bookdir = os.path.dirname(dest_db.format_abspath(book_id, '__COVER_INTERNAL__'))
            self.assertFalse(os.path.exists(os.path.join(bookdir, 'exf')))
            self.assertFalse(os.path.exists(os.path.join(bookdir, 'sub', 'recurse')))

        def clear_extra_files(book_id):
            for ef in dest_db.list_extra_files(book_id):
                os.remove(ef.file_path)

        assert_does_not_have_extra_files(1)

        rdata = copy_one_book(1, src_db, dest_db)
        self.assertEqual(rdata, make_rdata(new_book_id=max(dest_db.all_book_ids())))
        compare_field('timestamp')
        compare_field('uuid', self.assertNotEqual)
        self.assertEqual(src_db.all_annotations_for_book(1), dest_db.all_annotations_for_book(max(dest_db.all_book_ids())))
        assert_has_extra_files(rdata['new_book_id'])
        clear_extra_files(rdata['new_book_id'])

        rdata = copy_one_book(1, src_db, dest_db, preserve_date=False, preserve_uuid=True)
        self.assertEqual(rdata, make_rdata(new_book_id=max(dest_db.all_book_ids())))
        compare_field('timestamp', self.assertNotEqual)
        compare_field('uuid')
        assert_has_extra_files(rdata['new_book_id'])
        clear_extra_files(rdata['new_book_id'])

        rdata = copy_one_book(1, src_db, dest_db, duplicate_action='ignore')
        self.assertIsNone(rdata['new_book_id'])
        self.assertEqual(rdata['action'], 'duplicate')
        src_db.add_format(1, 'FMT1', BytesIO(b'replaced'), run_hooks=False)
        assert_does_not_have_extra_files(1)

        rdata = copy_one_book(1, src_db, dest_db, duplicate_action='add_formats_to_existing')
        self.assertEqual(rdata['action'], 'automerge')
        for new_book_id in (1, 4, 5):
            self.assertEqual(dest_db.format(new_book_id, 'FMT1'), b'replaced')
            assert_has_extra_files(new_book_id)
            clear_extra_files(new_book_id)

        src_db.add_format(1, 'FMT1', BytesIO(b'second-round'), run_hooks=False)
        rdata = copy_one_book(1, src_db, dest_db, duplicate_action='add_formats_to_existing', automerge_action='ignore')
        self.assertEqual(rdata['action'], 'automerge')
        for new_book_id in (1, 4, 5):
            self.assertEqual(dest_db.format(new_book_id, 'FMT1'), b'replaced')
            assert_does_not_have_extra_files(new_book_id)

        rdata = copy_one_book(1, src_db, dest_db, duplicate_action='add_formats_to_existing', automerge_action='new record')
        self.assertEqual(rdata['action'], 'automerge')
        for new_book_id in (1, 4, 5):
            self.assertEqual(dest_db.format(new_book_id, 'FMT1'), b'replaced')
            assert_does_not_have_extra_files(new_book_id)
        self.assertEqual(dest_db.format(rdata['new_book_id'], 'FMT1'), b'second-round')
        assert_has_extra_files(rdata['new_book_id'])

    # }}}

    def test_merging_extra_files(self):  # {{{
        db = self.init_cache()

        def add_extra(book_id, relpath):
            db.add_extra_files(book_id, {relpath: BytesIO(f'{book_id}:{relpath}'.encode())})

        def extra_files_for(book_id):
            ans = {}
            for ef in db.list_extra_files(book_id):
                with open(ef.file_path) as f:
                    ans[ef.relpath] = f.read()
            return ans

        add_extra(1, 'one'), add_extra(1, 'sub/one')
        add_extra(2, 'one'), add_extra(2, 'sub/one'), add_extra(2, 'two/two')
        add_extra(3, 'one'), add_extra(3, 'sub/one'), add_extra(3, 'three')

        self.assertEqual(extra_files_for(1), {
            'one': '1:one', 'sub/one': '1:sub/one',
        })
        db.merge_extra_files(1, (2, 3))
        self.assertEqual(extra_files_for(1), {
            'one': '1:one', 'sub/one': '1:sub/one',
            'merge conflict/one': '2:one', 'sub/merge conflict/one': '2:sub/one', 'two/two': '2:two/two',
            'three': '3:three', 'merge conflict 1/one': '3:one', 'sub/merge conflict 1/one': '3:sub/one',
        })
    # }}}
