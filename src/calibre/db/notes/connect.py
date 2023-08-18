#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import apsw
import os
import shutil
import time
import xxhash
from contextlib import suppress
from itertools import count, repeat
from typing import Optional, Union

from calibre.constants import iswindows
from calibre.db import FTSQueryError
from calibre.db.annotations import unicode_normalize
from calibre.utils.copy_files import WINDOWS_SLEEP_FOR_RETRY_TIME
from calibre.utils.filenames import copyfile_using_links, make_long_path_useable
from calibre.utils.icu import lower as icu_lower

from ..constants import NOTES_DIR_NAME
from .schema_upgrade import SchemaUpgrade

if iswindows:
    from calibre_extensions import winutil

class cmt(str):
    pass


copy_marked_up_text = cmt()
SEP = b'\0\x1c\0'
DOC_NAME = 'doc.html'

def hash_data(data: bytes) -> str:
    return 'xxh64:' + xxhash.xxh3_64_hexdigest(data)


def hash_key(key: str) -> str:
    return xxhash.xxh3_64_hexdigest(key.encode('utf-8'))


def remove_with_retry(x, is_dir=False):
    x = make_long_path_useable(x)
    f = (shutil.rmtree if is_dir else os.remove)
    try:
        f(x)
    except FileNotFoundError:
        return
    except OSError as e:
        if iswindows and e.winerror == winutil.ERROR_SHARING_VIOLATION:
            time.sleep(WINDOWS_SLEEP_FOR_RETRY_TIME)
            f(x)


