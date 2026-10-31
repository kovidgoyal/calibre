#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import os
import traceback
import weakref
from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Literal, cast, overload

from calibre import force_unicode
from calibre.constants import preferred_encoding
from calibre.db import _get_next_series_num_for_list, _get_series_values, get_data_as_dict
from calibre.db.adding import add_catalog, add_news, find_books_in_directory, import_book_directory, import_book_directory_multiple, recursive_import
from calibre.db.backend import DB
from calibre.db.backend import set_global_state as backend_set_global_state
from calibre.db.cache import Cache
from calibre.db.categories import CATEGORY_SORTS
from calibre.db.errors import NoSuchFormat
from calibre.db.view import View
from calibre.db.write import clean_identifier, get_series_values, normalize_whitespace
from calibre.utils.date import utcnow
from calibre.utils.icu import lower as icu_lower
from calibre.utils.search_query_parser import set_saved_searches

if TYPE_CHECKING:
    import builtins
    from collections.abc import Collection, ItemsView, Iterable, Iterator, KeysView, Mapping, Sequence, ValuesView
    from datetime import datetime, timedelta
    from typing import IO

    from qt.core import QImage, QPixmap

    from calibre.db.backend import CustomColumnData
    from calibre.db.cache import FormatMetadataDict
    from calibre.db.categories import Tag
    from calibre.db.view import TableRow
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.library.field_metadata import FieldMetadata
    from calibre.utils.filenames import WindowsAtomicFolderMove

    type CompiledRules = Iterable[tuple[Callable[[str], bool], bool]]
    type Duplicates = list[tuple[Metadata, list[str]]]
    type Listener = Callable[[str, Iterable[int]], object]
    type BookOnDeviceFunc = Callable[[int], Sequence[object] | None]


def cleanup_tags(tags: Iterable[str | bytes]) -> list[str]:
    tags = [x.decode(preferred_encoding, 'replace') if isinstance(x, bytes) else x for x in tags]
    tags = [x.strip().replace(',', ';') for x in tags if x.strip()]
    tags = [normalize_whitespace(x) for x in tags]
    ans, seen = [], set()
    for tag in tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            ans.append(tag)
    return ans


def create_backend(
    library_path: str,
    default_prefs: dict[str, object] | None = None,
    read_only: bool = False,
    progress_callback: Callable[[str | None, int], object] = lambda x, y: True,
    restore_all_prefs: bool = False,
    load_user_formatter_functions: bool = True,
    temp_db_path: str | None = None,
) -> DB:
    return DB(
        library_path,
        default_prefs=default_prefs,
        read_only=read_only,
        restore_all_prefs=restore_all_prefs,
        progress_callback=progress_callback,
        load_user_formatter_functions=load_user_formatter_functions,
        temp_db_path=temp_db_path,
    )


def set_global_state(db: Cache | LibraryDatabase) -> None:
    backend_set_global_state(db.backend)
    set_saved_searches(db, 'saved_searches')


class ThreadSafePrefs(MutableMapping):
    def __init__(self, db: Cache) -> None:
        self.db = weakref.ref(db)

    def has_setting(self, key: str) -> bool:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.has_setting(key)

    def __getitem__(self, key: str) -> object:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.__getitem__(key)

    def __delitem__(self, key: str) -> None:
        db = self.db()
        assert db is not None
        with db.write_lock:
            prefs = db.backend.prefs
            prefs.__delitem__(key)

    def __setitem__(self, key: str, val: object) -> None:
        db = self.db()
        assert db is not None
        with db.write_lock:
            prefs = db.backend.prefs
            prefs.__setitem__(key, val)

    def __contains__(self, key: object) -> bool:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.__contains__(key)

    def __iter__(self) -> Iterator[str]:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.__iter__()

    def __len__(self) -> int:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.__len__()

    def __bool__(self) -> bool:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return bool(prefs)

    def copy(self) -> dict[str, object]:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.copy()

    def items(self) -> ItemsView[str, object]:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.items()

    iteritems = items

    def keys(self) -> KeysView[str]:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.keys()

    iterkeys = keys

    def values(self) -> ValuesView[object]:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.values()

    itervalues = values

    @property
    def defaults(self) -> dict[str, object]:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.defaults

    @property
    def disable_setting(self) -> bool:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.disable_setting

    @disable_setting.setter
    def disable_setting(self, val: bool) -> None:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        prefs.disable_setting = val

    def get(self, key: str, default: object = None) -> object:  # ty: ignore[invalid-method-override]
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.get(key, default)

    def set(self, key: str, val: object) -> None:
        self.__setitem__(key, val)

    def get_namespaced(self, namespace: str, key: str, default: object = None) -> object:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.get_namespaced(namespace, key, default)

    def set_namespaced(self, namespace: str, key: str, val: object) -> None:
        db = self.db()
        assert db is not None
        with db.write_lock:
            prefs = db.backend.prefs
            return prefs.set_namespaced(namespace, key, val)

    def write_serialized(self, library_path: str) -> None:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        prefs.write_serialized(library_path)

    def to_raw(self, val: object) -> str:
        db = self.db()
        assert db is not None
        prefs = db.backend.prefs
        return prefs.to_raw(val)

    def raw_to_object(self, raw: str | bytes) -> object:
        if isinstance(raw, bytes):
            raw = raw.decode(preferred_encoding)
        import json

        from calibre.utils.config import from_json

        return json.loads(raw, object_hook=from_json)


