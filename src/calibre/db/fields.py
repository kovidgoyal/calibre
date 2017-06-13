#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
# from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from threading import Lock
from collections import defaultdict, Counter
from functools import partial

from calibre.db.tables import ONE_ONE, MANY_ONE, MANY_MANY, null
from calibre.db.write import Writer
from calibre.db.utils import force_to_bool, atof
from calibre.ebooks.metadata import title_sort, author_to_author_sort, rating_to_stars
from calibre.utils.config_base import tweaks
from calibre.utils.icu import sort_key
from calibre.utils.date import UNDEFINED_DATE, clean_date_for_sort, parse_date
from calibre.utils.localization import calibre_langcode_to_name


def bool_sort_key(bools_are_tristate):
    return (lambda x:{True: 1, False: 2, None: 3}.get(x, 3)) if bools_are_tristate else lambda x:{True: 1, False: 2, None: 2}.get(x, 2)


IDENTITY = lambda x: x


class InvalidLinkTable(Exception):

    def __init__(self, name):
        Exception.__init__(self, name)
        self.field_name = name


class Field(object):

    is_many = False
    is_many_many = False
    is_composite = False

    def __init__(self, name, table, bools_are_tristate, get_template_functions):
        self.name, self.table = name, table
        dt = self.metadata['datatype']
        self.has_text_data = dt in {'text', 'comments', 'series', 'enumeration'}
        self.table_type = self.table.table_type
        self._sort_key = (sort_key if dt in ('text', 'series', 'enumeration') else IDENTITY)

        # This will be compared to the output of sort_key() which is a
        # bytestring, therefore it is safer to have it be a bytestring.
        # Coercing an empty bytestring to unicode will never fail, but the
        # output of sort_key cannot be coerced to unicode
        self._default_sort_key = b''

        if dt in {'int', 'float', 'rating'}:
            self._default_sort_key = 0
        elif dt == 'bool':
            self._default_sort_key = None
            self._sort_key = bool_sort_key(bools_are_tristate)
        elif dt == 'datetime':
            self._default_sort_key = UNDEFINED_DATE
            if tweaks['sort_dates_using_visible_fields']:
                fmt = None
                if name in {'timestamp', 'pubdate', 'last_modified'}:
                    fmt = tweaks['gui_%s_display_format' % name]
                elif self.metadata['is_custom']:
                    fmt = self.metadata.get('display', {}).get('date_format', None)
                self._sort_key = partial(clean_date_for_sort, fmt=fmt)

        if self.name == 'languages':
            self._sort_key = lambda x:sort_key(calibre_langcode_to_name(x))
        self.is_multiple = (bool(self.metadata['is_multiple']) or self.name ==
                'formats')
        self.sort_sort_key = True
        if self.is_multiple and '&' in self.metadata['is_multiple']['list_to_ui']:
            self._sort_key = lambda x: sort_key(author_to_author_sort(x))
            self.sort_sort_key = False
        self.default_value = {} if name == 'identifiers' else () if self.is_multiple else None
        self.category_formatter = type(u'')
        if dt == 'rating':
            if self.metadata['display'].get('allow_half_stars', False):
                self.category_formatter = lambda x: rating_to_stars(x, True)
            else:
                self.category_formatter = rating_to_stars
        elif name == 'languages':
            self.category_formatter = calibre_langcode_to_name
        self.writer = Writer(self)
        self.series_field = None
        self.get_template_functions = get_template_functions

    @property
    def metadata(self):
        return self.table.metadata

    def for_book(self, book_id, default_value=None):
        '''
        Return the value of this field for the book identified by book_id.
        When no value is found, returns ``default_value``.
        '''
        raise NotImplementedError()

    def ids_for_book(self, book_id):
        '''
        Return a tuple of items ids for items associated with the book
        identified by book_ids. Returns an empty tuple if no such items are
        found.
        '''
        raise NotImplementedError()

    def books_for(self, item_id):
        '''
        Return the ids of all books associated with the item identified by
        item_id as a set. An empty set is returned if no books are found.
        '''
        raise NotImplementedError()

    def __iter__(self):
        '''
        Iterate over the ids for all values in this field.

        WARNING: Some fields such as composite fields and virtual
        fields like ondevice do not have ids for their values, in such
        cases this is an empty iterator.
        '''
        return iter(())

    def sort_keys_for_books(self, get_metadata, lang_map):
        '''
        Return a function that maps book_id to sort_key. The sort key is suitable for
        use in sorting the list of all books by this field, via the python cmp
        method.
        '''
        raise NotImplementedError()

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        '''
        Return a generator that yields items of the form (value, set of books
        ids that have this value). Here, value is a searchable value. Returned
        books_ids are restricted to the set of ids in candidates.
        '''
        raise NotImplementedError()

    def get_categories(self, tag_class, book_rating_map, lang_map, book_ids=None):
        ans = []
        if not self.is_many:
            return ans

        id_map = self.table.id_map
        special_sort = hasattr(self, 'category_sort_value')
        for item_id, item_book_ids in self.table.col_book_map.iteritems():
            if book_ids is not None:
                item_book_ids = item_book_ids.intersection(book_ids)
            if item_book_ids:
                ratings = tuple(r for r in (book_rating_map.get(book_id, 0) for
                                            book_id in item_book_ids) if r > 0)
                avg = sum(ratings)/len(ratings) if ratings else 0
                try:
                    name = self.category_formatter(id_map[item_id])
                except KeyError:
                    # db has entries in the link table without entries in the
                    # id table, for example, see
                    # https://bugs.launchpad.net/bugs/1218783
                    raise InvalidLinkTable(self.name)
                sval = (self.category_sort_value(item_id, item_book_ids, lang_map)
                    if special_sort else name)
                c = tag_class(name, id=item_id, sort=sval, avg=avg,
                              id_set=item_book_ids, count=len(item_book_ids))
                ans.append(c)
        return ans


