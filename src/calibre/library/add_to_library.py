#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from hashlib import sha1

from calibre.ebooks import BOOK_EXTENSIONS


def find_folders_under(root, db, add_root=True,  # {{{
        follow_links=False, cancel_callback=lambda : False):
    '''
    Find all folders under the specified root path, ignoring any folders under
    the library path of db

    If follow_links is True, follow symbolic links. WARNING; this can lead to
    infinite recursion.

    cancel_callback must be a no argument callable that returns True to cancel
    the search
    '''
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

    def __init__(self, parent_folder, formats):
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

    def hash_of_file(self, path):
        with open(path, 'rb') as f:
            return sha1(f.read()).digest()

    @property
    def hashes(self):
        return frozenset(self.formats.values())

    @property
    def is_empty(self):
        return len(self) == 0

    def __iter__(self):
        yield from self.path_map

    def __len__(self):
        return len(self.path_map)

    def remove(self, fmt):
        self.hash_map.pop(fmt, None)
        self.path_map.pop(fmt, None)

    def matches(self, other):
        if not self.hashes.intersection(other.hashes):
            return False
        for fmt in self:
            if self.hash_map[fmt] != other.hash_map.get(fmt, False):
                return False
        return True

    def merge(self, other):
        for fmt in list(other):
            self.path_map[fmt] = other.path_map[fmt]
            self.hash_map[fmt] = other.hash_map[fmt]
            other.remove(fmt)

# }}}


def books_in_folder(folder, one_per_folder,  # {{{
        cancel_callback=lambda : False):
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


def hash_merge_format_collections(collections, cancel_callback=lambda:False):
    ans = []

    collections = list(collections)
    l = len(collections)
    for i in range(l):
        if cancel_callback():
            return collections
        one = collections[i]
        if one.is_empty:
            continue
        for j in range(i+1, l):
            if cancel_callback():
                return collections
            two = collections[j]
            if two.is_empty:
                continue
            if one.matches(two):
                one.merge(two)
        ans.append(one)

    return ans