class LibraryDatabase:
    """Emulate the old LibraryDatabase2 interface"""

    PATH_LIMIT = DB.PATH_LIMIT
    WINDOWS_LIBRARY_PATH_LIMIT = DB.WINDOWS_LIBRARY_PATH_LIMIT
    CATEGORY_SORTS = CATEGORY_SORTS
    MATCH_TYPE = ('any', 'all')
    CUSTOM_DATA_TYPES = frozenset([
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
    ])

    # These attributes are assigned dynamically at module level after class definition
    multisort: Callable[..., None]
    all_custom: Callable[..., frozenset[str]]
    format_hash: Callable[..., str]
    index: Callable[..., int]
    has_cover: Callable[..., bool]
    get_tags: Callable[..., builtins.set[str]]
    get_categories: Callable[..., dict[str, list[Tag]]]
    get_identifiers: Callable[..., dict[str, str]]
    isbn: Callable[..., str | None]
    get_books_for_category: Callable[..., builtins.set[int]]
    get_data_as_dict: Callable[..., list[dict[str | int, object]]]
    find_identical_books: Callable[..., builtins.set[int]]
    get_top_level_move_items: Callable[..., tuple[builtins.set[str], dict[str, str]]]
    update_last_modified: Callable[..., None]
    all_formats: Callable[..., frozenset[str]]
    all_tags: Callable[..., list[str]]
    get_all_identifier_types: Callable[..., list[str]]
    get_authors_with_ids: Callable[..., list[list[int | str]]]
    get_author_id: Callable[..., int | None]
    metadata_for_field: Callable[..., dict[str, object] | None]
    saved_search_names: Callable[..., list[str]]
    saved_search_lookup: Callable[..., str | None]
    saved_search_set_all: Callable[..., None]
    saved_search_delete: Callable[..., None]
    saved_search_add: Callable[..., None]
    saved_search_rename: Callable[..., None]
    commit_dirty_cache: Callable[..., None]
    author_sort_from_authors: Callable[..., str]
    clean: Callable[..., None]
    clean_custom: Callable[..., None]
    clean_standard_field: Callable[..., None]
    commit: Callable[..., None]
    # Assigned dynamically in __init__ from self.data
    get_property: Callable[..., object]

    @classmethod
    def exists_at(cls, path: str | None) -> str | bool | None:
        return path and os.path.exists(os.path.join(path, 'metadata.db'))

    def __init__(
        self,
        library_path: str,
        default_prefs: dict[str, object] | None = None,
        read_only: bool = False,
        is_second_db: bool = False,
        progress_callback: Callable[[str | None, int], object] | None = None,
        restore_all_prefs: bool = False,
        row_factory: bool = False,
        temp_db_path: str | None = None,
    ) -> None:

        self.is_second_db = is_second_db
        if progress_callback is None:

            def progress_callback(x: str | None, y: int) -> bool:
                return True

        self.listeners: set[Listener] = set()

        backend = self.backend = create_backend(
            library_path,
            default_prefs=default_prefs,
            read_only=read_only,
            restore_all_prefs=restore_all_prefs,
            progress_callback=progress_callback,
            load_user_formatter_functions=not is_second_db,
            temp_db_path=temp_db_path,
        )
        cache = self.new_api = Cache(backend, library_database_instance=self)
        cache.init()
        self.data = View(cache)
        self.id = self.data.index_to_id
        self.row = self.data.id_to_index
        for x in (
            'get_property',
            'count',
            'refresh_ids',
            'set_marked_ids',
            'multisort',
            'search',
            'search_getting_ids',
        ):
            setattr(self, x, getattr(self.data, x))

        self.is_case_sensitive = getattr(backend, 'is_case_sensitive', False)
        self.custom_field_name = backend.custom_field_name

        self.last_update_check = self.last_modified()

        if not self.is_second_db:
            set_saved_searches(self, 'saved_searches')

    def close(self) -> None:
        if hasattr(self, 'new_api'):
            self.new_api.close()

    def break_cycles(self) -> None:
        if hasattr(self, 'backend'):
            delattr(self.backend, 'field_metadata')
            self.data.cache.backend = None  # ty: ignore[invalid-assignment]
            self.data.cache = None  # ty: ignore[invalid-assignment]
            for x in (
                'data',
                'backend',
                'new_api',
                'listeners',
            ):
                delattr(self, x)

    # Library wide properties {{{
    @property
    def prefs(self) -> ThreadSafePrefs:
        return ThreadSafePrefs(self.new_api)

    @property
    def field_metadata(self) -> FieldMetadata:
        return self.backend.field_metadata

    @property
    def user_version(self) -> int:
        return self.backend.user_version

    @property
    def library_id(self) -> str:
        return self.backend.library_id

    @property
    def library_path(self) -> str:
        return self.backend.library_path

    @property
    def dbpath(self) -> str:
        return self.backend.dbpath

    def last_modified(self) -> datetime:
        return self.new_api.last_modified()

    def check_if_modified(self) -> None:
        if self.last_modified() > self.last_update_check:
            self.backend.reopen()
            self.new_api.reload_from_db()
            self.data.refresh(clear_caches=False)  # caches are already cleared by reload_from_db()
        self.last_update_check = utcnow()

    @property
    def custom_column_num_map(self) -> dict[int, CustomColumnData]:
        return self.backend.custom_column_num_map

    @property
    def custom_column_label_map(self) -> dict[str, CustomColumnData]:
        return self.backend.custom_column_label_map

    @property
    def FIELD_MAP(self) -> dict[str | int, int]:
        return self.backend.FIELD_MAP

    @property
    def formatter_template_cache(self) -> dict[str, object]:
        return self.data.cache.formatter_template_cache

    def initialize_template_cache(self) -> None:
        self.data.cache.initialize_template_cache()

    def all_ids(self) -> tuple[int, ...]:
        "All book ids in the db. This can no longer be a generator because of db locking."
        return tuple(self.new_api.all_book_ids())

    def is_empty(self) -> bool:
        with self.new_api.safe_read_lock:
            return not bool(self.new_api.fields['title'].table.book_col_map)

    def get_usage_count_by_id(self, field: str) -> list[list[int]]:
        return [[k, v] for k, v in self.new_api.get_usage_count_by_id(field).items()]

    def field_id_map(self, field: str) -> list[tuple[int, str]]:
        return list(self.new_api.get_id_map(field).items())

    def get_custom_items_with_ids(self, label: str | None = None, num: int | None = None) -> list[list[int | str]]:
        try:
            return [[k, v] for k, v in self.new_api.get_id_map(self.custom_field_name(label, num)).items()]
        except ValueError:
            return []

    def refresh(self, field: str | None = None, ascending: bool = True) -> None:
        self.data.refresh(field=field, ascending=ascending)

    def get_id_from_uuid(self, uuid: str | None) -> int | None:
        if uuid:
            return self.new_api.lookup_by_uuid(uuid)

    def add_listener(self, listener: Listener) -> None:
        """
        Add a listener. Will be called on change events with two arguments.
        Event name and list of affected ids.
        """
        self.listeners.add(listener)

    def notify(self, event: str, ids: Iterable[int] | None = None) -> None:
        "Notify all listeners"
        if ids is None:
            ids = []
        for listener in self.listeners:
            try:
                listener(event, ids)
            except Exception:
                traceback.print_exc()
                continue

    # }}}

    def path(self, index: int, index_is_id: bool = False) -> str:
        "Return the relative path to the directory containing this books files as a unicode string."
        book_id = index if index_is_id else self.id(index)
        return self.new_api.get_book_path(book_id)

    def abspath(self, index: int, index_is_id: bool = False, create_dirs: bool = True) -> str:
        "Return the absolute path to the directory containing this books files as a unicode string."
        path = os.path.join(self.library_path, self.path(index, index_is_id=index_is_id))
        if create_dirs and not os.path.exists(path):
            os.makedirs(path)
        return path

    # Adding books {{{
    def create_book_entry(self, mi: Metadata, cover: bytes | None = None, add_duplicates: bool = True, force_id: int | None = None) -> int | None:
        ret = self.new_api.create_book_entry(mi, cover=cover, add_duplicates=add_duplicates, force_id=force_id)
        if ret is not None:
            self.data.books_added((ret,))
        return ret

    @overload
    def add_books(
        self, paths: Iterable[str], formats: Iterable[str], metadata: Iterable[Metadata], add_duplicates: bool = True, *, return_ids: Literal[True]
    ) -> tuple[tuple[list[str], list[str], list[Metadata]] | None, list[int]]: ...
    @overload
    def add_books(
        self, paths: Iterable[str], formats: Iterable[str], metadata: Iterable[Metadata], add_duplicates: bool = True, return_ids: Literal[False] = False
    ) -> tuple[tuple[list[str], list[str], list[Metadata]] | None, int]: ...
    @overload
    def add_books(
        self, paths: Iterable[str], formats: Iterable[str], metadata: Iterable[Metadata], add_duplicates: bool = True, return_ids: bool = False
    ) -> tuple[tuple[list[str], list[str], list[Metadata]] | None, list[int] | int]: ...
    def add_books(
        self, paths: Iterable[str], formats: Iterable[str], metadata: Iterable[Metadata], add_duplicates: bool = True, return_ids: bool = False
    ) -> tuple[tuple[list[str], list[str], list[Metadata]] | None, list[int] | int]:
        books = [(mi, {fmt: path}) for mi, path, fmt in zip(metadata, paths, formats)]
        book_ids, duplicates = self.new_api.add_books(books, add_duplicates=add_duplicates, dbapi=self)
        if duplicates:
            paths, formats, metadata = [], [], []
            for mi, format_map in duplicates:
                metadata.append(mi)
                for fmt, path in format_map.items():
                    formats.append(fmt)
                    paths.append(path)
            duplicates = (paths, formats, metadata)
        ids = book_ids if return_ids else len(book_ids)
        if book_ids:
            self.data.books_added(book_ids)
        return duplicates or None, ids  # ty: ignore[invalid-return-type]

    def import_book(
        self,
        mi: Metadata,
        formats: Iterable[str],
        notify: bool = True,
        import_hooks: bool = True,
        apply_import_tags: bool = True,
        preserve_uuid: bool = False,
    ) -> int:
        format_map = {}
        for path in formats:
            ext = os.path.splitext(path)[1][1:].upper()
            if ext == 'OPF':
                continue
            format_map[ext] = path
        book_ids, duplicates = self.new_api.add_books(
            [(mi, format_map)],
            add_duplicates=True,
            apply_import_tags=apply_import_tags,
            preserve_uuid=preserve_uuid,
            dbapi=self,
            run_hooks=import_hooks,
        )
        if book_ids:
            self.data.books_added(book_ids)
        if notify:
            self.notify('add', book_ids)
        return book_ids[0]

    def find_books_in_directory(self, dirpath: str, single_book_per_directory: bool, compiled_rules: CompiledRules = ()) -> Iterator[list[str]]:
        return find_books_in_directory(dirpath, single_book_per_directory, compiled_rules=compiled_rules)

    def import_book_directory_multiple(
        self,
        dirpath: str,
        callback: Callable[[str], object] | None = None,
        added_ids: builtins.set[int] | None = None,
        compiled_rules: CompiledRules = (),
    ) -> Duplicates:
        return import_book_directory_multiple(self, dirpath, callback=callback, added_ids=added_ids, compiled_rules=compiled_rules)

    def import_book_directory(
        self,
        dirpath: str,
        callback: Callable[[str], object] | None = None,
        added_ids: builtins.set[int] | None = None,
        compiled_rules: CompiledRules = (),
    ) -> Duplicates | None:
        return import_book_directory(self, dirpath, callback=callback, added_ids=added_ids, compiled_rules=compiled_rules)

    def recursive_import(
        self,
        root: str,
        single_book_per_directory: bool = True,
        callback: Callable[[str], object] | None = None,
        added_ids: builtins.set[int] | None = None,
        compiled_rules: CompiledRules = (),
    ) -> Duplicates:
        return recursive_import(
            self,
            root,
            single_book_per_directory=single_book_per_directory,
            callback=callback,
            added_ids=added_ids,
            compiled_rules=compiled_rules,
        )

    def add_catalog(self, path: str, title: str) -> int | None:
        book_id, new_book_added = add_catalog(self.new_api, path, title, dbapi=self)
        if book_id is not None and new_book_added:
            self.data.books_added((book_id,))
        return book_id

    def add_news(self, path: str, arg: Mapping[str, object]) -> int | None:
        book_id = add_news(self.new_api, path, arg, dbapi=self)
        if book_id is not None:
            self.data.books_added((book_id,))
        return book_id

    def add_format(
        self,
        index: int,
        fmt: str,
        stream: IO[bytes] | str,
        index_is_id: bool = False,
        path: str | None = None,
        notify: bool = True,
        replace: bool = True,
        copy_function: Callable[..., object] | None = None,
    ) -> bool:
        """path and copy_function are ignored by the new API"""
        book_id = index if index_is_id else self.id(index)
        ret = self.new_api.add_format(book_id, fmt, stream, replace=replace, run_hooks=False, dbapi=self)
        self.notify('metadata', [book_id])
        return ret

    def add_format_with_hooks(
        self,
        index: int,
        fmt: str,
        fpath: str | IO[bytes],
        index_is_id: bool = False,
        path: str | None = None,
        notify: bool = True,
        replace: bool = True,
    ) -> bool:
        """path is ignored by the new API"""
        book_id = index if index_is_id else self.id(index)
        ret = self.new_api.add_format(book_id, fmt, fpath, replace=replace, run_hooks=True, dbapi=self)
        self.notify('metadata', [book_id])
        return ret

    # }}}

    # Custom data {{{
    def add_custom_book_data(self, book_id: int, name: str, val: object) -> None:
        self.new_api.add_custom_book_data(name, {book_id: val})

    def add_multiple_custom_book_data(self, name: str, val_map: Mapping[int, object], delete_first: bool = False) -> None:
        self.new_api.add_custom_book_data(name, val_map, delete_first=delete_first)

    def get_custom_book_data(self, book_id: int, name: str, default: object = None) -> object:
        return self.new_api.get_custom_book_data(name, book_ids={book_id}, default=default).get(book_id, default)

    def get_all_custom_book_data(self, name: str, default: object = None) -> dict[int, object]:
        return self.new_api.get_custom_book_data(name, default=default)

    def delete_custom_book_data(self, book_id: int, name: str) -> None:
        self.new_api.delete_custom_book_data(name, book_ids=(book_id,))

    def delete_all_custom_book_data(self, name: str) -> None:
        self.new_api.delete_custom_book_data(name)

    def get_ids_for_custom_book_data(self, name: str) -> list[int]:
        return list(self.new_api.get_ids_for_custom_book_data(name))

    # }}}

    def sort(self, field: str, ascending: bool, subsort: bool = False) -> None:
        self.multisort([(field, ascending)])

    def get_field(self, index: int, key: str, default: object = None, index_is_id: bool = False) -> object:
        book_id = index if index_is_id else self.id(index)
        mi = self.new_api.get_metadata(book_id, get_cover=key == 'cover')
        return mi.get(key, default)

    def cover_last_modified(self, index: int, index_is_id: bool = False) -> datetime:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.cover_last_modified(book_id) or self.last_modified()

    def cover(
        self, index: int, index_is_id: bool = False, as_file: bool = False, as_image: bool = False, as_path: bool = False
    ) -> bytes | IO[bytes] | QImage | QPixmap | str | None:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.cover(book_id, as_file=as_file, as_image=as_image, as_path=as_path)

    def copy_cover_to(
        self,
        index: int,
        dest: str | IO[bytes],
        index_is_id: bool = False,
        windows_atomic_move: WindowsAtomicFolderMove | None = None,
        use_hardlink: bool = False,
    ) -> bool:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.copy_cover_to(book_id, dest, use_hardlink=use_hardlink)

    def copy_format_to(
        self,
        index: int,
        fmt: str,
        dest: str | IO[bytes],
        index_is_id: bool = False,
        windows_atomic_move: WindowsAtomicFolderMove | None = None,
        use_hardlink: bool = False,
    ) -> bool:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.copy_format_to(book_id, fmt, dest, use_hardlink=use_hardlink)

    def delete_book(self, book_id: int, notify: bool = True, commit: bool = True, permanent: bool = False, do_clean: bool = True) -> None:
        self.new_api.remove_books((book_id,), permanent=permanent)
        self.data.books_deleted((book_id,))
        if notify:
            self.notify('delete', [book_id])

    def dirtied(self, book_ids: Iterable[int], commit: bool = True) -> None:
        self.new_api.mark_as_dirty(frozenset(book_ids) if book_ids is not None else book_ids)

    def dirty_queue_length(self) -> int:
        return self.new_api.dirty_queue_length()

    def dump_metadata(
        self,
        book_ids: Collection[int] | None = None,
        remove_from_dirtied: bool = True,
        commit: bool = True,
        callback: Callable[[int, Metadata | bool | None, bool], object] | None = None,
    ) -> None:
        self.new_api.dump_metadata(book_ids=book_ids, remove_from_dirtied=remove_from_dirtied, callback=callback)

    def authors_sort_strings(self, index: int, index_is_id: bool = False) -> list[str]:
        book_id = index if index_is_id else self.id(index)
        return list(self.new_api.author_sort_strings_for_books((book_id,))[book_id])

    def author_sort_from_book(self, index: int, index_is_id: bool = False) -> str:
        return ' & '.join(self.authors_sort_strings(index, index_is_id=index_is_id))

    def authors_with_sort_strings(self, index: int, index_is_id: bool = False) -> list[tuple[int, str, str, str]]:
        book_id = index if index_is_id else self.id(index)
        with self.new_api.safe_read_lock:
            authors = self.new_api._field_ids_for('authors', book_id)
            adata = self.new_api._author_data(authors)
            return [(aid, adata[aid]['name'], adata[aid]['sort'], adata[aid]['link']) for aid in authors]

    def set_sort_field_for_author(self, old_id: int, new_sort: str, commit: bool = True, notify: bool = False) -> None:
        changed_books = self.new_api.set_sort_for_authors({old_id: new_sort})
        if notify:
            self.notify('metadata', list(changed_books))

    def set_link_field_for_author(self, aid: int, link: str, commit: bool = True, notify: bool = False) -> None:
        changed_books = self.new_api.set_link_for_authors({aid: link})
        if notify:
            self.notify('metadata', list(changed_books))

    def book_on_device(self, book_id: int) -> Sequence[object] | None:
        with self.new_api.safe_read_lock:
            return self.new_api.fields['ondevice'].book_on_device(book_id)

    def book_on_device_string(self, book_id: int) -> str:
        return cast('str', self.new_api.field_for('ondevice', book_id))

    def set_book_on_device_func(self, func: BookOnDeviceFunc) -> None:
        self.new_api.fields['ondevice'].set_book_on_device_func(func)

    @property
    def book_on_device_func(self) -> BookOnDeviceFunc | None:
        return self.new_api.fields['ondevice'].book_on_device_func

    def books_in_series(self, series_id: int) -> list[int]:
        with self.new_api.safe_read_lock:
            book_ids = self.new_api._books_for_field('series', series_id)
            ff = self.new_api._field_for
            return sorted(book_ids, key=lambda x: ff('series_index', x))  # ty: ignore[no-matching-overload]

    def books_in_series_of(self, index: int, index_is_id: bool = False) -> list[int]:
        book_id = index if index_is_id else self.id(index)
        series_ids = self.new_api.field_ids_for('series', book_id)
        if not series_ids:
            return []
        return self.books_in_series(series_ids[0])

    def books_with_same_title(self, mi: Metadata, all_matches: bool = True) -> builtins.set[int]:
        title = mi.title
        ans = set()
        if title:
            title = icu_lower(force_unicode(title))
            for book_id, x in self.new_api.get_id_map('title').items():
                if icu_lower(x) == title:
                    ans.add(book_id)
                    if not all_matches:
                        break
        return ans

    def set_conversion_options(self, book_id: int, fmt: str, options: object) -> None:
        self.new_api.set_conversion_options({book_id: options}, fmt=fmt)

    def conversion_options(self, book_id: int, fmt: str) -> object:
        return self.new_api.conversion_options(book_id, fmt=fmt)

    def has_conversion_options(self, ids: Iterable[int], format: str = 'PIPE') -> bool:
        return self.new_api.has_conversion_options(ids, fmt=format)

    def delete_conversion_options(self, book_id: int, fmt: str, commit: bool = True) -> None:
        self.new_api.delete_conversion_options((book_id,), fmt=fmt)

    def set(self, index: int, field: str, val: object, allow_case_change: bool = False) -> builtins.set[int]:
        book_id = self.id(index)
        try:
            return self.new_api.set_field(field, {book_id: val}, allow_case_change=allow_case_change)
        finally:
            self.notify('metadata', [book_id])

    def set_identifier(self, book_id: int, typ: str, val: str, notify: bool = True, commit: bool = True) -> None:
        with self.new_api.write_lock:
            identifiers = self.new_api._field_for('identifiers', book_id)
            typ, val = clean_identifier(typ, val)
            if typ:
                identifiers[typ] = val
                self.new_api._set_field('identifiers', {book_id: identifiers})
        self.notify('metadata', [book_id])

    def set_isbn(self, book_id: int, isbn: str, notify: bool = True, commit: bool = True) -> None:
        self.set_identifier(book_id, 'isbn', isbn, notify=notify, commit=commit)

    def set_tags(
        self,
        book_id: int,
        tags: Iterable[str] | None,
        append: bool = False,
        notify: bool = True,
        commit: bool = True,
        allow_case_change: bool = False,
    ) -> builtins.set[int]:
        tags = tags or []
        with self.new_api.write_lock:
            if append:
                otags = self.new_api._field_for('tags', book_id)
                existing = {icu_lower(x) for x in otags}
                tags = list(otags) + [x for x in tags if icu_lower(x) not in existing]
            ret = self.new_api._set_field('tags', {book_id: tags}, allow_case_change=allow_case_change)
        if notify:
            self.notify('metadata', [book_id])
        return ret

    def set_metadata(
        self,
        book_id: int,
        mi: Metadata,
        ignore_errors: bool = False,
        set_title: bool = True,
        set_authors: bool = True,
        commit: bool = True,
        force_changes: bool = False,
        notify: bool = True,
    ) -> None:
        self.new_api.set_metadata(
            book_id,
            mi,
            ignore_errors=ignore_errors,
            set_title=set_title,
            set_authors=set_authors,
            force_changes=force_changes,
        )
        if notify:
            self.notify('metadata', [book_id])

    def remove_all_tags(self, ids: Iterable[int], notify: bool = False, commit: bool = True) -> None:
        self.new_api.set_field('tags', {book_id: () for book_id in ids})
        if notify:
            self.notify('metadata', ids)

    def _do_bulk_modify(self, field: str, ids: Collection[int], add: Iterable[str], remove: Iterable[str], notify: bool) -> None:
        add = cleanup_tags(add)
        remove = cleanup_tags(remove)
        remove = set(remove) - set(add)
        if not ids or (not add and not remove):
            return

        remove = {icu_lower(x) for x in remove}
        with self.new_api.write_lock:
            val_map = {}
            for book_id in ids:
                tags = list(cast('tuple[str, ...]', self.new_api._field_for(field, book_id)))
                existing = {icu_lower(x) for x in tags}
                tags.extend(t for t in add if icu_lower(t) not in existing)
                tags = tuple(t for t in tags if icu_lower(t) not in remove)
                val_map[book_id] = tags
            self.new_api._set_field(field, val_map, allow_case_change=False)

        if notify:
            self.notify('metadata', ids)

    def bulk_modify_tags(self, ids: Collection[int], add: Iterable[str] | None = None, remove: Iterable[str] | None = None, notify: bool = False) -> None:
        if remove is None:
            remove = []
        if add is None:
            add = []
        self._do_bulk_modify('tags', ids, add, remove, notify)

    def set_custom_bulk_multiple(
        self,
        ids: Collection[int],
        add: Iterable[str] | None = None,
        remove: Iterable[str] | None = None,
        label: str | None = None,
        num: int | None = None,
        notify: bool = False,
    ) -> None:
        if remove is None:
            remove = []
        if add is None:
            add = []
        data = self.backend.custom_field_metadata(label, num)
        if not data['editable']:
            raise ValueError('Column {!r} is not editable'.format(data['label']))
        if data['datatype'] != 'text' or not data['is_multiple']:
            raise ValueError('Column {!r} is not text/multiple'.format(data['label']))
        field = self.custom_field_name(label, num)
        self._do_bulk_modify(field, ids, add, remove, notify)

    def unapply_tags(self, book_id: int, tags: Iterable[str], notify: bool = True) -> None:
        self.bulk_modify_tags((book_id,), remove=tags, notify=notify)

    def is_tag_used(self, tag: str) -> bool:
        return icu_lower(tag) in {icu_lower(x) for x in self.new_api.all_field_names('tags')}

    def delete_tag(self, tag: str) -> None:
        self.delete_tags((tag,))

    def delete_tags(self, tags: Iterable[str]) -> None:
        with self.new_api.write_lock:
            tag_map = {icu_lower(v): k for k, v in self.new_api._get_id_map('tags').items()}
            tag_ids = (tag_map.get(icu_lower(tag), None) for tag in tags)
            tag_ids = tuple(tid for tid in tag_ids if tid is not None)
            if tag_ids:
                self.new_api._remove_items('tags', tag_ids)

    def has_id(self, book_id: int) -> bool:
        return self.new_api.has_id(book_id)

    def format(
        self,
        index: int,
        fmt: str,
        index_is_id: bool = False,
        as_file: bool = False,
        mode: str = 'r+b',
        as_path: bool = False,
        preserve_filename: bool = False,
    ) -> bytes | IO[bytes] | str | None:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.format(book_id, fmt, as_file=as_file, as_path=as_path, preserve_filename=preserve_filename)

    def format_abspath(self, index: int, fmt: str, index_is_id: bool = False) -> str | None:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.format_abspath(book_id, fmt)

    def format_path(self, index: int, fmt: str, index_is_id: bool = False) -> str:
        book_id = index if index_is_id else self.id(index)
        ans = self.new_api.format_abspath(book_id, fmt)
        if ans is None:
            raise NoSuchFormat(f'Record {book_id} has no format: {fmt}')
        return ans

    def format_files(self, index: int, index_is_id: bool = False) -> list[tuple[str, str]]:
        book_id = index if index_is_id else self.id(index)
        return [(v, k) for k, v in self.new_api.format_files(book_id).items()]

    def format_metadata(self, book_id: int, fmt: str, allow_cache: bool = True, update_db: bool = False, commit: bool = False) -> FormatMetadataDict:
        return self.new_api.format_metadata(book_id, fmt, allow_cache=allow_cache, update_db=update_db)

    def format_last_modified(self, book_id: int, fmt: str) -> datetime | None:
        m = self.format_metadata(book_id, fmt)
        if m:
            return m['mtime']

    def formats(self, index: int, index_is_id: bool = False, verify_formats: bool = True) -> str | None:
        book_id = index if index_is_id else self.id(index)
        ans = self.new_api.formats(book_id, verify_formats=verify_formats)
        if ans:
            return ','.join(ans)

    def has_format(self, index: int, fmt: str, index_is_id: bool = False) -> bool:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.has_format(book_id, fmt)

    def refresh_format_cache(self) -> None:
        self.new_api.refresh_format_cache()

    def refresh_ondevice(self) -> None:
        self.new_api.refresh_ondevice()

    def tags_older_than(
        self, tag: str, delta: timedelta | None, must_have_tag: str | None = None, must_have_authors: Collection[str] | None = None
    ) -> Iterator[int]:
        yield from sorted(self.new_api.tags_older_than(tag, delta=delta, must_have_tag=must_have_tag, must_have_authors=must_have_authors))

    def sizeof_format(self, index: int, fmt: str, index_is_id: bool = False) -> int | None:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.format_metadata(book_id, fmt).get('size', None)

    def get_metadata(
        self, index: int, index_is_id: bool = False, get_cover: bool = False, get_user_categories: bool = True, cover_as_data: bool = False
    ) -> Metadata:
        book_id = index if index_is_id else self.id(index)
        return self.new_api.get_metadata(book_id, get_cover=get_cover, get_user_categories=get_user_categories, cover_as_data=cover_as_data)

    def rename_series(self, old_id: int, new_name: str, change_index: bool = True) -> None:
        self.new_api.rename_items('series', {old_id: new_name}, change_index=change_index)

    def get_custom(self, index: int, label: str | None = None, num: int | None = None, index_is_id: bool = False) -> object:
        book_id = index if index_is_id else self.id(index)
        ans = self.new_api.field_for(self.custom_field_name(label, num), book_id)
        if isinstance(ans, tuple):
            ans = list(ans)
        return ans

    def get_custom_extra(self, index: int, label: str | None = None, num: int | None = None, index_is_id: bool = False) -> float | None:
        data = self.backend.custom_field_metadata(label, num)
        # add future datatypes with an extra column here
        if data['datatype'] != 'series':
            return None
        book_id = index if index_is_id else self.id(index)
        return cast('float | None', self.new_api.field_for(self.custom_field_name(label, num) + '_index', book_id))

    def get_custom_and_extra(self, index: int, label: str | None = None, num: int | None = None, index_is_id: bool = False) -> tuple[object, float | None]:
        book_id = index if index_is_id else self.id(index)
        data = self.backend.custom_field_metadata(label, num)
        ans = self.new_api.field_for(self.custom_field_name(label, num), book_id)
        if isinstance(ans, tuple):
            ans = list(ans)
        if data['datatype'] != 'series':
            return ans, None
        return ans, cast('float | None', self.new_api.field_for(self.custom_field_name(label, num) + '_index', book_id))

    def get_next_cc_series_num_for(self, series: str | None, label: str | None = None, num: int | None = None) -> float | None:
        data = self.backend.custom_field_metadata(label, num)
        if data['datatype'] != 'series':
            return None
        return self.new_api.get_next_series_num_for(series, field=self.custom_field_name(label, num))

    def is_item_used_in_multiple(self, item: str, label: str | None = None, num: int | None = None) -> bool:
        existing_tags = self.all_custom(label=label, num=num)
        return icu_lower(item) in {icu_lower(t) for t in existing_tags}

    def delete_custom_item_using_id(self, item_id: int, label: str | None = None, num: int | None = None) -> None:
        self.new_api.remove_items(self.custom_field_name(label, num), (item_id,))

    def rename_custom_item(self, old_id: int, new_name: str, label: str | None = None, num: int | None = None) -> None:
        self.new_api.rename_items(self.custom_field_name(label, num), {old_id: new_name}, change_index=False)

    def delete_item_from_multiple(self, item: str, label: str | None = None, num: int | None = None) -> list[int]:
        field = self.custom_field_name(label, num)
        existing = self.new_api.get_id_map(field)
        rmap = {icu_lower(v): k for k, v in existing.items()}
        item_id = rmap.get(icu_lower(item), None)
        if item_id is None:
            return []
        return list(self.new_api.remove_items(field, (item_id,)))

    def set_custom(
        self,
        book_id: int,
        val: object,
        label: str | None = None,
        num: int | None = None,
        append: bool = False,
        notify: bool = True,
        extra: float | None = None,
        commit: bool = True,
        allow_case_change: bool = False,
    ) -> builtins.set[int]:
        field = self.custom_field_name(label, num)
        data = self.backend.custom_field_metadata(label, num)
        if data['datatype'] == 'composite':
            return set()
        if not data['editable']:
            raise ValueError('Column {!r} is not editable'.format(data['label']))
        if data['datatype'] == 'enumeration' and (val and val not in data['display']['enum_values']):
            return set()
        with self.new_api.write_lock:
            if append and data['is_multiple']:
                current = cast('tuple[str, ...]', self.new_api._field_for(field, book_id))
                existing = {icu_lower(x) for x in current}
                val = current + tuple(x for x in self.new_api.fields[field].writer.adapter(val) if icu_lower(x) not in existing)
                affected_books = self.new_api._set_field(field, {book_id: val}, allow_case_change=allow_case_change)
            else:
                affected_books = self.new_api._set_field(field, {book_id: val}, allow_case_change=allow_case_change)
            if data['datatype'] == 'series':
                s, sidx = get_series_values(val)  # ty: ignore[invalid-argument-type]
                if sidx is None:
                    extra = 1.0 if extra is None else extra
                    self.new_api._set_field(field + '_index', {book_id: extra})
        if notify and affected_books:
            self.notify('metadata', list(affected_books))
        return affected_books

    def set_custom_bulk(
        self,
        ids: Sequence[int],
        val: object,
        label: str | None = None,
        num: int | None = None,
        append: bool = False,
        notify: bool = True,
        extras: Sequence[float] | None = None,
    ) -> builtins.set[int] | None:
        if extras is not None and len(extras) != len(ids):
            raise ValueError('Length of ids and extras is not the same')
        field = self.custom_field_name(label, num)
        data = self.backend.custom_field_metadata(label, num)
        if data['datatype'] == 'composite':
            return set()
        if data['datatype'] == 'enumeration' and (val and val not in data['display']['enum_values']):
            return
        if not data['editable']:
            raise ValueError('Column {!r} is not editable'.format(data['label']))

        if append:
            for book_id in ids:
                self.set_custom(book_id, val, label=label, num=num, append=True, notify=False)
        else:
            with self.new_api.write_lock:
                self.new_api._set_field(field, {book_id: val for book_id in ids}, allow_case_change=False)
            if extras is not None:
                self.new_api._set_field(field + '_index', dict(zip(ids, extras)))
        if notify:
            self.notify('metadata', list(ids))

    def delete_custom_column(self, label: str | None = None, num: int | None = None) -> None:
        self.new_api.delete_custom_column(label, num)

    def create_custom_column(
        self, label: str, name: str, datatype: str, is_multiple: bool, editable: bool = True, display: dict[str, object] | None = None
    ) -> int:
        if display is None:
            display = {}
        return self.new_api.create_custom_column(label, name, datatype, is_multiple, editable=editable, display=display)

    def set_custom_column_metadata(
        self,
        num: int,
        name: str | None = None,
        label: str | None = None,
        is_editable: bool | None = None,
        display: dict[str, object] | None = None,
        notify: bool = True,
        update_last_modified: bool = False,
    ) -> None:
        changed = self.new_api.set_custom_column_metadata(
            num,
            name=name,
            label=label,
            is_editable=is_editable,
            display=display,
            update_last_modified=update_last_modified,
        )
        if changed and notify:
            self.notify('metadata', [])

    def remove_cover(self, book_id: int, notify: bool = True, commit: bool = True) -> None:
        self.new_api.set_cover({book_id: None})
        if notify:
            self.notify('cover', [book_id])

    def set_cover(self, book_id: int, data: bytes | IO[bytes] | QImage | QPixmap | None, notify: bool = True, commit: bool = True) -> None:
        self.new_api.set_cover({book_id: data})
        if notify:
            self.notify('cover', [book_id])

    def original_fmt(self, book_id: int, fmt: str) -> str:
        nfmt = (f'ORIGINAL_{fmt}').upper()
        return nfmt if self.new_api.has_format(book_id, nfmt) else fmt

    def save_original_format(self, book_id: int, fmt: str, notify: bool = True) -> bool:
        ret = self.new_api.save_original_format(book_id, fmt)
        if ret and notify:
            self.notify('metadata', [book_id])
        return ret

    def restore_original_format(self, book_id: int, original_fmt: str, notify: bool = True) -> bool:
        ret = self.new_api.restore_original_format(book_id, original_fmt)
        if ret and notify:
            self.notify('metadata', [book_id])
        return ret

    def remove_format(self, index: int, fmt: str, index_is_id: bool = False, notify: bool = True, commit: bool = True, db_only: bool = False) -> None:
        book_id = index if index_is_id else self.id(index)
        self.new_api.remove_formats({book_id: (fmt,)}, db_only=db_only)
        if notify:
            self.notify('metadata', [book_id])

    # Private interface {{{
    def __iter__(self) -> Iterator[TableRow]:
        yield from self.data.iterall()

    def _get_next_series_num_for_list(self, series_indices: Sequence[float]) -> float:
        return _get_next_series_num_for_list(series_indices)

    def _get_series_values(self, val: str) -> tuple[str, float | None]:
        return _get_series_values(val)

    # }}}