class OneToOneField(Field):

    def for_book(self, book_id, default_value=None):
        return self.table.book_col_map.get(book_id, default_value)

    def ids_for_book(self, book_id):
        return (book_id,)

    def books_for(self, item_id):
        return {item_id}

    def __iter__(self):
        return self.table.book_col_map.iterkeys()

    def sort_keys_for_books(self, get_metadata, lang_map):
        bcmg = self.table.book_col_map.get
        dk = self._default_sort_key
        sk = self._sort_key
        if sk is IDENTITY:
            return lambda book_id:bcmg(book_id, dk)
        return lambda book_id:sk(bcmg(book_id, dk))

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        cbm = self.table.book_col_map
        for book_id in candidates:
            yield cbm.get(book_id, default_value), {book_id}


class CompositeField(OneToOneField):

    is_composite = True
    SIZE_SUFFIX_MAP = {suffix:i for i, suffix in enumerate(('', 'K', 'M', 'G', 'T', 'P', 'E'))}

    def __init__(self, name, table, bools_are_tristate, get_template_functions):
        OneToOneField.__init__(self, name, table, bools_are_tristate, get_template_functions)

        self._render_cache = {}
        self._lock = Lock()
        m = self.metadata
        self._composite_name = '#' + m['label']
        try:
            self.splitter = m['is_multiple'].get('cache_to_list', None)
        except AttributeError:
            self.splitter = None
        composite_sort = m.get('display', {}).get('composite_sort', None)
        if composite_sort == 'number':
            self._default_sort_key = 0
            self._sort_key = self.number_sort_key
        elif composite_sort == 'date':
            self._default_sort_key = UNDEFINED_DATE
            self._filter_date = lambda x: x
            if tweaks['sort_dates_using_visible_fields']:
                fmt = m.get('display', {}).get('date_format', None)
                self._filter_date = partial(clean_date_for_sort, fmt=fmt)
            self._sort_key = self.date_sort_key
        elif composite_sort == 'bool':
            self._default_sort_key = None
            self._bool_sort_key = bool_sort_key(bools_are_tristate)
            self._sort_key = self.bool_sort_key
        elif self.splitter is not None:
            self._default_sort_key = ()
            self._sort_key = self.multiple_sort_key
        else:
            self._sort_key = sort_key

    def multiple_sort_key(self, val):
        val = (sort_key(x.strip()) for x in (val or '').split(self.splitter))
        return tuple(sorted(val))

    def number_sort_key(self, val):
        try:
            p = 1
            if val and val.endswith('B'):
                p = 1 << (10 * self.SIZE_SUFFIX_MAP.get(val[-2:-1], 0))
                val = val[:(-2 if p > 1 else -1)].strip()
            val = atof(val) * p
        except (TypeError, AttributeError, ValueError, KeyError):
            val = 0.0
        return val

    def date_sort_key(self, val):
        try:
            val = self._filter_date(parse_date(val))
        except (TypeError, ValueError, AttributeError, KeyError):
            val = UNDEFINED_DATE
        return val

    def bool_sort_key(self, val):
        return self._bool_sort_key(force_to_bool(val))

    def __render_composite(self, book_id, mi, formatter, template_cache):
        ' INTERNAL USE ONLY. DO NOT USE THIS OUTSIDE THIS CLASS! '
        ans = formatter.safe_format(
            self.metadata['display']['composite_template'], mi, _('TEMPLATE ERROR'),
            mi, column_name=self._composite_name, template_cache=template_cache,
            template_functions=self.get_template_functions()).strip()
        with self._lock:
            self._render_cache[book_id] = ans
        return ans

    def _render_composite_with_cache(self, book_id, mi, formatter, template_cache):
        ''' INTERNAL USE ONLY. DO NOT USE METHOD DIRECTLY. INSTEAD USE
         db.composite_for() OR mi.get(). Those methods make sure there is no
         risk of infinite recursion when evaluating templates that refer to
         themselves. '''
        with self._lock:
            ans = self._render_cache.get(book_id, None)
        if ans is None:
            return self.__render_composite(book_id, mi, formatter, template_cache)
        return ans

    def clear_caches(self, book_ids=None):
        with self._lock:
            if book_ids is None:
                self._render_cache.clear()
            else:
                for book_id in book_ids:
                    self._render_cache.pop(book_id, None)

    def get_value_with_cache(self, book_id, get_metadata):
        with self._lock:
            ans = self._render_cache.get(book_id, None)
        if ans is None:
            mi = get_metadata(book_id)
            return self.__render_composite(book_id, mi, mi.formatter, mi.template_cache)
        return ans

    def sort_keys_for_books(self, get_metadata, lang_map):
        gv = self.get_value_with_cache
        sk = self._sort_key
        if sk is IDENTITY:
            return lambda book_id:gv(book_id, get_metadata)
        return lambda book_id:sk(gv(book_id, get_metadata))

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        val_map = defaultdict(set)
        splitter = self.splitter
        for book_id in candidates:
            vals = self.get_value_with_cache(book_id, get_metadata)
            vals = (vv.strip() for vv in vals.split(splitter)) if splitter else (vals,)
            for v in vals:
                if v:
                    val_map[v].add(book_id)
        for val, book_ids in val_map.iteritems():
            yield val, book_ids

    def get_composite_categories(self, tag_class, book_rating_map, book_ids,
                                 is_multiple, get_metadata):
        ans = []
        id_map = defaultdict(set)
        for book_id in book_ids:
            val = self.get_value_with_cache(book_id, get_metadata)
            vals = [x.strip() for x in val.split(is_multiple)] if is_multiple else [val]
            for val in vals:
                if val:
                    id_map[val].add(book_id)
        for item_id, item_book_ids in id_map.iteritems():
            ratings = tuple(r for r in (book_rating_map.get(book_id, 0) for
                                        book_id in item_book_ids) if r > 0)
            avg = sum(ratings)/len(ratings) if ratings else 0
            c = tag_class(item_id, id=item_id, sort=item_id, avg=avg,
                            id_set=item_book_ids, count=len(item_book_ids))
            ans.append(c)
        return ans

    def get_books_for_val(self, value, get_metadata, book_ids):
        is_multiple = self.table.metadata['is_multiple'].get('cache_to_list', None)
        ans = set()
        for book_id in book_ids:
            val = self.get_value_with_cache(book_id, get_metadata)
            vals = {x.strip() for x in val.split(is_multiple)} if is_multiple else [val]
            if value in vals:
                ans.add(book_id)
        return ans


