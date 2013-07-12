#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, traceback
from functools import partial
from future_builtins import zip

from calibre.db import _get_next_series_num_for_list, _get_series_values
from calibre.db.adding import (
    find_books_in_directory, import_book_directory_multiple,
    import_book_directory, recursive_import, add_catalog, add_news)
from calibre.db.backend import DB
from calibre.db.cache import Cache
from calibre.db.categories import CATEGORY_SORTS
from calibre.db.view import View
from calibre.utils.date import utcnow

class LibraryDatabase(object):

    ''' Emulate the old LibraryDatabase2 interface '''

    PATH_LIMIT = DB.PATH_LIMIT
    WINDOWS_LIBRARY_PATH_LIMIT = DB.WINDOWS_LIBRARY_PATH_LIMIT
    CATEGORY_SORTS = CATEGORY_SORTS
    MATCH_TYPE = ('any', 'all')
    CUSTOM_DATA_TYPES = frozenset(['rating', 'text', 'comments', 'datetime',
        'int', 'float', 'bool', 'series', 'composite', 'enumeration'])

    @classmethod
    def exists_at(cls, path):
        return path and os.path.exists(os.path.join(path, 'metadata.db'))

    def __init__(self, library_path,
            default_prefs=None, read_only=False, is_second_db=False,
            progress_callback=lambda x, y:True, restore_all_prefs=False):

        self.is_second_db = is_second_db  # TODO: Use is_second_db
        self.listeners = set()

        backend = self.backend = DB(library_path, default_prefs=default_prefs,
                     read_only=read_only, restore_all_prefs=restore_all_prefs,
                     progress_callback=progress_callback)
        cache = self.new_api = Cache(backend)
        cache.init()
        self.data = View(cache)

        self.get_property = self.data.get_property

        for prop in (
                'author_sort', 'authors', 'comment', 'comments',
                'publisher', 'rating', 'series', 'series_index', 'tags',
                'title', 'timestamp', 'uuid', 'pubdate', 'ondevice',
                'metadata_last_modified', 'languages',
                ):
            fm = {'comment':'comments', 'metadata_last_modified':
                  'last_modified', 'title_sort':'sort'}.get(prop, prop)
            setattr(self, prop, partial(self.get_property,
                    loc=self.FIELD_MAP[fm]))

        for meth in ('get_next_series_num_for', 'has_book', 'author_sort_from_authors'):
            setattr(self, meth, getattr(self.new_api, meth))

        self.last_update_check = self.last_modified()

    def close(self):
        self.backend.close()

    def break_cycles(self):
        delattr(self.backend, 'field_metadata')
        self.data.cache.backend = None
        self.data.cache = None
        for x in ('data', 'backend', 'new_api', 'listeners',):
            delattr(self, x)

    # Library wide properties {{{
    @property
    def field_metadata(self):
        return self.backend.field_metadata

    @property
    def user_version(self):
        return self.backend.user_version

    @property
    def library_id(self):
        return self.backend.library_id

    @property
    def library_path(self):
        return self.backend.library_path

    @property
    def dbpath(self):
        return self.backend.dbpath

    def last_modified(self):
        return self.backend.last_modified()

    def check_if_modified(self):
        if self.last_modified() > self.last_update_check:
            self.refresh()
        self.last_update_check = utcnow()

    @property
    def custom_column_num_map(self):
        return self.backend.custom_column_num_map

    @property
    def custom_column_label_map(self):
        return self.backend.custom_column_label_map

    @property
    def FIELD_MAP(self):
        return self.backend.FIELD_MAP

    @property
    def formatter_template_cache(self):
        return self.data.cache.formatter_template_cache

    def initialize_template_cache(self):
        self.data.cache.initialize_template_cache()

    def all_ids(self):
        for book_id in self.data.cache.all_book_ids():
            yield book_id

    def refresh(self, field=None, ascending=True):
        self.data.cache.refresh()
        self.data.refresh(field=field, ascending=ascending)

    def add_listener(self, listener):
        '''
        Add a listener. Will be called on change events with two arguments.
        Event name and list of affected ids.
        '''
        self.listeners.add(listener)

    def notify(self, event, ids=[]):
        'Notify all listeners'
        for listener in self.listeners:
            try:
                listener(event, ids)
            except:
                traceback.print_exc()
                continue

    # }}}

    def path(self, index, index_is_id=False):
        'Return the relative path to the directory containing this books files as a unicode string.'
        book_id = index if index_is_id else self.data.index_to_id(index)
        return self.new_api.field_for('path', book_id).replace('/', os.sep)

    def abspath(self, index, index_is_id=False, create_dirs=True):
        'Return the absolute path to the directory containing this books files as a unicode string.'
        path = os.path.join(self.library_path, self.path(index, index_is_id=index_is_id))
        if create_dirs and not os.path.exists(path):
            os.makedirs(path)
        return path

    # Adding books {{{
    def create_book_entry(self, mi, cover=None, add_duplicates=True, force_id=None):
        return self.new_api.create_book_entry(mi, cover=cover, add_duplicates=add_duplicates, force_id=force_id)

    def add_books(self, paths, formats, metadata, add_duplicates=True, return_ids=False):
        books = [(mi, {fmt:path}) for mi, path, fmt in zip(metadata, paths, formats)]
        book_ids, duplicates = self.new_api.add_books(books, add_duplicates=add_duplicates, dbapi=self)
        if duplicates:
            paths, formats, metadata = [], [], []
            for mi, format_map in duplicates:
                metadata.append(mi)
                for fmt, path in format_map.iteritems():
                    formats.append(fmt)
                    paths.append(path)
            duplicates = (paths, formats, metadata)
        ids = book_ids if return_ids else len(book_ids)
        return duplicates or None, ids

    def import_book(self, mi, formats, notify=True, import_hooks=True, apply_import_tags=True, preserve_uuid=False):
        format_map = {}
        for path in formats:
            ext = os.path.splitext(path)[1][1:].upper()
            if ext == 'OPF':
                continue
            format_map[ext] = path
        book_ids, duplicates = self.new_api.add_books(
            [(mi, format_map)], add_duplicates=True, apply_import_tags=apply_import_tags, preserve_uuid=preserve_uuid, dbapi=self, run_hooks=import_hooks)
        if notify:
            self.notify('add', book_ids)
        return book_ids[0]

    def find_books_in_directory(self, dirpath, single_book_per_directory):
        return find_books_in_directory(dirpath, single_book_per_directory)

    def import_book_directory_multiple(self, dirpath, callback=None,
            added_ids=None):
        return import_book_directory_multiple(self, dirpath, callback=callback, added_ids=added_ids)

    def import_book_directory(self, dirpath, callback=None, added_ids=None):
        return import_book_directory(self, dirpath, callback=callback, added_ids=added_ids)

    def recursive_import(self, root, single_book_per_directory=True,
            callback=None, added_ids=None):
        return recursive_import(self, root, single_book_per_directory=single_book_per_directory, callback=callback, added_ids=added_ids)

    def add_catalog(self, path, title):
        return add_catalog(self.new_api, path, title)

    def add_news(self, path, arg):
        return add_news(self.new_api, path, arg)

    # }}}

    # Custom data {{{
    def add_custom_book_data(self, book_id, name, val):
        self.new_api.add_custom_book_data(name, {book_id:val})

    def add_multiple_custom_book_data(self, name, val_map, delete_first=False):
        self.new_api.add_custom_book_data(name, val_map, delete_first=delete_first)

    def get_custom_book_data(self, book_id, name, default=None):
        return self.new_api.get_custom_book_data(name, book_ids={book_id}, default=default).get(book_id, default)

    def get_all_custom_book_data(self, name, default=None):
        return self.new_api.get_custom_book_data(name, default=default)

    def delete_custom_book_data(self, book_id, name):
        self.new_api.delete_custom_book_data(name, book_ids=(book_id,))

    def delete_all_custom_book_data(self, name):
        self.new_api.delete_custom_book_data(name)

    def get_ids_for_custom_book_data(self, name):
        return list(self.new_api.get_ids_for_custom_book_data(name))
    # }}}

    # Private interface {{{

    def __iter__(self):
        for row in self.data.iterall():
            yield row

    def _get_next_series_num_for_list(self, series_indices):
        return _get_next_series_num_for_list(series_indices)

    def _get_series_values(self, val):
        return _get_series_values(val)

    # }}}