# Legacy getter API {{{
for prop in (
    'author_sort',
    'authors',
    'comment',
    'comments',
    'publisher',
    'max_size',
    'rating',
    'series',
    'series_index',
    'tags',
    'title',
    'title_sort',
    'timestamp',
    'uuid',
    'pubdate',
    'ondevice',
    'metadata_last_modified',
    'languages',
):

    def getter(prop: str) -> Callable[[LibraryDatabase, int, bool], object]:
        fm = {
            'comment': 'comments',
            'metadata_last_modified': 'last_modified',
            'title_sort': 'sort',
            'max_size': 'size',
        }.get(prop, prop)

        def func(self: LibraryDatabase, index: int, index_is_id: bool = False) -> object:
            return self.get_property(index, index_is_id=index_is_id, loc=self.FIELD_MAP[fm])

        return func

    setattr(LibraryDatabase, prop, getter(prop))

for prop in ('series', 'publisher'):

    def getter(field: str) -> Callable[[LibraryDatabase, int, bool], int | None]:
        def func(self: LibraryDatabase, index: int, index_is_id: bool = False) -> int | None:
            book_id = index if index_is_id else self.id(index)
            ans = self.new_api.field_ids_for(field, book_id)
            try:
                return ans[0]
            except IndexError:
                pass

        return func

    setattr(LibraryDatabase, prop + '_id', getter(prop))