class OnDeviceField(OneToOneField):

    def __init__(self, name, table, bools_are_tristate, get_template_functions):
        self.name = name
        self.book_on_device_func = None
        self.is_multiple = False
        self.cache = {}
        self._lock = Lock()
        self._metadata = {
            'table':None, 'column':None, 'datatype':'text', 'is_multiple':{},
            'kind':'field', 'name':_('On Device'), 'search_terms':['ondevice'],
            'is_custom':False, 'is_category':False, 'is_csp': False, 'display':{}}

    @property
    def metadata(self):
        return self._metadata

    def clear_caches(self, book_ids=None):
        with self._lock:
            if book_ids is None:
                self.cache.clear()
            else:
                for book_id in book_ids:
                    self.cache.pop(book_id, None)

    def book_on_device(self, book_id):
        with self._lock:
            ans = self.cache.get(book_id, null)
        if ans is null and callable(self.book_on_device_func):
            ans = self.book_on_device_func(book_id)
            with self._lock:
                self.cache[book_id] = ans
        return None if ans is null else ans

    def set_book_on_device_func(self, func):
        self.book_on_device_func = func

    def for_book(self, book_id, default_value=None):
        loc = []
        count = 0
        on = self.book_on_device(book_id)
        if on is not None:
            m, a, b, count = on[:4]
            if m is not None:
                loc.append(_('Main'))
            if a is not None:
                loc.append(_('Card A'))
            if b is not None:
                loc.append(_('Card B'))
        return ', '.join(loc) + ((' (%s books)'%count) if count > 1 else '')

    def __iter__(self):
        return iter(())

    def sort_keys_for_books(self, get_metadata, lang_map):
        return self.for_book

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        val_map = defaultdict(set)
        for book_id in candidates:
            val_map[self.for_book(book_id, default_value=default_value)].add(book_id)
        for val, book_ids in val_map.iteritems():
            yield val, book_ids


