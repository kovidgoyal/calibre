#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import os
from collections import OrderedDict, defaultdict
from threading import RLock as Lock
from typing import TYPE_CHECKING, cast

from calibre import filesystem_encoding
from calibre.db.cache import Cache
from calibre.db.legacy import LibraryDatabase, create_backend, set_global_state
from calibre.utils.filenames import samefile as _samefile
from calibre.utils.monotonic import monotonic

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Iterable

    from calibre.db.listeners import EventType
    from calibre.utils.config import JSONConfig

    # LibraryBroker loads Cache objects, GuiLibraryBroker loads LibraryDatabase objects
    type LoadedDB = Cache | LibraryDatabase


def gui_on_db_event(event_type: EventType, library_id: str, event_data: tuple[object, ...]) -> None:
    from calibre.gui2.ui import get_gui

    gui = get_gui()
    if gui is not None:
        gui.library_broker.on_db_event(event_type, library_id, event_data)


def canonicalize_path(p: str | bytes) -> str:
    if isinstance(p, bytes):
        p = p.decode(filesystem_encoding)
    p = os.path.abspath(p).replace(os.sep, '/').rstrip('/')
    return os.path.normcase(p)


def samefile(a: str | bytes, b: str | bytes) -> bool:
    a, b = canonicalize_path(a), canonicalize_path(b)
    if a == b:
        return True
    return _samefile(a, b)


def basename(path: str) -> str:
    while path and path[-1] in ('/' + os.sep):
        path = path[:-1]
    ans = os.path.basename(path)
    if not ans:
        # Can happen for a path like D:\ on windows
        if len(path) == 2 and path[1] == ':':
            ans = path[0]
    return ans or 'Library'


def init_library(library_path: str, is_default_library: bool) -> Cache:
    db = Cache(create_backend(library_path, load_user_formatter_functions=is_default_library))
    db.init()
    return db


def make_library_id_unique(library_id: str, existing: Container[str]) -> str:
    bname = library_id
    c = 0
    while library_id in existing:
        c += 1
        library_id = bname + f'{c}'
    return library_id


def library_id_from_path(path: str, existing: Container[str] = frozenset()) -> str:
    library_id = basename(path).replace(' ', '_')
    return make_library_id_unique(library_id, existing)


def correct_case_of_last_path_component(original_path: str) -> str:
    original_path = os.path.abspath(original_path)
    prefix, basename = os.path.split(original_path)
    q = basename.lower()
    try:
        equals = tuple(x for x in os.listdir(prefix) if x.lower() == q)
    except OSError:
        equals = ()
    if len(equals) > 1:
        if basename not in equals:
            basename = equals[0]
    elif equals:
        basename = equals[0]
    return os.path.join(prefix, basename)


def db_matches(db: LoadedDB, library_id: str, library_path: str | None) -> bool:
    db = db.new_api
    if getattr(db, 'server_library_id', object()) == library_id:
        return True
    dbpath = db.dbpath
    return samefile(dbpath, os.path.join(library_path, os.path.basename(dbpath)))  # ty: ignore[no-matching-overload]