LibraryDatabase.format_hash = lambda self, book_id, fmt: self.new_api.format_hash(book_id, fmt)
LibraryDatabase.index = lambda self, book_id, cache=False: self.data.id_to_index(book_id)
LibraryDatabase.has_cover = lambda self, book_id: self.new_api.field_for('cover', book_id)
LibraryDatabase.get_tags = lambda self, book_id: set(self.new_api.field_for('tags', book_id))
LibraryDatabase.get_categories = lambda self, sort='name', ids=None: self.new_api.get_categories(sort=sort, book_ids=ids)
LibraryDatabase.get_identifiers = lambda self, index, index_is_id=False: self.new_api.field_for('identifiers', index if index_is_id else self.id(index))
LibraryDatabase.isbn = lambda self, index, index_is_id=False: self.get_identifiers(index, index_is_id=index_is_id).get('isbn', None)
LibraryDatabase.get_books_for_category = lambda self, category, id_: self.new_api.get_books_for_category(category, id_)
LibraryDatabase.get_data_as_dict = get_data_as_dict
LibraryDatabase.find_identical_books = lambda self, mi: self.new_api.find_identical_books(mi)
LibraryDatabase.get_top_level_move_items = lambda self: self.new_api.get_top_level_move_items()
# }}}

# Legacy setter API {{{
for field in (
    '!authors',
    'author_sort',
    'comment',
    'has_cover',
    'identifiers',
    'languages',
    'pubdate',
    '!publisher',
    'rating',
    '!series',
    'series_index',
    'timestamp',
    'uuid',
    'title',
    'title_sort',
):

    def setter(field: str) -> Callable[..., object]:
        has_case_change = field.startswith('!')
        field = {'comment': 'comments', 'title_sort': 'sort'}.get(field, field)
        if has_case_change:
            field = field[1:]
            acc = field == 'series'

            def func(self: LibraryDatabase, book_id: int, val: object, notify: bool = True, commit: bool = True, allow_case_change: bool = acc) -> set[int]:
                ret = self.new_api.set_field(field, {book_id: val}, allow_case_change=allow_case_change)
                if notify:
                    self.notify('metadata', [book_id])
                return ret

        elif field == 'has_cover':

            def func(self: LibraryDatabase, book_id: int, val: object) -> None:
                self.new_api.set_field('cover', {book_id: bool(val)})

        else:
            null_field = field in {'title', 'sort', 'uuid'}
            retval = True if field == 'sort' else None

            def func(self: LibraryDatabase, book_id: int, val: object, notify: bool = True, commit: bool = True) -> set[int] | bool | None:
                if not val and null_field:
                    return False if field == 'sort' else None
                ret = self.new_api.set_field(field, {book_id: val})
                if notify:
                    self.notify('metadata', [book_id])
                return ret if field == 'languages' else retval

        return func

    setattr(LibraryDatabase, 'set_{}'.format(field.replace('!', '')), setter(field))

