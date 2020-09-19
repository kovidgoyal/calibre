#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import inspect, time, numbers
from io import BytesIO
from functools import partial
from operator import itemgetter

from calibre.library.field_metadata import fm_as_dict
from calibre.db.tests.base import BaseTest
from polyglot.builtins import iteritems, range, unicode_type, zip
from polyglot import reprlib

# Utils {{{


class ET(object):

    def __init__(self, func_name, args, kwargs={}, old=None, legacy=None):
        self.func_name = func_name
        self.args, self.kwargs = args, kwargs
        self.old, self.legacy = old, legacy

    def __call__(self, test):
        old = self.old or test.init_old(test.cloned_library)
        legacy = self.legacy or test.init_legacy(test.cloned_library)
        oldres = getattr(old, self.func_name)(*self.args, **self.kwargs)
        newres = getattr(legacy, self.func_name)(*self.args, **self.kwargs)
        test.assertEqual(oldres, newres, 'Equivalence test for %s with args: %s and kwargs: %s failed' % (
            self.func_name, reprlib.repr(self.args), reprlib.repr(self.kwargs)))
        self.retval = newres
        return newres


def get_defaults(spec):
    num = len(spec.defaults or ())
    if not num:
        return {}
    return dict(zip(spec.args[-num:], spec.defaults))


def compare_argspecs(old, new, attr):
    # We dont compare the names of the non-keyword arguments as they are often
    # different and they dont affect the usage of the API.

    ok = len(old.args) == len(new.args) and get_defaults(old) == get_defaults(new)
    if not ok:
        raise AssertionError('The argspec for %s does not match. %r != %r' % (attr, old, new))


def run_funcs(self, db, ndb, funcs):
    for func in funcs:
        meth, args = func[0], func[1:]
        if callable(meth):
            meth(*args)
        else:
            fmt = lambda x:x
            if meth[0] in {'!', '@', '#', '+', '$', '-', '%'}:
                if meth[0] != '+':
                    fmt = {'!':dict, '@':lambda x:frozenset(x or ()), '#':lambda x:set((x or '').split(',')),
                           '$':lambda x:set(tuple(y) for y in x), '-':lambda x:None,
                           '%':lambda x: set((x or '').split(','))}[meth[0]]
                else:
                    fmt = args[-1]
                    args = args[:-1]
                meth = meth[1:]
            res1, res2 = fmt(getattr(db, meth)(*args)), fmt(getattr(ndb, meth)(*args))
            self.assertEqual(res1, res2, 'The method: %s() returned different results for argument %s' % (meth, args))
# }}}


