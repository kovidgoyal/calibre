#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import shutil
import time
import traceback
from collections import defaultdict
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from functools import partial
from itertools import count, repeat

import apsw
import xxhash

from calibre import sanitize_file_name
from calibre.constants import iswindows
from calibre.db import FTSQueryError
from calibre.db.annotations import unicode_normalize
from calibre.db.constants import NOTES_DB_NAME, NOTES_DIR_NAME
from calibre.db.notes.schema_upgrade import SchemaUpgrade
from calibre.utils.copy_files import WINDOWS_SLEEP_FOR_RETRY_TIME
from calibre.utils.filenames import copyfile_using_links, make_long_path_useable
from calibre.utils.icu import lower as icu_lower
from calibre.utils.localization import _

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
    f = shutil.rmtree if is_dir else os.remove
    try:
        f(x)
    except FileNotFoundError:
        return
    except OSError as e:
        if iswindows and getattr(e, 'winerror', None) == winutil.ERROR_SHARING_VIOLATION:
            time.sleep(WINDOWS_SLEEP_FOR_RETRY_TIME)
            f(x)


class FileTransaction:
    """
    Undo log for the files of notes changed during a database transaction. Files that are removed or overwritten are moved
    into a staging folder rather than deleted, so that rolling back can restore them. Committing deletes the staging folder.
    """

    def __init__(self, staging_dir: str) -> None:
        self.staging_dir = staging_dir
        self.counter = count()
        self.undo_log: list[Callable[[], None]] = []

    def stage(self, path: str) -> bool:
        # Move path, a file or a folder, into the staging folder. Returns False if path does not exist.
        if not os.path.lexists(path):
            return False
        os.makedirs(self.staging_dir, exist_ok=True)
        staged = os.path.join(self.staging_dir, str(next(self.counter)))
        os.replace(path, staged)
        self.undo_log.append(partial(os.replace, staged, path))
        return True

    def created(self, path: str, is_dir: bool = False) -> None:
        # path is about to be created
        self.undo_log.append(partial(remove_with_retry, path, is_dir))

    def moved(self, src: str, dest: str) -> None:
        # src was moved to dest
        self.undo_log.append(partial(os.replace, dest, src))

    def rollback(self, to: int = 0) -> None:
        while len(self.undo_log) > to:
            undo = self.undo_log.pop()
            try:
                undo()
            except Exception:
                traceback.print_exc()

    def finish(self) -> None:
        self.undo_log = []
        remove_with_retry(self.staging_dir, is_dir=True)