for field in ('authors', 'tags', 'publisher'):

    def renamer(field: str) -> Callable[[LibraryDatabase, int, str], int | None]:
        def func(self: LibraryDatabase, old_id: int, new_name: str) -> int | None:
            id_map = self.new_api.rename_items(field, {old_id: new_name})[1]
            if field == 'authors':
                return id_map[old_id]

        return func

    fname = field[:-1] if field in {'tags', 'authors'} else field
    setattr(LibraryDatabase, f'rename_{fname}', renamer(field))

LibraryDatabase.update_last_modified = lambda self, book_ids, commit=False, now=None: self.new_api.update_last_modified(book_ids, now=now)

# }}}

# Legacy API to get information about many-(one, many) fields {{{
for field in ('authors', 'tags', 'publisher', 'series'):

    def getter(field: str) -> Callable[[LibraryDatabase], frozenset[str]]:
        def func(self: LibraryDatabase) -> frozenset[str]:
            return self.new_api.all_field_names(field)

        return func

    name = field[:-1] if field in {'authors', 'tags'} else field
    setattr(LibraryDatabase, f'all_{name}_names', getter(field))
LibraryDatabase.all_formats = lambda self: self.new_api.all_field_names('formats')
LibraryDatabase.all_custom = lambda self, label=None, num=None: self.new_api.all_field_names(self.custom_field_name(label, num))

