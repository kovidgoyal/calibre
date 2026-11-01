#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

import os
from hashlib import sha1
from typing import TYPE_CHECKING

from calibre.ebooks import BOOK_EXTENSIONS

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from calibre.db.legacy import LibraryDatabase


def find_folders_under(
    root: str,
    db: LibraryDatabase,
    add_root: bool = True,  # {{{
    follow_links: bool = False,
    cancel_callback: Callable[[], bool] = lambda: False,
) -> set[str]:
    """
    Find all folders under the specified root path, ignoring any folders under
    the library path of db

    If follow_links is True, follow symbolic links. WARNING; this can lead to
    infinite recursion.

    cancel_callback must be a no argument callable that returns True to cancel
    the search
    """
    lp = db.library_path
    if lp:
        lp = os.path.abspath(lp)

    root = os.path.abspath(root)

    ans = set()
    for dirpath, dirnames, __ in os.walk(root, topdown=True, followlinks=follow_links):
        if cancel_callback():
            break
        for x in list(dirnames):
            path = os.path.join(dirpath, x)
            if lp and path.startswith(lp):
                dirnames.remove(x)
        if lp and dirpath.startswith(lp):
            continue
        ans.add(dirpath)

    if not add_root:
        ans.remove(root)

    return ans


# }}}


class FormatCollection:  # {{{
    def __init__(self, parent_folder: str, formats: Iterable[str]) -> None:
        self.path_map = {}
        for x in set(formats):
            fmt = os.path.splitext(x)[1].lower()
            if fmt:
                fmt = fmt[1:]
                self.path_map[fmt] = x
        self.parent_folder = None
        self.hash_map = {}
        for fmt, path in self.format_map.items():
            self.hash_map[fmt] = self.hash_of_file(path)

    def hash_of_file(self, path: str) -> bytes:
        with open(path, 'rb') as f:
            return sha1(f.read()).digest()

    @property
    def hashes(self) -> frozenset[bytes]:
        return frozenset(self.formats.values())

    @property
    def is_empty(self) -> bool:
        return len(self) == 0

    def __iter__(self) -> Iterator[str]:
        yield from self.path_map

    def __len__(self) -> int:
        return len(self.path_map)

    def remove(self, fmt: str) -> None:
        self.hash_map.pop(fmt, None)
        self.path_map.pop(fmt, None)

    def matches(self, other: FormatCollection) -> bool:
        if not self.hashes.intersection(other.hashes):
            return False
        return all(self.hash_map[fmt] == other.hash_map.get(fmt, False) for fmt in self)

    def merge(self, other: FormatCollection) -> None:
        for fmt in list(other):
            self.path_map[fmt] = other.path_map[fmt]
            self.hash_map[fmt] = other.hash_map[fmt]
            other.remove(fmt)


# }}}


def books_in_folder(
    folder: str,
    one_per_folder: bool,  # {{{
    cancel_callback: Callable[[], bool] = lambda: False,
) -> list[FormatCollection] | None:
    dirpath = os.path.abspath(folder)
    if one_per_folder:
        formats = set()
        for path in os.listdir(dirpath):
            if cancel_callback():
                return []
            path = os.path.abspath(os.path.join(dirpath, path))
            if os.path.isdir(path) or not os.access(path, os.R_OK):
                continue
            ext = os.path.splitext(path)[1]
            if not ext:
                continue
            ext = ext[1:].lower()
            if ext not in BOOK_EXTENSIONS and ext != 'opf':
                continue
            formats.add(path)
        return [FormatCollection(folder, formats)]
    else:
        books = {}
        for path in os.listdir(dirpath):
            if cancel_callback():
                return
            path = os.path.abspath(os.path.join(dirpath, path))
            if os.path.isdir(path) or not os.access(path, os.R_OK):
                continue
            ext = os.path.splitext(path)[1]
            if not ext:
                continue
            ext = ext[1:].lower()
            if ext not in BOOK_EXTENSIONS:
                continue

            key = os.path.splitext(path)[0]
            if key not in books:
                books[key] = set()
            books[key].add(path)

        return [FormatCollection(folder, x) for x in books.values() if x]


# }}}


def hash_merge_format_collections(collections: Iterable[FormatCollection], cancel_callback: Callable[[], bool] = lambda: False) -> list[FormatCollection]:
    ans = []

    collections = list(collections)
    l = len(collections)
    for i in range(l):
        if cancel_callback():
            return collections
        one = collections[i]
        if one.is_empty:
            continue
        for j in range(i + 1, l):
            if cancel_callback():
                return collections
            two = collections[j]
            if two.is_empty:
                continue
            if one.matches(two):
                one.merge(two)
        ans.append(one)

    return ans
