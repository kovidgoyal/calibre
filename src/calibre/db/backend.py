#!/usr/bin/env python
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid@kovidgoyal.net>

# Imports {{{
import errno
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import uuid
from contextlib import closing, suppress
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict, cast, overload

import apsw

from calibre import as_unicode, force_unicode, prints
from calibre.constants import builtin_colors_light, builtin_decorations, filesystem_encoding, iswindows, plugins, preferred_encoding
from calibre.db import SPOOL_SIZE, FTSQueryError
from calibre.db.annotations import annot_db_data, unicode_normalize
from calibre.db.book_storage import BookStorageEntry, InvalidBookStorage, validate_book_storage
from calibre.db.constants import (
    BOOK_ID_PATH_TEMPLATE,
    COVER_FILE_NAME,
    DEFAULT_TRASH_EXPIRY_TIME_SECONDS,
    METADATA_FILE_NAME,
    NOTES_DIR_NAME,
    TRASH_DIR_NAME,
    TrashEntry,
)
from calibre.db.errors import NoSuchFormat
from calibre.db.schema_upgrades import SchemaUpgrade
from calibre.db.tables import (
    AuthorsTable,
    CompositeTable,
    FormatsTable,
    IdentifiersTable,
    ManyToManyTable,
    ManyToOneTable,
    OneToOneTable,
    PathTable,
    RatingTable,
    SizeTable,
    UUIDTable,
    read_books_table_columns,
)
from calibre.db.utils import atomic_write
from calibre.db.write import normalize_whitespace
from calibre.ebooks.metadata import author_to_author_sort, title_sort
from calibre.library.field_metadata import FieldMetadata
from calibre.ptempfile import PersistentTemporaryFile, TemporaryFile
from calibre.utils import pickle_binary_string, unpickle_binary_string
from calibre.utils.config import from_json, prefs, to_json, tweaks
from calibre.utils.copy_files import SourceDeletionFailed, copy_files, copy_tree, rename_files, windows_check_if_files_in_use
from calibre.utils.date import EPOCH, parse_date, utcfromtimestamp, utcnow
from calibre.utils.filenames import (
    ascii_filename,
    atomic_rename,
    copyfile_using_links,
    copytree_using_links,
    hardlink_file,
    is_case_sensitive,
    is_fat_filesystem,
    is_path_inside,
    make_long_path_useable,
    path_from_root,
    remove_dir_if_empty,
    samefile,
)
from calibre.utils.formatter_functions import compile_user_template_functions, formatter_functions, load_user_template_functions, unload_user_template_functions
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import sort_key
from calibre.utils.localization import _
from calibre.utils.resources import get_path as P
from calibre.utils.stop_gc import stop_gc
from polyglot.builtins import cmp, reraise

if iswindows:
    from calibre_extensions import winutil
if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Container, Generator, Iterable, Iterator, Mapping
    from threading import Event
    from types import TracebackType
    from typing import IO, BinaryIO
    from weakref import ref

    from _typeshed import SupportsWrite
    from apsw import Bindings, ScalarProtocol, SQLiteValue, SQLiteValues
    from PIL.Image import Image
    from qt.core import QImage, QPixmap

    from calibre.db.cache import Cache
    from calibre.db.fields import Field, FormatsField
    from calibre.db.fts.connect import FTS, FTSSearchResult
    from calibre.db.notes.connect import NoteData, NotesSearchResult
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.utils.filenames import WindowsAtomicFolderMove
    from calibre.utils.formatter_functions import FormatterFunction, FormatterUserFunction

    JSONDict = dict[str, Any]
    DBTable = OneToOneTable | ManyToOneTable

    class CustomColumnData(TypedDict):
        label: str
        name: str
        datatype: str
        editable: bool
        display: JSONDict
        normalized: bool
        num: int
        is_multiple: bool
        multiple_seps: NotRequired[dict[str, str]]

    class FormatMetadata(TypedDict, total=False):
        path: str
        size: int
        mtime: datetime

else:
    ScalarProtocol = None

# }}}

CUSTOM_DATA_TYPES = frozenset((
    'rating',
    'text',
    'comments',
    'datetime',
    'int',
    'float',
    'bool',
    'series',
    'composite',
    'enumeration',
))
WINDOWS_RESERVED_NAMES = frozenset('CON PRN AUX NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9'.split())


class DynamicFilter:  # {{{
    "No longer used, present for legacy compatibility"

    def __init__(self, name: str) -> None:
        self.name = name
        self.ids: frozenset[int] = frozenset()

    def __call__(self, id_: int) -> int:
        return int(id_ in self.ids)

    def change(self, ids: Iterable[int]) -> None:
        self.ids = frozenset(ids)


# }}}


class DBPrefs(dict):  # {{{
    "Store preferences as key:value pairs in the db"

    def __init__(self, db: DB) -> None:
        dict.__init__(self)
        self.db = db
        self.defaults: dict[str, object] = {}
        self.disable_setting = False
        self.load_from_db()

    def load_from_db(self) -> None:
        self.clear()
        for key, val in cast('list[tuple[str, str]]', self.db.conn.get('SELECT key,val FROM preferences')):
            try:
                val = self.raw_to_object(val)
            except Exception:
                prints('Failed to read value for:', key, 'from db')
                continue
            dict.__setitem__(self, key, val)

    def raw_to_object(self, raw: str | bytes) -> object:
        if not isinstance(raw, str):
            raw = raw.decode(preferred_encoding)
        return json.loads(raw, object_hook=from_json)

    def to_raw(self, val: object) -> str:
        # sort_keys=True is required so that the serialization of dictionaries is
        # not random, which is needed for the changed check in __setitem__
        return json.dumps(val, indent=2, default=to_json, sort_keys=True)

    def has_setting(self, key: str) -> bool:
        return key in self

    def __getitem__(self, key: str) -> object:
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def __delitem__(self, key: str) -> None:
        dict.__delitem__(self, key)
        self.db.execute('DELETE FROM preferences WHERE key=?', (key,))

    def __setitem__(self, key: str, val: object) -> None:
        if not self.disable_setting:
            raw = self.to_raw(val)
            do_set = False
            with self.db.conn:
                try:
                    dbraw = next(self.db.execute('SELECT id,val FROM preferences WHERE key=?', (key,)))
                except StopIteration:
                    dbraw = None
                if dbraw is None or dbraw[1] != raw:
                    if dbraw is None:
                        self.db.execute('INSERT INTO preferences (key,val) VALUES (?,?)', (key, raw))
                    else:
                        self.db.execute('UPDATE preferences SET val=? WHERE id=?', (raw, dbraw[0]))
                    do_set = True
            if do_set:
                dict.__setitem__(self, key, val)

    def set(self, key: str, val: object) -> None:
        self.__setitem__(key, val)

    def get_namespaced(self, namespace: str, key: str, default: object = None) -> object:
        key = f'namespaced:{namespace}:{key}'
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return default

    def set_namespaced(self, namespace: str, key: str, val: object) -> None:
        if ':' in key:
            raise KeyError('Colons are not allowed in keys')
        if ':' in namespace:
            raise KeyError('Colons are not allowed in the namespace')
        key = f'namespaced:{namespace}:{key}'
        self[key] = val

    def write_serialized(self, library_path: str) -> None:
        try:
            to_filename = os.path.join(library_path, 'metadata_db_prefs_backup.json')
            data = json.dumps(self, indent=2, default=to_json)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with open(to_filename, 'wb') as f:
                f.write(data)
        except Exception:
            import traceback

            traceback.print_exc()

    @classmethod
    def read_serialized(cls, library_path: str, recreate_prefs: bool = False) -> dict[str, object]:
        from_filename = os.path.join(library_path, 'metadata_db_prefs_backup.json')
        with open(from_filename, 'rb') as f:
            return json.load(f, object_hook=from_json)


# }}}

# Extra collators {{{


def pynocase(one: str | bytes, two: str | bytes, encoding: str = 'utf-8') -> int:
    if isinstance(one, bytes):
        try:
            one = one.decode(encoding, 'replace')
        except Exception:
            pass
    if isinstance(two, bytes):
        try:
            two = two.decode(encoding, 'replace')
        except Exception:
            pass
    return cmp(one.lower(), two.lower())


def _author_to_author_sort(x: str | None) -> str:
    if not x:
        return ''
    return author_to_author_sort(x.replace('|', ','))


def icu_collator(s1: str | bytes, s2: str | bytes) -> int:
    return cmp(sort_key(force_unicode(s1, 'utf-8')), sort_key(force_unicode(s2, 'utf-8')))


# }}}

# Unused aggregators {{{


def Concatenate(sep: str = ',') -> tuple[list[str], Callable[..., None], Callable[[list[str]], str | None]]:
    """String concatenation aggregator for sqlite"""

    def step(ctxt: list[str], value: str | None) -> None:
        if value is not None:
            ctxt.append(value)

    def finalize(ctxt: list[str]) -> str | None:
        try:
            if not ctxt:
                return None
            return sep.join(ctxt)
        except Exception:
            import traceback

            traceback.print_exc()
            raise

    return ([], step, finalize)


def SortedConcatenate(
    sep: str = ',',
) -> tuple[dict[int, str], Callable[..., None], Callable[[dict[int, str]], str | None]]:
    """String concatenation aggregator for sqlite, sorted by supplied index"""

    def step(ctxt: dict[int, str], ndx: int, value: str | None) -> None:
        if value is not None:
            ctxt[ndx] = value

    def finalize(ctxt: dict[int, str]) -> str | None:
        try:
            if len(ctxt) == 0:
                return None
            return sep.join(map(ctxt.get, sorted(ctxt)))  # ty: ignore[no-matching-overload]
        except Exception:
            import traceback

            traceback.print_exc()
            raise

    return ({}, step, finalize)


def IdentifiersConcat() -> tuple[list[str], Callable[..., None], Callable[[list[str]], str]]:
    """String concatenation aggregator for the identifiers map"""

    def step(ctxt: list[str], key: str, val: str) -> None:
        ctxt.append(f'{key}:{val}')

    def finalize(ctxt: list[str]) -> str:
        try:
            return ','.join(ctxt)
        except Exception:
            import traceback

            traceback.print_exc()
            raise

    return ([], step, finalize)


def AumSortedConcatenate() -> tuple[dict[int, str], Callable[..., None], Callable[[dict[int, str]], str | None]]:
    """String concatenation aggregator for the author sort map"""

    def step(ctxt: dict[int, str], ndx: int, author: str | None, sort: str, link: str) -> None:
        if author is not None:
            ctxt[ndx] = ':::'.join((author, sort, link))  # ruff: ignore[static-join-to-f-string]

    def finalize(ctxt: dict[int, str]) -> str | None:
        try:
            keys = list(ctxt)
            l = len(keys)
            if l == 0:
                return None
            if l == 1:
                return ctxt[keys[0]]
            return ':#:'.join([ctxt[v] for v in sorted(keys)])
        except Exception:
            import traceback

            traceback.print_exc()
            raise

    return ({}, step, finalize)


# }}}


# Annotations {{{
def annotations_for_book(cursor: apsw.Connection | apsw.Cursor, book_id: int, fmt: str, user_type: str = 'local', user: str = 'viewer') -> Iterator[JSONDict]:
    for (data,) in cursor.execute(
        'SELECT annot_data FROM annotations WHERE book=? AND format=? AND user_type=? AND user=?',
        (book_id, fmt.upper(), user_type, user),
    ):
        try:
            yield json.loads(data)
        except Exception:
            pass


def save_annotations_for_book(
    cursor: apsw.Cursor,
    book_id: int,
    fmt: str,
    annots_list: Iterable[tuple[JSONDict, float]],
    user_type: str = 'local',
    user: str = 'viewer',
) -> None:
    data = []
    fmt = fmt.upper()
    for annot, timestamp_in_secs in annots_list:
        atype = annot['type'].lower()
        aid, text = annot_db_data(annot)
        if aid is None:
            continue
        data.append((book_id, fmt, user_type, user, timestamp_in_secs, aid, atype, json.dumps(annot), text))
    cursor.execute('INSERT OR IGNORE INTO annotations_dirtied (book) VALUES (?)', (book_id,))
    cursor.execute('DELETE FROM annotations WHERE book=? AND format=? AND user_type=? AND user=?', (book_id, fmt, user_type, user))
    cursor.executemany(
        'INSERT OR REPLACE INTO annotations (book, format, user_type, user, timestamp, annot_id, annot_type, annot_data, searchable_text)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        data,
    )


def save_annotations_list_to_cursor(cursor: apsw.Cursor, alist: Iterable[tuple[JSONDict, float]], sync_annots_user: str, book_id: int, book_fmt: str) -> None:
    from calibre.db.annotations import annotations_as_copied_list, merge_annotations

    book_fmt = book_fmt.upper()
    amap = {}
    for annot in annotations_for_book(cursor, book_id, book_fmt):
        amap.setdefault(annot['type'], []).append(annot)
    merge_annotations((x[0] for x in alist), amap)
    if sync_annots_user:
        other_amap = {}
        for annot in annotations_for_book(cursor, book_id, book_fmt, user_type='web', user=sync_annots_user):
            other_amap.setdefault(annot['type'], []).append(annot)
        merge_annotations(amap, other_amap)
    alist = tuple(annotations_as_copied_list(amap))
    save_annotations_for_book(cursor, book_id, book_fmt, alist)
    if sync_annots_user:
        alist = tuple(annotations_as_copied_list(other_amap))
        save_annotations_for_book(cursor, book_id, book_fmt, alist, user_type='web', user=sync_annots_user)


def save_last_read_position_to_cursor(
    cursor: apsw.Cursor,
    book_id: int,
    fmt: str,
    user: str = '_',
    device: str = '_',
    cfi: str | None = None,
    epoch: float | None = None,
    pos_frac: float = 0,
) -> None:
    if cfi:
        cursor.execute(
            'INSERT OR REPLACE INTO last_read_positions(book,format,user,device,cfi,epoch,pos_frac) VALUES (?,?,?,?,?,?,?)',
            (book_id, fmt.upper(), user, device, cfi, epoch or time.time(), pos_frac),
        )
    else:
        cursor.execute(
            'DELETE FROM last_read_positions WHERE book=? AND format=? AND user=? AND device=?',
            (book_id, fmt.upper(), user, device),
        )


# }}}


# Book storage {{{
def database_has_book_storage_support(cursor: apsw.Connection | apsw.Cursor) -> bool:
    return next(cursor.execute('pragma user_version;'))[0] > 27


def book_storage_for_book(
    cursor: apsw.Connection | apsw.Cursor, book_id: int, fmt: str, user_type: str = 'local', user: str = 'viewer'
) -> BookStorageEntry | None:
    for timestamp, data in cursor.execute(
        'SELECT timestamp, data FROM book_storage WHERE book=? AND format=? AND user_type=? AND user=?',
        (book_id, fmt.upper(), user_type, user),
    ):
        try:
            return validate_book_storage({'timestamp': timestamp, 'data': json.loads(data)})
        except (ValueError, InvalidBookStorage) as err:
            prints(f'Ignoring invalid book storage for book: {book_id} format: {fmt} with error: {err}', file=sys.stderr)
    return None


def update_book_storage_for_book(
    cursor: apsw.Connection | apsw.Cursor, book_id: int, fmt: str, entry: BookStorageEntry, user_type: str = 'local', user: str = 'viewer'
) -> BookStorageEntry:
    """
    Store entry unless the existing storage for the book is newer. Returns
    whichever entry is stored after the update.
    """
    existing = book_storage_for_book(cursor, book_id, fmt, user_type, user)
    if existing is not None and existing['timestamp'] > entry['timestamp']:
        return existing
    cursor.execute(
        'INSERT OR REPLACE INTO book_storage (book, format, user_type, user, timestamp, data) VALUES (?, ?, ?, ?, ?, ?)',
        (book_id, fmt.upper(), user_type, user, entry['timestamp'], json.dumps(entry['data'], ensure_ascii=False)),
    )
    return entry