for func, field in {
    'all_authors': 'authors',
    'all_titles': 'title',
    'all_tags2': 'tags',
    'all_series': 'series',
    'all_publishers': 'publisher',
}.items():

    def getter(field: str) -> Callable[[LibraryDatabase], list[tuple[int, str]]]:
        def f(self: LibraryDatabase) -> list[tuple[int, str]]:
            return self.field_id_map(field)

        return f

    setattr(LibraryDatabase, func, getter(field))

LibraryDatabase.all_tags = lambda self: list(self.all_tag_names())
LibraryDatabase.get_all_identifier_types = lambda self: list(self.new_api.fields['identifiers'].table.all_identifier_types())
LibraryDatabase.get_authors_with_ids = lambda self: [[aid, adata['name'], adata['sort'], adata['link']] for aid, adata in self.new_api.author_data().items()]
LibraryDatabase.get_author_id = lambda self, author: {icu_lower(v): k for k, v in self.new_api.get_id_map('authors').items()}.get(icu_lower(author), None)

for field in ('tags', 'series', 'publishers', 'ratings', 'languages'):

    def getter(field: str) -> Callable[[LibraryDatabase], list[list[int | str]]]:
        fname = field[:-1] if field in {'publishers', 'ratings'} else field

        def func(self: LibraryDatabase) -> list[list[int | str]]:
            return [[tid, tag] for tid, tag in self.new_api.get_id_map(fname).items()]

        return func

    setattr(LibraryDatabase, f'get_{field}_with_ids', getter(field))

