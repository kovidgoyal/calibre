#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import inspect
from io import BytesIO
from repr import repr
from functools import partial
from tempfile import NamedTemporaryFile

from calibre.db.tests.base import BaseTest

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
            self.func_name, repr(self.args), repr(self.kwargs)))
        self.retval = newres
        return newres

def compare_argspecs(old, new, attr):
    num = len(old.defaults or ())

    ok = len(old.args) == len(new.args) and old.defaults == new.defaults and (num == 0 or old.args[-num:] == new.args[-num:])
    if not ok:
        raise AssertionError('The argspec for %s does not match. %r != %r' % (attr, old, new))

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

    def test_legacy_direct(self):  # {{{
        'Test methods that are directly equivalent in the old and new interface'
        from calibre.ebooks.metadata.book.base import Metadata
        ndb = self.init_legacy()
        db = self.init_old()
        for meth, args in {
            'get_next_series_num_for': [('A Series One',)],
            'author_sort_from_authors': [(['Author One', 'Author Two', 'Unknown'],)],
            'has_book':[(Metadata('title one'),), (Metadata('xxxx1111'),)],
            'all_author_names':[()],
            'all_tag_names':[()],
            'all_series_names':[()],
            'all_publisher_names':[()],
            '!all_authors':[()],
            '!all_tags2':[()],
            '@all_tags':[()],
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
        }.iteritems():
            for a in args:
                fmt = lambda x: x
                if meth[0] in {'!', '@'}:
                    fmt = {'!':dict, '@':frozenset}[meth[0]]
                    meth = meth[1:]
                elif meth == 'get_authors_with_ids':
                    fmt = lambda val:{x[0]:tuple(x[1:]) for x in val}
                self.assertEqual(fmt(getattr(db, meth)(*a)), fmt(getattr(ndb, meth)(*a)),
                                 'The method: %s() returned different results for argument %s' % (meth, a))
        db.close()
        # }}}

    def test_legacy_adding_books(self):  # {{{
        'Test various adding books methods'
        from calibre.ebooks.metadata.book.base import Metadata
        legacy, old = self.init_legacy(self.cloned_library), self.init_old(self.cloned_library)
        mi = Metadata('Added Book0', authors=('Added Author',))
        with NamedTemporaryFile(suffix='.aff') as f:
            f.write(b'xxx')
            f.flush()
            T = partial(ET, 'add_books', ([f.name], ['AFF'], [mi]), old=old, legacy=legacy)
            T()(self)
            book_id = T(kwargs={'return_ids':True})(self)[1][0]
            self.assertEqual(legacy.new_api.formats(book_id), ('AFF',))
            T(kwargs={'add_duplicates':False})(self)
            mi.title = 'Added Book1'
            mi.uuid = 'uuu'
            T = partial(ET, 'import_book', (mi,[f.name]), old=old, legacy=legacy)
            book_id = T()(self)
            self.assertNotEqual(legacy.uuid(book_id, index_is_id=True), old.uuid(book_id, index_is_id=True))
            book_id = T(kwargs={'preserve_uuid':True})(self)
            self.assertEqual(legacy.uuid(book_id, index_is_id=True), old.uuid(book_id, index_is_id=True))
            self.assertEqual(legacy.new_api.formats(book_id), ('AFF',))

            T = partial(ET, 'add_format', old=old, legacy=legacy)
            T((0, 'AFF', BytesIO(b'fffff')))(self)
            T((0, 'AFF', BytesIO(b'fffff')))(self)
            T((0, 'AFF', BytesIO(b'fffff')), {'replace':True})(self)
        with NamedTemporaryFile(suffix='.opf') as f:
            f.write(b'zzzz')
            f.flush()
            T = partial(ET, 'import_book', (mi,[f.name]), old=old, legacy=legacy)
            book_id = T()(self)
            self.assertFalse(legacy.new_api.formats(book_id))

        mi.title = 'Added Book2'
        T = partial(ET, 'create_book_entry', (mi,), old=old, legacy=legacy)
        T()
        T({'add_duplicates':False})
        T({'force_id':1000})

        with NamedTemporaryFile(suffix='.txt') as f:
            f.write(b'tttttt')
            f.seek(0)
            bid = legacy.add_catalog(f.name, 'My Catalog')
            self.assertEqual(old.add_catalog(f.name, 'My Catalog'), bid)
            cache = legacy.new_api
            self.assertEqual(cache.formats(bid), ('TXT',))
            self.assertEqual(cache.field_for('title', bid), 'My Catalog')
            self.assertEqual(cache.field_for('authors', bid), ('calibre',))
            self.assertEqual(cache.field_for('tags', bid), (_('Catalog'),))
            self.assertTrue(bid < legacy.add_catalog(f.name, 'Something else'))
            self.assertEqual(legacy.add_catalog(f.name, 'My Catalog'), bid)
            self.assertEqual(old.add_catalog(f.name, 'My Catalog'), bid)

            bid = legacy.add_news(f.name, {'title':'Events', 'add_title_tag':True, 'custom_tags':('one', 'two')})
            self.assertEqual(cache.formats(bid), ('TXT',))
            self.assertEqual(cache.field_for('authors', bid), ('calibre',))
            self.assertEqual(cache.field_for('tags', bid), (_('News'), 'Events', 'one', 'two'))

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
        }
        SKIP_ARGSPEC = {
            '__init__', 'get_next_series_num_for', 'has_book', 'author_sort_from_authors',
        }

        missing = []

        try:
            total = 0
            for attr in dir(db):
                if attr in SKIP_ATTRS:
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
                    except TypeError:
                        pass
                    else:
                        compare_argspecs(argspec, nargspec, attr)
        finally:
            for db in (ndb, db):
                db.close()
                db.break_cycles()

        if missing:
            pc = len(missing)/total
            raise AssertionError('{0:.1%} of API ({2} attrs) are missing. For example: {1}'.format(pc, ', '.join(missing[:5]), len(missing)))

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