class LazySortMap(object):

    __slots__ = ('default_sort_key', 'sort_key_func', 'id_map', 'cache')

    def __init__(self, default_sort_key, sort_key_func, id_map):
        self.default_sort_key = default_sort_key
        self.sort_key_func = sort_key_func
        self.id_map = id_map
        self.cache = {None:default_sort_key}

    def __call__(self, item_id):
        try:
            return self.cache[item_id]
        except KeyError:
            try:
                val = self.cache[item_id] = self.sort_key_func(self.id_map[item_id])
            except KeyError:
                val = self.cache[item_id] = self.default_sort_key
            return val


class ManyToOneField(Field):

    is_many = True

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, None)
        if ids is not None:
            ans = self.table.id_map[ids]
        else:
            ans = default_value
        return ans

    def ids_for_book(self, book_id):
        id_ = self.table.book_col_map.get(book_id, None)
        if id_ is None:
            return ()
        return (id_,)

    def books_for(self, item_id):
        return self.table.col_book_map.get(item_id, set())

    def __iter__(self):
        return self.table.id_map.iterkeys()

    def sort_keys_for_books(self, get_metadata, lang_map):
        sk_map = LazySortMap(self._default_sort_key, self._sort_key, self.table.id_map)
        bcmg = self.table.book_col_map.get
        return lambda book_id:sk_map(bcmg(book_id, None))

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        cbm = self.table.col_book_map
        empty = set()
        for item_id, val in self.table.id_map.iteritems():
            book_ids = cbm.get(item_id, empty).intersection(candidates)
            if book_ids:
                yield val, book_ids

    @property
    def book_value_map(self):
        try:
            return {book_id:self.table.id_map[item_id] for book_id, item_id in
                self.table.book_col_map.iteritems()}
        except KeyError:
            raise InvalidLinkTable(self.name)