def save_book_storage_to_cursor(cursor: apsw.Connection | apsw.Cursor, entry: BookStorageEntry, sync_annots_user: str, book_id: int, book_fmt: str) -> None:
    update_book_storage_for_book(cursor, book_id, book_fmt, entry)
    if sync_annots_user:
        update_book_storage_for_book(cursor, book_id, book_fmt, entry, user_type='web', user=sync_annots_user)


# }}}


class Connection(apsw.Connection):  # {{{
    BUSY_TIMEOUT = 10000  # milliseconds
    fts_dbpath: str | None
    notes_dbpath: str | None

    def __init__(self, path: str) -> None:
        from calibre.utils.localization import bcp47_locale_name
        from calibre_extensions.sqlite_extension import set_ui_language

        set_ui_language(bcp47_locale_name())
        super().__init__(path)
        plugins.load_apsw_extension(self, 'sqlite_extension')
        self.fts_dbpath = self.notes_dbpath = None

        self.setbusytimeout(self.BUSY_TIMEOUT)
        self.execute('PRAGMA cache_size=-5000; PRAGMA temp_store=2; PRAGMA foreign_keys=ON;')

        encoding = next(self.execute('PRAGMA encoding'))[0]
        self.createcollation('PYNOCASE', partial(pynocase, encoding=encoding))

        self.createscalarfunction('title_sort', cast('ScalarProtocol', title_sort))
        self.createscalarfunction('author_to_author_sort', cast('ScalarProtocol', _author_to_author_sort), 1)
        self.createscalarfunction('uuid4', lambda *a: str(uuid.uuid4()), 0)

        # Dummy functions for dynamically created filters
        self.createscalarfunction('books_list_filter', cast('ScalarProtocol', lambda x: 1), 1)
        self.createcollation('icucollate', icu_collator)

        # Legacy aggregators (never used) but present for backwards compat
        self.createaggregatefunction('sortconcat', SortedConcatenate, 2)
        self.createaggregatefunction('sortconcat_bar', partial(SortedConcatenate, sep='|'), 2)
        self.createaggregatefunction('sortconcat_amper', partial(SortedConcatenate, sep='&'), 2)
        self.createaggregatefunction('identifiers_concat', IdentifiersConcat, 2)
        self.createaggregatefunction('concat', Concatenate, 1)
        self.createaggregatefunction('aum_sortconcat', AumSortedConcatenate, 4)

    def create_dynamic_filter(self, name: str) -> None:
        f = DynamicFilter(name)
        self.createscalarfunction(name, cast('ScalarProtocol', f), 1)

    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[True] = True) -> list[SQLiteValues]: ...
    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[False]) -> SQLiteValue: ...
    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: bool) -> list[SQLiteValues] | SQLiteValue: ...
    def get(self, *args: str | Bindings | None, **kw: bool) -> list[SQLiteValues] | SQLiteValue:
        ans = self.cursor().execute(*args)  # ty: ignore[invalid-argument-type]
        if kw.get('all', True):
            return ans.fetchall()
        with suppress(StopIteration, IndexError):
            return next(ans)[0]

    @overload
    def get_dict(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[True] = True) -> tuple[dict[str, SQLiteValue], ...]: ...
    @overload
    def get_dict(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[False]) -> dict[str, SQLiteValue] | None: ...
    def get_dict(self, *args: str | Bindings | None, all: bool = True) -> tuple[dict[str, SQLiteValue], ...] | dict[str, SQLiteValue] | None:
        ans = self.cursor().execute(*args)  # ty: ignore[invalid-argument-type]
        desc = ans.getdescription()
        field_names = tuple(x[0] for x in desc)

        def as_dict(row: SQLiteValues) -> dict[str, SQLiteValue]:
            return dict(zip(field_names, row))

        if all:
            return tuple(map(as_dict, ans))
        ans = ans.fetchone()
        if ans is not None:
            ans = as_dict(ans)
        return ans

    def execute(self, statements: str, bindings: Bindings | None = None, *, can_cache: bool = True, prepare_flags: int = 0, explain: int = -1) -> apsw.Cursor:
        cursor = self.cursor()
        return cursor.execute(statements, bindings, can_cache=can_cache, prepare_flags=prepare_flags, explain=explain)

    def executemany(
        self, statements: str, sequenceofbindings: Iterable[Bindings], *, can_cache: bool = True, prepare_flags: int = 0, explain: int = -1
    ) -> apsw.Cursor:  # ty: ignore[invalid-return-type]
        with self:  # Disable autocommit mode, for performance
            return self.cursor().executemany(statements, sequenceofbindings, can_cache=can_cache, prepare_flags=prepare_flags, explain=explain)


# }}}


def set_global_state(backend: DB) -> None:
    load_user_template_functions(backend.library_id, (), precompiled_user_functions=backend.get_user_template_functions())


def rmtree_with_retry(path: str, sleep_time: float = 1) -> None:
    try:
        shutil.rmtree(path)
    except OSError as e:
        if e.errno == errno.ENOENT and not os.path.exists(path):
            return
        if iswindows and e.winerror == winutil.ERROR_SHARING_VIOLATION:
            time.sleep(sleep_time)  # In case something has temporarily locked a file
        shutil.rmtree(path)


def replace_with_retry(src: str, dest: str) -> None:
    try:
        os.replace(src, dest)
    except OSError:
        if iswindows:
            time.sleep(1)  # In case something has temporarily locked the file
            os.replace(src, dest)
        else:
            raise


def prepare_replacement_for(dest: str, dest_stat: os.stat_result, tpath: str) -> bool:
    """Give the file at tpath the same identity (permissions, ownership,
    extended attributes/ACLs) as the existing file at dest so that it can be
    renamed over dest. Returns False if that is not possible, in which case
    dest must be overwritten in place instead."""
    if not stat.S_ISREG(dest_stat.st_mode) or dest_stat.st_nlink > 1:
        # dest is a symlink or hardlink, replacing it would break the link
        return False
    try:
        shutil.copystat(dest, tpath)
        os.utime(tpath)  # copystat copies the times of the old file as well
        if not iswindows:
            tstat = os.stat(tpath)
            if (tstat.st_uid, tstat.st_gid) != (dest_stat.st_uid, dest_stat.st_gid):
                os.chown(tpath, dest_stat.st_uid, dest_stat.st_gid)
    except OSError:
        return False
    return True


def write_stream_to_format_file(stream: IO[bytes], dest: str) -> int:
    """Write the contents of stream to dest, returning the number of bytes
    written. If dest already exists, it is left unchanged if reading from
    stream or writing the data fails."""
    try:
        dest_stat = os.lstat(dest)
    except FileNotFoundError:
        try:
            with open(dest, 'wb') as f:
                shutil.copyfileobj(stream, f)
                return f.tell()
        except BaseException:
            # Do not leave a partially written new file behind
            with suppress(OSError):
                os.remove(dest)
            raise
    try:
        # No file extension so that a temp file orphaned by a crash is never
        # mistaken for a book format, for example when restoring the database
        fd, tpath = tempfile.mkstemp(prefix='.calibre-format-', dir=os.path.dirname(dest))
    except OSError:
        # Cannot create files in the book folder, fall back to overwriting the
        # existing file in place
        with open(dest, 'wb') as f:
            shutil.copyfileobj(stream, f)
            return f.tell()
    try:
        with open(fd, 'wb') as f:
            shutil.copyfileobj(stream, f)
            size = f.tell()
        if prepare_replacement_for(dest, dest_stat, tpath):
            replace_with_retry(tpath, dest)
        else:
            with open(tpath, 'rb') as src, open(dest, 'wb') as f:
                shutil.copyfileobj(src, f)
    finally:
        with suppress(FileNotFoundError):
            os.remove(tpath)
    return size


def open_with_retry(path: str, retry_pause: float) -> BinaryIO:
    try:
        f = open(path, 'rb')  # ruff: ignore[open-file-with-context-handler]
    except OSError:
        if iswindows:
            time.sleep(retry_pause)
        f = open(path, 'rb')  # ruff: ignore[open-file-with-context-handler]
    return f