class LegacyTest(BaseTest):

    ''' Test the emulation of the legacy interface. '''

    def test_library_wide_properties(self):  # {{{
        'Test library wide properties'
        def to_unicode(x):
            if isinstance(x, bytes):
                return x.decode('utf-8')
            if isinstance(x, dict):
                # We ignore the key rec_index, since it is not stable for
                # custom columns (it is created by iterating over a dict)
                return {k.decode('utf-8') if isinstance(k, bytes) else k:to_unicode(v)
                        for k, v in iteritems(x) if k != 'rec_index'}
            return x

        def get_props(db):
            props = ('user_version', 'is_second_db', 'library_id',
                    'custom_column_label_map', 'custom_column_num_map', 'library_path', 'dbpath')
            fprops = ('last_modified', )
            ans = {x:getattr(db, x) for x in props}
            ans.update({x:getattr(db, x)() for x in fprops})
            ans['all_ids'] = frozenset(db.all_ids())
            ans['field_metadata'] = fm_as_dict(db.field_metadata)
            return to_unicode(ans)

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
            for label, loc in iteritems(db.FIELD_MAP):
                if isinstance(label, numbers.Integral):
                    label = '#'+db.custom_column_num_map[label]['label']
                label = unicode_type(label)
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
                    # when generating series_sort values
                    ans[label] = None
            return ans

        db = self.init_legacy()
        new_vals = get_values(db)
        db.close()

        old = self.init_old()
        old_vals = get_values(old)
        old.close()
        old = None
        self.assertEqual(old_vals, new_vals)

    # }}}

    def test_refresh(self):  # {{{
        ' Test refreshing the view after a change to metadata.db '
        db = self.init_legacy()
        db2 = self.init_legacy()
        # Ensure that the following change will actually update the timestamp
        # on filesystems with one second resolution (OS X)
        time.sleep(1)
        self.assertEqual(db2.data.cache.set_field('title', {1:'xxx'}), {1})
        db2.close()
        del db2
        self.assertNotEqual(db.title(1, index_is_id=True), 'xxx')
        db.check_if_modified()
        self.assertEqual(db.title(1, index_is_id=True), 'xxx')
    # }}}

    def test_legacy_getters(self):  # {{{
        ' Test various functions to get individual bits of metadata '
        old = self.init_old()
        getters = ('path', 'abspath', 'title', 'title_sort', 'authors', 'series',
                   'publisher', 'author_sort', 'authors', 'comments',
                   'comment', 'publisher', 'rating', 'series_index', 'tags',
                   'timestamp', 'uuid', 'pubdate', 'ondevice',
                   'metadata_last_modified', 'languages')
        oldvals = {g:tuple(getattr(old, g)(x) for x in range(3)) + tuple(getattr(old, g)(x, True) for x in (1,2,3)) for g in getters}
        old_rows = {tuple(r)[:5] for r in old}
        old.close()
        db = self.init_legacy()
        newvals = {g:tuple(getattr(db, g)(x) for x in range(3)) + tuple(getattr(db, g)(x, True) for x in (1,2,3)) for g in getters}
        new_rows = {tuple(r)[:5] for r in db}
        for x in (oldvals, newvals):
            x['tags'] = tuple(set(y.split(',')) if y else y for y in x['tags'])
        self.assertEqual(oldvals, newvals)
        self.assertEqual(old_rows, new_rows)

    # }}}

    def test_legacy_direct(self):  # {{{
        'Test read-only methods that are directly equivalent in the old and new interface'
        from calibre.ebooks.metadata.book.base import Metadata
        from datetime import timedelta
        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old()
        newstag = ndb.new_api.get_item_id('tags', 'news')

        self.assertEqual(dict(db.prefs), dict(ndb.prefs))

        for meth, args in iteritems({
            'find_identical_books': [(Metadata('title one', ['author one']),), (Metadata('unknown'),), (Metadata('xxxx'),)],
            'get_books_for_category': [('tags', newstag), ('#formats', 'FMT1')],
            'get_next_series_num_for': [('A Series One',)],
            'get_id_from_uuid':[('ddddd',), (db.uuid(1, True),)],
            'cover':[(0,), (1,), (2,)],
            'get_author_id': [('author one',), ('unknown',), ('xxxxx',)],
            'series_id': [(0,), (1,), (2,)],
            'publisher_id': [(0,), (1,), (2,)],
            '@tags_older_than': [
                ('News', None), ('Tag One', None), ('xxxx', None), ('Tag One', None, 'News'), ('News', None, 'xxxx'),
                ('News', None, None, ['xxxxxxx']), ('News', None, 'Tag One', ['Author Two', 'Author One']),
                ('News', timedelta(0), None, None), ('News', timedelta(100000)),
            ],
            'format':[(1, 'FMT1', True), (2, 'FMT1', True), (0, 'xxxxxx')],
            'has_format':[(1, 'FMT1', True), (2, 'FMT1', True), (0, 'xxxxxx')],
            'sizeof_format':[(1, 'FMT1', True), (2, 'FMT1', True), (0, 'xxxxxx')],
            '@format_files':[(0,),(1,),(2,)],
            'formats':[(0,),(1,),(2,)],
            'max_size':[(0,),(1,),(2,)],
            'format_hash':[(1, 'FMT1'),(1, 'FMT2'), (2, 'FMT1')],
            'author_sort_from_authors': [(['Author One', 'Author Two', 'Unknown'],)],
            'has_book':[(Metadata('title one'),), (Metadata('xxxx1111'),)],
            'has_id':[(1,), (2,), (3,), (9999,)],
            'id':[(1,), (2,), (0,),],
            'index':[(1,), (2,), (3,), ],
            'row':[(1,), (2,), (3,), ],
            'is_empty':[()],
            'count':[()],
            'all_author_names':[()],
            'all_tag_names':[()],
            'all_series_names':[()],
            'all_publisher_names':[()],
            '!all_authors':[()],
            '!all_tags2':[()],
            '@all_tags':[()],
            '@get_all_identifier_types':[()],
            '!all_publishers':[()],
            '!all_titles':[()],
            '!all_series':[()],
            'standard_field_keys':[()],
            'all_field_keys':[()],
            'searchable_fields':[()],
            'search_term_to_field_key':[('author',), ('tag',)],
            'metadata_for_field':[('title',), ('tags',)],
            'sortable_field_keys':[()],
            'custom_field_keys':[(True,), (False,)],
            '!get_usage_count_by_id':[('authors',), ('tags',), ('series',), ('publisher',), ('#tags',), ('languages',)],
            'get_field':[(1, 'title'), (2, 'tags'), (0, 'rating'), (1, 'authors'), (2, 'series'), (1, '#tags')],
            'all_formats':[()],
            'get_authors_with_ids':[()],
            '!get_tags_with_ids':[()],
            '!get_series_with_ids':[()],
            '!get_publishers_with_ids':[()],
            '!get_ratings_with_ids':[()],
            '!get_languages_with_ids':[()],
            'tag_name':[(3,)],
            'author_name':[(3,)],
            'series_name':[(3,)],
            'authors_sort_strings':[(0,), (1,), (2,)],
            'author_sort_from_book':[(0,), (1,), (2,)],
            'authors_with_sort_strings':[(0,), (1,), (2,)],
            'book_on_device_string':[(1,), (2,), (3,)],
            'books_in_series_of':[(0,), (1,), (2,)],
            'books_with_same_title':[(Metadata(db.title(0)),), (Metadata(db.title(1)),), (Metadata('1234'),)],
        }):
            fmt = lambda x: x
            if meth[0] in {'!', '@'}:
                fmt = {'!':dict, '@':frozenset}[meth[0]]
                meth = meth[1:]
            elif meth == 'get_authors_with_ids':
                fmt = lambda val:{x[0]:tuple(x[1:]) for x in val}
            for a in args:
                self.assertEqual(fmt(getattr(db, meth)(*a)), fmt(getattr(ndb, meth)(*a)),
                                 'The method: %s() returned different results for argument %s' % (meth, a))

        def f(x, y):  # get_top_level_move_items is broken in the old db on case-insensitive file systems
            x.discard('metadata_db_prefs_backup.json')
            return x, y
        self.assertEqual(f(*db.get_top_level_move_items()), f(*ndb.get_top_level_move_items()))
        d1, d2 = BytesIO(), BytesIO()
        db.copy_cover_to(1, d1, True)
        ndb.copy_cover_to(1, d2, True)
        self.assertTrue(d1.getvalue() == d2.getvalue())
        d1, d2 = BytesIO(), BytesIO()
        db.copy_format_to(1, 'FMT1', d1, True)
        ndb.copy_format_to(1, 'FMT1', d2, True)
        self.assertTrue(d1.getvalue() == d2.getvalue())
        old = db.get_data_as_dict(prefix='test-prefix')
        new = ndb.get_data_as_dict(prefix='test-prefix')
        for o, n in zip(old, new):
            o = {unicode_type(k) if isinstance(k, bytes) else k:set(v) if isinstance(v, list) else v for k, v in iteritems(o)}
            n = {k:set(v) if isinstance(v, list) else v for k, v in iteritems(n)}
            self.assertEqual(o, n)

        ndb.search('title:Unknown')
        db.search('title:Unknown')
        self.assertEqual(db.row(3), ndb.row(3))
        self.assertRaises(ValueError, ndb.row, 2)
        self.assertRaises(ValueError, db.row, 2)
        db.close()
        # }}}

    def test_legacy_conversion_options(self):  # {{{
        'Test conversion options API'
        ndb = self.init_legacy()
        db  = self.init_old()
        all_ids = ndb.new_api.all_book_ids()
        op1 = {'xx': 'yy'}

        def decode(x):
            if isinstance(x, bytes):
                x = x.decode('utf-8')
            return x

        for x in (
            ('has_conversion_options', all_ids),
            ('conversion_options', 1, 'PIPE'),
            ('set_conversion_options', 1, 'PIPE', op1),
            ('has_conversion_options', all_ids),
            ('conversion_options', 1, 'PIPE'),
            ('delete_conversion_options', 1, 'PIPE'),
            ('has_conversion_options', all_ids),
        ):
            meth, args = x[0], x[1:]
            self.assertEqual(
                decode(getattr(db, meth)(*args)), decode(getattr(ndb, meth)(*args)),
                'The method: %s() returned different results for argument %s' % (meth, args)
            )
        db.close()
    # }}}

    def test_legacy_delete_using(self):  # {{{
        'Test delete_using() API'
        ndb = self.init_legacy()
        db = self.init_old()
        cache = ndb.new_api
        tmap = cache.get_id_map('tags')
        t = next(iter(tmap))
        pmap = cache.get_id_map('publisher')
        p = next(iter(pmap))
        run_funcs(self, db, ndb, (
            ('delete_tag_using_id', t),
            ('delete_publisher_using_id', p),
            (db.refresh,),
            ('all_tag_names',), ('tags', 0), ('tags', 1), ('tags', 2),
            ('all_publisher_names',), ('publisher', 0), ('publisher', 1), ('publisher', 2),
        ))
        db.close()
    # }}}

    def test_legacy_adding_books(self):  # {{{
        'Test various adding/deleting books methods'
        import sqlite3
        con = sqlite3.connect(":memory:")
        try:
            con.execute("create virtual table recipe using fts5(name, ingredients)")
        except Exception:
            self.skipTest('python sqlite3 module does not have FTS5 support')
        con.close()
        del con
        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.ptempfile import TemporaryFile
        legacy, old = self.init_legacy(self.cloned_library), self.init_old(self.cloned_library)
        mi = Metadata('Added Book0', authors=('Added Author',))
        with TemporaryFile(suffix='.aff') as name:
            with open(name, 'wb') as f:
                f.write(b'xxx')
            T = partial(ET, 'add_books', ([name], ['AFF'], [mi]), old=old, legacy=legacy)
            T()(self)
            book_id = T(kwargs={'return_ids':True})(self)[1][0]
            self.assertEqual(legacy.new_api.formats(book_id), ('AFF',))
            T(kwargs={'add_duplicates':False})(self)
            mi.title = 'Added Book1'
            mi.uuid = 'uuu'
            T = partial(ET, 'import_book', (mi,[name]), old=old, legacy=legacy)
            book_id = T()(self)
            self.assertNotEqual(legacy.uuid(book_id, index_is_id=True), old.uuid(book_id, index_is_id=True))
            book_id = T(kwargs={'preserve_uuid':True})(self)
            self.assertEqual(legacy.uuid(book_id, index_is_id=True), old.uuid(book_id, index_is_id=True))
            self.assertEqual(legacy.new_api.formats(book_id), ('AFF',))

            T = partial(ET, 'add_format', old=old, legacy=legacy)
            T((0, 'AFF', BytesIO(b'fffff')))(self)
            T((0, 'AFF', BytesIO(b'fffff')))(self)
            T((0, 'AFF', BytesIO(b'fffff')), {'replace':True})(self)
        with TemporaryFile(suffix='.opf') as name:
            with open(name, 'wb') as f:
                f.write(b'zzzz')
            T = partial(ET, 'import_book', (mi,[name]), old=old, legacy=legacy)
            book_id = T()(self)
            self.assertFalse(legacy.new_api.formats(book_id))

        mi.title = 'Added Book2'
        T = partial(ET, 'create_book_entry', (mi,), old=old, legacy=legacy)
        T()
        T({'add_duplicates':False})
        T({'force_id':1000})

        with TemporaryFile(suffix='.txt') as name:
            with open(name, 'wb') as f:
                f.write(b'tttttt')
            bid = legacy.add_catalog(name, 'My Catalog')
            self.assertEqual(old.add_catalog(name, 'My Catalog'), bid)
            cache = legacy.new_api
            self.assertEqual(cache.formats(bid), ('TXT',))
            self.assertEqual(cache.field_for('title', bid), 'My Catalog')
            self.assertEqual(cache.field_for('authors', bid), ('calibre',))
            self.assertEqual(cache.field_for('tags', bid), (_('Catalog'),))
            self.assertTrue(bid < legacy.add_catalog(name, 'Something else'))
            self.assertEqual(legacy.add_catalog(name, 'My Catalog'), bid)
            self.assertEqual(old.add_catalog(name, 'My Catalog'), bid)

            bid = legacy.add_news(name, {'title':'Events', 'add_title_tag':True, 'custom_tags':('one', 'two')})
            self.assertEqual(cache.formats(bid), ('TXT',))
            self.assertEqual(cache.field_for('authors', bid), ('calibre',))
            self.assertEqual(cache.field_for('tags', bid), (_('News'), 'Events', 'one', 'two'))

        self.assertTrue(legacy.cover(1, index_is_id=True))
        origcov = legacy.cover(1, index_is_id=True)
        self.assertTrue(legacy.has_cover(1))
        legacy.remove_cover(1)
        self.assertFalse(legacy.has_cover(1))
        self.assertFalse(legacy.cover(1, index_is_id=True))
        legacy.set_cover(3, origcov)
        self.assertEqual(legacy.cover(3, index_is_id=True), origcov)
        self.assertTrue(legacy.has_cover(3))

        self.assertTrue(legacy.format(1, 'FMT1', index_is_id=True))
        legacy.remove_format(1, 'FMT1', index_is_id=True)
        self.assertIsNone(legacy.format(1, 'FMT1', index_is_id=True))

        legacy.delete_book(1)
        old.delete_book(1)
        self.assertNotIn(1, legacy.all_ids())
        legacy.dump_metadata((2,3))
        old.close()
    # }}}

    def test_legacy_coverage(self):  # {{{
        ' Check that the emulation of the legacy interface is (almost) total '
        cl = self.cloned_library
        db = self.init_old(cl)
        ndb = self.init_legacy()

        SKIP_ATTRS = {
            'TCat_Tag', '_add_newbook_tag', '_clean_identifier', '_library_id_', '_set_authors',
            '_set_title', '_set_custom', '_update_author_in_cache',
            # Feeds are now stored in the config folder
            'get_feeds', 'get_feed', 'update_feed', 'remove_feeds', 'add_feed', 'set_feeds',
            # Obsolete/broken methods
            'author_id',  # replaced by get_author_id
            'books_for_author',  # broken
            'books_in_old_database', 'sizeof_old_database',  # unused
            'migrate_old',  # no longer supported
            'remove_unused_series',  # superseded by clean API
            'move_library_to',  # API changed, no code uses old API
            # Added compiled_rules() for calibredb add
            'find_books_in_directory', 'import_book_directory', 'import_book_directory_multiple', 'recursive_import',

            # Internal API
            'clean_user_categories',  'cleanup_tags',  'books_list_filter', 'conn', 'connect', 'construct_file_name',
            'construct_path_name', 'clear_dirtied', 'initialize_database', 'initialize_dynamic',
            'run_import_plugins', 'vacuum', 'set_path', 'row_factory', 'rows', 'rmtree', 'series_index_pat',
            'import_old_database', 'dirtied_lock', 'dirtied_cache', 'dirty_books_referencing',
            'windows_check_if_files_in_use', 'get_metadata_for_dump', 'get_a_dirtied_book', 'dirtied_sequence',
            'format_filename_cache', 'format_metadata_cache', 'filter', 'create_version1', 'normpath', 'custom_data_adapters',
            'custom_table_names', 'custom_columns_in_meta', 'custom_tables',
        }
        SKIP_ARGSPEC = {
            '__init__',
        }

        missing = []

        try:
            total = 0
            for attr in dir(db):
                if attr in SKIP_ATTRS or attr.startswith('upgrade_version'):
                    continue
                total += 1
                if not hasattr(ndb, attr):
                    missing.append(attr)
                    continue
                obj, nobj  = getattr(db, attr), getattr(ndb, attr)
                if attr not in SKIP_ARGSPEC:
                    try:
                        argspec = inspect.getargspec(obj)
                        nargspec = inspect.getargspec(nobj)
                    except (TypeError, ValueError):
                        pass
                    else:
                        compare_argspecs(argspec, nargspec, attr)
        finally:
            for db in (ndb, db):
                db.close()
                db.break_cycles()

        if missing:
            pc = len(missing)/total
            raise AssertionError('{0:.1%} of API ({2} attrs) are missing: {1}'.format(pc, ', '.join(missing), len(missing)))

    # }}}

    def test_legacy_custom_data(self):  # {{{
        'Test the API for custom data storage'
        legacy, old = self.init_legacy(self.cloned_library), self.init_old(self.cloned_library)
        for name in ('name1', 'name2', 'name3'):
            T = partial(ET, 'add_custom_book_data', old=old, legacy=legacy)
            T((1, name, 'val1'))(self)
            T((2, name, 'val2'))(self)
            T((3, name, 'val3'))(self)
            T = partial(ET, 'get_ids_for_custom_book_data', old=old, legacy=legacy)
            T((name,))(self)
            T = partial(ET, 'get_custom_book_data', old=old, legacy=legacy)
            T((1, name, object()))
            T((9, name, object()))
            T = partial(ET, 'get_all_custom_book_data', old=old, legacy=legacy)
            T((name, object()))
            T((name+'!', object()))
            T = partial(ET, 'delete_custom_book_data', old=old, legacy=legacy)
            T((name, 1))
            T = partial(ET, 'get_all_custom_book_data', old=old, legacy=legacy)
            T((name, object()))
            T = partial(ET, 'delete_all_custom_book_data', old=old, legacy=legacy)
            T((name))
            T = partial(ET, 'get_all_custom_book_data', old=old, legacy=legacy)
            T((name, object()))

        T = partial(ET, 'add_multiple_custom_book_data', old=old, legacy=legacy)
        T(('n', {1:'val1', 2:'val2'}))(self)
        T = partial(ET, 'get_all_custom_book_data', old=old, legacy=legacy)
        T(('n', object()))
        old.close()
    # }}}

    def test_legacy_setters(self):  # {{{
        'Test methods that are directly equivalent in the old and new interface'
        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.utils.date import now
        n = now()
        ndb = self.init_legacy(self.cloned_library)
        amap = ndb.new_api.get_id_map('authors')
        sorts = [(aid, 's%d' % aid) for aid in amap]
        db = self.init_old(self.cloned_library)
        run_funcs(self, db, ndb, (
            ('+format_metadata', 1, 'FMT1', itemgetter('size')),
            ('+format_metadata', 1, 'FMT2', itemgetter('size')),
            ('+format_metadata', 2, 'FMT1', itemgetter('size')),
            ('get_tags', 0), ('get_tags', 1), ('get_tags', 2),
            ('is_tag_used', 'News'), ('is_tag_used', 'xchkjgfh'),
            ('bulk_modify_tags', (1,), ['t1'], ['News']),
            ('bulk_modify_tags', (2,), ['t1'], ['Tag One', 'Tag Two']),
            ('bulk_modify_tags', (3,), ['t1', 't2', 't3']),
            (db.clean,),
            ('@all_tags',),
            ('@tags', 0), ('@tags', 1), ('@tags', 2),

            ('unapply_tags', 1, ['t1']),
            ('unapply_tags', 2, ['xxxx']),
            ('unapply_tags', 3, ['t2', 't3']),
            (db.clean,),
            ('@all_tags',),
            ('@tags', 0), ('@tags', 1), ('@tags', 2),

            ('update_last_modified', (1,), True, n), ('update_last_modified', (3,), True, n),
            ('metadata_last_modified', 1, True), ('metadata_last_modified', 3, True),
            ('set_sort_field_for_author', sorts[0][0], sorts[0][1]),
            ('set_sort_field_for_author', sorts[1][0], sorts[1][1]),
            ('set_sort_field_for_author', sorts[2][0], sorts[2][1]),
            ('set_link_field_for_author', sorts[0][0], sorts[0][1]),
            ('set_link_field_for_author', sorts[1][0], sorts[1][1]),
            ('set_link_field_for_author', sorts[2][0], sorts[2][1]),
            (db.refresh,),
            ('author_sort', 0), ('author_sort', 1), ('author_sort', 2),
        ))
        omi = [db.get_metadata(x) for x in (0, 1, 2)]
        nmi = [ndb.get_metadata(x) for x in (0, 1, 2)]
        self.assertEqual([x.author_sort_map for x in omi], [x.author_sort_map for x in nmi])
        self.assertEqual([x.author_link_map for x in omi], [x.author_link_map for x in nmi])
        db.close()

        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)

        run_funcs(self, db, ndb, (
            ('set_authors', 1, ('author one',),), ('set_authors', 2, ('author two',), True, True, True),
            ('set_author_sort', 3, 'new_aus'),
            ('set_comment', 1, ''), ('set_comment', 2, None), ('set_comment', 3, '<p>a comment</p>'),
            ('set_has_cover', 1, True), ('set_has_cover', 2, True), ('set_has_cover', 3, 1),
            ('set_identifiers', 2, {'test':'', 'a':'b'}), ('set_identifiers', 3, {'id':'1', 'isbn':'9783161484100'}), ('set_identifiers', 1, {}),
            ('set_languages', 1, ('en',)),
            ('set_languages', 2, ()),
            ('set_languages', 3, ('deu', 'spa', 'fra')),
            ('set_pubdate', 1, None), ('set_pubdate', 2, '2011-1-7'),
            ('set_series', 1, 'a series one'), ('set_series', 2, 'another series [7]'), ('set_series', 3, 'a third series'),
            ('set_publisher', 1, 'publisher two'), ('set_publisher', 2, None), ('set_publisher', 3, 'a third puB'),
            ('set_rating', 1, 2.3), ('set_rating', 2, 0), ('set_rating', 3, 8),
            ('set_timestamp', 1, None), ('set_timestamp', 2, '2011-1-7'),
            ('set_uuid', 1, None), ('set_uuid', 2, 'a test uuid'),
            ('set_title', 1, 'title two'), ('set_title', 2, None), ('set_title', 3, 'The Test Title'),
            ('set_tags', 1, ['a1', 'a2'], True), ('set_tags', 2, ['b1', 'tag one'], False, False, False, True), ('set_tags', 3, ['A1']),
            (db.refresh,),
            ('title', 0), ('title', 1), ('title', 2),
            ('title_sort', 0), ('title_sort', 1), ('title_sort', 2),
            ('authors', 0), ('authors', 1), ('authors', 2),
            ('author_sort', 0), ('author_sort', 1), ('author_sort', 2),
            ('has_cover', 3), ('has_cover', 1), ('has_cover', 2),
            ('get_identifiers', 0), ('get_identifiers', 1), ('get_identifiers', 2),
            ('pubdate', 0), ('pubdate', 1), ('pubdate', 2),
            ('timestamp', 0), ('timestamp', 1), ('timestamp', 2),
            ('publisher', 0), ('publisher', 1), ('publisher', 2),
            ('rating', 0), ('+rating', 1, lambda x: x or 0), ('rating', 2),
            ('series', 0), ('series', 1), ('series', 2),
            ('series_index', 0), ('series_index', 1), ('series_index', 2),
            ('uuid', 0), ('uuid', 1), ('uuid', 2),
            ('isbn', 0), ('isbn', 1), ('isbn', 2),
            ('@tags', 0), ('@tags', 1), ('@tags', 2),
            ('@all_tags',),
            ('@get_all_identifier_types',),

            ('set_title_sort', 1, 'Title Two'), ('set_title_sort', 2, None), ('set_title_sort', 3, 'The Test Title_sort'),
            ('set_series_index', 1, 2.3), ('set_series_index', 2, 0), ('set_series_index', 3, 8),
            ('set_identifier', 1, 'moose', 'val'), ('set_identifier', 2, 'test', ''), ('set_identifier', 3, '', ''),
            (db.refresh,),
            ('series_index', 0), ('series_index', 1), ('series_index', 2),
            ('title_sort', 0), ('title_sort', 1), ('title_sort', 2),
            ('get_identifiers', 0), ('get_identifiers', 1), ('get_identifiers', 2),
            ('@get_all_identifier_types',),

            ('set_metadata', 1, Metadata('title', ('a1',)), False, False, False, True, True),
            ('set_metadata', 3, Metadata('title', ('a1',))),
            (db.refresh,),
            ('title', 0), ('title', 1), ('title', 2),
            ('title_sort', 0), ('title_sort', 1), ('title_sort', 2),
            ('authors', 0), ('authors', 1), ('authors', 2),
            ('author_sort', 0), ('author_sort', 1), ('author_sort', 2),
            ('@tags', 0), ('@tags', 1), ('@tags', 2),
            ('@all_tags',),
            ('@get_all_identifier_types',),
        ))
        db.close()

        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)

        run_funcs(self, db, ndb, (
            ('set', 0, 'title', 'newtitle'),
            ('set', 0, 'tags', 't1,t2,tag one', True),
            ('set', 0, 'authors', 'author one & Author Two', True),
            ('set', 0, 'rating', 3.2),
            ('set', 0, 'publisher', 'publisher one', False),
            (db.refresh,),
            ('title', 0),
            ('rating', 0),
            ('#tags', 0), ('#tags', 1), ('#tags', 2),
            ('authors', 0), ('authors', 1), ('authors', 2),
            ('publisher', 0), ('publisher', 1), ('publisher', 2),
            ('delete_tag', 'T1'), ('delete_tag', 'T2'), ('delete_tag', 'Tag one'), ('delete_tag', 'News'),
            (db.clean,), (db.refresh,),
            ('@all_tags',),
            ('#tags', 0), ('#tags', 1), ('#tags', 2),
        ))
        db.close()

        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)
        run_funcs(self, db, ndb, (
            ('remove_all_tags', (1, 2, 3)),
            (db.clean,),
            ('@all_tags',),
            ('@tags', 0), ('@tags', 1), ('@tags', 2),
        ))
        db.close()

        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)
        a = {v:k for k, v in iteritems(ndb.new_api.get_id_map('authors'))}['Author One']
        t = {v:k for k, v in iteritems(ndb.new_api.get_id_map('tags'))}['Tag One']
        s = {v:k for k, v in iteritems(ndb.new_api.get_id_map('series'))}['A Series One']
        p = {v:k for k, v in iteritems(ndb.new_api.get_id_map('publisher'))}['Publisher One']
        run_funcs(self, db, ndb, (
            ('rename_author', a, 'Author Two'),
            ('rename_tag', t, 'News'),
            ('rename_series', s, 'ss'),
            ('rename_publisher', p, 'publisher one'),
            (db.clean,),
            (db.refresh,),
            ('@all_tags',),
            ('tags', 0), ('tags', 1), ('tags', 2),
            ('series', 0), ('series', 1), ('series', 2),
            ('publisher', 0), ('publisher', 1), ('publisher', 2),
            ('series_index', 0), ('series_index', 1), ('series_index', 2),
            ('authors', 0), ('authors', 1), ('authors', 2),
            ('author_sort', 0), ('author_sort', 1), ('author_sort', 2),
        ))
        db.close()

    # }}}

    def test_legacy_custom(self):  # {{{
        'Test the legacy API for custom columns'
        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)
        # Test getting
        run_funcs(self, db, ndb, (
            ('all_custom', 'series'), ('all_custom', 'tags'), ('all_custom', 'rating'), ('all_custom', 'authors'), ('all_custom', None, 7),
            ('get_next_cc_series_num_for', 'My Series One', 'series'), ('get_next_cc_series_num_for', 'My Series Two', 'series'),
            ('is_item_used_in_multiple', 'My Tag One', 'tags'),
            ('is_item_used_in_multiple', 'My Series One', 'series'),
            ('$get_custom_items_with_ids', 'series'), ('$get_custom_items_with_ids', 'tags'), ('$get_custom_items_with_ids', 'float'),
            ('$get_custom_items_with_ids', 'rating'), ('$get_custom_items_with_ids', 'authors'), ('$get_custom_items_with_ids', None, 7),
        ))
        for label in ('tags', 'series', 'authors', 'comments', 'rating', 'date', 'yesno', 'isbn', 'enum', 'formats', 'float', 'comp_tags'):
            for func in ('get_custom', 'get_custom_extra', 'get_custom_and_extra'):
                run_funcs(self, db, ndb, [(func, idx, label) for idx in range(3)])

        # Test renaming/deleting
        t = {v:k for k, v in iteritems(ndb.new_api.get_id_map('#tags'))}['My Tag One']
        t2 = {v:k for k, v in iteritems(ndb.new_api.get_id_map('#tags'))}['My Tag Two']
        a = {v:k for k, v in iteritems(ndb.new_api.get_id_map('#authors'))}['My Author Two']
        a2 = {v:k for k, v in iteritems(ndb.new_api.get_id_map('#authors'))}['Custom One']
        s = {v:k for k, v in iteritems(ndb.new_api.get_id_map('#series'))}['My Series One']
        run_funcs(self, db, ndb, (
            ('delete_custom_item_using_id', t, 'tags'),
            ('delete_custom_item_using_id', a, 'authors'),
            ('rename_custom_item', t2, 't2', 'tags'),
            ('rename_custom_item', a2, 'custom one', 'authors'),
            ('rename_custom_item', s, 'My Series Two', 'series'),
            ('delete_item_from_multiple', 'custom two', 'authors'),
            (db.clean,),
            (db.refresh,),
            ('all_custom', 'series'), ('all_custom', 'tags'), ('all_custom', 'authors'),
        ))
        for label in ('tags', 'authors', 'series'):
            run_funcs(self, db, ndb, [('get_custom_and_extra', idx, label) for idx in range(3)])
        db.close()

        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)
        # Test setting
        run_funcs(self, db, ndb, (
            ('-set_custom', 1, 't1 & t2', 'authors'),
            ('-set_custom', 1, 't3 & t4', 'authors', None, True),
            ('-set_custom', 3, 'test one & test Two', 'authors'),
            ('-set_custom', 1, 'ijfkghkjdf', 'enum'),
            ('-set_custom', 3, 'One', 'enum'),
            ('-set_custom', 3, 'xxx', 'formats'),
            ('-set_custom', 1, 'my tag two', 'tags', None, False, False, None, True, True),
            (db.clean,), (db.refresh,),
            ('all_custom', 'series'), ('all_custom', 'tags'), ('all_custom', 'authors'),
        ))
        for label in ('tags', 'series', 'authors', 'comments', 'rating', 'date', 'yesno', 'isbn', 'enum', 'formats', 'float', 'comp_tags'):
            for func in ('get_custom', 'get_custom_extra', 'get_custom_and_extra'):
                run_funcs(self, db, ndb, [(func, idx, label) for idx in range(3)])
        db.close()

        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)
        # Test setting bulk
        run_funcs(self, db, ndb, (
            ('set_custom_bulk', (1,2,3), 't1 & t2', 'authors'),
            ('set_custom_bulk', (1,2,3), 'a series', 'series', None, False, False, (9, 10, 11)),
            ('set_custom_bulk', (1,2,3), 't1', 'tags', None, True),
            (db.clean,), (db.refresh,),
            ('all_custom', 'series'), ('all_custom', 'tags'), ('all_custom', 'authors'),
        ))
        for label in ('tags', 'series', 'authors', 'comments', 'rating', 'date', 'yesno', 'isbn', 'enum', 'formats', 'float', 'comp_tags'):
            for func in ('get_custom', 'get_custom_extra', 'get_custom_and_extra'):
                run_funcs(self, db, ndb, [(func, idx, label) for idx in range(3)])
        db.close()

        ndb = self.init_legacy(self.cloned_library)
        db = self.init_old(self.cloned_library)
        # Test bulk multiple
        run_funcs(self, db, ndb, (
            ('set_custom_bulk_multiple', (1,2,3), ['t1'], ['My Tag One'], 'tags'),
            (db.clean,), (db.refresh,),
            ('all_custom', 'tags'),
            ('get_custom', 0, 'tags'), ('get_custom', 1, 'tags'), ('get_custom', 2, 'tags'),
        ))
        db.close()

        o = self.cloned_library
        n = self.cloned_library
        ndb, db = self.init_legacy(n), self.init_old(o)
        ndb.create_custom_column('created', 'Created', 'text', True, True, {'moose':'cat'})
        db.create_custom_column('created', 'Created', 'text', True, True, {'moose':'cat'})
        db.close()
        ndb, db = self.init_legacy(n), self.init_old(o)
        self.assertEqual(db.custom_column_label_map['created'], ndb.backend.custom_field_metadata('created'))
        num = db.custom_column_label_map['created']['num']
        ndb.set_custom_column_metadata(num, is_editable=False, name='Crikey', display={})
        db.set_custom_column_metadata(num, is_editable=False, name='Crikey', display={})
        db.close()
        ndb, db = self.init_legacy(n), self.init_old(o)
        self.assertEqual(db.custom_column_label_map['created'], ndb.backend.custom_field_metadata('created'))
        db.close()
        ndb = self.init_legacy(n)
        ndb.delete_custom_column('created')
        ndb = self.init_legacy(n)
        self.assertRaises(KeyError, ndb.custom_field_name, num=num)

        # Test setting custom series
        ndb = self.init_legacy(self.cloned_library)
        ndb.set_custom(1, 'TS [9]', label='series')
        self.assertEqual(ndb.new_api.field_for('#series', 1), 'TS')
        self.assertEqual(ndb.new_api.field_for('#series_index', 1), 9)
    # }}}

    def test_legacy_saved_search(self):  # {{{
        ' Test legacy saved search API '
        db, ndb = self.init_old(), self.init_legacy()
        run_funcs(self, db, ndb, (
            ('saved_search_set_all', {'one':'a', 'two':'b'}),
            ('saved_search_names',),
            ('saved_search_lookup', 'one'),
            ('saved_search_lookup', 'two'),
            ('saved_search_lookup', 'xxx'),
            ('saved_search_rename', 'one', '1'),
            ('saved_search_names',),
            ('saved_search_lookup', '1'),
            ('saved_search_delete', '1'),
            ('saved_search_names',),
            ('saved_search_add', 'n', 'm'),
            ('saved_search_names',),
            ('saved_search_lookup', 'n'),
        ))
        db.close()
    # }}}