class LibraryBroker:
    def __init__(self, libraries: Iterable[str]) -> None:
        self.lock = Lock()
        self.lmap: OrderedDict[str, str] = OrderedDict()
        self.library_name_map: dict[str, str] = {}
        self.original_path_map: dict[str, str] = {}
        seen: set[str] = set()
        for original_path in libraries:
            path = canonicalize_path(original_path)
            if path in seen:
                continue
            is_samefile = False
            for s in seen:
                if samefile(s, path):
                    is_samefile = True
                    break
            seen.add(path)
            if is_samefile or not LibraryDatabase.exists_at(path):
                continue
            corrected_path = correct_case_of_last_path_component(original_path)
            library_id = library_id_from_path(corrected_path, self.lmap)
            self.lmap[library_id] = path
            self.library_name_map[library_id] = basename(corrected_path)
            self.original_path_map[path] = original_path
        self.loaded_dbs: dict[str, LoadedDB | None] = {}
        self.category_caches, self.search_caches, self.tag_browser_caches = (
            defaultdict(OrderedDict),
            defaultdict(OrderedDict),
            defaultdict(OrderedDict),
        )

    def get(self, library_id: str | None = None) -> Cache | None:
        # Subclasses whose init_library() does not return Cache objects must override this
        with self:
            library_id = library_id or self.default_library
            if library_id in self.loaded_dbs:
                return cast('Cache | None', self.loaded_dbs[library_id])
            path = self.lmap.get(library_id)
            if path is None:
                return
            try:
                self.loaded_dbs[library_id] = ans = self.init_library(path, library_id == self.default_library)
                ans.new_api.server_library_id = library_id
            except Exception:
                self.loaded_dbs[library_id] = None
                raise
            return cast('Cache', ans)

    def init_library(self, library_path: str, is_default_library: bool) -> LoadedDB:
        library_path = self.original_path_map.get(library_path, library_path)
        return init_library(library_path, is_default_library)

    def close(self) -> None:
        with self:
            for db in self.loaded_dbs.values():
                getattr(db, 'close', lambda: None)()
            self.lmap, self.loaded_dbs = OrderedDict(), {}

    @property
    def default_library(self) -> str:
        return next(iter(self.lmap))

    @property
    def library_map(self) -> dict[str, str]:
        with self:
            return self.library_name_map.copy()

    def allowed_libraries(self, filter_func: Callable[[Iterable[str]], Container[str]]) -> OrderedDict[str, str]:
        with self:
            allowed_names = filter_func(basename(l) for l in self.lmap.values())
            return OrderedDict(((lid, self.library_map[lid]) for lid, path in self.lmap.items() if basename(path) in allowed_names))

    def path_for_library_id(self, library_id: str) -> str | None:
        with self:
            lpath = self.lmap.get(library_id)
            if lpath is None:
                q = library_id.lower()
                for k, v in self.lmap.items():
                    if k.lower() == q:
                        lpath = v
                        break
                else:
                    return
            return self.original_path_map.get(lpath)

    def __enter__(self) -> None:
        self.lock.acquire()

    def __exit__(self, *a: object) -> None:
        self.lock.release()


EXPIRED_AGE = 300  # seconds


def load_gui_libraries(gprefs: JSONConfig | None = None) -> list[str]:
    if gprefs is None:
        from calibre.utils.config import JSONConfig

        gprefs = JSONConfig('gui')
    stats = gprefs.get('library_usage_stats', {})
    return sorted(stats, key=stats.get, reverse=True)


def path_for_db(db: LoadedDB) -> str:
    return db.new_api.backend.library_path


