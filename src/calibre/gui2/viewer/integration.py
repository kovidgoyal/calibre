#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re


def get_book_library_details(absolute_path_to_ebook):
    absolute_path_to_ebook = os.path.abspath(os.path.expanduser(absolute_path_to_ebook))
    base = os.path.dirname(absolute_path_to_ebook)
    m = re.search(r' \((\d+)\)$', os.path.basename(base))
    if m is None:
        return
    book_id = int(m.group(1))
    library_dir = os.path.dirname(os.path.dirname(base))
    dbpath = os.path.join(library_dir, 'metadata.db')
    dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH') or dbpath
    if not os.path.exists(dbpath):
        return
    return {'dbpath': dbpath, 'book_id': book_id, 'fmt': absolute_path_to_ebook.rpartition('.')[-1].upper()}


def load_annotations_map_from_library(book_library_details):
    import apsw
    from calibre.db.backend import annotations_for_book, Connection
    ans = {}
    dbpath = book_library_details['dbpath']
    try:
        conn = apsw.Connection(dbpath, flags=apsw.SQLITE_OPEN_READONLY)
    except Exception:
        return ans
    try:
        conn.setbusytimeout(Connection.BUSY_TIMEOUT)
        for annot in annotations_for_book(conn.cursor(), book_library_details['book_id'], book_library_details['fmt']):
            ans.setdefault(annot['type'], []).append(annot)
    finally:
        conn.close()
    return ans


def save_annotations_list_to_library(book_library_details, alist):
    import apsw
    from calibre.db.backend import save_annotations_for_book, Connection
    dbpath = book_library_details['dbpath']
    try:
        conn = apsw.Connection(dbpath, flags=apsw.SQLITE_OPEN_READWRITE)
    except Exception:
        return
    try:
        conn.setbusytimeout(Connection.BUSY_TIMEOUT)
        with conn:
            save_annotations_for_book(conn.cursor(), book_library_details['book_id'], book_library_details['fmt'], alist)
    finally:
        conn.close()
