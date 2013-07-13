#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, traceback, types
from functools import partial
from future_builtins import zip

from calibre import force_unicode
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

        MT = lambda func: types.MethodType(func, self, LibraryDatabase)

        for meth in ('get_next_series_num_for', 'has_book', 'author_sort_from_authors'):
            setattr(self, meth, getattr(self.new_api, meth))

        # Legacy API to get information about many-(one, many) fields
        for field in ('authors', 'tags', 'publisher', 'series'):
            def getter(field):
                def func(self):
                    return self.new_api.all_field_names(field)
                return func
            name = field[:-1] if field in {'authors', 'tags'} else field
            setattr(self, 'all_%s_names' % name, MT(getter(field)))
            self.all_formats = MT(lambda self:self.new_api.all_field_names('formats'))

        for func, field in {'all_authors':'authors', 'all_titles':'title', 'all_tags2':'tags', 'all_series':'series', 'all_publishers':'publisher'}.iteritems():
            setattr(self, func, partial(self.field_id_map, field))
        self.all_tags = MT(lambda self: list(self.all_tag_names()))
        self.get_authors_with_ids = MT(
            lambda self: [[aid, adata['name'], adata['sort'], adata['link']] for aid, adata in self.new_api.author_data().iteritems()])
        for field in ('tags', 'series', 'publishers', 'ratings', 'languages'):
            def getter(field):
                fname = field[:-1] if field in {'publishers', 'ratings'} else field
                def func(self):
                    return [[tid, tag] for tid, tag in self.new_api.get_id_map(fname).iteritems()]
                return func
            setattr(self, 'get_%s_with_ids' % field,
                    MT(getter(field)))
        for field in ('author', 'tag', 'series'):
            def getter(field):
                field = field if field == 'series' else (field+'s')
                def func(self, item_id):
                    return self.new_api.get_item_name(field, item_id)
                return func
            setattr(self, '%s_name' % field, MT(getter(field)))

        # Legacy field API
        for func in (
            'standard_field_keys', 'custom_field_keys', 'all_field_keys',
            'searchable_fields', 'sortable_field_keys',
            'search_term_to_field_key', 'custom_field_metadata',
            'all_metadata'):
            setattr(self, func, getattr(self.field_metadata, func))
        self.metadata_for_field = self.field_metadata.get

        self.last_update_check = self.last_modified()
        self.book_on_device_func = None
        # Cleaning is not required anymore
        self.clean = self.clean_custom = MT(lambda self:None)
        self.clean_standard_field = MT(lambda self, field, commit=False:None)
        # apsw operates in autocommit mode
        self.commit = MT(lambda self:None)

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

    def get_usage_count_by_id(self, field):
        return [[k, v] for k, v in self.new_api.get_usage_count_by_id(field).iteritems()]

    def field_id_map(self, field):
        return [(k, v) for k, v in self.new_api.get_id_map(field).iteritems()]

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

    def add_format(self, index, fmt, stream, index_is_id=False, path=None, notify=True, replace=True, copy_function=None):
        ''' path and copy_function are ignored by the new API '''
        book_id = index if index_is_id else self.data.index_to_id(index)
        try:
            return self.new_api.add_format(book_id, fmt, stream, replace=replace, run_hooks=False, dbapi=self)
        except:
            raise
        else:
            self.notify('metadata', [book_id])

    def add_format_with_hooks(self, index, fmt, fpath, index_is_id=False, path=None, notify=True, replace=True):
        ''' path is ignored by the new API '''
        book_id = index if index_is_id else self.data.index_to_id(index)
        try:
            return self.new_api.add_format(book_id, fmt, fpath, replace=replace, run_hooks=True, dbapi=self)
        except:
            raise
        else:
            self.notify('metadata', [book_id])

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

    def get_field(self, index, key, default=None, index_is_id=False):
        book_id = index if index_is_id else self.data.index_to_id(index)
        mi = self.new_api.get_metadata(book_id, get_cover=key == 'cover')
        return mi.get(key, default)

    def authors_sort_strings(self, index, index_is_id=False):
        book_id = index if index_is_id else self.data.index_to_id(index)
        with self.new_api.read_lock:
            authors = self.new_api._field_ids_for('authors', book_id)
            adata = self.new_api._author_data(authors)
            return [adata[aid]['sort'] for aid in authors]

    def author_sort_from_book(self, index, index_is_id=False):
        return ' & '.join(self.authors_sort_strings(index, index_is_id=index_is_id))

    def authors_with_sort_strings(self, index, index_is_id=False):
        book_id = index if index_is_id else self.data.index_to_id(index)
        with self.new_api.read_lock:
            authors = self.new_api._field_ids_for('authors', book_id)
            adata = self.new_api._author_data(authors)
            return [(aid, adata[aid]['name'], adata[aid]['sort'], adata[aid]['link']) for aid in authors]

    def book_on_device(self, book_id):
        if callable(self.book_on_device_func):
            return self.book_on_device_func(book_id)
        return None

    def book_on_device_string(self, book_id):
        loc = []
        count = 0
        on = self.book_on_device(book_id)
        if on is not None:
            m, a, b, count = on[:4]
            if m is not None:
                loc.append(_('Main'))
            if a is not None:
                loc.append(_('Card A'))
            if b is not None:
                loc.append(_('Card B'))
        return ', '.join(loc) + ((_(' (%s books)')%count) if count > 1 else '')

    def set_book_on_device_func(self, func):
        self.book_on_device_func = func

    def books_in_series(self, series_id):
        with self.new_api.read_lock:
            book_ids = self.new_api._books_for_field('series', series_id)
            ff = self.new_api._field_for
            return sorted(book_ids, key=lambda x:ff('series_index', x))

    def books_in_series_of(self, index, index_is_id=False):
        book_id = index if index_is_id else self.data.index_to_id(index)
        series_ids = self.new_api.field_ids_for('series', book_id)
        if not series_ids:
            return []
        return self.books_in_series(series_ids[0])

    def books_with_same_title(self, mi, all_matches=True):
        title = mi.title
        ans = set()
        if title:
            title = icu_lower(force_unicode(title))
            for book_id, x in self.new_api.get_id_map('title').iteritems():
                if icu_lower(x) == title:
                    ans.add(book_id)
                    if not all_matches:
                        break
        return ans

    def set_conversion_options(self, book_id, fmt, options):
        self.new_api.set_conversion_options({book_id:options}, fmt=fmt)

    def conversion_options(self, book_id, fmt):
        return self.new_api.conversion_options(book_id, fmt=fmt)

    def has_conversion_options(self, ids, format='PIPE'):
        return self.new_api.has_conversion_options(ids, fmt=format)

    def delete_conversion_options(self, book_id, fmt, commit=True):
        self.new_api.delete_conversion_options((book_id,), fmt=fmt)

    # Private interface {{{
    def __iter__(self):
        for row in self.data.iterall():
            yield row

    def _get_next_series_num_for_list(self, series_indices):
        return _get_next_series_num_for_list(series_indices)

    def _get_series_values(self, val):
        return _get_series_values(val)

    # }}}

