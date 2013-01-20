#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
#from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from threading import Lock
from collections import defaultdict

from calibre.db.tables import ONE_ONE, MANY_ONE, MANY_MANY
from calibre.ebooks.metadata import title_sort
from calibre.utils.config_base import tweaks
from calibre.utils.icu import sort_key
from calibre.utils.date import UNDEFINED_DATE
from calibre.utils.localization import calibre_langcode_to_name

class Field(object):

    def __init__(self, name, table):
        self.name, self.table = name, table
        self.has_text_data = self.metadata['datatype'] in ('text', 'comments',
                'series', 'enumeration')
        self.table_type = self.table.table_type
        dt = self.metadata['datatype']
        self._sort_key = (sort_key if dt in ('text', 'series', 'enumeration') else lambda x: x)
        self._default_sort_key = ''
        if self.metadata['datatype'] in ('int', 'float', 'rating'):
            self._default_sort_key = 0
        elif self.metadata['datatype'] == 'bool':
            self._default_sort_key = None
        elif self.metadata['datatype'] == 'datetime':
            self._default_sort_key = UNDEFINED_DATE
        if self.name == 'languages':
            self._sort_key = lambda x:sort_key(calibre_langcode_to_name(x))
        self.is_multiple = (bool(self.metadata['is_multiple']) or self.name ==
                'formats')

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
        item_id as a tuple. An empty tuple is returned if no books are found.
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

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        '''
        Return a mapping of book_id -> sort_key. The sort key is suitable for
        use in sorting the list of all books by this field, via the python cmp
        method. all_book_ids is the list/set of book ids for which sort_keys
        should be generated.
        '''
        raise NotImplementedError()

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        '''
        Return a generator that yields items of the form (value, set of books
        ids that have this value). Here, value is a searchable value. For
        OneToOneField the set of books ids will contain only a single id, but for
        other fields it will generally have more than one id. Returned books_ids
        are restricted to the set of ids in candidates.
        '''
        raise NotImplementedError()

class OneToOneField(Field):

    def for_book(self, book_id, default_value=None):
        return self.table.book_col_map.get(book_id, default_value)

    def ids_for_book(self, book_id):
        return (book_id,)

    def books_for(self, item_id):
        return (item_id,)

    def __iter__(self):
        return self.table.book_col_map.iterkeys()

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        return {id_ : self._sort_key(self.table.book_col_map.get(id_,
            self._default_sort_key)) for id_ in all_book_ids}

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        cbm = self.table.book_col_map
        for book_id in candidates:
            yield cbm.get(book_id, default_value), {book_id}

class CompositeField(OneToOneField):

    def __init__(self, *args, **kwargs):
        OneToOneField.__init__(self, *args, **kwargs)

        self._render_cache = {}
        self._lock = Lock()

    def render_composite(self, book_id, mi):
        with self._lock:
            ans = self._render_cache.get(book_id, None)
        if ans is None:
            ans = mi.get('#'+self.metadata['label'])
            with self._lock:
                self._render_cache[book_id] = ans
        return ans

    def clear_cache(self):
        with self._lock:
            self._render_cache = {}

    def pop_cache(self, book_id):
        with self._lock:
            self._render_cache.pop(book_id, None)

    def get_value_with_cache(self, book_id, get_metadata):
        with self._lock:
            ans = self._render_cache.get(book_id, None)
        if ans is None:
            mi = get_metadata(book_id)
            ans = mi.get('#'+self.metadata['label'])
        return ans

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        return {id_ : sort_key(self.get_value_with_cache(id_, get_metadata)) for id_ in
                all_book_ids}

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        for book_id in candidates:
            yield self.get_value_with_cache(book_id, get_metadata), {book_id}

class OnDeviceField(OneToOneField):

    def __init__(self, name, table):
        self.name = name
        self.book_on_device_func = None
        self.is_multiple = False

    def book_on_device(self, book_id):
        if callable(self.book_on_device_func):
            return self.book_on_device_func(book_id)
        return None

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

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        return {id_ : self.for_book(id_) for id_ in
                all_book_ids}

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        for book_id in candidates:
            yield self.for_book(book_id, default_value=default_value), {book_id}