class Notes:
    max_retired_items = 256

    def __init__(self, backend):
        self.temp_table_counter = count()
        self.file_txn: FileTransaction | None = None
        conn = backend.get_connection()
        libdir = os.path.dirname(os.path.abspath(conn.db_filename('main')))
        self.notes_dir = os.path.join(libdir, NOTES_DIR_NAME)
        self.resources_dir = os.path.join(self.notes_dir, 'resources')
        self.backup_dir = os.path.join(self.notes_dir, 'backup')
        self.retired_dir = os.path.join(self.notes_dir, 'retired')
        self.staging_dir = os.path.join(self.notes_dir, 'staged')
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir, exist_ok=True)
            if iswindows:
                winutil.set_file_attributes(self.notes_dir, winutil.FILE_ATTRIBUTE_HIDDEN | winutil.FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
        try:
            os.makedirs(self.resources_dir, exist_ok=True)
        except FileExistsError:
            os.remove(self.resources_dir)
            os.makedirs(self.resources_dir, exist_ok=True)
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
        except FileExistsError:
            os.remove(self.backup_dir)
            os.makedirs(self.backup_dir, exist_ok=True)
        try:
            os.makedirs(self.retired_dir, exist_ok=True)
        except FileExistsError:
            os.remove(self.retired_dir)
            os.makedirs(self.retired_dir, exist_ok=True)
        # Left behind by a file transaction that was interrupted by a crash
        remove_with_retry(self.staging_dir, is_dir=True)
        self.reopen(backend)
        for cat in backend.deleted_fields:
            self.delete_field(conn, cat)

    def reopen(self, backend):
        conn = backend.get_connection()
        conn.notes_dbpath = os.path.join(self.notes_dir, NOTES_DB_NAME)
        conn.execute('ATTACH DATABASE ? AS notes_db', (conn.notes_dbpath,))
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

    def rename_field(self, conn, old_field_name, new_field_name):
        conn.execute('UPDATE notes_db.notes SET colname=? WHERE colname=?', (new_field_name, old_field_name))
        old_backup = make_long_path_useable(os.path.join(self.backup_dir, old_field_name))
        new_backup = make_long_path_useable(os.path.join(self.backup_dir, new_field_name))
        if os.path.exists(old_backup) and not os.path.exists(new_backup):
            os.rename(old_backup, new_backup)

    def delete_field(self, conn, field_name):
        note_ids = conn.get('SELECT id from notes_db.notes WHERE colname=?', (field_name,))
        if note_ids:
            conn.execute(
                'DELETE FROM notes_db.notes_resources_link WHERE note IN (SELECT id FROM notes_db.notes WHERE colname=?)',
                (field_name,),
            )
            conn.execute('DELETE FROM notes_db.notes WHERE colname=?', (field_name,))
            self.remove_unreferenced_resources(conn)

    @contextmanager
    def file_transaction(self) -> Generator[None]:
        """
        Wrap this around a database transaction that changes notes, so that the files of the notes (backups, resources and
        retired notes) are restored if the transaction is rolled back, which it signals by raising. Nested uses behave like
        savepoints.
        """
        txn = self.file_txn
        if txn is not None:
            mark = len(txn.undo_log)
            try:
                yield
            except BaseException:
                txn.rollback(mark)
                raise
            return
        self.file_txn = txn = FileTransaction(make_long_path_useable(self.staging_dir))
        try:
            yield
        except BaseException:
            self.file_txn = None
            txn.rollback()
            txn.finish()
            raise
        self.file_txn = None
        txn.finish()

    def remove_file(self, path: str, is_dir: bool = False) -> None:
        txn = self.file_txn
        if txn is not None:
            try:
                txn.stage(make_long_path_useable(path))
                return
            except OSError:
                # Cannot move it, delete it as without a transaction
                traceback.print_exc()
        remove_with_retry(path, is_dir)

    def prepare_write(self, path: str) -> None:
        # Call before writing the file at path (long path useable), so that a rollback restores the previous contents
        txn = self.file_txn
        if txn is not None and not txn.stage(path):
            txn.created(path)

    def makedirs(self, path: str) -> None:
        # path must be long path useable
        txn = self.file_txn
        if txn is not None:
            # Record the outermost folder that has to be created
            top, parent = None, path
            while not os.path.exists(parent):
                top, parent = parent, os.path.dirname(parent)
                if parent == top:
                    break
            if top is None:
                return
            txn.created(top, is_dir=True)
        os.makedirs(path, exist_ok=True)

    def move_file(self, src: str, dest: str) -> None:
        # Move src over dest, both long path useable
        self.prepare_write(dest)
        os.replace(src, dest)
        if self.file_txn is not None:
            self.file_txn.moved(src, dest)

    def remove_unreferenced_resources(self, conn):
        found = False
        for (rhash,) in conn.get('SELECT hash FROM notes_db.resources WHERE hash NOT IN (SELECT resource FROM notes_db.notes_resources_link)'):
            found = True
            self.remove_file(self.path_for_resource(rhash))
        if found:
            conn.execute('DELETE FROM notes_db.resources WHERE hash NOT IN (SELECT resource FROM notes_db.notes_resources_link)')

    def path_for_resource(self, resource_hash: str) -> str:
        hashalg, digest = resource_hash.split(':', 1)
        prefix = digest[:2]
        # Can't use colons in filenames on windows safely
        return os.path.join(self.resources_dir, prefix, f'{hashalg}-{digest}')

    def remove_resources(self, conn, note_id, resources_to_potentially_remove, delete_from_link_table=True):
        if not isinstance(resources_to_potentially_remove, tuple):
            resources_to_potentially_remove = tuple(resources_to_potentially_remove)
        if delete_from_link_table:
            conn.executemany(
                '''
                DELETE FROM notes_db.notes_resources_link WHERE note=? AND resource=?
            ''',
                tuple((note_id, x) for x in resources_to_potentially_remove),
            )
        stmt = '''
            WITH resources_table(value) AS (VALUES {})
            SELECT value FROM resources_table WHERE value NOT IN (SELECT resource FROM notes_db.notes_resources_link)
        '''.format(','.join(repeat('(?)', len(resources_to_potentially_remove))))
        for (x,) in conn.execute(stmt, resources_to_potentially_remove):
            p = self.path_for_resource(x)
            self.remove_file(p)
            self.remove_file(p + METADATA_EXT)

    def note_id_for(self, conn, field_name, item_id):
        return conn.get('SELECT id FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name), all=False)

    def resources_used_by(self, conn, note_id):
        if note_id is not None:
            for (h,) in conn.execute('SELECT resource from notes_db.notes_resources_link WHERE note=?', (note_id,)):
                yield h

    def set_backup_for(self, field_name, item_id, item_value, marked_up_text, searchable_text, resource_hashes):
        path = make_long_path_useable(os.path.join(self.backup_dir, field_name, str(item_id)))
        self.makedirs(os.path.dirname(path))
        self.prepare_write(path)
        with open(path, 'wb') as f:
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
            destdir = make_long_path_useable(self.path_to_retired_dir_for_item(field_name, item_id, item_value))
            self.makedirs(destdir)
            self.move_file(path, os.path.join(destdir, DOC_NAME))
            self.add_retired_metadata(destdir, resources, note_id)
            self.trim_retired_dir()

    def retire_backup_data(self, field_name, item_value, raw, resources):
        destdir = make_long_path_useable(self.path_to_retired_dir_for_item(field_name, None, item_value))
        self.makedirs(destdir)
        doc_path = os.path.join(destdir, DOC_NAME)
        self.prepare_write(doc_path)
        with open(doc_path, 'wb') as f:
            f.write(raw)
        self.add_retired_metadata(destdir, resources, -1)

    def add_retired_metadata(self, destdir, resources, note_id):
        nif_path = os.path.join(destdir, 'note_id')
        self.prepare_write(nif_path)
        with open(nif_path, 'w') as nif:
            nif.write(str(note_id))
        for rhash, rname in resources:
            rpath = make_long_path_useable(self.path_for_resource(rhash))
            if os.path.exists(rpath):
                rdest = os.path.join(destdir, 'res-' + rname)
                self.prepare_write(rdest)
                with suppress(shutil.SameFileError):
                    copyfile_using_links(rpath, rdest, dest_is_dir=False)

    def unretire(self, conn, field_name, item_id, item_value) -> int:
        srcdir = make_long_path_useable(self.path_to_retired_dir_for_item(field_name, item_id, item_value))
        note_id = -1
        if not os.path.exists(srcdir) or self.note_id_for(conn, field_name, item_id) is not None:
            return note_id
        with open(os.path.join(srcdir, DOC_NAME), 'rb') as src:
            try:
                a, b, _x = src.read().split(SEP, 2)
            except Exception:
                return note_id
            marked_up_text, searchable_text = a.decode('utf-8'), b.decode('utf-8')
        resources = set()
        for x in os.listdir(srcdir):
            if x.startswith('res-'):
                rname = x.split('-', 1)[1]
                with open(os.path.join(srcdir, x), 'rb') as rsrc:
                    resources.add(self.add_resource(conn, rsrc, rname, update_name=False))
        note_id = self.set_note(
            conn,
            field_name,
            item_id,
            item_value,
            marked_up_text,
            resources,
            searchable_text,
            add_item_value_to_searchable_text=False,
        )
        if note_id > -1:
            self.remove_file(srcdir, is_dir=True)
        return note_id

    def remove_retired_entry(self, field_name, item_id, item_value):
        srcdir = self.path_to_retired_dir_for_item(field_name, item_id, item_value)
        self.remove_file(srcdir, is_dir=True)

    def set_note(
        self,
        conn,
        field_name,
        item_id,
        item_value,
        marked_up_text='',
        used_resource_hashes=(),
        searchable_text=copy_marked_up_text,
        ctime=None,
        mtime=None,
        add_item_value_to_searchable_text=True,
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
                        tuple(old_resources),
                    )
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
                note_id = conn.get(
                    '''
                    INSERT INTO notes_db.notes (item,colname,doc,searchable_text,ctime,mtime) VALUES (?,?,?,?,?,?) RETURNING notes.id;
                ''',
                    (item_id, field_name, marked_up_text, searchable_text, ctime, mtime),
                    all=False,
                )
            else:
                note_id = conn.get(
                    '''
                    INSERT INTO notes_db.notes (item,colname,doc,searchable_text) VALUES (?,?,?,?) RETURNING notes.id;
                ''',
                    (item_id, field_name, marked_up_text, searchable_text),
                    all=False,
                )
        else:
            conn.execute(
                'UPDATE notes_db.notes SET doc=?,searchable_text=? WHERE id=?',
                (marked_up_text, searchable_text, note_id),
            )
        if resources_to_potentially_remove:
            self.remove_resources(conn, note_id, resources_to_potentially_remove)
        if resources_to_add:
            conn.executemany(
                '''
                INSERT INTO notes_db.notes_resources_link (note,resource) VALUES (?,?);
            ''',
                tuple((note_id, x) for x in resources_to_add),
            )
        self.set_backup_for(field_name, item_id, item_value, marked_up_text, searchable_text, used_resource_hashes)
        return note_id

    def get_note(self, conn, field_name, item_id):
        return conn.get('SELECT doc FROM notes_db.notes WHERE item=? AND colname=?', (item_id, field_name), all=False)

    def get_note_data(self, conn, field_name, item_id):
        ans = None
        for note_id, doc, searchable_text, ctime, mtime in conn.execute(
            'SELECT id,doc,searchable_text,ctime,mtime FROM notes_db.notes WHERE item=? AND colname=?',
            (item_id, field_name),
        ):
            ans = {
                'id': note_id,
                'doc': doc,
                'searchable_text': searchable_text,
                'ctime': ctime,
                'mtime': mtime,
                'resource_hashes': frozenset(self.resources_used_by(conn, note_id)),
            }
            break
        return ans

    def get_all_items_that_have_notes(self, conn, field_name=None):
        if field_name:
            return {item_id for (item_id,) in conn.execute('SELECT item FROM notes_db.notes WHERE colname=?', (field_name,))}
        ans = defaultdict(set)
        for note_id, field_name in conn.execute('SELECT item, colname FROM notes_db.notes'):
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
        self.set_note(
            conn,
            field_name,
            new_item_id,
            new_item_value,
            old_note['doc'],
            old_note['resource_hashes'],
            old_note['searchable_text'],
        )

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
                self.remove_file(path, is_dir=True)

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
            self.makedirs(os.path.dirname(path))
            self.prepare_write(path)
            with open(path, 'wb') as f:
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
                        self.prepare_write(path + METADATA_EXT)
                        with open(path + METADATA_EXT, 'w') as fn:
                            fn.write(json.dumps({'name': name}))
                        break
                    except apsw.ConstraintError:
                        c += 1
                        name = f'{base_name}-{c}{ext}'
            break
        else:
            while True:
                try:
                    conn.get('INSERT INTO notes_db.resources (hash,name) VALUES (?,?)', (resource_hash, name), all=False)
                    self.prepare_write(path + METADATA_EXT)
                    with open(path + METADATA_EXT, 'w') as fn:
                        fn.write(json.dumps({'name': name}))
                    break
                except apsw.ConstraintError:
                    c += 1
                    name = f'{base_name}-{c}{ext}'
        return resource_hash

    def get_resource_data(self, conn, resource_hash) -> dict | None:
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

    def all_notes(self, conn, restrict_to_fields=(), limit=None, snippet_size=64, return_text=True, process_each_result=None):
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

    def search(
        self,
        conn,
        fts_engine_query,
        use_stemming,
        highlight_start,
        highlight_end,
        snippet_size,
        restrict_to_fields=(),
        return_text=True,
        process_each_result=None,
        limit=None,
    ):
        if not fts_engine_query:
            yield from self.all_notes(
                conn,
                restrict_to_fields,
                limit=limit,
                snippet_size=snippet_size,
                return_text=return_text,
                process_each_result=process_each_result,
            )
            return
        fts_engine_query = unicode_normalize(fts_engine_query)
        fts_table = 'notes_fts' + ('_stemmed' if use_stemming else '')
        hl_data = ()
        if return_text:
            text = 'notes.searchable_text'
            if highlight_start is not None and highlight_end is not None:
                if snippet_size is not None:
                    text = f'''snippet("{fts_table}", 0, ?, ?, '…', {max(1, min(snippet_size, 64))})'''
                else:
                    text = f'''highlight("{fts_table}", 0, ?, ?)'''
                hl_data = (highlight_start, highlight_end)
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
            for record in conn.execute(query, hl_data + restrict_to_fields + (fts_engine_query,)):
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
            for dirpath, _x, filenames in os.walk(make_long_path_useable(which)):
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
        resource_names = {}
        errors = []
        for subdir in os.listdir(make_long_path_useable(self.resources_dir)):
            try:
                subitems = os.listdir(make_long_path_useable(os.path.join(self.resources_dir, subdir)))
            except NotADirectoryError:
                continue
            for rf in subitems:
                if not rf.endswith(METADATA_EXT):
                    name_path = os.path.join(self.resources_dir, subdir, rf + METADATA_EXT)
                    name = 'unnamed'
                    with suppress(OSError), open(make_long_path_useable(name_path)) as n:
                        name = json.loads(n.read())['name']
                    resource_names[rf.replace('-', ':', 1)] = name
        items = {}
        for f in os.listdir(make_long_path_useable(self.backup_dir)):
            if f in self.allowed_fields:
                items[f] = []
                for x in os.listdir(make_long_path_useable(os.path.join(self.backup_dir, f))):
                    with suppress(Exception):
                        items[f].append(int(x))
        known_resources = frozenset(resource_names)
        conn.executemany('INSERT OR REPLACE INTO notes_db.resources (hash,name) VALUES (?,?)', tuple(resource_names.items()))
        i, total = 0, sum(len(x) for x in items.values())
        report_progress(None, total)

        # The backups are named by item id and the ids in the restored database can be different, so read all the
        # backups and remove them before restoring any notes, otherwise set_note() could overwrite unread backups and
        # obsolete backups would be restored again by the next rebuild.
        entries = []
        for field, item_ids in items.items():
            for old_item_id in item_ids:
                path = os.path.join(self.backup_dir, field, str(old_item_id))
                try:
                    with open(make_long_path_useable(path), 'rb') as f:
                        raw = f.read()
                        st = os.stat(f.fileno())
                except OSError as e:
                    errors.append(_('Failed to read from document for {path} with error: {error}').format(path=f'{field}:{old_item_id}', error=e))
                    i += 1
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
                    i += 1
                    report_progress('', i)
                    continue
                entries.append((field, path, raw, st, doc, searchable_text, frozenset(res.splitlines()), old_item_val))
        for entry in entries:
            remove_with_retry(entry[1])
        # If there are multiple backups for an item, as left behind by older versions of calibre, the newest one wins
        entries.sort(key=lambda entry: entry[3].st_mtime)

        rmaps = {field: {v: k for k, v in tables[field].id_map.items()} for field in items}
        for field, path, raw, st, doc, searchable_text, resources, old_item_val in entries:
            i += 1
            missing_resources = resources - known_resources
            resources &= known_resources
            item_id = rmaps[field].get(old_item_val)
            if item_id is None:
                errors.append(
                    _(
                        'The item {old_item_val} does not exist in the {field} column in the restored database, its notes'
                        ' will be restored if the item is created again'
                    ).format(old_item_val=old_item_val, field=field)
                )
            else:
                report_progress(old_item_val, i)
                if missing_resources:
                    errors.append(_('Some resources for {} were missing').format(old_item_val))
                try:
                    self.set_note(
                        conn,
                        field,
                        item_id,
                        old_item_val,
                        doc,
                        resources,
                        searchable_text,
                        ctime=getattr(st, 'st_birthtime', st.st_ctime),  # type: ignore
                        mtime=st.st_mtime,
                    )
                    continue
                except Exception as e:
                    errors.append(_('Failed to set note for {path} with error: {error}').format(path=old_item_val, error=e))
            # Keep the notes that could not be restored as retired notes, so that they are restored when an item with
            # the same name is created
            try:
                self.retire_backup_data(field, old_item_val, raw, tuple((h, resource_names[h]) for h in resources))
            except Exception as e:
                errors.append(_('Failed to preserve the notes for {path} with error: {error}').format(path=old_item_val, error=e))
            report_progress('', i)
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
            conn,
            field_name,
            item_id,
            item_value,
            marked_up_text=doc,
            used_resource_hashes=resources,
            searchable_text=searchable_text,
            ctime=ctime,
            mtime=mtime,
        )