for field in ('author', 'tag', 'series'):

    def getter(field: str) -> Callable[[LibraryDatabase, int], str]:
        field = field if field == 'series' else (field + 's')

        def func(self: LibraryDatabase, item_id: int) -> str:
            return self.new_api.get_item_name(field, item_id)

        return func

    setattr(LibraryDatabase, f'{field}_name', getter(field))

for field in ('publisher', 'series', 'tag'):

    def getter(field: str) -> Callable[[LibraryDatabase, int], None]:
        fname = 'tags' if field == 'tag' else field

        def func(self: LibraryDatabase, item_id: int) -> None:
            self.new_api.remove_items(fname, (item_id,))

        return func

    setattr(LibraryDatabase, f'delete_{field}_using_id', getter(field))
# }}}

# Legacy field API {{{
for func in (
    'standard_field_keys',
    '!custom_field_keys',
    'all_field_keys',
    'searchable_fields',
    'sortable_field_keys',
    'search_term_to_field_key',
    '!custom_field_metadata',
    'all_metadata',
):

    def getter(func: str) -> Callable[..., object]:
        if func.startswith('!'):
            func = func[1:]

            def meth(self: LibraryDatabase, include_composites: bool = True) -> object:
                return getattr(self.field_metadata, func)(include_composites=include_composites)

        elif func == 'search_term_to_field_key':

            def meth(self: LibraryDatabase, term: str) -> str:
                return self.field_metadata.search_term_to_field_key(term)

        else:

            def meth(self: LibraryDatabase) -> object:
                return getattr(self.field_metadata, func)()

        return meth

    setattr(LibraryDatabase, func.replace('!', ''), getter(func))