class ManyToOneField(Field):

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
        return self.table.col_book_map.get(item_id, ())

    def __iter__(self):
        return self.table.id_map.iterkeys()

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        ans = {id_ : self.table.book_col_map.get(id_, None)
                for id_ in all_book_ids}
        sk_map = {cid : (self._default_sort_key if cid is None else
                self._sort_key(self.table.id_map[cid]))
                for cid in ans.itervalues()}
        return {id_ : sk_map[cid] for id_, cid in ans.iteritems()}

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        cbm = self.table.col_book_map
        for item_id, val in self.table.id_map.iteritems():
            book_ids = set(cbm.get(item_id, ())).intersection(candidates)
            if book_ids:
                yield val, book_ids

class ManyToManyField(Field):

    def __init__(self, *args, **kwargs):
        Field.__init__(self, *args, **kwargs)
        self.alphabetical_sort = self.name != 'authors'

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, ())
        if ids:
            ans = tuple(self.table.id_map[i] for i in ids)
        else:
            ans = default_value
        return ans

    def ids_for_book(self, book_id):
        return self.table.book_col_map.get(book_id, ())

    def books_for(self, item_id):
        return self.table.col_book_map.get(item_id, ())

    def __iter__(self):
        return self.table.id_map.iterkeys()

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        ans = {id_ : self.table.book_col_map.get(id_, ())
                for id_ in all_book_ids}
        all_cids = set()
        for cids in ans.itervalues():
            all_cids = all_cids.union(set(cids))
        sk_map = {cid : self._sort_key(self.table.id_map[cid])
                for cid in all_cids}
        return {id_ : (tuple(sk_map[cid] for cid in cids) if cids else
                        (self._default_sort_key,))
                for id_, cids in ans.iteritems()}

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        cbm = self.table.col_book_map
        for item_id, val in self.table.id_map.iteritems():
            book_ids = set(cbm.get(item_id, ())).intersection(candidates)
            if book_ids:
                yield val, book_ids

class IdentifiersField(ManyToManyField):

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, ())
        if not ids:
            ids = default_value
        return ids

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        'Sort by identifier keys'
        ans = {id_ : self.table.book_col_map.get(id_, ())
                for id_ in all_book_ids}
        return {id_ : (tuple(sorted(cids.iterkeys())) if cids else
                        (self._default_sort_key,))
                for id_, cids in ans.iteritems()}


class AuthorsField(ManyToManyField):

    def author_data(self, author_id):
        return {
            'name' : self.table.id_map[author_id],
            'sort' : self.table.asort_map[author_id],
            'link' : self.table.alink_map[author_id],
        }

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

class SeriesField(ManyToOneField):

    def sort_key_for_series(self, book_id, get_lang, series_sort_order):
        sid = self.table.book_col_map.get(book_id, None)
        if sid is None:
            return self._default_sort_key
        return self._sort_key(title_sort(self.table.id_map[sid],
                                         order=series_sort_order,
                                         lang=get_lang(book_id)))

    def sort_keys_for_books(self, get_metadata, get_lang, all_book_ids):
        sso = tweaks['title_series_sorting']
        return {book_id:self.sort_key_for_series(book_id, get_lang, sso) for book_id
                in all_book_ids}

def create_field(name, table):
    cls = {
            ONE_ONE : OneToOneField,
            MANY_ONE : ManyToOneField,
            MANY_MANY : ManyToManyField,
        }[table.table_type]
    if name == 'authors':
        cls = AuthorsField
    elif name == 'ondevice':
        cls = OnDeviceField
    elif name == 'formats':
        cls = FormatsField
    elif name == 'identifiers':
        cls = IdentifiersField
    elif table.metadata['datatype'] == 'composite':
        cls = CompositeField
    elif table.metadata['datatype'] == 'series':
        cls = SeriesField
    return cls(name, table)

