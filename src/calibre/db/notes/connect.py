#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
import time
import xxhash
from contextlib import suppress
from itertools import repeat

from calibre.constants import iswindows
from calibre.utils.copy_files import WINDOWS_SLEEP_FOR_RETRY_TIME
from calibre.utils.filenames import make_long_path_useable

from ..constants import NOTES_DIR_NAME
from .schema_upgrade import SchemaUpgrade

if iswindows:
    from calibre_extensions import winutil

class cmt(str):
    pass


copy_marked_up_text = cmt()
SEP = b'\0\x1c\0'


def hash_data(data: bytes) -> str:
    return 'xxh64:' + xxhash.xxh3_64_hexdigest(data)


def remove_with_retry(x):
    x = make_long_path_useable(x)
    try:
        os.remove(x)
    except FileNotFoundError:
        return
    except OSError as e:
        if iswindows and e.winerror == winutil.ERROR_SHARING_VIOLATION:
            time.sleep(WINDOWS_SLEEP_FOR_RETRY_TIME)
            os.remove(x)


class Notes:

    max_retired_items = 256

    def __init__(self, backend):
        conn = backend.get_connection()
        libdir = os.path.dirname(os.path.abspath(conn.db_filename('main')))
        notes_dir = os.path.join(libdir, NOTES_DIR_NAME)
        self.resources_dir = os.path.join(notes_dir, 'resources')
        self.backup_dir = os.path.join(notes_dir, 'backup')
        self.retired_dir = os.path.join(notes_dir, 'retired')
        if not os.path.exists(notes_dir):
            os.makedirs(notes_dir, exist_ok=True)
            if iswindows:
                winutil.set_file_attributes(notes_dir, winutil.FILE_ATTRIBUTE_HIDDEN | winutil.FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
        dbpath = os.path.join(notes_dir, 'notes.db')
        conn.execute("ATTACH DATABASE ? AS notes_db", (dbpath,))
        os.makedirs(self.resources_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.retired_dir, exist_ok=True)
        self.allowed_fields = set()
        triggers = []
        for table in backend.tables.values():
            m = table.metadata
            if not table.supports_notes or m.get('datatype') == 'rating':
                continue
            self.allowed_fields.add(table.name)
            triggers.append(
                f'CREATE TEMP TRIGGER IF NOT EXISTS notes_db_{table.name.replace("#", "_")}_deleted_trigger AFTER DELETE ON main.{m["table"]} BEGIN\n'
                f"  DELETE FROM notes WHERE colname = '{table.name}' AND item = OLD.id;\n"
                'END;'
            )
        SchemaUpgrade(conn, '\n'.join(triggers))
        conn.notes_dbpath = dbpath

    def path_for_resource(self, resource_hash: str) -> str:
        idx = resource_hash.index(':')
        prefix = resource_hash[idx + 1: idx + 3]
        return os.path.join(self.resources_dir, prefix, resource_hash)

    def remove_resources(self, conn, note_id, resources_to_potentially_remove, delete_from_link_table=True):
        if not isinstance(resources_to_potentially_remove, tuple):
            resources_to_potentially_remove = tuple(resources_to_potentially_remove)
        if delete_from_link_table:
            conn.executemany('''
                DELETE FROM notes_db.notes_resources_link WHERE note=? AND hash=?
            ''', tuple((note_id, x) for x in resources_to_potentially_remove))
        stmt = '''
            WITH resources_table(value) AS (VALUES {})
            SELECT value FROM resources_table WHERE value NOT IN (SELECT hash FROM notes_db.notes_resources_link)
        '''.format(','.join(repeat('(?)', len(resources_to_potentially_remove))))
        for (x,) in conn.execute(stmt, resources_to_potentially_remove):
            remove_with_retry(self.path_for_resource(x))

    def note_id_for(self, conn, field_name, item_id):
        for (ans,) in conn.execute('SELECT id FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name)):
            return ans

    def resources_used_by(self, conn, note_id):
        if note_id is not None:
            for (h,) in conn.execute('SELECT hash from notes_db.notes_resources_link WHERE note=?', (note_id,)):
                yield h

    def set_backup_for(self, field_name, item_id, marked_up_text='', searchable_text=''):
        path = make_long_path_useable(os.path.join(self.backup_dir, field_name, str(item_id)))
        if marked_up_text:
            try:
                f = open(path, 'wb')
            except FileNotFoundError:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                f = open(path, 'wb')
            with f:
                f.write(marked_up_text.encode('utf-8'))
                f.write(SEP)
                f.write(searchable_text.encode('utf-8'))
        else:
            if os.path.exists(path):
                dest = make_long_path_useable(os.path.join(self.retired_dir, f'{item_id}_{field_name}'))
                os.replace(path, dest)
                self.trim_retired_dir()

    def set_note(self, conn, field_name, item_id, marked_up_text='', hashes_of_used_resources=(), searchable_text=copy_marked_up_text):
        if searchable_text is copy_marked_up_text:
            searchable_text = marked_up_text
        note_id = self.note_id_for(conn, field_name, item_id)
        old_resources = frozenset(self.resources_used_by(conn, note_id))
        if not marked_up_text:
            if note_id is not None:
                conn.execute('DELETE FROM notes_db.notes WHERE id=?', (note_id,))
                self.set_backup_for(field_name, item_id)
                if old_resources:
                    self.remove_resources(conn, note_id, old_resources, delete_from_link_table=False)
            return
        new_resources = frozenset(hashes_of_used_resources)
        resources_to_potentially_remove = old_resources - new_resources
        resources_to_add = new_resources - old_resources
        if note_id is None:
            note_id, = next(conn.execute('''
                INSERT INTO notes_db.notes (item,colname,doc,searchable_text) VALUES (?,?,?,?) RETURNING id;
            ''', (item_id, field_name, marked_up_text, searchable_text)))
        else:
            conn.execute('UPDATE notes_db.notes SET doc=?,searchable_text=?', (marked_up_text, searchable_text))
        if resources_to_potentially_remove:
            self.remove_resources(conn, note_id, resources_to_potentially_remove)
        if resources_to_add:
            conn.executemany('''
                INSERT INTO notes_db.notes_resources_link (note,hash) VALUES (?,?);
            ''', tuple((note_id, x) for x in resources_to_add))
        self.set_backup_for(field_name, item_id, marked_up_text, searchable_text)
        return note_id

    def get_note(self, conn, field_name, item_id):
        for (doc,) in conn.execute('SELECT doc FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name)):
            return doc

    def get_note_data(self, conn, field_name, item_id):
        for (note_id, doc, searchable_text) in conn.execute(
            'SELECT id,doc,searchable_text FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name)
        ):
            return {
                'id': note_id, 'doc': doc, 'searchable_text': searchable_text,
                'resource_hashes': frozenset(self.resources_used_by(conn, note_id)),
            }

    def rename_note(self, conn, field_name, old_item_id, new_item_id):
        note_id = self.note_id_for(conn, field_name, old_item_id)
        if note_id is None:
            return
        new_note = self.get_note(conn, field_name, new_item_id)
        if new_note:
            return
        old_note = self.get_note_data(conn, field_name, old_item_id)
        if not old_note or not old_note['doc']:
            return
        self.set_note(conn, field_name, new_item_id, old_note['doc'], old_note['resource_hashes'], old_note['searchable_text'])

    def trim_retired_dir(self):
        mpath_map = {}
        items = []
        for d in os.scandir(self.retired_dir):
            mpath_map[d.path] = d.stat(follow_symlinks=False).st_mtime_ns
            items.append(d.path)
        extra = len(items) - self.max_retired_items
        if extra > 0:
            items.sort(key=mpath_map.__getitem__)
            for path in items[:extra]:
                remove_with_retry(path)

    def add_resource(self, path_or_stream_or_data):
        if isinstance(path_or_stream_or_data, bytes):
            data = path_or_stream_or_data
        elif isinstance(path_or_stream_or_data, str):
            with open(path_or_stream_or_data, 'rb') as f:
                data = f.read()
        else:
            data = f.read()
        resource_hash = hash_data(data)
        path = self.path_for_resource(resource_hash)
        path = make_long_path_useable(path)
        exists = False
        try:
            s = os.stat(path, follow_symlinks=False)
        except OSError:
            pass
        else:
            exists = s.st_size == len(data)
        if exists:
            return resource_hash

        try:
            f = open(path, 'wb')
        except FileNotFoundError:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            f = open(path, 'wb')
        with f:
            f.write(data)
        return resource_hash

    def get_resource(self, resource_hash) -> bytes:
        path = self.path_for_resource(resource_hash)
        path = make_long_path_useable(path)
        with suppress(FileNotFoundError), open(path, 'rb') as f:
            return f.read()
        return b''
