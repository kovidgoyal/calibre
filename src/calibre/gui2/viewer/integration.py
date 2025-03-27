#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re


def get_book_library_details(absolute_path_to_ebook):
    from calibre.srv.library_broker import correct_case_of_last_path_component, library_id_from_path
    absolute_path_to_ebook = os.path.abspath(os.path.expanduser(absolute_path_to_ebook))
    base = os.path.dirname(absolute_path_to_ebook)
    m = re.search(r' \((\d+)\)$', os.path.basename(base))
    if m is None:
        return
    book_id = int(m.group(1))
    library_dir = os.path.dirname(os.path.dirname(base))
    corrected_path = correct_case_of_last_path_component(library_dir)
    library_id = library_id_from_path(corrected_path)
    dbpath = os.path.join(library_dir, 'metadata.db')
    dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH') or dbpath
    if not os.path.exists(dbpath):
        return
    return {'dbpath': dbpath, 'book_id': book_id, 'fmt': absolute_path_to_ebook.rpartition('.')[-1].upper(), 'library_id': library_id}


def database_has_annotations_support(cursor):
    return next(cursor.execute('pragma user_version;'))[0] > 23


def load_annotations_map_from_library(book_library_details, user_type='local', user='viewer'):
    import apsw

    from calibre.db.backend import Connection, annotations_for_book
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


def send_msg_to_calibre(alist, sync_annots_user, library_id, book_id, book_fmt) -> bool:
    import json

    from calibre.gui2.listener import send_message_in_process

    packet = json.dumps({
        'alist': alist,
        'sync_annots_user': sync_annots_user,
        'library_id': library_id,
        'book_id': book_id,
        'book_fmt': book_fmt,
    })
    msg = 'save-annotations:' + packet
    try:
        send_message_in_process(msg)
        return True
    except Exception:
        return False


def save_annotations_in_gui(library_broker, msg) -> bool:
    import json
    data = json.loads(msg)
    db = library_broker.get(data['library_id'])
    if db:
        db = db.new_api
        with db.write_lock:
            if db._has_format(data['book_id'], data['book_fmt']):
                db._save_annotations_list(int(data['book_id']), data['book_fmt'].upper(), data['sync_annots_user'], data['alist'])
                return True
    return False


def save_annotations_list_to_library(book_library_details, alist, sync_annots_user='', calibre_data=None):
    calibre_data = calibre_data or {}
    if calibre_data.get('library_id') and calibre_data.get('book_id') and send_msg_to_calibre(
            alist, sync_annots_user, calibre_data['library_id'], calibre_data['book_id'], calibre_data['book_fmt']):
        return

    import apsw

    from calibre.db.backend import Connection, save_annotations_list_to_cursor
    dbpath = book_library_details['dbpath']
    try:
        conn = apsw.Connection(dbpath, flags=apsw.SQLITE_OPEN_READWRITE)
    except Exception:
        return
    try:
        conn.setbusytimeout(Connection.BUSY_TIMEOUT)
        if not database_has_annotations_support(conn.cursor()):
            return
        with conn:
            save_annotations_list_to_cursor(conn.cursor(), alist, sync_annots_user, book_library_details['book_id'], book_library_details['fmt'])
    finally:
        conn.close()
