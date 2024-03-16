#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import apsw
import json
import os
import shutil
import time
import xxhash
from contextlib import suppress
from itertools import count, repeat
from collections import defaultdict
from typing import Optional

from calibre import sanitize_file_name
from calibre.constants import iswindows
from calibre.db import FTSQueryError
from calibre.db.annotations import unicode_normalize
from calibre.utils.copy_files import WINDOWS_SLEEP_FOR_RETRY_TIME
from calibre.utils.filenames import copyfile_using_links, make_long_path_useable
from calibre.utils.icu import lower as icu_lower

from ..constants import NOTES_DB_NAME, NOTES_DIR_NAME
from .schema_upgrade import SchemaUpgrade

if iswindows:
    from calibre_extensions import winutil

class cmt(str):
    pass


copy_marked_up_text = cmt()
SEP = b'\0\x1c\0'
DOC_NAME = 'doc.html'
METADATA_EXT = '.metadata'


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
        self.temp_table_counter = count()
        conn = backend.get_connection()
        libdir = os.path.dirname(os.path.abspath(conn.db_filename('main')))
        self.notes_dir = os.path.join(libdir, NOTES_DIR_NAME)
        self.resources_dir = os.path.join(self.notes_dir, 'resources')
        self.backup_dir = os.path.join(self.notes_dir, 'backup')
        self.retired_dir = os.path.join(self.notes_dir, 'retired')
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir, exist_ok=True)
            if iswindows:
                winutil.set_file_attributes(self.notes_dir, winutil.FILE_ATTRIBUTE_HIDDEN | winutil.FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
        os.makedirs(self.resources_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.retired_dir, exist_ok=True)
        self.reopen(backend)
        for cat in backend.deleted_fields:
            self.delete_field(conn, cat)

    def reopen(self, backend):
        conn = backend.get_connection()
        conn.notes_dbpath = os.path.join(self.notes_dir, NOTES_DB_NAME)
        conn.execute("ATTACH DATABASE ? AS notes_db", (conn.notes_dbpath,))
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
        self.allowed_fields = frozenset(self.allowed_fields)
        SchemaUpgrade(conn, '\n'.join(triggers))

    def delete_field(self, conn, field_name):
        note_ids = conn.get('SELECT id from notes_db.notes WHERE colname=?', (field_name,))
        if note_ids:
            conn.execute(
                'DELETE FROM notes_db.notes_resources_link WHERE note IN (SELECT id FROM notes_db.notes WHERE colname=?)', (field_name,)
            )
            conn.execute('DELETE FROM notes_db.notes WHERE colname=?', (field_name,))
            self.remove_unreferenced_resources(conn)

    def remove_unreferenced_resources(self, conn):
        found = False
        for (rhash,) in conn.get('SELECT hash FROM notes_db.resources WHERE hash NOT IN (SELECT resource FROM notes_db.notes_resources_link)'):
            found = True
            remove_with_retry(self.path_for_resource(rhash))
        if found:
            conn.execute('DELETE FROM notes_db.resources WHERE hash NOT IN (SELECT resource FROM notes_db.notes_resources_link)')

    def path_for_resource(self, resource_hash: str) -> str:
        hashalg, digest = resource_hash.split(':', 1)
        prefix = digest[:2]
        # Cant use colons in filenames on windows safely
        return os.path.join(self.resources_dir, prefix, f'{hashalg}-{digest}')

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
            p = self.path_for_resource(x)
            remove_with_retry(p)
            remove_with_retry(p + METADATA_EXT)

    def note_id_for(self, conn, field_name, item_id):
        return conn.get('SELECT id FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name), all=False)

    def resources_used_by(self, conn, note_id):
        if note_id is not None:
            for (h,) in conn.execute('SELECT resource from notes_db.notes_resources_link WHERE note=?', (note_id,)):
                yield h

    def set_backup_for(self, field_name, item_id, item_value, marked_up_text, searchable_text, resource_hashes):
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
            f.write(SEP)
            f.write('\n'.join(resource_hashes).encode('utf-8'))
            f.write(SEP)
            f.write(item_value.encode('utf-8'))

    def path_to_retired_dir_for_item(self, field_name, item_id, item_value):
        key = icu_lower(item_value or '')
        return os.path.join(self.retired_dir, hash_key(f'{field_name} {key}'))

    def retire_entry(self, field_name, item_id, item_value, resources, note_id):
        path = make_long_path_useable(os.path.join(self.backup_dir, field_name, str(item_id)))
        if os.path.exists(path):
            destdir = self.path_to_retired_dir_for_item(field_name, item_id, item_value)
            os.makedirs(make_long_path_useable(destdir), exist_ok=True)
            dest = os.path.join(destdir, DOC_NAME)
            os.replace(path, make_long_path_useable(dest))
            with open(make_long_path_useable(os.path.join(destdir, 'note_id')), 'w') as nif:
                nif.write(str(note_id))
            for rhash, rname in resources:
                rpath = make_long_path_useable(self.path_for_resource(rhash))
                if os.path.exists(rpath):
                    rdest = os.path.join(destdir, 'res-'+rname)
                    with suppress(shutil.SameFileError):
                        copyfile_using_links(rpath, make_long_path_useable(rdest), dest_is_dir=False)
            self.trim_retired_dir()

    def unretire(self, conn, field_name, item_id, item_value) -> int:
        srcdir = make_long_path_useable(self.path_to_retired_dir_for_item(field_name, item_id, item_value))
        note_id = -1
        if not os.path.exists(srcdir) or self.note_id_for(conn, field_name, item_id) is not None:
            return note_id
        with open(os.path.join(srcdir, DOC_NAME), 'rb') as src:
            try:
                a, b, _ = src.read().split(SEP, 2)
            except Exception:
                return note_id
            marked_up_text, searchable_text = a.decode('utf-8'), b.decode('utf-8')
        resources = set()
        for x in os.listdir(srcdir):
            if x.startswith('res-'):
                rname = x.split('-', 1)[1]
                with open(os.path.join(srcdir, x), 'rb') as rsrc:
                    resources.add(self.add_resource(conn, rsrc, rname, update_name=False))
        note_id = self.set_note(conn, field_name, item_id, item_value, marked_up_text, resources, searchable_text, add_item_value_to_searchable_text=False)
        if note_id > -1:
            remove_with_retry(srcdir, is_dir=True)
        return note_id

    def remove_retired_entry(self, field_name, item_id, item_value):
        srcdir = self.path_to_retired_dir_for_item(field_name, item_id, item_value)
        remove_with_retry(srcdir, is_dir=True)

    def set_note(
            self, conn, field_name, item_id, item_value, marked_up_text='', used_resource_hashes=(),
            searchable_text=copy_marked_up_text, ctime=None, mtime=None, add_item_value_to_searchable_text=True
    ):
        if searchable_text is copy_marked_up_text:
            searchable_text = marked_up_text
        if add_item_value_to_searchable_text:
            searchable_text = item_value + '\n' + searchable_text
        note_id = self.note_id_for(conn, field_name, item_id)
        old_resources = frozenset(self.resources_used_by(conn, note_id))
        if not marked_up_text:
            if note_id is not None:
                conn.execute('DELETE FROM notes_db.notes WHERE id=?', (note_id,))
                resources = ()
                if old_resources:
                    resources = conn.get(
                        'SELECT hash,name FROM notes_db.resources WHERE hash IN ({})'.format(','.join(repeat('?', len(old_resources)))),
                        tuple(old_resources))
                self.retire_entry(field_name, item_id, item_value, resources, note_id)
                if old_resources:
                    self.remove_resources(conn, note_id, old_resources, delete_from_link_table=False)
            return -1
        new_resources = frozenset(used_resource_hashes)
        resources_to_potentially_remove = old_resources - new_resources
        resources_to_add = new_resources - old_resources
        if note_id is None:
            self.remove_retired_entry(field_name, item_id, item_value)
            if ctime is not None or mtime is not None:
                now = time.time()
                if ctime is None:
                    ctime = now
                if mtime is None:
                    mtime = now
                note_id = conn.get('''
                    INSERT INTO notes_db.notes (item,colname,doc,searchable_text,ctime,mtime) VALUES (?,?,?,?,?,?) RETURNING notes.id;
                ''', (item_id, field_name, marked_up_text, searchable_text, ctime, mtime), all=False)
            else:
                note_id = conn.get('''
                    INSERT INTO notes_db.notes (item,colname,doc,searchable_text) VALUES (?,?,?,?) RETURNING notes.id;
                ''', (item_id, field_name, marked_up_text, searchable_text), all=False)
        else:
            conn.execute('UPDATE notes_db.notes SET doc=?,searchable_text=? WHERE id=?', (marked_up_text, searchable_text, note_id))
        if resources_to_potentially_remove:
            self.remove_resources(conn, note_id, resources_to_potentially_remove)
        if resources_to_add:
            conn.executemany('''
                INSERT INTO notes_db.notes_resources_link (note,resource) VALUES (?,?);
            ''', tuple((note_id, x) for x in resources_to_add))
        self.set_backup_for(field_name, item_id, item_value, marked_up_text, searchable_text, used_resource_hashes)
        return note_id

    def get_note(self, conn, field_name, item_id):
        return conn.get('SELECT doc FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name), all=False)

    def get_note_data(self, conn, field_name, item_id):
        ans = None
        for (note_id, doc, searchable_text, ctime, mtime) in conn.execute(
            'SELECT id,doc,searchable_text,ctime,mtime FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name)
        ):
            ans = {
                'id': note_id, 'doc': doc, 'searchable_text': searchable_text,
                'ctime': ctime, 'mtime': mtime,
                'resource_hashes': frozenset(self.resources_used_by(conn, note_id)),
            }
            break
        return ans

    def get_all_items_that_have_notes(self, conn, field_name=None):
        if field_name:
            return {item_id for (item_id,) in conn.execute('SELECT item FROM notes_db.notes WHERE colname=?', (field_name,))}
        ans = defaultdict(set)
        for (note_id, field_name) in conn.execute('SELECT item, colname FROM notes_db.notes'):
            ans[field_name].add(note_id)
        return ans

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
        self.set_note(conn, field_name, new_item_id, new_item_value, old_note['doc'], old_note['resource_hashes'], old_note['searchable_text'])

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

    def add_resource(self, conn, path_or_stream_or_data, name, update_name=True, mtime=None):
        if isinstance(path_or_stream_or_data, bytes):
            data = path_or_stream_or_data
        elif isinstance(path_or_stream_or_data, str):
            with open(path_or_stream_or_data, 'rb') as f:
                data = f.read()
        else:
            data = path_or_stream_or_data.read()
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
        if not exists:
            try:
                f = open(path, 'wb')
            except FileNotFoundError:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                f = open(path, 'wb')
            with f:
                f.write(data)
            if mtime is not None:
                os.utime(f.name, (mtime, mtime))

        name = sanitize_file_name(name)
        base_name, ext = os.path.splitext(name)
        c = 0
        for (existing_name,) in conn.execute('SELECT name FROM notes_db.resources WHERE hash=?', (resource_hash,)):
            if existing_name != name and update_name:
                while True:
                    try:
                        conn.execute('UPDATE notes_db.resources SET name=? WHERE hash=?', (name, resource_hash))
                        with open(path + METADATA_EXT, 'w') as fn:
                            fn.write(json.dumps({'name':name}))
                        break
                    except apsw.ConstraintError:
                        c += 1
                        name = f'{base_name}-{c}{ext}'
            break
        else:
            while True:
                try:
                    conn.get('INSERT INTO notes_db.resources (hash,name) VALUES (?,?)', (resource_hash, name), all=False)
                    with open(path + METADATA_EXT, 'w') as fn:
                        fn.write(json.dumps({'name':name}))
                    break
                except apsw.ConstraintError:
                    c += 1
                    name = f'{base_name}-{c}{ext}'
        return resource_hash

    def get_resource_data(self, conn, resource_hash) -> Optional[dict]:
        ans = None
        for (name,) in conn.execute('SELECT name FROM notes_db.resources WHERE hash=?', (resource_hash,)):
            path = self.path_for_resource(resource_hash)
            path = make_long_path_useable(path)
            os.listdir(os.path.dirname(path))
            with suppress(FileNotFoundError), open(path, 'rb') as f:
                mtime = os.stat(f.fileno()).st_mtime
                ans = {'name': name, 'data': f.read(), 'hash': resource_hash, 'mtime': mtime}
                break
        return ans

    def all_notes(self, conn, restrict_to_fields=(), limit=None, snippet_size=64, return_text=True, process_each_result=None) -> list[dict]:
        if snippet_size is None:
            snippet_size = 64
        char_size = snippet_size * 8
        query = 'SELECT {0}.id, {0}.colname, {0}.item, substr({0}.searchable_text, 0, {1}) FROM {0} '.format('notes', char_size)
        if restrict_to_fields:
            query += ' WHERE notes_db.notes.colname IN ({})'.format(','.join(repeat('?', len(restrict_to_fields))))
        query += ' ORDER BY mtime DESC'
        if limit is not None:
            query += f' LIMIT {limit}'
        for record in conn.execute(query, tuple(restrict_to_fields)):
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

    def search(self,
        conn, fts_engine_query, use_stemming, highlight_start, highlight_end, snippet_size, restrict_to_fields=(),
        return_text=True, process_each_result=None, limit=None
    ):
        if not fts_engine_query:
            yield from self.all_notes(
                conn, restrict_to_fields, limit=limit, snippet_size=snippet_size, return_text=return_text, process_each_result=process_each_result)
            return
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
        if limit is not None:
            query += f' LIMIT {limit}'
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

    def export_non_db_data(self, zf):
        import zipfile
        def add_dir(which):
            for dirpath, _, filenames in os.walk(make_long_path_useable(which)):
                for f in filenames:
                    path = os.path.join(dirpath, f)
                    with open(path, 'rb') as src:
                        zi = zipfile.ZipInfo.from_file(path, arcname=os.path.relpath(path, self.notes_dir))
                        with zf.open(zi, 'w') as dest:
                            shutil.copyfileobj(src, dest)
        add_dir(self.backup_dir)
        add_dir(self.resources_dir)

    def vacuum(self, conn):
        conn.execute('VACUUM notes_db')

    def restore(self, conn, tables, report_progress):
        resources = {}
        errors = []
        for subdir in os.listdir(make_long_path_useable(self.resources_dir)):
            for rf in os.listdir(make_long_path_useable(os.path.join(self.resources_dir, subdir))):
                if not rf.endswith(METADATA_EXT):
                    name_path = os.path.join(self.resources_dir, subdir, rf + METADATA_EXT)
                    name = 'unnamed'
                    with suppress(OSError), open(make_long_path_useable(name_path)) as n:
                        name = json.loads(n.read())['name']
                    resources[rf.replace('-', ':', 1)] = name
        items = {}
        for f in os.listdir(make_long_path_useable(self.backup_dir)):
            if f in self.allowed_fields:
                items[f] = []
                for x in os.listdir(make_long_path_useable(os.path.join(self.backup_dir, f))):
                    with suppress(Exception):
                        items[f].append(int(x))
        known_resources = frozenset(resources)
        conn.executemany('INSERT OR REPLACE INTO notes_db.resources (hash,name) VALUES (?,?)', tuple(resources.items()))
        i, total = 0, sum(len(x) for x in items.values())
        report_progress(None, total)
        for field, entries in items.items():
            table = tables[field]
            rmap = {v: k for k, v in table.id_map.items()}
            for old_item_id in entries:
                i += 1
                try:
                    with open(make_long_path_useable(os.path.join(self.backup_dir, field, str(old_item_id))), 'rb') as f:
                        raw = f.read()
                        st = os.stat(f.fileno())
                except OSError as e:
                    errors.append(_('Failed to read from document for {path} with error: {error}').format(path=f'{field}:{old_item_id}', error=e))
                    report_progress('', i)
                    continue
                parts = raw.split(SEP, 3)
                try:
                    if len(parts) == 4:
                        doc, searchable_text, res, old_item_val = (str(x, 'utf-8') for x in parts)
                    else:
                        doc, searchable_text, res = (str(x, 'utf-8') for x in parts)
                        old_item_val = searchable_text.split('\n', 1)[0]
                except Exception as err:
                    errors.append(_('Failed to parse document for: {0} with error: {1}').format(old_item_id, err))
                    report_progress('', i)
                    continue
                item_id = rmap.get(old_item_val)
                if item_id is None:
                    errors.append(_(
                        'The item {old_item_val} does not exist in the {field} column in the restored database, could not restore its notes'
                    ).format(old_item_val=old_item_val, field=field))
                    report_progress('', i)
                    continue
                report_progress(old_item_val, i)
                resources = frozenset(res.splitlines())
                missing_resources = resources - known_resources
                if missing_resources:
                    errors.append(_('Some resources for {} were missing').format(old_item_val))
                resources &= known_resources
                try:
                    self.set_note(conn, field, item_id, old_item_val, doc, resources, searchable_text, ctime=st.st_ctime, mtime=st.st_mtime)
                except Exception as e:
                    errors.append(_('Failed to set note for {path} with error: {error}').format(path=old_item_val, error=e))
        return errors

    def export_note(self, conn, field_name, item_id):
        nd = self.get_note_data(conn, field_name, item_id)
        if nd is None:
            return ''
        from .exim import export_note

        def get_resource(rhash):
            return self.get_resource_data(conn, rhash)
        return export_note(nd['doc'], get_resource)

    def import_note(self, conn, field_name, item_id, item_value, html, basedir, ctime=None, mtime=None):
        from .exim import import_note
        def add_resource(path_or_stream_or_data, name):
            return self.add_resource(conn, path_or_stream_or_data, name)
        doc, searchable_text, resources = import_note(html, basedir, add_resource)
        return self.set_note(
            conn, field_name, item_id, item_value, marked_up_text=doc, used_resource_hashes=resources, searchable_text=searchable_text,
            ctime=ctime, mtime=mtime
        )