class Notes:

    max_retired_items = 256

    def __init__(self, backend):
        conn = backend.get_connection()
        self.temp_table_counter = count()
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

    def path_for_resource(self, conn, resource_hash_or_resource_id: Union[str,int]) -> str:
        if isinstance(resource_hash_or_resource_id, str):
            resource_hash = resource_hash_or_resource_id
        else:
            resource_hash = conn.get('SELECT hash FROM notes_db.resources WHERE id=?', (resource_hash_or_resource_id,), all=False)
        idx = resource_hash.index(':')
        prefix = resource_hash[idx + 1: idx + 3]
        return os.path.join(self.resources_dir, prefix, resource_hash)

    def remove_resources(self, conn, note_id, resources_to_potentially_remove, delete_from_link_table=True):
        if not isinstance(resources_to_potentially_remove, tuple):
            resources_to_potentially_remove = tuple(resources_to_potentially_remove)
        if delete_from_link_table:
            conn.executemany('''
                DELETE FROM notes_db.notes_resources_link WHERE note=? AND resource=?
            ''', tuple((note_id, x) for x in resources_to_potentially_remove))
        stmt = '''
            WITH resources_table(value) AS (VALUES {})
            SELECT value FROM resources_table WHERE value NOT IN (SELECT resource FROM notes_db.notes_resources_link)
        '''.format(','.join(repeat('(?)', len(resources_to_potentially_remove))))
        for (x,) in conn.execute(stmt, resources_to_potentially_remove):
            remove_with_retry(self.path_for_resource(conn, x))

    def note_id_for(self, conn, field_name, item_id):
        return conn.get('SELECT id FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name), all=False)

    def resources_used_by(self, conn, note_id):
        if note_id is not None:
            for (h,) in conn.execute('SELECT resource from notes_db.notes_resources_link WHERE note=?', (note_id,)):
                yield h

    def set_backup_for(self, field_name, item_id, marked_up_text, searchable_text):
        path = make_long_path_useable(os.path.join(self.backup_dir, field_name, str(item_id)))
        try:
            f = open(path, 'wb')
        except FileNotFoundError:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            f = open(path, 'wb')
        with f:
            f.write(marked_up_text.encode('utf-8'))
            f.write(SEP)
            f.write(searchable_text.encode('utf-8'))

    def retire_entry(self, field_name, item_id, item_value, resources, note_id):
        path = make_long_path_useable(os.path.join(self.backup_dir, field_name, str(item_id)))
        if os.path.exists(path):
            key = icu_lower(item_value or '')
            destdir = os.path.join(self.retired_dir, hash_key(f'{field_name} {key}'))
            os.makedirs(make_long_path_useable(destdir), exist_ok=True)
            dest = os.path.join(destdir, DOC_NAME)
            os.replace(path, make_long_path_useable(dest))
            with open(make_long_path_useable(os.path.join(destdir, 'note_id')), 'w') as nif:
                nif.write(str(note_id))
            for rhash, rname in resources:
                rpath = make_long_path_useable(self.path_for_resource(None, rhash))
                if os.path.exists(rpath):
                    rdest = os.path.join(destdir, 'res-'+rname)
                    copyfile_using_links(rpath, make_long_path_useable(rdest), dest_is_dir=False)
            self.trim_retired_dir()

    def unretire(self, conn, field_name, item_id, item_value) -> int:
        key = icu_lower(item_value or '')
        srcdir = make_long_path_useable(os.path.join(self.retired_dir, hash_key(f'{field_name} {key}')))
        note_id = -1
        if not os.path.exists(srcdir) or self.note_id_for(conn, field_name, item_id) is not None:
            return note_id
        with open(os.path.join(srcdir, DOC_NAME), 'rb') as src:
            a, b = src.read().partition(SEP)[::2]
            marked_up_text, searchable_text = a.decode('utf-8'), b.decode('utf-8')
        resources = set()
        for x in os.listdir(srcdir):
            if x.startswith('res-'):
                rname = x.split('-', 1)[1]
                with open(os.path.join(srcdir, x), 'rb') as rsrc:
                    resources.add(self.add_resource(conn, rsrc, rname))
        note_id = self.set_note(conn, field_name, item_id, item_value, marked_up_text, resources, searchable_text)
        if note_id > -1:
            remove_with_retry(srcdir, is_dir=True)
        return note_id

    def set_note(self, conn, field_name, item_id, item_value, marked_up_text='', used_resource_ids=(), searchable_text=copy_marked_up_text):
        if searchable_text is copy_marked_up_text:
            searchable_text = marked_up_text
        note_id = self.note_id_for(conn, field_name, item_id)
        old_resources = frozenset(self.resources_used_by(conn, note_id))
        if not marked_up_text:
            if note_id is not None:
                conn.execute('DELETE FROM notes_db.notes WHERE id=?', (note_id,))
                resources = ()
                if old_resources:
                    resources = conn.get(
                        'SELECT hash,name FROM notes_db.resources WHERE id IN ({})'.format(','.join(repeat('?', len(old_resources)))),
                        tuple(old_resources))
                self.retire_entry(field_name, item_id, item_value, resources, note_id)
                if old_resources:
                    self.remove_resources(conn, note_id, old_resources, delete_from_link_table=False)
            return -1
        new_resources = frozenset(used_resource_ids)
        resources_to_potentially_remove = old_resources - new_resources
        resources_to_add = new_resources - old_resources
        if note_id is None:
            note_id = conn.get('''
                INSERT INTO notes_db.notes (item,colname,doc,searchable_text) VALUES (?,?,?,?) RETURNING notes.id;
            ''', (item_id, field_name, marked_up_text, searchable_text), all=False)
        else:
            conn.execute('UPDATE notes_db.notes SET doc=?,searchable_text=?', (marked_up_text, searchable_text))
        if resources_to_potentially_remove:
            self.remove_resources(conn, note_id, resources_to_potentially_remove)
        if resources_to_add:
            conn.executemany('''
                INSERT INTO notes_db.notes_resources_link (note,resource) VALUES (?,?);
            ''', tuple((note_id, x) for x in resources_to_add))
        self.set_backup_for(field_name, item_id, marked_up_text, searchable_text)
        return note_id

    def get_note(self, conn, field_name, item_id):
        return conn.get('SELECT doc FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name), all=False)

    def get_note_data(self, conn, field_name, item_id):
        for (note_id, doc, searchable_text) in conn.execute(
            'SELECT id,doc,searchable_text FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name)
        ):
            return {
                'id': note_id, 'doc': doc, 'searchable_text': searchable_text,
                'resource_ids': frozenset(self.resources_used_by(conn, note_id)),
            }

    def rename_note(self, conn, field_name, old_item_id, new_item_id, new_item_value):
        note_id = self.note_id_for(conn, field_name, old_item_id)
        if note_id is None:
            return
        new_note = self.get_note(conn, field_name, new_item_id)
        if new_note:
            return
        old_note = self.get_note_data(conn, field_name, old_item_id)
        if not old_note or not old_note['doc']:
            return
        self.set_note(conn, field_name, new_item_id, new_item_value, old_note['doc'], old_note['resource_ids'], old_note['searchable_text'])

    def trim_retired_dir(self):
        items = []
        for d in os.scandir(make_long_path_useable(self.retired_dir)):
            items.append(d.path)
        extra = len(items) - self.max_retired_items
        if extra > 0:
            def key(path):
                path = os.path.join(path, 'note_id')
                with suppress(OSError):
                    with open(path) as f:
                        return os.stat(path, follow_symlinks=False).st_mtime_ns, int(f.read())
            items.sort(key=key)
            for path in items[:extra]:
                remove_with_retry(path, is_dir=True)

    def add_resource(self, conn, path_or_stream_or_data, name):
        if isinstance(path_or_stream_or_data, bytes):
            data = path_or_stream_or_data
        elif isinstance(path_or_stream_or_data, str):
            with open(path_or_stream_or_data, 'rb') as f:
                data = f.read()
        else:
            data = path_or_stream_or_data.read()
        resource_hash = hash_data(data)
        path = self.path_for_resource(conn, resource_hash)
        path = make_long_path_useable(path)
        exists = False
        try:
            s = os.stat(path, follow_symlinks=False)
        except OSError:
            pass
        else:
            exists = s.st_size == len(data)
        if not exists:
            try:
                f = open(path, 'wb')
            except FileNotFoundError:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                f = open(path, 'wb')
            with f:
                f.write(data)
        base_name, ext = os.path.splitext(name)
        c = 0
        for (resource_id, existing_name) in conn.execute('SELECT id,name FROM notes_db.resources WHERE hash=?', (resource_hash,)):
            if existing_name != name:
                while True:
                    try:
                        conn.execute('UPDATE notes_db.resources SET name=? WHERE id=?', (name, resource_id))
                        break
                    except apsw.ConstraintError:
                        c += 1
                        name = f'{base_name}-{c}{ext}'
            break
        else:
            while True:
                try:
                    resource_id = conn.get('INSERT INTO notes_db.resources (hash,name) VALUES (?,?) RETURNING id', (resource_hash, name), all=False)
                    break
                except apsw.ConstraintError:
                    c += 1
                    name = f'{base_name}-{c}{ext}'
        return resource_id

    def get_resource_data(self, conn, resource_id) -> Optional[dict]:
        for (name, resource_hash) in conn.execute('SELECT name,hash FROM notes_db.resources WHERE id=?', (resource_id,)):
            path = self.path_for_resource(conn, resource_hash)
            path = make_long_path_useable(path)
            with suppress(FileNotFoundError), open(path, 'rb') as f:
                return {'name': name, 'data': f.read(), 'hash': resource_hash}

    def search(self,
        conn, fts_engine_query, use_stemming, highlight_start, highlight_end, snippet_size, restrict_to_fields=(),
        return_text=True, process_each_result=None
    ):
        fts_engine_query = unicode_normalize(fts_engine_query)
        fts_table = 'notes_fts' + ('_stemmed' if use_stemming else '')
        if return_text:
            text = 'notes.searchable_text'
            if highlight_start is not None and highlight_end is not None:
                if snippet_size is not None:
                    text = f'''snippet("{fts_table}", 0, '{highlight_start}', '{highlight_end}', '…', {max(1, min(snippet_size, 64))})'''
                else:
                    text = f'''highlight("{fts_table}", 0, '{highlight_start}', '{highlight_end}')'''
            text = ', ' + text
        else:
            text = ''
        query = 'SELECT {0}.id, {0}.colname, {0}.item {1} FROM {0} '.format('notes', text)
        query += f' JOIN {fts_table} ON notes_db.notes.id = {fts_table}.rowid'
        query += ' WHERE '
        if restrict_to_fields:
            query += ' notes_db.notes.colname IN ({}) AND '.format(','.join(repeat('?', len(restrict_to_fields))))
        query += f' "{fts_table}" MATCH ?'
        query += f' ORDER BY {fts_table}.rank '
        try:
            for record in conn.execute(query, restrict_to_fields+(fts_engine_query,)):
                result = {
                    'id': record[0],
                    'field': record[1],
                    'item_id': record[2],
                    'text': record[3] if return_text else '',
                }
                if process_each_result is not None:
                    result = process_each_result(result)
                ret = yield result
                if ret is True:
                    break
        except apsw.SQLError as e:
            raise FTSQueryError(fts_engine_query, query, e) from e
