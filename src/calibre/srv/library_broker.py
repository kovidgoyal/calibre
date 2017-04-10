#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from collections import OrderedDict, defaultdict
from threading import Lock

from calibre import filesystem_encoding
from calibre.db.cache import Cache
from calibre.db.legacy import LibraryDatabase, create_backend, set_global_state
from calibre.utils.filenames import samefile
from calibre.utils.monotonic import monotonic


def init_library(library_path, is_default_library):
    db = Cache(
        create_backend(
            library_path, load_user_formatter_functions=is_default_library
        )
    )
    db.init()
    return db


def make_library_id_unique(library_id, existing):
    bname = library_id
    c = 0
    while library_id in existing:
        c += 1
        library_id = bname + ('%d' % c)
    return library_id


def canonicalize_path(p):
    if isinstance(p, bytes):
        p = p.decode(filesystem_encoding)
    p = os.path.abspath(p).replace(os.sep, '/').rstrip('/')
    return p


def library_id_from_path(path, existing):
    library_id = os.path.basename(path).replace(' ', '_')
    return make_library_id_unique(library_id, existing)


class LibraryBroker(object):

    def __init__(self, libraries):
        self.lock = Lock()
        self.lmap = {}
        seen = set()
        for i, path in enumerate(canonicalize_path(p) for p in libraries):
            if path in seen:
                continue
            seen.add(path)
            if not LibraryDatabase.exists_at(path):
                continue
            library_id = library_id_from_path(path, self.lmap)
            if i == 0:
                self.default_library = library_id
            self.lmap[library_id] = path
        self.loaded_dbs = {}
        self.category_caches, self.search_caches, self.tag_browser_caches = (
            defaultdict(OrderedDict), defaultdict(OrderedDict), defaultdict(OrderedDict))

    def get(self, library_id=None):
        with self:
            library_id = library_id or self.default_library
            if library_id in self.loaded_dbs:
                return self.loaded_dbs[library_id]
            path = self.lmap.get(library_id)
            if path is None:
                return
            try:
                self.loaded_dbs[library_id] = ans = self.init_library(
                    path, library_id == self.default_library
                )
                ans.new_api.server_library_id = library_id
            except Exception:
                self.loaded_dbs[library_id] = None
                raise
            return ans

    def init_library(self, library_path, is_default_library):
        return init_library(library_path, is_default_library)

    def close(self):
        with self:
            for db in self.loaded_dbs.itervalues():
                getattr(db, 'close', lambda: None)()
            self.lmap, self.loaded_dbs = {}, {}

    @property
    def library_map(self):
        return {k: os.path.basename(v) for k, v in self.lmap.iteritems()}

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, *a):
        self.lock.release()


EXPIRED_AGE = 300  # seconds


class GuiLibraryBroker(LibraryBroker):

    def __init__(self, db):
        from calibre.gui2 import gprefs
        stats = gprefs.get('library_usage_stats', {})
        libraries = sorted(stats, key=stats.get, reverse=True)
        self.last_used_times = defaultdict(lambda: -EXPIRED_AGE)
        self.gui_library_id = None
        LibraryBroker.__init__(self, libraries)
        self.gui_library_changed(db)

    def init_library(self, library_path, is_default_library):
        return LibraryDatabase(library_path, is_second_db=True)

    def get(self, library_id=None):
        try:
            return getattr(LibraryBroker.get(self, library_id), 'new_api', None)
        finally:
            self.last_used_times[library_id or self.default_library] = monotonic()

    def get_library(self, library_path):
        library_path = canonicalize_path(library_path)
        with self:
            for library_id, path in self.lmap.iteritems():
                if samefile(library_path, path):
                    db = self.loaded_dbs.get(library_id)
                    if db is None:
                        db = self.loaded_dbs[library_id] = self.init_library(path, False)
                    return db
            db = self.init_library(library_path, False)
            library_id = library_id_from_path(library_path, self.lmap)
            self.lmap[library_id] = library_path
            self.loaded_dbs[library_id] = db
            return db

    def prepare_for_gui_library_change(self, newloc):
        # Must be called with lock held
        for library_id, path in self.lmap.iteritems():
            db = self.loaded_dbs.get(library_id)
            if db is not None and samefile(newloc, path):
                if library_id == self.gui_library_id:
                    # Have to reload db
                    self.loaded_dbs.pop(library_id, None)
                    return
                set_global_state(db)
                return db

    def gui_library_changed(self, db, prune=True):
        # Must be called with lock held
        newloc = canonicalize_path(db.backend.library_path)
        for library_id, path in self.lmap.iteritems():
            if samefile(newloc, path):
                self.loaded_dbs[library_id] = db
                self.gui_library_id = library_id
                break
        else:
            library_id = self.gui_library_id = library_id_from_path(newloc, self.lmap)
            self.lmap[library_id] = newloc
            self.loaded_dbs[library_id] = db
        if prune:
            self._prune_loaded_dbs()

    def _prune_loaded_dbs(self):
        now = monotonic()
        for library_id in tuple(self.loaded_dbs):
            if library_id != self.gui_library_id and now - self.last_used_times[library_id] > EXPIRED_AGE:
                db = self.loaded_dbs.pop(library_id)
                db.close()
                db.break_cycles()

    def prune_loaded_dbs(self):
        with self:
            self._prune_loaded_dbs()

    def remove_library(self, path):
        with self:
            path = canonicalize_path(path)
            for library_id, q in self.lmap.iteritems():
                if samefile(path, q):
                    break
            else:
                return
            self.lmap.pop(library_id, None)
            db = self.loaded_dbs.pop(library_id, None)
            if db is not None:
                db.close()
                db.break_cycles()
