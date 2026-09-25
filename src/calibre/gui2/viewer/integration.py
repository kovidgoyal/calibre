#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
import sys
from datetime import datetime

from calibre.db.book_storage import BookStorageEntry
from calibre.db.constants import EBOOK_VIEWER_DEVICE, EBOOK_VIEWER_USER


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
    return {
        'dbpath': dbpath,
        'book_id': book_id,
        'fmt': absolute_path_to_ebook.rpartition('.')[-1].upper(),
        'library_id': library_id,
    }


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
        for annot in annotations_for_book(cursor, book_library_details['book_id'], book_library_details['fmt'], user_type=user_type, user=user):
            ans.setdefault(annot['type'], []).append(annot)
    finally:
        conn.close()
    return ans


def send_msg_to_calibre(alist, sync_annots_user, library_id, book_id, book_fmt, last_read_data) -> bool:
    import json

    from calibre.gui2.listener import send_message_in_process

    packet = json.dumps({
        'alist': alist,
        'sync_annots_user': sync_annots_user,
        'library_id': library_id,
        'book_id': book_id,
        'book_fmt': book_fmt,
        'last_read_data': last_read_data,
    })
    msg = 'save-annotations:' + packet
    try:
        send_message_in_process(msg)
        return True
    except Exception:
        return False


def save_annotations_in_gui(library_broker, msg) -> tuple[str, int]:
    import json

    data = json.loads(msg)
    db = library_broker.get(data['library_id'])
    lid, book_id = '', 0
    if db:
        db = db.new_api
        book_id, fmt = int(data['book_id']), data['book_fmt'].upper()
        with db.write_lock:
            if db._has_format(book_id, fmt):
                lid = db.library_id
                db._save_annotations_list(book_id, fmt, data['sync_annots_user'], data['alist'])
                if lrd := data.get('last_read_data'):
                    epoch = datetime.fromisoformat(lrd['timestamp']).timestamp()
                    db._set_last_read_position(
                        book_id,
                        fmt,
                        user=EBOOK_VIEWER_USER,
                        device=EBOOK_VIEWER_DEVICE,
                        cfi=lrd['cfi'],
                        pos_frac=lrd['pos_frac'],
                        epoch=epoch,
                    )
    return lid, book_id


def save_annotations_list_to_library(book_library_details, alist, sync_annots_user='', calibre_data=None, last_read_data=None):
    calibre_data = calibre_data or {}
    if (
        (lid := calibre_data.get('library_id'))
        and (bid := calibre_data.get('book_id'))
        and send_msg_to_calibre(alist, sync_annots_user, lid, bid, calibre_data['book_fmt'], last_read_data)
    ):
        return

    import apsw

    from calibre.db.backend import Connection, save_annotations_list_to_cursor, save_last_read_position_to_cursor

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
            if last_read_data:
                epoch = datetime.fromisoformat(last_read_data['timestamp']).timestamp()
                save_last_read_position_to_cursor(
                    conn.cursor(),
                    book_library_details['book_id'],
                    book_library_details['fmt'],
                    EBOOK_VIEWER_USER,
                    EBOOK_VIEWER_DEVICE,
                    last_read_data['cfi'],
                    epoch=epoch,
                    pos_frac=last_read_data['pos_frac'],
                )
    finally:
        conn.close()


def load_book_storage_from_library(book_library_details, user_type='local', user='viewer') -> BookStorageEntry | None:
    import apsw

    from calibre.db.backend import Connection, book_storage_for_book, database_has_book_storage_support

    dbpath = book_library_details['dbpath']
    try:
        conn = apsw.Connection(dbpath, flags=apsw.SQLITE_OPEN_READONLY)
    except apsw.Error as err:
        print(f'Failed to open {dbpath} to read book storage with error: {err}', file=sys.stderr)
        return None
    try:
        conn.setbusytimeout(Connection.BUSY_TIMEOUT)
        cursor = conn.cursor()
        if not database_has_book_storage_support(cursor):
            return None
        return book_storage_for_book(cursor, book_library_details['book_id'], book_library_details['fmt'], user_type=user_type, user=user)
    finally:
        conn.close()


def send_book_storage_msg_to_calibre(entry: BookStorageEntry, sync_annots_user: str, library_id: str, book_id: int, book_fmt: str) -> bool:
    import json

    from calibre.gui2.listener import send_message_in_process

    packet = json.dumps({
        'entry': entry,
        'sync_annots_user': sync_annots_user,
        'library_id': library_id,
        'book_id': book_id,
        'book_fmt': book_fmt,
    })
    try:
        send_message_in_process('save-book-storage:' + packet)
        return True
    except Exception:
        return False


def save_book_storage_in_gui(library_broker, msg: str) -> bool:
    import json

    from calibre.db.book_storage import validate_book_storage

    data = json.loads(msg)
    entry = validate_book_storage(data['entry'])
    db = library_broker.get(data['library_id'])
    if not db:
        return False
    db = db.new_api
    book_id, fmt = int(data['book_id']), data['book_fmt'].upper()
    with db.write_lock:
        if not db._has_format(book_id, fmt):
            return False
        db._save_book_storage(book_id, fmt, data['sync_annots_user'], entry)
    return True


def save_book_storage_to_library(book_library_details, entry: BookStorageEntry, sync_annots_user: str = '', calibre_data=None) -> None:
    calibre_data = calibre_data or {}
    if (
        (lid := calibre_data.get('library_id'))
        and (bid := calibre_data.get('book_id'))
        and send_book_storage_msg_to_calibre(entry, sync_annots_user, lid, bid, calibre_data['book_fmt'])
    ):
        return

    import apsw

    from calibre.db.backend import Connection, database_has_book_storage_support, save_book_storage_to_cursor

    dbpath = book_library_details['dbpath']
    try:
        conn = apsw.Connection(dbpath, flags=apsw.SQLITE_OPEN_READWRITE)
    except apsw.Error as err:
        print(f'Failed to open {dbpath} to save book storage with error: {err}', file=sys.stderr)
        return
    try:
        conn.setbusytimeout(Connection.BUSY_TIMEOUT)
        if not database_has_book_storage_support(conn.cursor()):
            print(f'Not saving book storage to {dbpath} as it was last opened by an older version of calibre', file=sys.stderr)
            return
        with conn:
            save_book_storage_to_cursor(conn.cursor(), entry, sync_annots_user, book_library_details['book_id'], book_library_details['fmt'])
    finally:
        conn.close()