class ManyToManyField(Field):

    is_many = True
    is_many_many = True

    def __init__(self, *args, **kwargs):
        Field.__init__(self, *args, **kwargs)

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, ())
        if ids:
            ans = (self.table.id_map[i] for i in ids)
            if self.table.sort_alpha:
                ans = tuple(sorted(ans, key=sort_key))
            else:
                ans = tuple(ans)
        else:
            ans = default_value
        return ans

    def ids_for_book(self, book_id):
        return self.table.book_col_map.get(book_id, ())

    def books_for(self, item_id):
        return self.table.col_book_map.get(item_id, set())

    def __iter__(self):
        return self.table.id_map.iterkeys()

    def sort_keys_for_books(self, get_metadata, lang_map):
        sk_map = LazySortMap(self._default_sort_key, self._sort_key, self.table.id_map)
        bcmg = self.table.book_col_map.get
        dsk = (self._default_sort_key,)
        if self.sort_sort_key:
            def sk(book_id):
                return tuple(sorted(sk_map(x) for x in bcmg(book_id, ()))) or dsk
        else:
            def sk(book_id):
                return tuple(sk_map(x) for x in bcmg(book_id, ())) or dsk
        return sk

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        cbm = self.table.col_book_map
        empty = set()
        for item_id, val in self.table.id_map.iteritems():
            book_ids = cbm.get(item_id, empty).intersection(candidates)
            if book_ids:
                yield val, book_ids

    def iter_counts(self, candidates):
        val_map = defaultdict(set)
        cbm = self.table.book_col_map
        for book_id in candidates:
            val_map[len(cbm.get(book_id, ()))].add(book_id)
        for count, book_ids in val_map.iteritems():
            yield count, book_ids

    @property
    def book_value_map(self):
        try:
            return {book_id:tuple(self.table.id_map[item_id] for item_id in item_ids)
                for book_id, item_ids in self.table.book_col_map.iteritems()}
        except KeyError:
            raise InvalidLinkTable(self.name)


class IdentifiersField(ManyToManyField):

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, ())
        if not ids:
            try:
                ids = default_value.copy()  # in case default_value is a mutable dict
            except AttributeError:
                ids = default_value
        return ids

    def sort_keys_for_books(self, get_metadata, lang_map):
        'Sort by identifier keys'
        bcmg = self.table.book_col_map.get
        dv = {self._default_sort_key:None}
        return lambda book_id: tuple(sorted(bcmg(book_id, dv).iterkeys()))

    def iter_searchable_values(self, get_metadata, candidates, default_value=()):
        bcm = self.table.book_col_map
        for book_id in candidates:
            val = bcm.get(book_id, default_value)
            if val:
                yield val, {book_id}

    def get_categories(self, tag_class, book_rating_map, lang_map, book_ids=None):
        ans = []

        for id_key, item_book_ids in self.table.col_book_map.iteritems():
            if book_ids is not None:
                item_book_ids = item_book_ids.intersection(book_ids)
            if item_book_ids:
                c = tag_class(id_key, id_set=item_book_ids, count=len(item_book_ids))
                ans.append(c)
        return ans


class AuthorsField(ManyToManyField):

    def author_data(self, author_id):
        return {
            'name': self.table.id_map[author_id],
            'sort': self.table.asort_map[author_id],
            'link': self.table.alink_map[author_id],
        }

    def category_sort_value(self, item_id, book_ids, lang_map):
        return self.table.asort_map[item_id]

    def db_author_sort_for_book(self, book_id):
        return self.author_sort_field.for_book(book_id)

    def author_sort_for_book(self, book_id):
        return ' & '.join(self.table.asort_map[k] for k in
                          self.table.book_col_map[book_id])


class FormatsField(ManyToManyField):

    def for_book(self, book_id, default_value=None):
        return self.table.book_col_map.get(book_id, default_value)

    def format_fname(self, book_id, fmt):
        return self.table.fname_map[book_id][fmt.upper()]

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        val_map = defaultdict(set)
        cbm = self.table.book_col_map
        for book_id in candidates:
            vals = cbm.get(book_id, ())
            for val in vals:
                val_map[val].add(book_id)

        for val, book_ids in val_map.iteritems():
            yield val, book_ids

    def get_categories(self, tag_class, book_rating_map, lang_map, book_ids=None):
        ans = []

        for fmt, item_book_ids in self.table.col_book_map.iteritems():
            if book_ids is not None:
                item_book_ids = item_book_ids.intersection(book_ids)
            if item_book_ids:
                c = tag_class(fmt, id_set=item_book_ids, count=len(item_book_ids))
                ans.append(c)
        return ans


