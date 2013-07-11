#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from calibre.ebooks import BOOK_EXTENSIONS

def find_books_in_directory(dirpath, single_book_per_directory):
    dirpath = os.path.abspath(dirpath)
    if single_book_per_directory:
        formats = []
        for path in os.listdir(dirpath):
            path = os.path.abspath(os.path.join(dirpath, path))
            if os.path.isdir(path) or not os.access(path, os.R_OK):
                continue
            ext = os.path.splitext(path)[1]
            if not ext:
                continue
            ext = ext[1:].lower()
            if ext not in BOOK_EXTENSIONS and ext != 'opf':
                continue
            formats.append(path)
        yield formats
    else:
        books = {}
        for path in os.listdir(dirpath):
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
                books[key] = []
            books[key].append(path)

        for formats in books.values():
            yield formats

def import_book_directory_multiple(db, dirpath, callback=None,
        added_ids=None):
    from calibre.ebooks.metadata.meta import metadata_from_formats

    duplicates = []
    for formats in find_books_in_directory(dirpath, False):
        mi = metadata_from_formats(formats)
        if mi.title is None:
            continue
        if db.has_book(mi):
            duplicates.append((mi, formats))
            continue
        book_id = db.import_book(mi, formats)
        if added_ids is not None:
            added_ids.add(book_id)
        if callable(callback):
            if callback(mi.title):
                break
    return duplicates

def import_book_directory(db, dirpath, callback=None, added_ids=None):
    from calibre.ebooks.metadata.meta import metadata_from_formats
    dirpath = os.path.abspath(dirpath)
    formats = find_books_in_directory(dirpath, True)
    formats = list(formats)[0]
    if not formats:
        return
    mi = metadata_from_formats(formats)
    if mi.title is None:
        return
    if db.has_book(mi):
        return [(mi, formats)]
    book_id = db.import_book(mi, formats)
    if added_ids is not None:
        added_ids.add(book_id)
    if callable(callback):
        callback(mi.title)

def recursive_import(db, root, single_book_per_directory=True,
        callback=None, added_ids=None):
    root = os.path.abspath(root)
    duplicates  = []
    for dirpath in os.walk(root):
        res = (import_book_directory(db, dirpath[0], callback=callback,
            added_ids=added_ids) if single_book_per_directory else
            import_book_directory_multiple(db, dirpath[0],
                callback=callback, added_ids=added_ids))
        if res is not None:
            duplicates.extend(res)
        if callable(callback):
            if callback(''):
                break
    return duplicates