class GuiLibraryBroker(LibraryBroker):
    # init_library() and gui_library_changed() only store LibraryDatabase objects
    loaded_dbs: dict[str, LibraryDatabase | None]  # ty: ignore[invalid-attribute-override]

    def __init__(self, db: LibraryDatabase) -> None:
        from calibre.gui2 import gprefs

        self.last_used_times: defaultdict[str | None, float] = defaultdict(lambda: float(-EXPIRED_AGE))
        self.gui_library_id: str | None = None
        self.listening_for_db_events = False
        LibraryBroker.__init__(self, load_gui_libraries(gprefs))
        self.gui_library_changed(db)

    def init_library(self, library_path: str, is_default_library: bool) -> LibraryDatabase:
        library_path = self.original_path_map.get(library_path, library_path)
        db = LibraryDatabase(library_path, is_second_db=True)
        if self.listening_for_db_events:
            db.new_api.add_listener(gui_on_db_event)
        return db

    def get(self, library_id: str | None = None) -> Cache | None:
        try:
            return getattr(LibraryBroker.get(self, library_id), 'new_api', None)
        finally:
            self.last_used_times[library_id or self.default_library] = monotonic()

    def start_listening_for_db_events(self) -> None:
        with self:
            self.listening_for_db_events = True
            for db in self.loaded_dbs.values():
                db.new_api.add_listener(gui_on_db_event)  # ty: ignore[unresolved-attribute]

    def on_db_event(self, event_type: EventType, library_id: str, event_data: tuple[object, ...]) -> None:
        from calibre.gui2.ui import get_gui

        gui = get_gui()
        if gui is not None:
            with self:
                db = self.loaded_dbs.get(library_id)
            if db is not None:
                gui.event_in_db.emit(db, event_type, event_data)

    def get_library(self, original_library_path: str) -> LibraryDatabase:
        library_path = canonicalize_path(original_library_path)
        with self:
            for library_id, path in self.lmap.items():
                if samefile(library_path, path):
                    db = self.loaded_dbs.get(library_id)
                    if db is None:
                        db = self.loaded_dbs[library_id] = self.init_library(path, False)
                    db.new_api.server_library_id = library_id
                    return db
            # A new library
            if library_path not in self.original_path_map:
                self.original_path_map[library_path] = original_library_path
            db = self.init_library(library_path, False)
            corrected_path = correct_case_of_last_path_component(original_library_path)
            library_id = library_id_from_path(corrected_path, self.lmap)
            db.new_api.server_library_id = library_id
            self.lmap[library_id] = library_path
            self.library_name_map[library_id] = basename(corrected_path)
            self.loaded_dbs[library_id] = db
            return db

    def prepare_for_gui_library_change(self, newloc: str) -> LibraryDatabase | None:
        # Must be called with lock held
        for library_id, path in self.lmap.items():
            db = self.loaded_dbs.get(library_id)
            if db is not None and samefile(newloc, path):
                if library_id == self.gui_library_id:
                    # Have to reload db
                    self.loaded_dbs.pop(library_id, None)
                    return
                set_global_state(db)
                return db

    def gui_library_changed(self, db: LibraryDatabase, olddb: LibraryDatabase | None = None) -> None:
        # Must be called with lock held
        original_path = path_for_db(db)
        newloc = canonicalize_path(original_path)
        for library_id, path in self.lmap.items():
            if samefile(newloc, path):
                self.loaded_dbs[library_id] = db
                self.gui_library_id = library_id
                break
        else:
            # A new library
            corrected_path = correct_case_of_last_path_component(original_path)
            library_id = self.gui_library_id = library_id_from_path(corrected_path, self.lmap)
            self.lmap[library_id] = newloc
            self.library_name_map[library_id] = basename(corrected_path)
            self.original_path_map[newloc] = original_path
            self.loaded_dbs[library_id] = db
        db.new_api.server_library_id = library_id
        if self.listening_for_db_events:
            db.new_api.add_listener(gui_on_db_event)
        if olddb is not None and samefile(path_for_db(olddb), path_for_db(db)):
            # This happens after a restore database, for example
            olddb.close(), olddb.break_cycles()
        self._prune_loaded_dbs()

    def is_gui_library(self, library_path: str) -> bool:
        with self:
            if self.gui_library_id and self.gui_library_id in self.lmap:
                return samefile(library_path, self.lmap[self.gui_library_id])
            return False

    def _prune_loaded_dbs(self) -> None:
        now = monotonic()
        for library_id in tuple(self.loaded_dbs):
            if library_id != self.gui_library_id and now - self.last_used_times[library_id] > EXPIRED_AGE:
                db = self.loaded_dbs.pop(library_id, None)
                if db is not None:
                    db.close()
                    db.break_cycles()

    def prune_loaded_dbs(self) -> None:
        with self:
            self._prune_loaded_dbs()

    def unload_library(self, library_path: str) -> None:
        with self:
            path = canonicalize_path(library_path)
            for library_id, q in self.lmap.items():
                if samefile(path, q):
                    break
            else:
                return
            db = self.loaded_dbs.pop(library_id, None)
            if db is not None:
                db.close()
                db.break_cycles()

    def remove_library(self, path: str) -> None:
        with self:
            path = canonicalize_path(path)
            for library_id, q in self.lmap.items():
                if samefile(path, q):
                    break
            else:
                return
            (
                self.lmap.pop(library_id, None),
                self.library_name_map.pop(library_id, None),
                self.original_path_map.pop(path, None),
            )
            db = self.loaded_dbs.pop(library_id, None)
            if db is not None:
                db.close()
                db.break_cycles()