class DB:
    PATH_LIMIT = 40 if iswindows else 100
    WINDOWS_LIBRARY_PATH_LIMIT = 75
    _exists: bool
    tables: dict[str, DBTable]
    custom_column_label_map: dict[str, CustomColumnData]
    custom_column_num_map: dict[int, CustomColumnData]

    # Initialize database {{{

    def __init__(
        self,
        library_path: str | bytes,
        default_prefs: JSONDict | None = None,
        read_only: bool = False,
        restore_all_prefs: bool = False,
        progress_callback: Callable[[str | None, int], object] = lambda x, y: True,
        load_user_formatter_functions: bool = True,
        temp_db_path: str | None = None,
    ) -> None:
        self.is_closed = False
        if isinstance(library_path, bytes):
            library_path = library_path.decode(filesystem_encoding)
        self.field_metadata = FieldMetadata()

        self.library_path = os.path.abspath(library_path)
        self.dbpath = os.path.join(library_path, 'metadata.db')
        self.dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH', self.dbpath)

        if iswindows and len(self.library_path) + 4 * self.PATH_LIMIT + 10 > 259:
            raise ValueError(
                _('Path to library ({0}) too long. It must be less than {1} characters.').format(self.library_path, 259 - 4 * self.PATH_LIMIT - 10)
            )
        exists = self._exists = os.path.exists(self.dbpath)
        if not exists:
            # Be more strict when creating new libraries as the old calculation
            # allowed for max path lengths of 265 chars.
            if iswindows and len(self.library_path) > self.WINDOWS_LIBRARY_PATH_LIMIT:
                raise ValueError(_('Path to library too long. It must be less than %d characters.') % self.WINDOWS_LIBRARY_PATH_LIMIT)

        if temp_db_path is not None:
            if not os.path.exists(temp_db_path):
                raise FileNotFoundError(f"temp_db_path '{temp_db_path} doesn't refer to a file")
            # temp_db_path specifies a path to the database to use for this
            # library. It should be in its own folder along with .calnotes.
            # It overrides the environment variable CALIBRE_OVERRIDE_DATABASE_PATH.
            self.dbpath = temp_db_path
        elif read_only and os.path.exists(self.dbpath):
            # Work on only a copy of metadata.db to ensure that
            # metadata.db is not changed
            pt = PersistentTemporaryFile('_metadata_ro.db')
            pt.close()
            shutil.copyfile(self.dbpath, pt.name)
            self.dbpath = pt.name

        if not os.path.exists(os.path.dirname(self.dbpath)):
            os.makedirs(os.path.dirname(self.dbpath))

        self._conn: Connection | None = None
        if self.user_version == 0:
            self.initialize_database()

        if not os.path.exists(self.library_path):
            os.makedirs(self.library_path)
        self.is_case_sensitive = is_case_sensitive(self.library_path)
        self.is_fat_filesystem = is_fat_filesystem(self.library_path)

        SchemaUpgrade(self, self.library_path, self.field_metadata)

        # Guarantee that the library_id is set
        self.library_id  # ruff: ignore[useless-expression]

        # Fix legacy triggers and columns
        self.execute('''
        DROP TRIGGER IF EXISTS author_insert_trg;
        CREATE TEMP TRIGGER author_insert_trg
            AFTER INSERT ON authors
            BEGIN
            UPDATE authors SET sort=author_to_author_sort(NEW.name) WHERE id=NEW.id;
        END;
        DROP TRIGGER IF EXISTS author_update_trg;
        CREATE TEMP TRIGGER author_update_trg
            BEFORE UPDATE ON authors
            BEGIN
            UPDATE authors SET sort=author_to_author_sort(NEW.name)
            WHERE id=NEW.id AND name <> NEW.name;
        END;
        UPDATE authors SET sort=author_to_author_sort(name) WHERE sort IS NULL;
        ''')

        # Initialize_prefs must be called before initialize_custom_columns because
        # icc can set a pref.
        self.initialize_prefs(default_prefs, restore_all_prefs, progress_callback)
        self.initialize_custom_columns()
        self.initialize_tables()
        self.set_user_template_functions(compile_user_template_functions(self.prefs.get('user_template_functions', [])))
        if cast('float', self.prefs['last_expired_trash_at']) > 0:
            self.ensure_trash_dir(during_init=True)
        if load_user_formatter_functions:
            set_global_state(self)
        self.initialize_notes()

    @property
    def max_number_of_variables(self) -> int:
        return self.conn.limit(apsw.SQLITE_LIMIT_VARIABLE_NUMBER)

    @property
    def last_expired_trash_at(self) -> float:
        return float(cast('float', self.prefs['last_expired_trash_at']))

    @last_expired_trash_at.setter
    def last_expired_trash_at(self, val: float) -> None:
        self.prefs['last_expired_trash_at'] = float(val)

    def get_template_functions(self) -> dict[str, FormatterFunction]:
        return self._template_functions

    def get_user_template_functions(self) -> dict[str, FormatterUserFunction]:
        return self._user_template_functions

    def set_user_template_functions(self, user_formatter_functions: dict[str, FormatterUserFunction]) -> None:
        self._user_template_functions = user_formatter_functions
        self._template_functions: dict[str, FormatterFunction] = formatter_functions().get_builtins_and_aliases().copy()
        self._template_functions.update(user_formatter_functions)

    def initialize_prefs(self, default_prefs: JSONDict | None, restore_all_prefs: bool, progress_callback: Callable[[str | None, int], object]) -> None:  # {{{
        self.prefs = DBPrefs(self)

        if default_prefs is not None and not self._exists:
            progress_callback(None, len(default_prefs))
            # Only apply default prefs to a new database
            for i, key in enumerate(default_prefs):
                # be sure that prefs not to be copied are listed below
                if restore_all_prefs or key != 'news_to_be_synced':
                    self.prefs[key] = default_prefs[key]
                    progress_callback(_('restored preference ') + key, i + 1)
            if 'field_metadata' in default_prefs:
                fmvals = [f for f in default_prefs['field_metadata'].values() if f['is_custom']]
                progress_callback(None, len(fmvals))
                for i, f in enumerate(fmvals):
                    progress_callback(_('creating custom column ') + f['label'], i)
                    self.create_custom_column(
                        f['label'],
                        f['name'],
                        f['datatype'],
                        (f['is_multiple'] is not None and len(f['is_multiple']) > 0),
                        f['is_editable'],
                        f['display'],
                    )

        defs = self.prefs.defaults
        defs['gui_restriction'] = defs['cs_restriction'] = ''
        defs['categories_using_hierarchy'] = []
        defs['column_color_rules'] = []
        defs['column_icon_rules'] = []
        defs['cover_grid_icon_rules'] = []
        defs['grouped_search_make_user_categories'] = []
        defs['similar_authors_search_key'] = 'authors'
        defs['similar_authors_match_kind'] = 'match_any'
        defs['similar_publisher_search_key'] = 'publisher'
        defs['similar_publisher_match_kind'] = 'match_any'
        defs['similar_tags_search_key'] = 'tags'
        defs['similar_tags_match_kind'] = 'match_all'
        defs['similar_series_search_key'] = 'series'
        defs['similar_series_match_kind'] = 'match_any'
        defs['last_expired_trash_at'] = 0.0
        defs['expire_old_trash_after'] = DEFAULT_TRASH_EXPIRY_TIME_SECONDS
        defs['book_display_fields'] = [
            ('title', False),
            ('authors', True),
            ('series', True),
            ('identifiers', True),
            ('tags', True),
            ('formats', True),
            ('path', True),
            ('publisher', False),
            ('rating', False),
            ('author_sort', False),
            ('sort', False),
            ('timestamp', False),
            ('uuid', False),
            ('comments', True),
            ('id', False),
            ('pubdate', False),
            ('last_modified', False),
            ('size', False),
            ('languages', False),
            ('pages', False),
        ]
        defs['popup_book_display_fields'] = [('title', True)] + [(f[0], True) for f in defs['book_display_fields'] if f[0] != 'title']
        defs['qv_display_fields'] = [('title', True), ('authors', True), ('series', True)]
        defs['virtual_libraries'] = {}
        defs['virtual_lib_on_startup'] = defs['cs_virtual_lib_on_startup'] = ''
        defs['virt_libs_hidden'] = defs['virt_libs_order'] = ()
        defs['update_all_last_mod_dates_on_start'] = False
        defs['field_under_covers_in_grid'] = 'title'
        defs['cover_browser_title_template'] = '{title}'
        defs['cover_browser_subtitle_field'] = 'rating'
        defs['styled_columns'] = {}
        defs['edit_metadata_ignore_display_order'] = False
        defs['fts_enabled'] = False
        defs['column_tooltip_templates'] = {}
        defs['bookshelf_grouping_mode'] = ''
        defs['bookshelf_title_template'] = '{title}'
        defs['bookshelf_author_template'] = ''
        defs['bookshelf_spine_size_template'] = '{pages}'
        defs['bookshelf_icon_rules'] = []

        # Migrate the beta bookshelf_grouping_mode
        if self.prefs.get('bookshelf_grouping_mode', '') == 'none':
            self.prefs.set('bookshelf_grouping_mode', '')

        # Migrate the bool tristate tweak
        defs['bools_are_tristate'] = tweaks.get('bool_custom_columns_are_tristate', 'yes') == 'yes'
        if self.prefs.get('bools_are_tristate') is None:
            self.prefs.set('bools_are_tristate', defs['bools_are_tristate'])

        # Migrate column coloring rules
        if self.prefs.get('column_color_name_1', None) is not None:
            from calibre.library.coloring import migrate_old_rule

            old_rules = []
            for i in range(1, 6):
                col = self.prefs.get(f'column_color_name_{i}', None)
                templ = self.prefs.get(f'column_color_template_{i}', None)
                if col and templ:
                    try:
                        del self.prefs[f'column_color_name_{i}']
                        rules = migrate_old_rule(self.field_metadata, templ)
                        for templ in rules:
                            old_rules.append((col, templ))
                    except Exception:
                        pass
            if old_rules:
                self.prefs['column_color_rules'] += old_rules  # ty: ignore[unsupported-operator]

        # Migrate saved search and user categories to db preference scheme
        def migrate_preference(key: str, default: object) -> None:
            oldval = prefs[key]
            if oldval != default:
                self.prefs[key] = oldval
                prefs[key] = default
            if key not in self.prefs:
                self.prefs[key] = default

        migrate_preference('user_categories', {})
        migrate_preference('saved_searches', {})

        # migrate grouped_search_terms
        if self.prefs.get('grouped_search_terms', None) is None:
            try:
                ogst = tweaks.get('grouped_search_terms', {})
                ngst = {}
                for t in ogst:
                    ngst[icu_lower(t)] = ogst[t]
                self.prefs.set('grouped_search_terms', ngst)
            except Exception:
                pass

        # migrate the gui_restriction preference to a virtual library
        gr_pref = self.prefs.get('gui_restriction', None)
        if gr_pref:
            virt_libs = self.prefs.get('virtual_libraries', {})
            virt_libs[gr_pref] = 'search:"' + gr_pref + '"'
            self.prefs['virtual_libraries'] = virt_libs
            self.prefs['gui_restriction'] = ''
            self.prefs['virtual_lib_on_startup'] = gr_pref

        # migrate the cs_restriction preference to a virtual library
        gr_pref = self.prefs.get('cs_restriction', None)
        if gr_pref:
            virt_libs = self.prefs.get('virtual_libraries', {})
            virt_libs[gr_pref] = 'search:"' + gr_pref + '"'
            self.prefs['virtual_libraries'] = virt_libs
            self.prefs['cs_restriction'] = ''
            self.prefs['cs_virtual_lib_on_startup'] = gr_pref

        # Rename any user categories with names that differ only in case
        user_cats = self.prefs.get('user_categories', [])
        catmap = {}
        for uc in user_cats:
            ucl = icu_lower(uc)
            if ucl not in catmap:
                catmap[ucl] = []
            catmap[ucl].append(uc)
        cats_changed = False
        for uc, user_cat in catmap.items():
            if len(user_cat) > 1:
                prints('found user category case overlap', user_cat)
                cat = user_cat[0]
                suffix = 1
                while icu_lower(cat + str(suffix)) in catmap:
                    suffix += 1
                prints(f'Renaming user category {cat} to {cat + str(suffix)}')
                user_cats[cat + str(suffix)] = user_cats[cat]
                del user_cats[cat]
                cats_changed = True
        if cats_changed:
            self.prefs.set('user_categories', user_cats)

    # }}}

    def initialize_custom_columns(self) -> None:  # {{{
        self.custom_columns_deleted = False
        self.deleted_fields: list[str] = []
        with self.conn:
            # Delete previously marked custom columns
            for num, label in cast('list[tuple[int, str]]', self.conn.get('SELECT id,label FROM custom_columns WHERE mark_for_delete=1')):
                table, lt = self.custom_table_names(num)
                self.execute(f'''\
                        DROP INDEX   IF EXISTS {table}_idx;
                        DROP INDEX   IF EXISTS {lt}_aidx;
                        DROP INDEX   IF EXISTS {lt}_bidx;
                        DROP TRIGGER IF EXISTS fkc_update_{lt}_a;
                        DROP TRIGGER IF EXISTS fkc_update_{lt}_b;
                        DROP TRIGGER IF EXISTS fkc_insert_{lt};
                        DROP TRIGGER IF EXISTS fkc_delete_{lt};
                        DROP TRIGGER IF EXISTS fkc_insert_{table};
                        DROP TRIGGER IF EXISTS fkc_delete_{table};
                        DROP VIEW    IF EXISTS tag_browser_{table};
                        DROP VIEW    IF EXISTS tag_browser_filtered_{table};
                        DROP TABLE   IF EXISTS {table};
                        DROP TABLE   IF EXISTS {lt};
                        ''')
                self.prefs.set('update_all_last_mod_dates_on_start', True)
                self.deleted_fields.append('#' + label)
            self.execute('DELETE FROM custom_columns WHERE mark_for_delete=1')

        # Load metadata for custom columns
        self.custom_column_label_map, self.custom_column_num_map = {}, {}
        self.custom_column_num_to_label_map: dict[int, str] = {}
        triggers: list[str] = []
        remove: list[CustomColumnData] = []
        custom_tables = self.custom_tables
        for record in cast(
            'list[tuple[str, str, str, int, str, int, int, int]]',
            self.conn.get('SELECT label,name,datatype,editable,display,normalized,id,is_multiple FROM custom_columns'),
        ):
            data: CustomColumnData = {
                'label': record[0],
                'name': record[1],
                'datatype': record[2],
                'editable': bool(record[3]),
                'display': json.loads(record[4]),
                'normalized': bool(record[5]),
                'num': record[6],
                'is_multiple': bool(record[7]),
            }
            if data['display'] is None:
                data['display'] = {}
            # set up the is_multiple separator dict
            if data['is_multiple']:
                if data['display'].get('is_names', False):
                    seps = {'cache_to_list': '|', 'ui_to_list': '&', 'list_to_ui': ' & '}
                elif data['datatype'] == 'composite':
                    seps = {'cache_to_list': ',', 'ui_to_list': ',', 'list_to_ui': ', '}
                else:
                    seps = {'cache_to_list': '|', 'ui_to_list': ',', 'list_to_ui': ', '}
            else:
                seps = {}
            data['multiple_seps'] = seps

            table, lt = self.custom_table_names(data['num'])
            if table not in custom_tables or (data['normalized'] and lt not in custom_tables):
                remove.append(data)
                continue

            self.custom_column_num_map[data['num']] = self.custom_column_label_map[data['label']] = data
            self.custom_column_num_to_label_map[data['num']] = data['label']

            # Create Foreign Key triggers
            if data['normalized']:
                trigger = f'DELETE FROM {lt} WHERE book=OLD.id;'
            else:
                trigger = f'DELETE FROM {table} WHERE book=OLD.id;'
            triggers.append(trigger)

        if remove:
            with self.conn:
                for data in remove:
                    prints('WARNING: Custom column {!r} not found, removing.'.format(data['label']))
                    self.execute('DELETE FROM custom_columns WHERE id=?', (data['num'],))

        if triggers:
            with self.conn:
                self.execute(
                    '''\
                    CREATE TEMP TRIGGER custom_books_delete_trg
                        AFTER DELETE ON books
                        BEGIN
                        {}
                    END;
                    '''.format(' \n'.join(triggers))
                )

        # Setup data adapters
        def adapt_text(x: str | bytes | Iterable[str | bytes] | None, d: CustomColumnData) -> list[str] | str | None:
            if d['is_multiple']:
                if x is None:
                    return []
                if isinstance(x, bytes):
                    x = x.decode(preferred_encoding, 'replace')
                if isinstance(x, str):
                    x = x.split(d['multiple_seps']['ui_to_list'])
                x = [y.strip() for y in x if y.strip()]
                x = [y.decode(preferred_encoding, 'replace') if not isinstance(y, str) else y for y in x]
                return [normalize_whitespace(y) for y in x]
            else:
                return x if x is None or isinstance(x, str) else x.decode(preferred_encoding, 'replace')  # ty: ignore[unresolved-attribute]

        def adapt_datetime(x: str | bytes | datetime | None, d: CustomColumnData) -> datetime | None:
            if isinstance(x, (str, bytes)):
                if isinstance(x, bytes):
                    x = x.decode(preferred_encoding, 'replace')
                x = parse_date(x, assume_utc=False, as_utc=False)
            return x

        def adapt_bool(x: str | bytes | bool | None, d: CustomColumnData) -> bool | None:
            if isinstance(x, (str, bytes)):
                if isinstance(x, bytes):
                    x = x.decode(preferred_encoding, 'replace')
                x = x.lower()
                if x == 'true':
                    x = True
                elif x == 'false':
                    x = False
                elif x == 'none':
                    x = None
                else:
                    x = bool(int(x))
            return x

        def adapt_enum(x: str | bytes | None, d: CustomColumnData) -> list[str] | str | None:
            v = adapt_text(x, d)
            if not v:
                v = None
            return v

        def adapt_number(x: str | bytes | float | None, d: CustomColumnData) -> float | None:
            if x is None:
                return None
            if isinstance(x, (str, bytes)):
                if isinstance(x, bytes):
                    x = x.decode(preferred_encoding, 'replace')
                if x.lower() == 'none':
                    return None
            if d['datatype'] == 'int':
                return int(x)
            return float(x)

        self.custom_data_adapters: dict[str, Callable[..., object]] = {
            'float': adapt_number,
            'int': adapt_number,
            'rating': lambda x, d: x if x is None else min(10.0, max(0.0, float(x))),
            'bool': adapt_bool,
            'comments': lambda x, d: adapt_text(x, {'is_multiple': False}),  # ty: ignore[invalid-argument-type, missing-typed-dict-key]
            'datetime': adapt_datetime,
            'text': adapt_text,
            'series': adapt_text,
            'enumeration': adapt_enum,
        }

        # Create Tag Browser categories for custom columns
        for k in sorted(self.custom_column_label_map):
            v = self.custom_column_label_map[k]
            if v['normalized']:
                is_category = True
            else:
                is_category = False
            is_m = v['multiple_seps']
            tn = 'custom_column_{}'.format(v['num'])
            self.field_metadata.add_custom_field(
                label=v['label'],
                table=tn,
                column='value',
                datatype=v['datatype'],
                colnum=v['num'],
                name=v['name'],
                display=v['display'],
                is_multiple=is_m,
                is_category=is_category,
                is_editable=v['editable'],
                is_csp=False,
            )

    # }}}

    def initialize_tables(self) -> None:  # {{{
        tables = self.tables = {}
        for col in (
            'title',
            'sort',
            'author_sort',
            'series_index',
            'comments',
            'timestamp',
            'pubdate',
            'uuid',
            'path',
            'cover',
            'pages',
            'last_modified',
        ):
            metadata = self.field_metadata[col].copy()
            if col == 'comments':
                metadata['table'], metadata['column'] = 'comments', 'text'
            if not metadata['table']:
                metadata['table'], metadata['column'] = 'books', ('has_cover' if col == 'cover' else col)
            if not metadata['column']:
                metadata['column'] = col
            tables[col] = (PathTable if col == 'path' else UUIDTable if col == 'uuid' else OneToOneTable)(col, metadata)

        for col in ('series', 'publisher'):
            tables[col] = ManyToOneTable(col, self.field_metadata[col].copy())

        for col in ('authors', 'tags', 'formats', 'identifiers', 'languages', 'rating'):
            cls = {
                'authors': AuthorsTable,
                'formats': FormatsTable,
                'identifiers': IdentifiersTable,
                'rating': RatingTable,
            }.get(col, ManyToManyTable)
            tables[col] = cls(col, self.field_metadata[col].copy())

        tables['size'] = SizeTable('size', self.field_metadata['size'].copy())

        self.FIELD_MAP: dict[str | int, int] = {
            'id': 0,
            'title': 1,
            'authors': 2,
            'timestamp': 3,
            'size': 4,
            'rating': 5,
            'tags': 6,
            'comments': 7,
            'series': 8,
            'publisher': 9,
            'series_index': 10,
            'sort': 11,
            'author_sort': 12,
            'formats': 13,
            'path': 14,
            'pubdate': 15,
            'uuid': 16,
            'cover': 17,
            'au_map': 18,
            'last_modified': 19,
            'identifiers': 20,
            'languages': 21,
            'pages': 22,
        }

        for k, v in self.FIELD_MAP.items():
            self.field_metadata.set_field_record_index(k, v, prefer_custom=False)

        base = max(self.FIELD_MAP.values())

        for label_ in sorted(self.custom_column_label_map):
            data = self.custom_column_label_map[label_]
            label = self.field_metadata.custom_field_prefix + label_
            metadata = self.field_metadata[label].copy()
            link_table = self.custom_table_names(data['num'])[1]
            self.FIELD_MAP[data['num']] = base = base + 1
            self.field_metadata.set_field_record_index(label_, base, prefer_custom=True)
            if data['datatype'] == 'series':
                # account for the series index column. Field_metadata knows that
                # the series index is one larger than the series. If you change
                # it here, be sure to change it there as well.
                self.FIELD_MAP[str(data['num']) + '_index'] = base = base + 1
                self.field_metadata.set_field_record_index(label_ + '_index', base, prefer_custom=True)

            if data['normalized']:
                if metadata['is_multiple']:
                    tables[label] = ManyToManyTable(label, metadata, link_table=link_table)
                else:
                    tables[label] = ManyToOneTable(label, metadata, link_table=link_table)
                    if metadata['datatype'] == 'series':
                        # Create series index table
                        label += '_index'
                        metadata = self.field_metadata[label].copy()
                        metadata['column'] = 'extra'
                        metadata['table'] = link_table
                        tables[label] = OneToOneTable(label, metadata)
            elif data['datatype'] == 'composite':
                tables[label] = CompositeTable(label, metadata)
            else:
                tables[label] = OneToOneTable(label, metadata)

        self.FIELD_MAP['ondevice'] = base = base + 1
        self.field_metadata.set_field_record_index('ondevice', base, prefer_custom=False)
        self.FIELD_MAP['marked'] = base = base + 1
        self.field_metadata.set_field_record_index('marked', base, prefer_custom=False)
        self.FIELD_MAP['series_sort'] = base = base + 1
        self.field_metadata.set_field_record_index('series_sort', base, prefer_custom=False)
        self.FIELD_MAP['in_tag_browser'] = base = base + 1
        self.field_metadata.set_field_record_index('in_tag_browser', base, prefer_custom=False)

    # }}}

    def initialize_notes(self) -> None:
        from .notes.connect import Notes

        self.notes = Notes(self)

    def clear_notes_for_category_items(self, field_name: str, item_map: Mapping[int, str | None]) -> None:
        for item_id, item_val in item_map.items():
            self.notes.set_note(self.conn, field_name, item_id, item_val or '')

    def delete_category_items(
        self, field_name: str, table_name: str, item_map: Mapping[int, str | None], link_table_name: str = '', link_col_name: str = ''
    ) -> None:
        self.clear_notes_for_category_items(field_name, item_map)
        bindings = tuple((x,) for x in item_map)
        if link_table_name and link_col_name:
            self.executemany(f'DELETE FROM {link_table_name} WHERE {link_col_name}=?', bindings)
        self.executemany(f'DELETE FROM {table_name} WHERE id=?', bindings)

    def rename_category_item(
        self,
        field_name: str,
        table_name: str,
        link_table_name: str,
        link_col_name: str,
        old_item_id: int,
        new_item_id: int,
        new_item_value: str | None,
    ) -> None:
        self.notes.rename_note(self.conn, field_name, old_item_id, new_item_id, new_item_value or '')
        # For custom series this means that the series index can
        # potentially have duplicates/be incorrect, but there is no way to
        # handle that in this context.
        self.execute(
            f'UPDATE {link_table_name} SET {link_col_name}=? WHERE {link_col_name}=?; DELETE FROM {table_name} WHERE id=?',
            (new_item_id, old_item_id, old_item_id),
        )

    def notes_for(self, field_name: str, item_id: int) -> str:
        return self.notes.get_note(self.conn, field_name, item_id) or ''

    def notes_data_for(self, field_name: str, item_id: int) -> NoteData | None:
        return self.notes.get_note_data(self.conn, field_name, item_id)

    def get_all_items_that_have_notes(self, field_name: str | None) -> set[int] | dict[str, set[int]]:
        return self.notes.get_all_items_that_have_notes(self.conn, field_name)

    def set_notes_for(self, field: str, item_id: int, doc: str, searchable_text: str, resource_hashes: Collection[str], remove_unused_resources: bool) -> int:
        id_val = cast('ManyToOneTable', self.tables[field]).id_map[item_id]
        note_id = self.notes.set_note(self.conn, field, item_id, id_val, doc, resource_hashes, searchable_text)
        if remove_unused_resources:
            self.notes.remove_unreferenced_resources(self.conn)
        return note_id

    def unretire_note_for(self, field: str, item_id: int) -> int:
        id_val = cast('ManyToOneTable', self.tables[field]).id_map[item_id]
        return self.notes.unretire(self.conn, field, item_id, id_val)

    def add_notes_resource(self, path_or_stream: str | bytes | IO[bytes], name: str, mtime: float | None = None) -> str:
        return self.notes.add_resource(self.conn, path_or_stream, name, mtime=mtime)

    def get_notes_resource(self, resource_hash: str) -> JSONDict | None:
        return self.notes.get_resource_data(self.conn, resource_hash)

    def notes_resources_used_by(self, field: str, item_id: int) -> Iterator[str]:
        conn = self.conn
        note_id = self.notes.note_id_for(conn, field, item_id)
        if note_id is not None:
            yield from self.notes.resources_used_by(conn, note_id)

    def unretire_note(self, field: str, item_id: int, item_val: str) -> int:
        return self.notes.unretire(self.conn, field, item_id, item_val)

    def search_notes(
        self,
        fts_engine_query: str,
        use_stemming: bool,
        highlight_start: str | None,
        highlight_end: str | None,
        snippet_size: int | None,
        restrict_to_fields: tuple[str, ...],
        return_text: bool,
        process_each_result: Callable[[NotesSearchResult], NotesSearchResult] | None,
        limit: int | None,
    ) -> Generator[NotesSearchResult, bool | None]:
        yield from self.notes.search(
            self.conn,
            fts_engine_query,
            use_stemming,
            highlight_start,
            highlight_end,
            snippet_size,
            restrict_to_fields,
            return_text,
            process_each_result,
            limit,
        )

    def export_notes_data(self, outfile: str | IO[bytes]) -> None:
        import zipfile

        with zipfile.ZipFile(outfile, mode='w') as zf:
            pt = PersistentTemporaryFile()
            try:
                pt.close()
                self.backup_notes_database(pt.name)
                with open(pt.name, 'rb') as dbf:
                    zf.writestr('notes.db', dbf.read())
            finally:
                try:
                    os.remove(pt.name)
                except OSError:
                    if not iswindows:
                        raise
                    time.sleep(1)
                    os.remove(pt.name)
            self.notes.export_non_db_data(zf)

    def restore_notes(self, report_progress: Callable[[str | None, int], object]) -> list[str]:
        return self.notes.restore(self.conn, self.tables, report_progress)

    def import_note(self, field: str, item_id: int, html: str | bytes, basedir: str, ctime: float | None, mtime: float | None) -> int:
        id_val = cast('ManyToOneTable', self.tables[field]).id_map[item_id]
        return self.notes.import_note(self.conn, field, item_id, id_val, html, basedir, ctime, mtime)  # ty: ignore[invalid-argument-type]

    def export_note(self, field: str, item_id: int) -> str:
        return self.notes.export_note(self.conn, field, item_id)

    def initialize_fts(self, dbref: ref[Cache] | None) -> FTS | None:
        self.fts = None
        if not self.prefs['fts_enabled']:
            return
        from .fts.connect import FTS

        self.fts = FTS(dbref)  # ty: ignore[invalid-argument-type]
        return self.fts

    def enable_fts(self, dbref: ref[Cache] | None = None) -> FTS | None:
        enabled = dbref is not None
        self.prefs['fts_enabled'] = enabled
        self.initialize_fts(dbref)
        if self.fts is not None:
            self.fts.dirty_existing()
        return self.fts

    @property
    def fts_enabled(self) -> bool:
        return getattr(self, 'fts', None) is not None

    @property
    def fts_has_idle_workers(self) -> bool:
        if not self.fts_enabled:
            return False
        assert self.fts is not None
        return self.fts.pool.num_of_idle_workers > 0

    @property
    def fts_num_of_workers(self) -> int:
        if not self.fts_enabled:
            return 0
        assert self.fts is not None
        return self.fts.pool.num_of_workers

    @fts_num_of_workers.setter
    def fts_num_of_workers(self, num: int) -> None:
        if self.fts_enabled:
            assert self.fts is not None
            self.fts.pool.num_of_workers = num

    def get_next_fts_job(self) -> tuple[int, str] | tuple[None, None]:
        assert self.fts is not None
        return self.fts.get_next_fts_job()

    def reindex_fts(self) -> None:
        if self.conn.fts_dbpath:
            self.conn.execute('DETACH fts_db')
            os.remove(self.conn.fts_dbpath)
            self.conn.fts_dbpath = None

    def remove_dirty_fts(self, book_id: int, fmt: str) -> None:
        assert self.fts is not None
        return self.fts.remove_dirty(book_id, fmt)

    def queue_fts_job(self, book_id: int, fmt: str, path: str, fmt_size: int, fmt_hash: str, start_time: float) -> bool:
        assert self.fts is not None
        return self.fts.queue_job(book_id, fmt, path, fmt_size, fmt_hash, start_time)

    def commit_fts_result(self, book_id: int, fmt: str, fmt_size: int, fmt_hash: str, text: str, err_msg: str) -> None:
        if self.fts is not None:
            return self.fts.commit_result(book_id, fmt, fmt_size, fmt_hash, text, err_msg)

    def fts_unindex(self, book_id: int, fmt: str | None = None) -> None:
        assert self.fts is not None
        self.fts.unindex(book_id, fmt=fmt)

    def reindex_fts_book(self, book_id: int, *fmts: str) -> None:
        assert self.fts is not None
        return self.fts.dirty_book(book_id, *fmts)

    def fts_search(
        self,
        fts_engine_query: str,
        use_stemming: bool,
        highlight_start: str | None,
        highlight_end: str | None,
        snippet_size: int | None,
        restrict_to_book_ids: Collection[int] | None,
        return_text: bool,
        process_each_result: Callable[[FTSSearchResult], FTSSearchResult] | None,
    ) -> Generator[FTSSearchResult, bool | None]:
        assert self.fts is not None
        yield from self.fts.search(
            fts_engine_query,
            use_stemming,
            highlight_start,
            highlight_end,
            snippet_size,
            restrict_to_book_ids,
            return_text,
            process_each_result,
        )

    def shutdown_fts(self) -> None:
        if self.fts_enabled:
            assert self.fts is not None
            self.fts.shutdown()

    def join_fts(self) -> None:
        if self.fts:
            self.fts.pool.join()
            self.fts = None

    def get_connection(self) -> Connection:
        return self.conn

    @property
    def conn(self) -> Connection:
        if self._conn is None:
            self._conn = Connection(self.dbpath)
            self.is_closed = False
            if self._exists and self.user_version == 0:
                self._conn.close()
                os.remove(self.dbpath)
                self._conn = Connection(self.dbpath)
        return self._conn

    def execute(self, sql: str, bindings: Bindings | None = None) -> apsw.Cursor:
        try:
            return self.conn.cursor().execute(sql, bindings)
        except apsw.IOError:
            # This can happen if the computer was suspended see for example:
            # https://bugs.launchpad.net/bugs/1286522. Try to reopen the db
            if not self.conn.getautocommit():
                raise  # We are in a transaction, re-opening the db will fail anyway
            self.reopen(force=True)
            return self.conn.cursor().execute(sql, bindings)

    def executemany(self, sql: str, sequence_of_bindings: Iterable[Bindings]) -> apsw.Cursor:  # ty: ignore[invalid-return-type]
        try:
            with self.conn:  # Disable autocommit mode, for performance
                return self.conn.cursor().executemany(sql, sequence_of_bindings)
        except apsw.IOError:
            # This can happen if the computer was suspended see for example:
            # https://bugs.launchpad.net/bugs/1286522. Try to reopen the db
            if not self.conn.getautocommit():
                raise  # We are in a transaction, re-opening the db will fail anyway
            self.reopen(force=True)
            with self.conn:  # Disable autocommit mode, for performance
                return self.conn.cursor().executemany(sql, sequence_of_bindings)

    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[True] = True) -> list[SQLiteValues]: ...
    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: Literal[False]) -> SQLiteValue: ...
    @overload
    def get(self, sql: str, bindings: Bindings | None = None, /, *, all: bool) -> list[SQLiteValues] | SQLiteValue: ...
    def get(self, *args: str | Bindings | None, **kw: bool) -> list[SQLiteValues] | SQLiteValue:
        ans = self.execute(*args)  # ty: ignore[invalid-argument-type]
        if kw.get('all', True):
            return ans.fetchall()
        try:
            return next(ans)[0]
        except StopIteration, IndexError:
            return None

    def last_insert_rowid(self) -> int:
        return self.conn.last_insert_rowid()

    def custom_field_name(self, label: str | None = None, num: int | None = None) -> str:
        if label is not None:
            return self.field_metadata.custom_field_prefix + label
        return self.field_metadata.custom_field_prefix + self.custom_column_num_to_label_map[num]  # ty: ignore[invalid-argument-type]

    def custom_field_metadata(self, label: str | None = None, num: int | None = None) -> CustomColumnData:
        if label is not None:
            return self.custom_column_label_map[label]
        return self.custom_column_num_map[num]  # ty: ignore[invalid-argument-type]

    def set_custom_column_metadata(
        self, num: int, name: str | None = None, label: str | None = None, is_editable: bool | None = None, display: JSONDict | None = None
    ) -> bool:
        changed = False
        if name is not None:
            self.execute('UPDATE custom_columns SET name=? WHERE id=?', (name, num))
            changed = True
        if label is not None:
            old_label = cast('str | None', self.conn.get('SELECT label FROM custom_columns WHERE id=?', (num,), all=False))
            self.execute('UPDATE custom_columns SET label=? WHERE id=?', (label, num))
            changed = True
            if old_label is not None and old_label != label:
                self.notes.rename_field(self.conn, '#' + old_label, '#' + label)
        if is_editable is not None:
            self.execute('UPDATE custom_columns SET editable=? WHERE id=?', (bool(is_editable), num))
            self.custom_column_num_map[num]['editable'] = bool(is_editable)
            changed = True
        if display is not None:
            self.execute('UPDATE custom_columns SET display=? WHERE id=?', (json.dumps(display), num))
            changed = True
        # Note: the caller is responsible for scheduling a metadata backup if necessary
        return changed

    def create_custom_column(
        self, label: str, name: str, datatype: str, is_multiple: bool, editable: bool = True, display: JSONDict | None = None
    ) -> int:  # {{{
        import re

        if display is None:
            display = {}
        if not label:
            raise ValueError(_('No label was provided'))
        if re.match(r'^\w*$', label) is None or not label[0].isalpha() or label.lower() != label:
            raise ValueError(_('The label must contain only lower case letters, digits and underscores, and start with a letter'))
        if datatype not in CUSTOM_DATA_TYPES:
            raise ValueError(f'{datatype!r} is not a supported data type')
        normalized = datatype not in ('datetime', 'comments', 'int', 'bool', 'float', 'composite')
        is_multiple = is_multiple and datatype in ('text', 'composite')
        self.execute(
            ('INSERT INTO custom_columns(label,name,datatype,is_multiple,editable,display,normalized)VALUES (?,?,?,?,?,?,?)'),
            (label, name, datatype, is_multiple, editable, json.dumps(display), normalized),
        )
        num = self.conn.last_insert_rowid()

        if datatype in ('rating', 'int'):
            dt = 'INT'
        elif datatype in ('text', 'comments', 'series', 'composite', 'enumeration'):
            dt = 'TEXT'
        elif datatype == 'float':
            dt = 'REAL'
        elif datatype == 'datetime':
            dt = 'timestamp'
        elif datatype == 'bool':
            dt = 'BOOL'
        collate = 'COLLATE NOCASE' if dt == 'TEXT' else ''
        table, lt = self.custom_table_names(num)
        if normalized:
            if datatype == 'series':
                s_index = 'extra REAL,'
            else:
                s_index = ''
            lines = [
                f'''\
                CREATE TABLE {table}(
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    value {dt} NOT NULL {collate},
                    link TEXT NOT NULL DEFAULT "",
                    UNIQUE(value));
                ''',
                f'CREATE INDEX {table}_idx ON {table} (value {collate});',
                f'''\
                CREATE TABLE {lt}(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book INTEGER NOT NULL,
                    value INTEGER NOT NULL,
                    {s_index}
                    UNIQUE(book, value)
                    );''',
                f'CREATE INDEX {lt}_aidx ON {lt} (value);',
                f'CREATE INDEX {lt}_bidx ON {lt} (book);',
                f'''\
                CREATE TRIGGER fkc_update_{lt}_a
                        BEFORE UPDATE OF book ON {lt}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                            END;
                        END;
                CREATE TRIGGER fkc_update_{lt}_b
                        BEFORE UPDATE OF author ON {lt}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from {table} WHERE id=NEW.value) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: value not in {table}')
                            END;
                        END;
                CREATE TRIGGER fkc_insert_{lt}
                        BEFORE INSERT ON {lt}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                                WHEN (SELECT id from {table} WHERE id=NEW.value) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: value not in {table}')
                            END;
                        END;
                CREATE TRIGGER fkc_delete_{lt}
                        AFTER DELETE ON {table}
                        BEGIN
                            DELETE FROM {lt} WHERE value=OLD.id;
                        END;

                CREATE VIEW tag_browser_{table} AS SELECT
                    id,
                    value,
                    (SELECT COUNT(id) FROM {lt} WHERE value={table}.id) count,
                    (SELECT AVG(r.rating)
                     FROM {lt},
                          books_ratings_link as bl,
                          ratings as r
                     WHERE {lt}.value={table}.id and bl.book={lt}.book and
                           r.id = bl.rating and r.rating <> 0) avg_rating,
                    value AS sort
                FROM {table};

                CREATE VIEW tag_browser_filtered_{table} AS SELECT
                    id,
                    value,
                    (SELECT COUNT({lt}.id) FROM {lt} WHERE value={table}.id AND
                    books_list_filter(book)) count,
                    (SELECT AVG(r.rating)
                     FROM {lt},
                          books_ratings_link as bl,
                          ratings as r
                     WHERE {lt}.value={table}.id AND bl.book={lt}.book AND
                           r.id = bl.rating AND r.rating <> 0 AND
                           books_list_filter(bl.book)) avg_rating,
                    value AS sort
                FROM {table};

                ''',
            ]
        else:
            lines = [
                f'''\
                CREATE TABLE {table}(
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    book  INTEGER,
                    value {dt} NOT NULL {collate},
                    UNIQUE(book));
                ''',
                f'CREATE INDEX {table}_idx ON {table} (book);',
                f'''\
                CREATE TRIGGER fkc_insert_{table}
                        BEFORE INSERT ON {table}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                            END;
                        END;
                CREATE TRIGGER fkc_update_{table}
                        BEFORE UPDATE OF book ON {table}
                        BEGIN
                            SELECT CASE
                                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
                            END;
                        END;
                ''',
            ]
        script = ' \n'.join(lines)
        self.execute(script)
        self.prefs.set('update_all_last_mod_dates_on_start', True)
        return num

    # }}}

    def delete_custom_column(self, label: str | None = None, num: int | None = None) -> None:
        data = self.custom_field_metadata(label, num)
        self.execute('UPDATE custom_columns SET mark_for_delete=1 WHERE id=?', (data['num'],))
        self.notes.delete_field(self.conn, '#' + data['label'])

    def close(self, force: bool = True, unload_formatter_functions: bool = True) -> None:
        if getattr(self, '_conn', None) is not None:
            if self.prefs['expire_old_trash_after'] == 0:
                self.expire_old_trash(0)
            if unload_formatter_functions:
                try:
                    unload_user_template_functions(self.library_id)
                except Exception:
                    pass
            assert self._conn is not None
            self._conn.close(force)
            del self._conn
            self.is_closed = True

    def reopen(self, force: bool = True) -> None:
        self.close(force=force, unload_formatter_functions=False)
        self._conn = None
        self.conn  # ruff: ignore[useless-expression] # Connect to refresh
        self.notes.reopen(self)

    def dump_and_restore(self, callback: Callable[[str], object] | None = None, sql: str | bytes | None = None) -> None:
        from apsw import Shell  # type: ignore

        if callback is None:

            def callback(x: str) -> str:
                return x

        uv = int(self.user_version)

        with TemporaryFile(suffix='.sql') as fname:
            if sql is None:
                callback(_('Dumping database to SQL') + '...')
                with open(fname, 'w', encoding='utf-8') as buf:
                    shell = Shell(db=self.conn, stdout=buf)
                    shell.process_command('.dump')
            else:
                with open(fname, 'wb') as buf:
                    buf.write(sql if isinstance(sql, bytes) else sql.encode('utf-8'))

            with TemporaryFile(suffix='_tmpdb.db', dir=os.path.dirname(self.dbpath)) as tmpdb:
                callback(_('Restoring database from SQL') + '...')
                with closing(Connection(tmpdb)) as conn:
                    shell = Shell(db=conn, encoding='utf-8')
                    shell.process_command('.read ' + fname.replace(os.sep, '/'))
                    conn.execute(f'PRAGMA user_version={uv};')

                self.close(unload_formatter_functions=False)
                try:
                    atomic_rename(tmpdb, self.dbpath)
                finally:
                    self.reopen()

    def vacuum(self, include_fts_db: bool, include_notes_db: bool, rebuild_annotations_fts: bool) -> None:
        self.execute('VACUUM')
        if rebuild_annotations_fts:
            self.execute('INSERT INTO annotations_fts(annotations_fts) VALUES("rebuild");')
            self.execute('INSERT INTO annotations_fts_stemmed(annotations_fts_stemmed) VALUES("rebuild");')
        if self.fts_enabled and include_fts_db:
            assert self.fts is not None
            self.fts.vacuum()
        if include_notes_db:
            self.notes.vacuum(self.conn)

    @property
    def user_version(self) -> int:
        """The user version of this database"""
        return cast('int', self.conn.get('PRAGMA user_version;', all=False))

    @user_version.setter
    def user_version(self, val: int) -> None:
        self.execute(f'PRAGMA user_version={int(val)}')

    def initialize_database(self) -> None:
        metadata_sqlite = P('metadata_sqlite.sql', data=True, allow_user_override=False).decode('utf-8')
        with self.conn:
            self.conn.cursor().execute(metadata_sqlite)
            if self.user_version == 0:
                self.user_version = 1

    # }}}

    def __enter__(self) -> None:
        self.conn.__enter__()

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, tb: TracebackType | None) -> None:
        self.conn.__exit__(exc_type, exc_value, tb)

    def clone_for_readonly_access(self, dest_dir: str) -> str:
        dbpath = os.path.abspath(self.conn.db_filename('main'))
        clone_db_path = os.path.join(dest_dir, os.path.basename(dbpath))
        shutil.copy2(dbpath, clone_db_path)
        notes_dir = os.path.join(os.path.dirname(dbpath), NOTES_DIR_NAME)
        if os.path.exists(notes_dir):
            shutil.copytree(notes_dir, os.path.join(dest_dir, NOTES_DIR_NAME))
        return clone_db_path

    def normpath(self, path: str) -> str:
        path = os.path.abspath(os.path.realpath(path))
        if not self.is_case_sensitive:
            path = os.path.normcase(path).lower()
        return path

    def is_deletable(self, path: str) -> str | bool:
        return path and not self.normpath(self.library_path).startswith(self.normpath(path))

    def rmtree(self, path: str) -> None:
        if self.is_deletable(path):
            rmtree_with_retry(path)

    def construct_path_name(self, book_id: int | str, title: str, author: str) -> str:
        """
        Construct the directory name for this book based on its metadata.
        """
        book_id = BOOK_ID_PATH_TEMPLATE.format(book_id)
        l = self.PATH_LIMIT - (len(book_id) // 2) - 2
        author = ascii_filename(author)[:l]
        title = ascii_filename(title.lstrip())[:l].rstrip()
        if not title:
            title = 'Unknown'[:l]
        try:
            while author[-1] in (' ', '.'):
                author = author[:-1]
        except IndexError:
            author = ''
        if not author:
            author = ascii_filename(_('Unknown'))
        if author.upper() in WINDOWS_RESERVED_NAMES:
            author += 'w'
        return f'{author}/{title}{book_id}'

    def construct_file_name(self, book_id: int, title: str, author: str, extlen: int) -> str:
        """
        Construct the file name for this book based on its metadata.
        """
        extlen = max(extlen, 14)  # 14 accounts for ORIGINAL_EPUB
        # The PATH_LIMIT on windows already takes into account the doubling
        # (it is used to enforce the total path length limit, individual path
        # components can be much longer than the total path length would allow on
        # windows).
        l = (self.PATH_LIMIT - (extlen // 2) - 2) if iswindows else ((self.PATH_LIMIT - extlen - 2) // 2)
        if l < 5:
            raise ValueError(f'Extension length too long: {extlen}')
        author = ascii_filename(author)[:l]
        title = ascii_filename(title.lstrip())[:l].rstrip()
        if not title:
            title = 'Unknown'[:l]
        name = title + ' - ' + author
        while name.endswith('.'):
            name = name[:-1]
        if not name:
            name = ascii_filename(_('Unknown'))
        return name

    # Database layer API {{{

    def custom_table_names(self, num: int) -> tuple[str, str]:
        return f'custom_column_{num}', f'books_custom_column_{num}_link'

    @property
    def custom_tables(self) -> set[str]:
        return {
            x[0]
            for x in cast(
                'list[tuple[str]]',
                self.conn.get("SELECT name FROM sqlite_master WHERE type='table' AND (name GLOB 'custom_column_*' OR name GLOB 'books_custom_column_*')"),
            )
        }

    @classmethod
    def exists_at(cls, path: str | None) -> str | bool | None:
        return path and os.path.exists(os.path.join(path, 'metadata.db'))

    @property
    def library_id(self) -> str:
        """The UUID for this library. As long as the user only operates  on libraries with calibre, it will be unique"""

        if getattr(self, '_library_id_', None) is None:
            ans = cast('str | None', self.conn.get('SELECT uuid FROM library_id', all=False))
            if ans is None:
                ans = str(uuid.uuid4())
                self.library_id = ans
            else:
                self._library_id_ = ans
        return self._library_id_

    @library_id.setter
    def library_id(self, val: object) -> None:
        self._library_id_ = str(val)
        self.execute(
            '''
                DELETE FROM library_id;
                INSERT INTO library_id (uuid) VALUES (?);
                ''',
            (self._library_id_,),
        )

    def last_modified(self) -> datetime:
        """Return last modified time as a UTC datetime object"""
        return utcfromtimestamp(os.stat(self.dbpath).st_mtime)

    def read_tables(self) -> None:
        """
        Read all data from the db into the python in-memory tables
        """

        # Reading creates many long lived container objects, none of which are
        # garbage. Their number grows with the size of the library, and with
        # the cyclic garbage collector enabled it repeatedly traverses all of
        # them, which is slow in larger libraries.
        with self.conn, stop_gc:  # Use a single transaction, to ensure nothing modifies the db while we are reading
            books_columns = tuple(t for t in self.tables.values() if isinstance(t, OneToOneTable) and t.is_books_table_column)
            already_read: set[DBTable] = set(books_columns) if read_books_table_columns(self, books_columns) else set()
            # The size table is read from the scan of the data table done by
            # the formats table, so it must be read after it
            size_table = self.tables['size']
            already_read.add(size_table)
            for table in self.tables.values():
                if table not in already_read:
                    self._read_table(table, table.read, self)
            self._read_table(size_table, self._read_size_table)

    def _read_size_table(self) -> None:
        size_table = cast('SizeTable', self.tables['size'])
        if not size_table.read_from_formats(self.tables['uuid'].book_col_map, cast('FormatsTable', self.tables['formats'])):
            size_table.read(self)

    def _read_table(self, table: DBTable, read: Callable[..., None], *args: DB) -> None:
        try:
            read(*args)
        except Exception:
            prints('Failed to read table:', table.name)
            import pprint

            pprint.pprint(table.metadata)
            raise

    def find_path_for_book(self, book_id: int) -> str | None:
        q = BOOK_ID_PATH_TEMPLATE.format(book_id)
        for author_dir in os.scandir(self.library_path):
            if not author_dir.is_dir():
                continue
            try:
                book_dir_iter = os.scandir(author_dir.path)
            except OSError:
                pass
            else:
                for book_dir in book_dir_iter:
                    if book_dir.name.endswith(q) and book_dir.is_dir():
                        return book_dir.path

    def format_abspath(self, book_id: int, fmt: str, fname: str, book_path: str, do_file_rename: bool = True) -> str | None:
        path = os.path.join(self.library_path, book_path)
        fmt = ('.' + fmt.lower()) if fmt else ''
        fmt_path = os.path.join(path, fname + fmt)
        if os.path.exists(fmt_path):
            return fmt_path
        if not fmt:
            return
        q = fmt.lower()
        try:
            candidates = os.scandir(path)
        except OSError:
            return
        with candidates:
            for x in candidates:
                if x.name.endswith(q) and x.is_file() and not x.name.startswith('._'):
                    if not do_file_rename:
                        return x.path
                    x = x.path
                    with suppress(OSError):
                        atomic_rename(x, fmt_path)
                        return fmt_path
                    try:
                        shutil.move(x, fmt_path)
                    except shutil.SameFileError, OSError:
                        # some other process synced in the file since the last
                        # os.path.exists()
                        return x
                    return fmt_path

    def cover_abspath(self, book_id: int, path: str) -> str | None:
        path = os.path.join(self.library_path, path)
        fmt_path = os.path.join(path, COVER_FILE_NAME)
        if os.path.exists(fmt_path):
            return fmt_path

    def is_path_inside_book_dir(self, path: str, book_relpath: str, sub_path: str) -> bool:
        book_path = os.path.abspath(os.path.join(self.library_path, book_relpath, sub_path))
        return is_path_inside(book_path, path, case_sensitive=self.is_case_sensitive)

    def apply_to_format[T](self, book_id: int, path: str, fname: str, fmt: str, func: Callable[[BinaryIO], T], missing_value: T | None = None) -> T | None:
        path = self.format_abspath(book_id, fmt, fname, path)  # ty: ignore[invalid-assignment]
        if path is None:
            return missing_value
        with open(path, 'r+b') as f:
            return func(f)

    def format_hash(self, book_id: int, fmt: str, fname: str, path: str) -> str:
        path = self.format_abspath(book_id, fmt, fname, path)  # ty: ignore[invalid-assignment]
        if path is None:
            raise NoSuchFormat(f'Record {book_id} has no fmt: {fmt}')
        sha = hashlib.sha256()
        with open(path, 'rb') as f:
            while True:
                raw = f.read(SPOOL_SIZE)
                sha.update(raw)
                if len(raw) < SPOOL_SIZE:
                    break
        return sha.hexdigest()

    def format_metadata(self, book_id: int, fmt: str, fname: str, path: str) -> FormatMetadata:
        path = self.format_abspath(book_id, fmt, fname, path)  # ty: ignore[invalid-assignment]
        ans: FormatMetadata = {}
        if path is not None:
            stat = os.stat(path)
            ans['path'] = path
            ans['size'] = stat.st_size
            ans['mtime'] = utcfromtimestamp(stat.st_mtime)
        return ans

    def has_format(self, book_id: int, fmt: str, fname: str, path: str) -> bool:
        return self.format_abspath(book_id, fmt, fname, path) is not None

    def is_format_accessible(self, book_id: int, fmt: str, fname: str, path: str) -> str | bool | None:
        fpath = self.format_abspath(book_id, fmt, fname, path)
        return fpath and os.access(fpath, os.R_OK | os.W_OK)

    def rename_format_file(self, book_id: int, src_fname: str, src_fmt: str, dest_fname: str, dest_fmt: str, path: str) -> int:
        src_path = self.format_abspath(book_id, src_fmt, src_fname, path)
        if src_path is None:
            raise NoSuchFormat(f'Record {book_id} has no fmt: {src_fmt}')
        dest_path = self.format_abspath(book_id, dest_fmt, dest_fname, path)
        if not dest_path:
            dest_path = os.path.join(self.library_path, path, dest_fname + '.' + dest_fmt.lower())
        atomic_rename(src_path, dest_path)
        return os.path.getsize(dest_path)

    def remove_formats(self, remove_map: Mapping[int, Iterable[tuple[str, str, str]]], metadata_map: Mapping[int, JSONDict]) -> dict[int, set[str]]:
        self.ensure_trash_dir()
        removed_map: dict[int, set[str]] = {}
        for book_id, removals in remove_map.items():
            paths = set()
            removed_map[book_id] = set()
            for fmt, fname, path in removals:
                path = self.format_abspath(book_id, fmt, fname, path)
                if path:
                    paths.add(path)
                    removed_map[book_id].add(fmt.upper())
            if paths:
                self.move_book_files_to_trash(book_id, paths, metadata_map[book_id])
        return removed_map

    def cover_last_modified(self, path: str) -> datetime | None:
        path = os.path.abspath(os.path.join(self.library_path, path, COVER_FILE_NAME))
        try:
            return utcfromtimestamp(os.stat(path).st_mtime)
        except OSError:
            pass  # Cover doesn't exist

    def copy_cover_to(
        self,
        path: str,
        dest: str | SupportsWrite[bytes],
        windows_atomic_move: WindowsAtomicFolderMove | None = None,
        use_hardlink: bool = False,
        report_file_size: Callable[[int], object] | None = None,
    ) -> bool:
        path = os.path.abspath(os.path.join(self.library_path, path, COVER_FILE_NAME))
        if windows_atomic_move is not None:
            if not isinstance(dest, (str, bytes)):
                raise Exception('Error, you must pass the dest as a path when using windows_atomic_move')
            if os.access(path, os.R_OK) and dest and not samefile(dest, path):  # ty: ignore[invalid-argument-type]
                windows_atomic_move.copy_path_to(path, dest)  # ty: ignore[invalid-argument-type]
                return True
        elif os.access(path, os.R_OK):
            with open_with_retry(path, 0.2) as f:
                if hasattr(dest, 'write'):
                    if report_file_size is not None:
                        f.seek(0, os.SEEK_END)
                        report_file_size(f.tell())
                        f.seek(0)
                    shutil.copyfileobj(f, dest)  # ty: ignore[invalid-argument-type]
                    if hasattr(dest, 'flush'):
                        dest.flush()  # ty: ignore[call-non-callable]
                    return True
                elif dest and not samefile(dest, path):
                    if use_hardlink:
                        try:
                            hardlink_file(path, dest)
                            return True
                        except Exception:
                            pass
                    with open(dest, 'wb') as d:
                        shutil.copyfileobj(f, d)
                    return True
        return False

    def cover_or_cache(self, path: str, timestamp: float, as_what: str = 'bytes') -> tuple[bool, bytes | Image | None, float | None]:
        path = os.path.abspath(os.path.join(self.library_path, path, COVER_FILE_NAME))
        try:
            stat = os.stat(path)
        except OSError:
            return False, None, None
        if abs(timestamp - stat.st_mtime) < 0.1:
            return True, None, None
        with open_with_retry(path, 0.2) as f:
            if as_what == 'pil_image':
                from PIL import Image

                data = Image.open(f)
                data.load()
            else:
                data = f.read()
        return True, data, stat.st_mtime

    def cover_timestamp(self, path: str) -> float | None:
        path = os.path.abspath(os.path.join(self.library_path, path, COVER_FILE_NAME))
        try:
            stat = os.stat(path)
        except OSError:
            return None
        return stat.st_mtime

    def compress_covers(self, path_map: Mapping[int, str], jpeg_quality: int, progress_callback: Callable[[int, int, int | str], object] | None) -> None:
        cpath_map: dict[int, tuple[str, int]] = {}
        if not progress_callback:

            def progress_callback(book_id: int, old_sz: int, new_sz: int | str) -> None:
                return None

        for book_id, path in path_map.items():
            path = os.path.abspath(os.path.join(self.library_path, path, COVER_FILE_NAME))
            try:
                sz = os.path.getsize(path)
            except OSError:
                progress_callback(book_id, 0, 'ENOENT')
            else:
                cpath_map[book_id] = (path, sz)
        from calibre.db.covers import compress_covers

        compress_covers(cpath_map, jpeg_quality, progress_callback)

    def set_cover(self, book_id: int, path: str, data: bytes | QImage | QPixmap | IO[bytes] | None, no_processing: bool = False) -> None:
        path = os.path.abspath(os.path.join(self.library_path, path))
        if not os.path.exists(path):
            os.makedirs(path)
        path = os.path.join(path, COVER_FILE_NAME)
        if callable(getattr(data, 'save', None)):
            from calibre.gui2 import pixmap_to_data

            data = pixmap_to_data(data)
        elif callable(getattr(data, 'read', None)):
            data = data.read()  # ty: ignore[unresolved-attribute]
        if data is None:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    if iswindows:
                        time.sleep(0.2)
                    os.remove(path)
        elif no_processing:
            with open(path, 'wb') as f:
                f.write(data)  # ty: ignore[invalid-argument-type]
        else:
            from calibre.utils.img import save_cover_data_to

            try:
                save_cover_data_to(data, path)  # ty: ignore[no-matching-overload]
            except OSError:
                if iswindows:
                    time.sleep(0.2)
                save_cover_data_to(data, path)  # ty: ignore[no-matching-overload]

    def copy_format_to(
        self,
        book_id: int,
        fmt: str,
        fname: str,
        path: str,
        dest: str | SupportsWrite[bytes],
        windows_atomic_move: WindowsAtomicFolderMove | None = None,
        use_hardlink: bool = False,
        report_file_size: Callable[[int], object] | None = None,
    ) -> bool:
        path = self.format_abspath(book_id, fmt, fname, path)  # ty: ignore[invalid-assignment]
        if path is None:
            return False
        if windows_atomic_move is not None:
            if not isinstance(dest, (str, bytes)):
                raise Exception('Error, you must pass the dest as a path when using windows_atomic_move')
            if dest:
                if samefile(dest, path):  # ty: ignore[invalid-argument-type]
                    # Ensure that the file has the same case as dest
                    try:
                        if path != dest:
                            os.rename(path, dest)
                    except Exception:
                        pass  # Nothing too catastrophic happened, the cases mismatch, that's all
                else:
                    windows_atomic_move.copy_path_to(path, dest)  # ty: ignore[invalid-argument-type]
        elif hasattr(dest, 'write'):
            with open(path, 'rb') as f:
                if report_file_size is not None:
                    f.seek(0, os.SEEK_END)
                    report_file_size(f.tell())
                    f.seek(0)
                shutil.copyfileobj(f, dest)  # ty: ignore[invalid-argument-type]
            if hasattr(dest, 'flush'):
                dest.flush()  # ty: ignore[call-non-callable]
        elif dest:
            if samefile(dest, path):
                if not self.is_case_sensitive and path != dest:
                    # Ensure that the file has the same case as dest
                    try:
                        os.rename(path, dest)
                    except OSError:
                        pass  # Nothing too catastrophic happened, the cases mismatch, that's all
            else:
                if use_hardlink:
                    try:
                        hardlink_file(path, dest)
                        return True
                    except Exception:
                        pass
                shutil.copyfile(path, make_long_path_useable(dest))
        return True

    def windows_check_if_files_in_use(self, paths: Iterable[str]) -> None:
        """
        Raises an EACCES IOError if any of the files in the specified folders
        are opened in another program on windows.
        """
        if iswindows:
            for path in paths:
                spath = os.path.join(self.library_path, *path.split('/'))
                if os.path.exists(spath):
                    windows_check_if_files_in_use(spath)

    def add_format(
        self,
        book_id: int,
        fmt: str,
        stream: str | IO[bytes],
        title: str,
        author: str,
        path: str,
        current_name: str | None,
        mtime: float | None = None,
    ) -> tuple[int, str]:
        fmt = ('.' + fmt.lower()) if fmt else ''
        fname = self.construct_file_name(book_id, title, author, len(fmt))
        path = os.path.join(self.library_path, path)
        dest = os.path.join(path, fname + fmt)
        if not os.path.exists(path):
            os.makedirs(path)
        size = 0
        if current_name is not None:
            old_path = os.path.join(path, current_name + fmt)
            if old_path != dest:
                # Ensure that the old format file is not orphaned, this can
                # happen if the algorithm in construct_file_name is changed.
                try:
                    # rename rather than remove, so that if something goes
                    # wrong in the rest of this function, at least the file is
                    # not deleted
                    os.replace(old_path, dest)
                except OSError as e:
                    if getattr(e, 'errno', None) != errno.ENOENT:
                        # Failing to rename the old format will at worst leave a
                        # harmless orphan, so log and ignore the error
                        import traceback

                        traceback.print_exc()

        if isinstance(stream, str):
            if not stream:
                raise ValueError(f'No file specified for the {fmt} format of book {book_id}')
            replace_with_retry(stream, dest)
            size = os.path.getsize(dest)
        elif not getattr(stream, 'name', False) or not samefile(dest, stream.name):
            size = write_stream_to_format_file(stream, dest)
            if mtime is not None:
                os.utime(dest, (mtime, mtime))
        elif os.path.exists(dest):
            size = os.path.getsize(dest)
            if mtime is not None:
                os.utime(dest, (mtime, mtime))

        return size, fname

    def update_path(self, book_id: int, title: str, author: str, path_field: Field, formats_field: FormatsField) -> None:
        current_path = cast('str', path_field.for_book(book_id, default_value=''))
        path = self.construct_path_name(book_id, title, author)
        formats = cast('tuple[str, ...]', formats_field.for_book(book_id, default_value=()))
        try:
            extlen = max(len(fmt) for fmt in formats) + 1
        except ValueError:
            extlen = 10
        fname = self.construct_file_name(book_id, title, author, extlen)

        def rename_format_files() -> bool:
            changed = False
            for fmt in formats:
                name = formats_field.format_fname(book_id, fmt)
                if name and name != fname:
                    changed = True
                    break
            if changed:
                rename_map: dict[str, str] = {}
                for fmt in formats:
                    current_fname = formats_field.format_fname(book_id, fmt)
                    current_fmt_path = self.format_abspath(book_id, fmt, current_fname, current_path, do_file_rename=False)
                    if current_fmt_path:
                        new_fmt_path = os.path.abspath(os.path.join(os.path.dirname(current_fmt_path), fname + '.' + fmt.lower()))
                        if current_fmt_path != new_fmt_path:
                            rename_map[current_fmt_path] = new_fmt_path
                if rename_map:
                    rename_files(rename_map)
            return changed

        def update_paths_in_db() -> None:
            with self.conn:
                for fmt in formats:
                    formats_field.table.set_fname(book_id, fmt, fname, self)
                cast('PathTable', path_field.table).set_path(book_id, path, self)

        if not current_path:
            update_paths_in_db()
            return

        if path == current_path:
            # Only format paths have possibly changed
            if rename_format_files():
                update_paths_in_db()
            return

        spath = os.path.join(self.library_path, *current_path.split('/'))
        tpath = os.path.join(self.library_path, *path.split('/'))
        if samefile(spath, tpath):
            # format paths changed and case of path to book folder changed
            rename_format_files()
            update_paths_in_db()
            curpath = self.library_path
            c1, c2 = current_path.split('/'), path.split('/')
            if not self.is_case_sensitive and len(c1) == len(c2):
                # On case-insensitive systems, title and author renames that only
                # change case don't cause any changes to the directories in the file
                # system. This can lead to having the directory names not match the
                # title/author, which leads to trouble when libraries are copied to
                # a case-sensitive system. The following code attempts to fix this
                # by checking each segment. If they are different because of case,
                # then rename the segment. Note that the code above correctly
                # handles files in the directories, so no need to do them here.
                for oldseg, newseg in zip(c1, c2):
                    if oldseg.lower() == newseg.lower() and oldseg != newseg:
                        try:
                            os.replace(os.path.join(curpath, oldseg), os.path.join(curpath, newseg))
                        except OSError:
                            break  # Fail silently since nothing catastrophic has happened
                    curpath = os.path.join(curpath, newseg)
            return

        with suppress(FileNotFoundError):
            self.rmtree(tpath)

        lfmts = tuple(fmt.lower() for fmt in formats)
        existing_format_filenames: dict[str, str] = {}
        for fmt in lfmts:
            current_fname = formats_field.format_fname(book_id, fmt)
            current_fmt_path = self.format_abspath(book_id, fmt, current_fname, current_path, do_file_rename=False)
            if current_fmt_path:
                existing_format_filenames[os.path.basename(current_fmt_path)] = fmt

        def transform_format_filenames(src_path: str, dest_path: str) -> str:
            src_dir, src_filename = os.path.split(os.path.abspath(src_path))
            if src_dir != spath:
                return dest_path
            fmt = existing_format_filenames.get(src_filename)
            if not fmt:
                return dest_path
            return os.path.join(os.path.dirname(dest_path), fname + '.' + fmt)

        if os.path.exists(spath):
            copy_tree(
                os.path.abspath(spath),
                tpath,
                delete_source=True,
                transform_destination_filename=transform_format_filenames,
            )
            parent = os.path.dirname(spath)
            with suppress(OSError):
                remove_dir_if_empty(parent, ignore_metadata_caches=True)
        else:
            os.makedirs(tpath)
        update_paths_in_db()

    def copy_extra_file_to(self, book_id: int, book_path: str, relpath: str, stream_or_path: str | SupportsWrite[bytes]) -> None:
        full_book_path = os.path.abspath(os.path.join(self.library_path, book_path))
        try:
            extra_file_path = path_from_root(full_book_path, relpath, case_sensitive=self.is_case_sensitive)
        except ValueError:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), relpath)
        src_path = make_long_path_useable(extra_file_path)
        if isinstance(stream_or_path, str):
            shutil.copy2(src_path, make_long_path_useable(stream_or_path))
        else:
            with open(src_path, 'rb') as src:
                shutil.copyfileobj(src, stream_or_path)

    @overload
    def iter_extra_files(
        self, book_id: int, book_path: str, formats_field: FormatsField, yield_paths: Literal[False] = False, pattern: str = ''
    ) -> Iterator[tuple[str, BinaryIO, os.stat_result]]: ...
    @overload
    def iter_extra_files(
        self, book_id: int, book_path: str, formats_field: FormatsField, yield_paths: Literal[True], pattern: str = ''
    ) -> Iterator[tuple[str, str, os.stat_result]]: ...
    def iter_extra_files(
        self, book_id: int, book_path: str, formats_field: FormatsField, yield_paths: bool = False, pattern: str = ''
    ) -> Iterator[tuple[str, str | BinaryIO, os.stat_result]]:
        known_files = {COVER_FILE_NAME, METADATA_FILE_NAME}
        if '/' not in pattern:
            for fmt in cast('tuple[str, ...]', formats_field.for_book(book_id, default_value=())):
                fname = formats_field.format_fname(book_id, fmt)
                fpath = self.format_abspath(book_id, fmt, fname, book_path, do_file_rename=False)
                if fpath:
                    known_files.add(os.path.basename(fpath))
        full_book_path = os.path.abspath(os.path.join(self.library_path, book_path))
        if pattern:
            from pathlib import Path

            try:
                path_from_root(full_book_path, pattern, case_sensitive=self.is_case_sensitive)
            except ValueError:
                return

            def iterator() -> Iterator[str]:
                p = Path(full_book_path)
                for x in p.glob(pattern):
                    path = str(x)
                    if is_path_inside(full_book_path, path, case_sensitive=self.is_case_sensitive):
                        yield path

        else:

            def iterator() -> Iterator[str]:
                for dirpath, dirnames, filenames in os.walk(full_book_path):
                    for fname in filenames:
                        path = os.path.join(dirpath, fname)
                        yield path

        for path in iterator():
            if os.access(path, os.R_OK):
                relpath = os.path.relpath(path, full_book_path)
                relpath = relpath.replace(os.sep, '/')
                if relpath not in known_files:
                    try:
                        stat_result = os.stat(path)
                    except OSError:
                        continue
                    if stat.S_ISDIR(stat_result.st_mode):
                        continue
                    if yield_paths:
                        yield relpath, path, stat_result
                    else:
                        with open_with_retry(path, 1) as src:
                            yield relpath, src, stat_result

    def remove_extra_files(self, book_path: str, relpaths: Iterable[str], permanent: bool) -> dict[str, Exception | None]:
        bookdir = os.path.join(self.library_path, book_path)
        errors: dict[str, Exception | None] = {}
        for relpath in relpaths:
            try:
                path = path_from_root(bookdir, relpath, case_sensitive=self.is_case_sensitive)
            except ValueError:
                continue
            try:
                if permanent:
                    try:
                        os.remove(make_long_path_useable(path))
                    except FileNotFoundError:
                        pass
                    except Exception:
                        if not iswindows:
                            raise
                        time.sleep(1)
                        os.remove(make_long_path_useable(path))
                else:
                    from calibre.utils.recycle_bin import recycle

                    assert recycle is not None
                    recycle(make_long_path_useable(path))
            except Exception as e:
                import traceback

                traceback.print_exc()
                errors[relpath] = e
        return errors

    def rename_extra_file(self, relpath: str, newrelpath: str, book_path: str, replace: bool = True) -> bool:
        bookdir = os.path.join(self.library_path, book_path)
        try:
            src = path_from_root(bookdir, relpath, case_sensitive=self.is_case_sensitive)
            dest = path_from_root(bookdir, newrelpath, case_sensitive=self.is_case_sensitive)
        except ValueError:
            return False
        src, dest = make_long_path_useable(src), make_long_path_useable(dest)
        if src == dest or not os.path.exists(src):
            return False
        if not replace and os.path.exists(dest) and not os.path.samefile(src, dest):
            return False
        try:
            os.replace(src, dest)
        except FileNotFoundError:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.replace(src, dest)
        return True

    def add_extra_file(self, relpath: str, stream: str | IO[bytes], book_path: str, replace: bool = True, auto_rename: bool = False) -> str | None:
        bookdir = os.path.join(self.library_path, book_path)
        try:
            dest = path_from_root(bookdir, relpath, case_sensitive=self.is_case_sensitive)
        except ValueError:
            return None
        if not replace and os.path.exists(make_long_path_useable(dest)):
            if not auto_rename:
                return None
            dirname, basename = os.path.split(dest)
            num = 0
            while True:
                mdir = 'merge conflict'
                if num:
                    mdir += f' {num}'
                candidate = os.path.join(dirname, mdir, basename)
                if not os.path.exists(make_long_path_useable(candidate)):
                    dest = candidate
                    break
                num += 1
        ldest = make_long_path_useable(dest)
        os.makedirs(os.path.dirname(ldest), exist_ok=True)
        # Do not destroy an existing file if reading the source fails part way
        if isinstance(stream, str):
            src = make_long_path_useable(stream)
            with open(src, 'rb') as f:
                write_stream_to_format_file(f, ldest)
            shutil.copystat(src, ldest)  # as shutil.copy2() does
        else:
            write_stream_to_format_file(stream, ldest)
        return os.path.relpath(dest, bookdir).replace(os.sep, '/')

    def write_backup(self, path: str, raw: bytes) -> None:
        path = os.path.abspath(os.path.join(self.library_path, path, METADATA_FILE_NAME))
        try:
            with open(path, 'wb') as f:
                f.write(raw)
        except OSError:
            exc_info = sys.exc_info()
            try:
                os.makedirs(os.path.dirname(path))
            except OSError as err:
                if err.errno == errno.EEXIST:
                    # Parent directory already exists, re-raise original exception
                    reraise(*exc_info)
                raise
            finally:
                del exc_info
            with open(path, 'wb') as f:
                f.write(raw)

    def read_backup(self, path: str) -> bytes:
        path = os.path.abspath(os.path.join(self.library_path, path, METADATA_FILE_NAME))
        with open(path, 'rb') as f:
            return f.read()

    @property
    def trash_dir(self) -> str:
        return os.path.abspath(os.path.join(self.library_path, TRASH_DIR_NAME))

    def clear_trash_dir(self) -> None:
        tdir = self.trash_dir
        if os.path.exists(tdir):
            self.rmtree(tdir)
            self.ensure_trash_dir()

    def ensure_trash_dir(self, during_init: bool = False) -> None:
        tdir = self.trash_dir
        os.makedirs(os.path.join(tdir, 'b'), exist_ok=True)
        os.makedirs(os.path.join(tdir, 'f'), exist_ok=True)
        if iswindows:
            from calibre_extensions import winutil

            winutil.set_file_attributes(tdir, winutil.FILE_ATTRIBUTE_HIDDEN | winutil.FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
        if time.time() - self.last_expired_trash_at >= 3600:
            self.expire_old_trash(during_init=during_init)

    def delete_trash_entry(self, book_id: int, category: str) -> None:
        self.ensure_trash_dir()
        path = os.path.join(self.trash_dir, category, str(book_id))
        if os.path.exists(path):
            self.rmtree(path)

    def expire_old_trash(self, expire_age_in_seconds: float = -1, during_init: bool = False) -> None:
        if expire_age_in_seconds < 0:
            expire_age_in_seconds = max(1 * 24 * 3600, float(cast('float', self.prefs['expire_old_trash_after'])))
        self.last_expired_trash_at = now = time.time()
        removals = []
        for base in ('b', 'f'):
            base = os.path.join(self.trash_dir, base)
            for x in os.scandir(base):
                if x.is_dir(follow_symlinks=False):
                    try:
                        st = x.stat(follow_symlinks=False)
                        mtime = st.st_mtime
                    except OSError:
                        mtime = 0
                    if mtime + expire_age_in_seconds <= now or expire_age_in_seconds <= 0:
                        removals.append(make_long_path_useable(x.path))
        for x in removals:
            try:
                rmtree_with_retry(x)  # during init we dont want to slow down because of windows mandatory file locking
            except OSError:
                if not during_init:
                    raise
                import traceback

                traceback.print_exc()

    def move_book_to_trash(self, book_id: int, book_dir_abspath: str) -> None:
        dest = os.path.join(self.trash_dir, 'b', str(book_id))
        if os.path.exists(dest):
            rmtree_with_retry(dest)
        try:
            copy_tree(book_dir_abspath, dest, delete_source=True)
        except SourceDeletionFailed:
            raise  # dest is a complete copy of the book
        except Exception:
            # Nothing was deleted from the book folder, remove the incomplete
            # copy so that it cannot be restored from the trash
            try:
                rmtree_with_retry(dest)
            except Exception:
                import traceback

                prints(f'Failed to remove incomplete trash entry: {dest}')
                traceback.print_exc()
            raise

    def move_book_files_to_trash(self, book_id: int, format_abspaths: Iterable[str], metadata: JSONDict) -> None:
        dest = os.path.join(self.trash_dir, 'f', str(book_id))
        if not os.path.exists(dest):
            os.makedirs(dest)
        fmap = {}
        for path in format_abspaths:
            ext = path.rpartition('.')[-1].lower()
            fmap[path] = os.path.join(dest, ext)
        atomic_write(os.path.join(dest, 'metadata.json'), json.dumps(metadata).encode('utf-8'))
        copy_files(fmap, delete_source=True)

    def get_metadata_for_trash_book(self, book_id: int, read_annotations: bool = True) -> tuple[Metadata, tuple[JSONDict, ...], list[tuple[str, int, str]]]:
        from .restore import read_opf

        bdir = os.path.join(self.trash_dir, 'b', str(book_id))
        if not os.path.isdir(bdir):
            raise ValueError(f'The book {book_id} not present in the trash folder')
        mi, _, annotations = read_opf(bdir, read_annotations=read_annotations)
        formats = []
        for x in os.scandir(bdir):
            if x.is_file() and x.name not in (COVER_FILE_NAME, METADATA_FILE_NAME) and '.' in x.name:
                try:
                    size = x.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
                fname, ext = os.path.splitext(x.name)
                formats.append((ext[1:].upper(), size, fname))
        return mi, annotations, formats

    def move_book_from_trash(self, book_id: int, path: str) -> None:
        bdir = os.path.join(self.trash_dir, 'b', str(book_id))
        if not os.path.isdir(bdir):
            raise ValueError(f'The book {book_id} not present in the trash folder')
        dest = os.path.abspath(os.path.join(self.library_path, path))
        copy_tree(bdir, dest, delete_source=True)

    def copy_book_from_trash(self, book_id: int, dest: str) -> None:
        bdir = os.path.join(self.trash_dir, 'b', str(book_id))
        if not os.path.isdir(bdir):
            raise ValueError(f'The book {book_id} not present in the trash folder')
        copy_tree(bdir, dest, delete_source=False)

    def path_for_trash_format(self, book_id: int, fmt: str) -> str:
        bdir = os.path.join(self.trash_dir, 'f', str(book_id))
        if not os.path.isdir(bdir):
            return ''
        path = os.path.join(bdir, fmt.lower())
        if not os.path.exists(path):
            path = ''
        return path

    def remove_trash_formats_dir_if_empty(self, book_id: int) -> None:
        bdir = os.path.join(self.trash_dir, 'f', str(book_id))
        if os.path.isdir(bdir) and len(os.listdir(bdir)) <= 1:  # don't count metadata.json
            self.rmtree(bdir)

    def list_trash_entries(self) -> tuple[list[TrashEntry], list[TrashEntry]]:
        from calibre.ebooks.metadata.opf2 import OPF

        self.ensure_trash_dir()
        books: list[TrashEntry]
        files: list[TrashEntry]
        books, files = [], []
        base = os.path.join(self.trash_dir, 'b')
        unknown = _('Unknown')
        au = (unknown,)
        for x in os.scandir(base):
            if x.is_dir(follow_symlinks=False):
                try:
                    book_id = int(x.name)
                    mtime = x.stat(follow_symlinks=False).st_mtime
                    with open(make_long_path_useable(os.path.join(x.path, METADATA_FILE_NAME)), 'rb') as opf_stream:
                        opf = OPF(opf_stream, basedir=x.path)
                except Exception:
                    import traceback

                    traceback.print_exc()
                    continue
                books.append(
                    TrashEntry(
                        book_id,
                        opf.title or unknown,
                        (opf.authors or au)[0],
                        os.path.join(x.path, COVER_FILE_NAME),
                        mtime,
                    )
                )
        base = os.path.join(self.trash_dir, 'f')
        um = {'title': unknown, 'authors': au}
        for x in os.scandir(base):
            if x.is_dir(follow_symlinks=False):
                try:
                    book_id = int(x.name)
                    mtime = x.stat(follow_symlinks=False).st_mtime
                except Exception:
                    continue
                formats = set()
                metadata = um
                for f in os.scandir(x.path):
                    if f.is_file(follow_symlinks=False):
                        if f.name == 'metadata.json':
                            try:
                                with open(f.path, 'rb') as mf:
                                    metadata = json.loads(mf.read())
                            except Exception:
                                import traceback

                                traceback.print_exc()
                                continue
                        else:
                            formats.add(f.name.upper())
                if formats:
                    ttitle: str = str(metadata.get('title') or unknown)
                    files.append(TrashEntry(book_id, ttitle, (metadata.get('authors') or au)[0], '', mtime, tuple(formats)))
        return books, files

    def remove_books(self, path_map: Mapping[int, str | None], permanent: bool = False) -> dict[int, str]:
        """
        Delete the folders of the specified books (or move them to the trash)
        and remove the books from the database. A book whose folder could not be
        deleted or moved is left in the database. Returns a map of book id to
        error details for such books.
        """
        import traceback

        self.ensure_trash_dir()
        removed: list[int]
        failures: dict[int, str]
        removed, failures = [], {}
        parent_paths: set[str] = set()
        for book_id, path in path_map.items():
            if path:
                path = os.path.abspath(os.path.join(self.library_path, path))
                if os.path.exists(path) and self.is_deletable(path):
                    try:
                        self.rmtree(path) if permanent else self.move_book_to_trash(book_id, path)
                    except SourceDeletionFailed:
                        # The book is safely in the trash, only some leftover
                        # files could not be removed from the library folder
                        prints(f'Book {book_id} was moved to the trash but some files were left behind in: {path}')
                        traceback.print_exc()
                    except Exception:
                        failures[book_id] = traceback.format_exc()
                        continue
                    parent_paths.add(os.path.dirname(path))
            removed.append(book_id)
        self.executemany('DELETE FROM books WHERE id=?', [(x,) for x in removed])
        for path in parent_paths:
            remove_dir_if_empty(path, ignore_metadata_caches=True)
        return failures

    def add_custom_data(self, name: str, val_map: Mapping[int, object], delete_first: bool) -> None:
        # Serialize before changing anything, and delete and insert in one transaction, so that a failure cannot lose the old data
        rows = [(book_id, name, json.dumps(val, default=to_json)) for book_id, val in val_map.items()]
        with self.conn:
            if delete_first:
                self.execute('DELETE FROM books_plugin_data WHERE name=?', (name,))
            self.executemany('INSERT OR REPLACE INTO books_plugin_data (book, name, val) VALUES (?, ?, ?)', rows)

    def get_custom_book_data(self, name: str, book_ids: Iterable[int], default: object = None) -> dict[int, object]:
        book_ids = frozenset(book_ids)

        def safe_load(val: str) -> object:
            try:
                return json.loads(val, object_hook=from_json)
            except Exception:
                return default

        if len(book_ids) == 1:
            bid = next(iter(book_ids))
            ans = {book_id: safe_load(val) for book_id, val in self.execute('SELECT book, val FROM books_plugin_data WHERE book=? AND name=?', (bid, name))}
            return ans or {bid: default}

        ans: dict[int, object] = {}
        for book_id, val in self.execute('SELECT book, val FROM books_plugin_data WHERE name=?', (name,)):
            if not book_ids or book_id in book_ids:
                val = safe_load(val)
                ans[book_id] = val
        return ans

    def delete_custom_book_data(self, name: str, book_ids: Collection[int]) -> None:
        if book_ids:
            self.executemany('DELETE FROM books_plugin_data WHERE book=? AND name=?', [(book_id, name) for book_id in book_ids])
        else:
            self.execute('DELETE FROM books_plugin_data WHERE name=?', (name,))

    def dirtied_books(self) -> Iterator[int]:
        for (book_id,) in self.execute('SELECT book FROM metadata_dirtied'):
            yield book_id

    def dirty_books(self, book_ids: Iterable[int]) -> None:
        self.executemany('INSERT OR IGNORE INTO metadata_dirtied (book) VALUES (?)', ((x,) for x in book_ids))

    def mark_book_as_clean(self, book_id: int) -> None:
        self.execute('DELETE FROM metadata_dirtied WHERE book=?', (book_id,))

    def get_ids_for_custom_book_data(self, name: str) -> frozenset[int]:
        return frozenset(r[0] for r in self.execute('SELECT book FROM books_plugin_data WHERE name=?', (name,)))

    def annotations_for_book(self, book_id: int, fmt: str, user_type: str, user: str) -> Iterator[JSONDict]:
        yield from annotations_for_book(self.conn, book_id, fmt, user_type, user)

    def save_annotations_list(self, book_id: int, book_fmt: str, sync_annots_user: str, alist: Iterable[tuple[JSONDict, float]]) -> None:
        conn = self.conn
        with conn:
            save_annotations_list_to_cursor(conn.cursor(), alist, sync_annots_user, book_id, book_fmt)

    def book_storage_for_book(self, book_id: int, fmt: str, user_type: str, user: str) -> BookStorageEntry | None:
        return book_storage_for_book(self.conn, book_id, fmt, user_type, user)

    def update_book_storage_for_book(self, book_id: int, fmt: str, entry: BookStorageEntry, user_type: str, user: str) -> BookStorageEntry:  # ty: ignore[invalid-return-type]
        with self.conn:
            return update_book_storage_for_book(self.conn.cursor(), book_id, fmt, entry, user_type, user)

    def save_book_storage(self, book_id: int, book_fmt: str, sync_annots_user: str, entry: BookStorageEntry) -> None:
        with self.conn:
            save_book_storage_to_cursor(self.conn.cursor(), entry, sync_annots_user, book_id, book_fmt)

    def search_annotations(
        self,
        fts_engine_query: str,
        use_stemming: bool,
        highlight_start: str | None,
        highlight_end: str | None,
        snippet_size: int | None,
        annotation_type: str | None,
        restrict_to_book_ids: Container[int] | None,
        restrict_to_user: tuple[str, str] | None,
        ignore_removed: bool = False,
        annotation_style: Mapping[str, object] | None = None,
    ) -> Iterator[JSONDict]:
        fts_engine_query = unicode_normalize(fts_engine_query)
        fts_table = 'annotations_fts_stemmed' if use_stemming else 'annotations_fts'
        text = 'annotations.searchable_text'
        data: list[str] = []
        if highlight_start is not None and highlight_end is not None:
            if snippet_size is not None:
                text = f"snippet({fts_table}, 0, ?, ?, '…', {max(1, min(snippet_size, 64))})"
            else:
                text = f'highlight({fts_table}, 0, ?, ?)'
            data.append(highlight_start)
            data.append(highlight_end)
        query = 'SELECT {0}.id, {0}.book, {0}.format, {0}.user_type, {0}.user, {0}.annot_data, {1} FROM {0} '
        query = query.format('annotations', text)
        query += f' JOIN {fts_table} ON annotations.id = {fts_table}.rowid'
        query += f' WHERE {fts_table} MATCH ?'
        data.append(fts_engine_query)
        if restrict_to_user:
            query += ' AND annotations.user_type = ? AND annotations.user = ?'
            data += list(restrict_to_user)
        if annotation_type:
            query += ' AND annotations.annot_type = ? '
            data.append(annotation_type)
        query += f' ORDER BY {fts_table}.rank '
        ls = json.loads
        query_style = None if annotation_style is None else tuple(annotation_style.items())
        sentinel = object()
        try:
            for rowid, book_id, fmt, user_type, user, annot_data, text in self.execute(query, tuple(data)):
                if restrict_to_book_ids is not None and book_id not in restrict_to_book_ids:
                    continue
                try:
                    parsed_annot = ls(annot_data)
                except Exception:
                    continue
                if ignore_removed and parsed_annot.get('removed'):
                    continue
                if query_style is not None and ((s := parsed_annot.get('style')) is None or not all(s.get(k, sentinel) == v for k, v in query_style)):
                    continue
                yield {
                    'id': rowid,
                    'book_id': book_id,
                    'format': fmt,
                    'user_type': user_type,
                    'user': user,
                    'text': text,
                    'annotation': parsed_annot,
                }
        except apsw.SQLError as e:
            raise FTSQueryError(fts_engine_query, query, e)

    def all_annotations_for_book(self, book_id: int, ignore_removed: bool = False) -> Iterator[JSONDict]:
        for fmt, user_type, user, data in self.execute('SELECT format, user_type, user, annot_data FROM annotations WHERE book=?', (book_id,)):
            try:
                annot = json.loads(data)
            except Exception:
                continue
            if not ignore_removed or not annot.get('removed'):
                yield {'format': fmt, 'user_type': user_type, 'user': user, 'annotation': annot}

    def book_ids_for_annotations(self, annot_ids: Iterable[int], ignore_removed: bool = False) -> dict[int, int]:
        ans: dict[int, int] = {}
        annot_ids = tuple(annot_ids)
        for i in range(0, len(annot_ids), 500):
            chunk = annot_ids[i : i + 500]
            q = 'SELECT id, book, annot_data FROM annotations WHERE id IN ({})'.format(','.join('?' * len(chunk)))
            for annot_id, book_id, data in self.execute(q, chunk):
                if ignore_removed:
                    try:
                        removed = json.loads(data).get('removed')
                    except Exception:
                        removed = False  # corrupted annotations can still be deleted
                    if removed:
                        continue
                ans[annot_id] = book_id
        return ans

    def delete_annotations(self, annot_ids: Iterable[int]) -> None:
        replacements: list[tuple[str, float, int]] = []
        removals: list[tuple[int]] = []
        now = utcnow()
        ts = now.isoformat()
        timestamp = (now - EPOCH).total_seconds()
        for annot_id in annot_ids:
            for raw_annot_data, annot_type in self.execute('SELECT annot_data, annot_type FROM annotations WHERE id=?', (annot_id,)):
                try:
                    annot_data = json.loads(raw_annot_data)
                except Exception:
                    removals.append((annot_id,))
                    continue
                now = utcnow()
                new_annot: JSONDict = {'removed': True, 'timestamp': ts, 'type': annot_type}
                uuid = annot_data.get('uuid')
                if uuid is not None:
                    new_annot['uuid'] = uuid
                else:
                    new_annot['title'] = annot_data['title']
                replacements.append((json.dumps(new_annot), timestamp, annot_id))
        if replacements:
            self.executemany("UPDATE annotations SET annot_data=?, timestamp=?, searchable_text='' WHERE id=?", replacements)
        if removals:
            self.executemany('DELETE FROM annotations WHERE id=?', removals)

    def update_annotations(self, annot_id_map: Mapping[int, JSONDict]) -> None:
        now = utcnow()
        ts = now.isoformat()
        timestamp = (now - EPOCH).total_seconds()
        with self.conn:
            for annot_id, annot in annot_id_map.items():
                atype = annot['type']
                aid, text = annot_db_data(annot)
                if aid is not None:
                    annot['timestamp'] = ts
                    self.execute(
                        'UPDATE annotations SET annot_data=?, timestamp=?, annot_type=?, searchable_text=?, annot_id=? WHERE id=?',
                        (json.dumps(annot), timestamp, atype, text, aid, annot_id),
                    )

    def all_annotations(
        self,
        restrict_to_user: tuple[str, str] | None = None,
        limit: int | None = None,
        annotation_type: str | None = None,
        annotation_style: Mapping[str, object] | None = None,
        ignore_removed: bool = False,
        restrict_to_book_ids: Container[int] | None = None,
    ) -> Iterator[JSONDict]:
        ls = json.loads
        q = 'SELECT id, book, format, user_type, user, annot_data FROM annotations'
        data: list[str] = []
        restrict_clauses: list[str] = []
        if restrict_to_user is not None:
            data.extend(restrict_to_user)
            restrict_clauses.append(' user_type = ? AND user = ?')
        if annotation_type:
            data.append(annotation_type)
            restrict_clauses.append(' annot_type = ? ')
        if restrict_clauses:
            q += ' WHERE ' + ' AND '.join(restrict_clauses)
        q += ' ORDER BY timestamp DESC '
        count = 0
        query_style = None if annotation_style is None else tuple(annotation_style.items())
        sentinel = object()
        for rowid, book_id, fmt, user_type, user, annot_data in self.execute(q, tuple(data)):
            if restrict_to_book_ids is not None and book_id not in restrict_to_book_ids:
                continue
            try:
                annot = ls(annot_data)
                atype = annot['type']
            except Exception:
                continue
            if ignore_removed and annot.get('removed'):
                continue
            text = ''
            if atype == 'bookmark':
                text = annot['title']
            elif atype == 'highlight':
                if query_style is not None and ((s := annot.get('style')) is None or not all(s.get(k, sentinel) == v for k, v in query_style)):
                    continue
                text = annot.get('highlighted_text') or ''
            yield {
                'id': rowid,
                'book_id': book_id,
                'format': fmt,
                'user_type': user_type,
                'user': user,
                'text': text,
                'annotation': annot,
            }
            count += 1
            if limit is not None and count >= limit:
                break

    def all_annotation_users(self) -> apsw.Cursor:
        return self.execute('SELECT DISTINCT user_type, user FROM annotations')

    def all_annotation_types(self) -> Iterator[str]:
        for x in self.execute('SELECT DISTINCT annot_type FROM annotations'):
            yield x[0]

    def all_annotation_styles(self) -> dict[str, JSONDict]:
        all_styles = [{'kind': 'color', 'which': style} for style in builtin_colors_light.keys()] + [
            {'kind': 'decoration', 'which': style} for style in builtin_decorations.keys()
        ]
        ans = {style['which']: style for style in all_styles}
        # Merge in custom highlight styles found in the database.  Custom
        # styles are stored as JSON inside the annot_data column with
        # 'type': 'custom' and a 'friendly_name' key.  We scan the DB to
        # discover them, since they are not part of the built-in set.
        try:
            for (raw_annot_data,) in self.execute(
                "SELECT annot_data FROM annotations WHERE json_extract(annot_data, '$.style.type') = 'custom' AND json_extract(annot_data, '$.removed') IS NULL"
            ):
                try:
                    style = json.loads(raw_annot_data).get('style')
                except Exception:
                    continue
                if style is not None and isinstance(style, dict):
                    name = style.get('friendly_name') or style.get('which')
                    if name and name not in ans:
                        ans[name] = style
        except Exception:
            # Best-effort: if the query fails (e.g. schema mismatch) just
            # return the built-in styles.
            pass
        return ans

    def set_annotations_for_book(
        self, book_id: int, fmt: str, annots_list: Iterable[tuple[JSONDict, float]], user_type: str = 'local', user: str = 'viewer'
    ) -> None:
        try:
            with self.conn:  # Disable autocommit mode, for performance
                save_annotations_for_book(self.conn.cursor(), book_id, fmt, annots_list, user_type, user)
        except apsw.IOError:
            # This can happen if the computer was suspended see for example:
            # https://bugs.launchpad.net/bugs/1286522. Try to reopen the db
            if not self.conn.getautocommit():
                raise  # We are in a transaction, re-opening the db will fail anyway
            self.reopen(force=True)
            with self.conn:  # Disable autocommit mode, for performance
                save_annotations_for_book(self.conn.cursor(), book_id, fmt, annots_list, user_type, user)

    def dirty_books_with_dirtied_annotations(self) -> bool:
        with self.conn:
            self.execute('INSERT or IGNORE INTO metadata_dirtied(book) SELECT book FROM annotations_dirtied;')
            changed = self.conn.changes() > 0
            if changed:
                self.execute('DELETE FROM annotations_dirtied')
        return changed

    def annotation_count_for_book(self, book_id: int) -> int:
        for (count,) in self.execute(
            '''
                 SELECT count(id) FROM annotations
                 WHERE book=? AND json_extract(annot_data, '$.removed') IS NULL
                 ''',
            (book_id,),
        ):
            return count
        return 0

    def reindex_annotations(self) -> None:
        self.execute(
            '''
            INSERT INTO {0}({0}) VALUES('rebuild');
            INSERT INTO {1}({1}) VALUES('rebuild');
        '''.format('annotations_fts', 'annotations_fts_stemmed')
        )

    def set_last_read_position(
        self,
        book_id: int,
        fmt: str,
        user: str = '_',
        device: str = '_',
        cfi: str | None = None,
        epoch: float | None = None,
        pos_frac: float = 0,
    ) -> None:
        save_last_read_position_to_cursor(self.conn.cursor(), book_id, fmt, user, device, cfi, epoch, pos_frac)

    def conversion_options(self, book_id: int, fmt: str) -> bytes | None:
        for (data,) in cast(
            'list[tuple[bytes | None]]', self.conn.get('SELECT data FROM conversion_options WHERE book=? AND format=?', (book_id, fmt.upper()))
        ):
            if data:
                try:
                    return unpickle_binary_string(bytes(data))
                except Exception:
                    pass

    def has_conversion_options(self, ids: Iterable[int], fmt: str = 'PIPE') -> bool:  # ty: ignore[invalid-return-type]
        ids = frozenset(ids)
        with self.conn:
            self.execute('DROP TABLE IF EXISTS conversion_options_temp; CREATE TEMP TABLE conversion_options_temp (id INTEGER PRIMARY KEY);')
            self.executemany('INSERT INTO conversion_options_temp VALUES (?)', [(x,) for x in ids])
            for (book_id,) in self.conn.get(
                'SELECT book FROM conversion_options WHERE format=? AND book IN (SELECT id FROM conversion_options_temp)',
                (fmt.upper(),),
            ):
                return True
            return False

    def delete_conversion_options(self, book_ids: Iterable[int], fmt: str) -> None:
        self.executemany('DELETE FROM conversion_options WHERE book=? AND format=?', [(book_id, fmt.upper()) for book_id in book_ids])

    def set_conversion_options(self, options: Mapping[int, object], fmt: str) -> None:
        def map_data(x: object) -> bytes:
            if not isinstance(x, (str, bytes)):
                x = str(x)
            x = x.encode('utf-8') if isinstance(x, str) else x
            x = pickle_binary_string(x)
            return x

        options = [(book_id, fmt.upper(), map_data(data)) for book_id, data in options.items()]  # ty: ignore[invalid-assignment]
        self.executemany('INSERT OR REPLACE INTO conversion_options(book,format,data) VALUES (?,?,?)', options)  # ty: ignore[invalid-argument-type]

    def get_top_level_move_items(self, all_paths: Iterable[str]) -> tuple[set[str], dict[str, str]]:
        items = set(os.listdir(self.library_path))
        paths = set(all_paths)
        paths.update({'metadata.db', 'full-text-search.db', 'metadata_db_prefs_backup.json', NOTES_DIR_NAME})
        path_map = {x: x for x in paths}
        if not self.is_case_sensitive:
            for x in items:
                path_map[x.lower()] = x
            items = {x.lower() for x in items}
            paths = {x.lower() for x in paths}
        items = items.intersection(paths)
        return items, path_map

    def move_library_to(
        self,
        all_paths: Iterable[str],
        newloc: str,
        progress: Callable[[str, int, int], object] = (lambda item_name, item_count, total: None),
        abort: Event | None = None,
    ) -> None:
        if not os.path.exists(newloc):
            os.makedirs(newloc)
        old_dirs, old_files = set(), set()
        items, path_map = self.get_top_level_move_items(all_paths)
        total = len(items) + 1
        for i, x in enumerate(items):
            if abort is not None and abort.is_set():
                return
            src = os.path.join(self.library_path, x)
            dest = os.path.join(newloc, path_map[x])
            if os.path.isdir(src):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                copytree_using_links(src, dest, dest_is_parent=False)
                old_dirs.add(src)
            else:
                if os.path.exists(dest):
                    os.remove(dest)
                copyfile_using_links(src, dest, dest_is_dir=False)
                old_files.add(src)
            x = path_map[x]
            if not isinstance(x, str):
                x = x.decode(filesystem_encoding, 'replace')
            progress(x, i + 1, total)

        dbpath = os.path.join(newloc, os.path.basename(self.dbpath))
        odir = self.library_path
        self.conn.close()
        self.library_path, self.dbpath = newloc, dbpath
        if self._conn is not None:
            self._conn.close()
        self._conn = None
        for loc in old_dirs:
            try:
                rmtree_with_retry(loc)
            except OSError as e:
                if os.path.exists(loc):
                    prints('Failed to delete:', loc, 'with error:', as_unicode(e))
        for loc in old_files:
            try:
                os.remove(loc)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    prints('Failed to delete:', loc, 'with error:', as_unicode(e))
        try:
            os.rmdir(odir)
        except OSError:
            pass
        self.conn  # ruff: ignore[useless-expression] # Connect to the moved metadata.db
        progress(_('Completed'), total, total)

    def _backup_database(self, path: str, name: str, extra_sql: str = '', num_of_retries: int = 10, busy_timeout: float = 60) -> None:
        for retry_count in range(num_of_retries):
            try:
                with closing(apsw.Connection(path)) as dest_db:
                    with dest_db.backup('main', self.conn, name) as b:
                        busy_since = None
                        while not b.done:
                            try:
                                b.step(128)
                            except apsw.BusyError as e:
                                # Locks on some filesystems such as SMB/CIFS
                                # shares never succeed, so dont retry forever
                                now = time.monotonic()
                                if busy_since is None:
                                    busy_since = now
                                elif now - busy_since > busy_timeout:
                                    raise apsw.BusyError(
                                        f'Could not lock the database at {path} for {busy_timeout} seconds.'
                                        ' The filesystem it is on probably does not support file locking.'
                                    ) from e
                                time.sleep(0.05)
                            else:
                                busy_since = None
                    if extra_sql:
                        dest_db.cursor().execute(extra_sql)
                return
            except apsw.IOError as e:
                # backup step() can fail transiently, either with
                # SQLITE_IOERR_SHORT_READ when the source database is modified
                # while it is being read, or with a plain SQLITE_IOERR and no
                # error message set on the connection, which apsw reports as
                # "not an error". Once step() fails the backup object is dead,
                # so restart the entire backup. Any other extended result code
                # is a genuine I/O error, and is not retried.
                if retry_count >= num_of_retries - 1 or getattr(e, 'extendedresult', None) not in (apsw.SQLITE_IOERR, apsw.SQLITE_IOERR_SHORT_READ):
                    raise
                with suppress(OSError):
                    os.remove(path)
                time.sleep(0.2)

    @staticmethod
    def can_use_sqlite_in(base: str) -> bool:
        import tempfile

        fd, path = tempfile.mkstemp(suffix='-lock-test.db', dir=base)
        os.close(fd)
        try:
            with closing(apsw.Connection(path)) as conn:
                conn.cursor().execute('BEGIN EXCLUSIVE; CREATE TABLE t(x); COMMIT;')
        except apsw.Error as e:
            prints(f'Cannot use SQLite databases in {base} with error: {as_unicode(e)}')
            return False
        finally:
            with suppress(OSError):
                os.remove(path)
        return True

    def backup_database(self, path: str) -> None:
        self._backup_database(path, 'main', 'DELETE FROM metadata_dirtied; VACUUM;')

    def backup_fts_database(self, path: str) -> None:
        self._backup_database(path, 'fts_db')

    def backup_notes_database(self, path: str) -> None:
        self._backup_database(path, 'notes_db')

    def size_stats(self) -> dict[str, int]:
        main_size = notes_size = fts_size = 0
        with suppress(OSError):
            main_size = os.path.getsize(self.dbpath)
        if self.conn.notes_dbpath:
            with suppress(OSError):
                notes_size = os.path.getsize(self.conn.notes_dbpath)
        if self.conn.fts_dbpath:
            with suppress(OSError):
                fts_size = os.path.getsize(self.conn.fts_dbpath)
        return {'main': main_size, 'fts': fts_size, 'notes': notes_size}

    # }}}
