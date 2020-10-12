#!/usr/bin/env python
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


def database_has_annotations_support(cursor):
    return next(cursor.execute('pragma user_version;'))[0] > 23


def load_annotations_map_from_library(book_library_details, user_type='local', user='viewer'):
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
        cursor = conn.cursor()
        if not database_has_annotations_support(cursor):
            return ans
        for annot in annotations_for_book(
            cursor, book_library_details['book_id'], book_library_details['fmt'],
            user_type=user_type, user=user
        ):
            ans.setdefault(annot['type'], []).append(annot)
    finally:
        conn.close()
    return ans


def save_annotations_list_to_library(book_library_details, alist, sync_annots_user=''):
    import apsw
    from calibre.db.backend import save_annotations_for_book, Connection, annotations_for_book
    from calibre.gui2.viewer.annotations import annotations_as_copied_list
    from calibre.db.annotations import merge_annotations
    dbpath = book_library_details['dbpath']
    try:
        conn = apsw.Connection(dbpath, flags=apsw.SQLITE_OPEN_READWRITE)
    except Exception:
        return
    try:
        conn.setbusytimeout(Connection.BUSY_TIMEOUT)
        if not database_has_annotations_support(conn.cursor()):
            return
        amap = {}
        with conn:
            cursor = conn.cursor()
            for annot in annotations_for_book(cursor, book_library_details['book_id'], book_library_details['fmt']):
                amap.setdefault(annot['type'], []).append(annot)
            merge_annotations((x[0] for x in alist), amap)
            if sync_annots_user:
                other_amap = {}
                for annot in annotations_for_book(cursor, book_library_details['book_id'], book_library_details['fmt'], user_type='web', user=sync_annots_user):
                    other_amap.setdefault(annot['type'], []).append(annot)
                merge_annotations(amap, other_amap)
            alist = tuple(annotations_as_copied_list(amap))
            save_annotations_for_book(cursor, book_library_details['book_id'], book_library_details['fmt'], alist)
            if sync_annots_user:
                alist = tuple(annotations_as_copied_list(other_amap))
                save_annotations_for_book(cursor, book_library_details['book_id'], book_library_details['fmt'], alist, user_type='web', user=sync_annots_user)
    finally:
        conn.close()
