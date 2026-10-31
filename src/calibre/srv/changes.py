#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping


class ChangeEvent:
    book_ids: frozenset[int]

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        return '{}(book_ids={})'.format(self.__class__.__name__, ','.join(sorted(map(str, self.book_ids))))


class BooksAdded(ChangeEvent):
    def __init__(self, book_ids: Iterable[int]) -> None:
        ChangeEvent.__init__(self)
        self.book_ids = frozenset(book_ids)


class BooksDeleted(ChangeEvent):
    def __init__(self, book_ids: Iterable[int]) -> None:
        ChangeEvent.__init__(self)
        self.book_ids = frozenset(book_ids)


class FormatsAdded(ChangeEvent):
    def __init__(self, formats_map: Mapping[int, Collection[str]]) -> None:
        ChangeEvent.__init__(self)
        self.formats_map = formats_map

    @property
    def book_ids(self) -> frozenset[int]:  # ty: ignore[invalid-property-type-override]
        return frozenset(self.formats_map)


class FormatsRemoved(ChangeEvent):
    def __init__(self, formats_map: Mapping[int, Collection[str]]) -> None:
        ChangeEvent.__init__(self)
        self.formats_map = formats_map

    @property
    def book_ids(self) -> frozenset[int]:  # ty: ignore[invalid-property-type-override]
        return frozenset(self.formats_map)


class MetadataChanged(ChangeEvent):
    def __init__(self, book_ids: Iterable[int]) -> None:
        ChangeEvent.__init__(self)
        self.book_ids = frozenset(book_ids)


class SavedSearchesChanged(ChangeEvent):
    def __init__(self, added: Iterable[str] = (), removed: Iterable[str] = ()) -> None:
        ChangeEvent.__init__(self)
        self.added = frozenset(added)
        self.removed = frozenset(removed)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(added={sorted(map(str, self.added))}, removed={sorted(map(str, self.removed))})'


class VirtualLibrariesChanged(ChangeEvent):
    def __init__(self, added: Iterable[str] = (), removed: Iterable[str] = (), renamed: Iterable[tuple[str, str]] = ()) -> None:
        ChangeEvent.__init__(self)
        self.added = frozenset(added)
        self.removed = frozenset(removed)
        self.renamed = tuple(renamed)  # (old_name, new_name) pairs, in the order they were renamed

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(added={sorted(map(str, self.added))}, removed={sorted(map(str, self.removed))}, renamed={list(self.renamed)})'


books_added = BooksAdded
formats_added = FormatsAdded
formats_removed = FormatsRemoved
books_deleted = BooksDeleted
metadata = MetadataChanged
saved_searches = SavedSearchesChanged
virtual_libraries = VirtualLibrariesChanged
