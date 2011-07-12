#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.db.tables import ONE_ONE, MANY_ONE, MANY_MANY

class Field(object):

    def __init__(self, name, table):
        self.name, self.table = name, table
        self.has_text_data = self.metadata['datatype'] in ('text', 'comments',
                'series', 'enumeration')
        self.table_type = self.table.table_type

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

class OneToOneField(Field):

    def for_book(self, book_id, default_value=None):
        return self.table.book_col_map.get(book_id, default_value)

    def ids_for_book(self, book_id):
        return (book_id,)

    def books_for(self, item_id):
        return (item_id,)

    def __iter__(self):
        return self.table.book_col_map.iterkeys()

class ManyToOneField(Field):

    def for_book(self, book_id, default_value=None):
        ids = self.table.book_col_map.get(book_id, None)
        if ids is not None:
            ans = self.id_map[ids]
        else:
            ans = default_value
        return ans

    def ids_for_book(self, book_id):
        ids = self.table.book_col_map.get(book_id, None)
        if ids is None:
            return ()
        return ids

    def books_for(self, item_id):
        return self.table.col_book_map.get(item_id, ())

    def __iter__(self):
        return self.table.id_map.iterkeys()

class ManyToManyField(Field):

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

def create_field(name, table):
    cls = {
            ONE_ONE : OneToOneField,
            MANY_ONE : ManyToOneField,
            MANY_MANY : ManyToManyField,
        }[table.table_type]
    return cls(name, table)

