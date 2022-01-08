#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


class ChangeEvent:

    def __init__(self):
        pass

    def __repr__(self):
        return '{}(book_ids={})'.format(
            self.__class__.__name__, ','.join(sorted(map(str, self.book_ids)))
        )


class BooksAdded(ChangeEvent):

    def __init__(self, book_ids):
        ChangeEvent.__init__(self)
        self.book_ids = frozenset(book_ids)


class BooksDeleted(ChangeEvent):

    def __init__(self, book_ids):
        ChangeEvent.__init__(self)
        self.book_ids = frozenset(book_ids)


class FormatsAdded(ChangeEvent):

    def __init__(self, formats_map):
        ChangeEvent.__init__(self)
        self.formats_map = formats_map

    @property
    def book_ids(self):
        return frozenset(self.formats_map)


class FormatsRemoved(ChangeEvent):

    def __init__(self, formats_map):
        ChangeEvent.__init__(self)
        self.formats_map = formats_map

    @property
    def book_ids(self):
        return frozenset(self.formats_map)


class MetadataChanged(ChangeEvent):

    def __init__(self, book_ids):
        ChangeEvent.__init__(self)
        self.book_ids = frozenset(book_ids)


class SavedSearchesChanged(ChangeEvent):

    def __init__(self, added=(), removed=()):
        ChangeEvent.__init__(self)
        self.added = frozenset(added)
        self.removed = frozenset(removed)

    def __repr__(self):
        return '{}(added={}, removed={})'.format(
            self.__class__.__name__,
            sorted(map(str, self.added)), sorted(map(str, self.removed))
        )


books_added = BooksAdded
formats_added = FormatsAdded
formats_removed = FormatsRemoved
books_deleted = BooksDeleted
metadata = MetadataChanged
saved_searches = SavedSearchesChanged