LibraryDatabase.metadata_for_field = lambda self, field: self.field_metadata.get(field)

# }}}

# Miscellaneous API {{{
for meth in (
    'get_next_series_num_for',
    'has_book',
):

    def getter(meth: str) -> Callable[[LibraryDatabase, object], float | bool]:
        def func(self: LibraryDatabase, x: object) -> float | bool:
            return getattr(self.new_api, meth)(x)

        return func

    setattr(LibraryDatabase, meth, getter(meth))

LibraryDatabase.saved_search_names = lambda self: self.new_api.saved_search_names()
LibraryDatabase.saved_search_lookup = lambda self, x: self.new_api.saved_search_lookup(x)
LibraryDatabase.saved_search_set_all = lambda self, smap: self.new_api.saved_search_set_all(smap)
LibraryDatabase.saved_search_delete = lambda self, x: self.new_api.saved_search_delete(x)
LibraryDatabase.saved_search_add = lambda self, x, y: self.new_api.saved_search_add(x, y)
LibraryDatabase.saved_search_rename = lambda self, x, y: self.new_api.saved_search_rename(x, y)
LibraryDatabase.commit_dirty_cache = lambda self: self.new_api.commit_dirty_cache()
LibraryDatabase.author_sort_from_authors = lambda self, x: self.new_api.author_sort_from_authors(x)
# Cleaning is not required anymore
LibraryDatabase.clean = LibraryDatabase.clean_custom = lambda self: None
LibraryDatabase.clean_standard_field = lambda self, field, commit=False: None
# apsw operates in autocommit mode
LibraryDatabase.commit = lambda self: None
# }}}