class LazySeriesSortMap(object):

    __slots__ = ('default_sort_key', 'sort_key_func', 'id_map', 'cache')

    def __init__(self, default_sort_key, sort_key_func, id_map):
        self.default_sort_key = default_sort_key
        self.sort_key_func = sort_key_func
        self.id_map = id_map
        self.cache = {}

    def __call__(self, item_id, lang):
        try:
            return self.cache[(item_id, lang)]
        except KeyError:
            try:
                val = self.cache[(item_id, lang)] = self.sort_key_func(self.id_map[item_id], lang)
            except KeyError:
                val = self.cache[(item_id, lang)] = self.default_sort_key
            return val


class SeriesField(ManyToOneField):

    def sort_keys_for_books(self, get_metadata, lang_map):
        sso = tweaks['title_series_sorting']
        ssk = self._sort_key
        ts = title_sort

        def sk(val, lang):
            return ssk(ts(val, order=sso, lang=lang))
        sk_map = LazySeriesSortMap(self._default_sort_key, sk, self.table.id_map)
        bcmg = self.table.book_col_map.get
        lang_map = {k:v[0] if v else None for k, v in lang_map.iteritems()}

        def key(book_id):
            lang = lang_map.get(book_id, None)
            return sk_map(bcmg(book_id, None), lang)

        return key

    def category_sort_value(self, item_id, book_ids, lang_map):
        lang = None
        tss = tweaks['title_series_sorting']
        if tss != 'strictly_alphabetic':
            c = Counter()

            for book_id in book_ids:
                l = lang_map.get(book_id, None)
                if l:
                    c[l[0]] += 1

            if c:
                lang = c.most_common(1)[0][0]
        val = self.table.id_map[item_id]
        return title_sort(val, order=tss, lang=lang)

    def iter_searchable_values_for_sort(self, candidates, lang_map, default_value=None):
        cbm = self.table.col_book_map
        sso = tweaks['title_series_sorting']
        ts = title_sort
        empty = set()
        lang_map = {k:v[0] if v else None for k, v in lang_map.iteritems()}
        for item_id, val in self.table.id_map.iteritems():
            book_ids = cbm.get(item_id, empty).intersection(candidates)
            if book_ids:
                lang_counts = Counter()
                for book_id in book_ids:
                    lang = lang_map.get(book_id)
                    if lang:
                        lang_counts[lang[0]] += 1
                lang = lang_counts.most_common(1)[0][0] if lang_counts else None
                yield ts(val, order=sso, lang=lang), book_ids


class TagsField(ManyToManyField):

    def get_news_category(self, tag_class, book_ids=None):
        news_id = None
        ans = []
        for item_id, val in self.table.id_map.iteritems():
            if val == _('News'):
                news_id = item_id
                break
        if news_id is None:
            return ans

        news_books = self.table.col_book_map[news_id]
        if book_ids is not None:
            news_books = news_books.intersection(book_ids)
        if not news_books:
            return ans
        for item_id, item_book_ids in self.table.col_book_map.iteritems():
            item_book_ids = item_book_ids.intersection(news_books)
            if item_book_ids:
                name = self.category_formatter(self.table.id_map[item_id])
                if name == _('News'):
                    continue
                c = tag_class(name, id=item_id, sort=name,
                              id_set=item_book_ids, count=len(item_book_ids))
                ans.append(c)
        return ans


def create_field(name, table, bools_are_tristate, get_template_functions):
    cls = {
            ONE_ONE: OneToOneField,
            MANY_ONE: ManyToOneField,
            MANY_MANY: ManyToManyField,
        }[table.table_type]
    if name == 'authors':
        cls = AuthorsField
    elif name == 'ondevice':
        cls = OnDeviceField
    elif name == 'formats':
        cls = FormatsField
    elif name == 'identifiers':
        cls = IdentifiersField
    elif name == 'tags':
        cls = TagsField
    elif table.metadata['datatype'] == 'composite':
        cls = CompositeField
    elif table.metadata['datatype'] == 'series':
        cls = SeriesField
    return cls(name, table, bools_are_tristate, get_template_functions)
