#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.db.tables import ONE_ONE, MANY_ONE, MANY_MANY
from calibre.utils.icu import sort_key

class Field(object):

    def __init__(self, name, table):
        self.name, self.table = name, table
        self.has_text_data = self.metadata['datatype'] in ('text', 'comments',
                'series', 'enumeration')
        self.table_type = self.table.table_type
        dt = self.metadata['datatype']
        self._sort_key = (sort_key if dt == 'text' else lambda x: x)

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
        Iterate over the ids for all values in this field
        '''
        raise NotImplementedError()

    def sort_books(self, get_metadata, all_book_ids, ascending=True):
        '''
        Sort books by this field. Returns a sorted list of book_ids

        :param _get_metadata: A callable which when called with the book_id
        returns the Metadata object for that book. Needed for sorting composite
        columns.

        :param all_book_ids: The set of ids for all books.
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

    def iter_book_ids(self):
        return self.table.book_col_map.iterkeys()

    def sort_books(self, get_metadata, all_book_ids, ascending=True):
        return sorted(self.iter_book_ids(), reverse=not ascending,
            key=lambda i: self._sort_key(self.book_col_map[i]))

class CompositeField(OneToOneField):

    def __init__(self, *args, **kwargs):
        OneToOneField.__init__(self, *args, **kwargs)

        self._render_cache = {}

    def render_composite(self, book_id, mi):
        ans = self._render_cache.get(book_id, None)
        if ans is None:
            ans = mi.get(self.metadata['label'])
            self._render_cache[book_id] = ans
        return ans

    def clear_cache(self):
        self._render_cache = {}

    def pop_cache(self, book_id):
        self._render_cache.pop(book_id, None)

    def get_value_with_cache(self, book_id, get_metadata):
        ans = self._render_cache.get(book_id, None)
        if ans is None:
            mi = get_metadata(book_id)
            ans = mi.get(self.metadata['label'])
            self._render_cache[book_id] = ans
        return ans

    def sort_books(self, get_metadata, all_book_ids, ascending=True):
        return sorted(all_book_ids, reverse=not ascending,
                key=lambda i: sort_key(self.get_value_with_cache(i,
                    get_metadata)))

class OnDeviceField(OneToOneField):

    def __init__(self, name, table):
        self.name = name
        self.book_on_device_func = None

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

    def iter_book_ids(self):
        return iter(())

    def sort_books(self, get_metadata, all_book_ids, ascending=True):
        return sorted(all_book_ids, reverse=not ascending,
                key=self.for_book)

class ManyToOneField(Field):

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, None)
        if ids is not None:
            ans = self.id_map[ids]
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

    def sort_books(self, get_metadata, all_book_ids, ascending=True):
        ids = sorted(self.id_map,
                key=lambda i:self._sort_key(self.id_map[i]))
        sm = {id_ : idx for idx, id_ in enumerate(ids)}
        return sorted(all_book_ids, reverse=not ascending,
                key=lambda book_id : sm.get(
                    self.book_col_map.get(book_id, None),
                    -1))

class ManyToManyField(Field):

    def __init__(self, *args, **kwargs):
        Field.__init__(self, *args, **kwargs)
        self.alphabetical_sort = self.name != 'authors'

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, ())
        if ids:
            ans = tuple(self.id_map[i] for i in ids)
        else:
            ans = default_value
        return ans

    def ids_for_book(self, book_id):
        return self.table.book_col_map.get(book_id, ())

    def books_for(self, item_id):
        return self.table.col_book_map.get(item_id, ())

    def __iter__(self):
        return self.table.id_map.iterkeys()

    def sort_books(self, get_metadata, all_book_ids, ascending=True):
        ids = sorted(self.id_map,
                key=lambda i:self._sort_key(self.id_map[i]))
        sm = {id_ : idx for idx, id_ in enumerate(ids)}

        def sort_key_for_book(book_id):
            item_ids = self.table.book_col_map.get(book_id, ())
            if self.alphabetical_sort:
                item_ids = sorted(item_ids, key=sm.get)
            return tuple(map(sm.get, item_ids))

        return sorted(all_book_ids, reverse=not ascending,
                key=sort_key_for_book)

class AuthorsField(ManyToManyField):

    def author_data(self, author_id):
        return {
            'name' : self.table.id_map[author_id],
            'sort' : self.table.asort_map[author_id],
            'link' : self.table.alink_map[author_id],
        }

class FormatsField(ManyToManyField):

    def format_fname(self, book_id, fmt):
        return self.table.fname_map[book_id][fmt.upper()]

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
    elif table.metadata['datatype'] == 'composite':
        cls = CompositeField
    return cls(name, table)

