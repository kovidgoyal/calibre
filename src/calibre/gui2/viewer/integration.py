#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
from threading import Event, Lock, Thread


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


def database_has_last_read_positions_support(cursor):
    return next(cursor.execute('pragma user_version;'))[0] >= 22


def send_last_read_position_to_calibre(cfi, pos_frac, library_id, book_id, book_fmt) -> bool:
    import json

    from calibre.gui2.listener import send_message_in_process

    packet = json.dumps({
        'cfi': cfi,
        'pos_frac': pos_frac,
        'library_id': library_id,
        'book_id': book_id,
        'book_fmt': book_fmt,
    })
    msg = 'save-last-read-position:' + packet
    try:
        send_message_in_process(msg)
        return True
    except Exception:
        return False


def save_last_read_position_in_gui(library_broker, msg) -> bool:
    import json
    data = json.loads(msg)
    db = library_broker.get(data['library_id'])
    if db:
        db.new_api.set_last_read_position(
            int(data['book_id']), data['book_fmt'].upper(),
            user='local', device='calibre-desktop-viewer',
            cfi=data['cfi'], pos_frac=data['pos_frac'])
        return True
    return False


def save_last_read_position_to_library(book_library_details, cfi, pos_frac, calibre_data=None):
    calibre_data = calibre_data or {}
    if (calibre_data.get('library_id') and calibre_data.get('book_id') and
            send_last_read_position_to_calibre(
                cfi, pos_frac, calibre_data['library_id'],
                calibre_data['book_id'], calibre_data['book_fmt'])):
        return

    import apsw

    from calibre.db.backend import Connection, save_last_read_position_to_cursor
    dbpath = book_library_details['dbpath']
    try:
        conn = apsw.Connection(dbpath, flags=apsw.SQLITE_OPEN_READWRITE)
    except Exception:
        return
    try:
        conn.setbusytimeout(Connection.BUSY_TIMEOUT)
        if not database_has_last_read_positions_support(conn.cursor()):
            return
        with conn:
            save_last_read_position_to_cursor(
                conn.cursor(), book_library_details['book_id'], book_library_details['fmt'],
                'local', 'calibre-desktop-viewer', cfi, pos_frac=pos_frac)
    finally:
        conn.close()


class LastReadPositionSaver(Thread):
    '''
    Background thread that saves the last read position to the calibre library
    database, debounced to avoid excessive I/O during active reading.
    '''

    DEBOUNCE_SECONDS = 3.0

    def __init__(self):
        super().__init__(name='LastReadPositionSaver', daemon=True)
        self._lock = Lock()
        self._pending = None
        self._event = Event()
        self._stop = False

    def save_position(self, book_library_details, cfi, pos_frac, calibre_data):
        with self._lock:
            self._pending = (book_library_details, cfi, pos_frac, calibre_data)
        self._event.set()

    def shutdown(self):
        with self._lock:
            self._stop = True
        self._event.set()
        self.join()

    def _save_pending(self):
        with self._lock:
            pending = self._pending
            self._pending = None
        if pending:
            book_library_details, cfi, pos_frac, calibre_data = pending
            try:
                save_last_read_position_to_library(book_library_details, cfi, pos_frac, calibre_data)
            except Exception:
                import traceback
                traceback.print_exc()

    def run(self):
        while True:
            self._event.wait()
            self._event.clear()
            with self._lock:
                stop = self._stop
            if stop:
                self._save_pending()
                return
            # Debounce: keep waiting as long as new events arrive within DEBOUNCE_SECONDS
            while self._event.wait(timeout=self.DEBOUNCE_SECONDS):
                self._event.clear()
                with self._lock:
                    if self._stop:
                        self._save_pending()
                        return
            self._save_pending()
