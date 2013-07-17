#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, traceback, types
from future_builtins import zip

from calibre import force_unicode, isbytestring
from calibre.constants import preferred_encoding
from calibre.db import _get_next_series_num_for_list, _get_series_values
from calibre.db.adding import (
    find_books_in_directory, import_book_directory_multiple,
    import_book_directory, recursive_import, add_catalog, add_news)
from calibre.db.backend import DB
from calibre.db.cache import Cache
from calibre.db.errors import NoSuchFormat
from calibre.db.categories import CATEGORY_SORTS
from calibre.db.view import View
from calibre.db.write import clean_identifier
from calibre.utils.date import utcnow

def cleanup_tags(tags):
    tags = [x.strip().replace(',', ';') for x in tags if x.strip()]
    tags = [x.decode(preferred_encoding, 'replace')
                if isbytestring(x) else x for x in tags]
    tags = [u' '.join(x.split()) for x in tags]
    ans, seen = [], set([])
    for tag in tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            ans.append(tag)
    return ans


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
        self.id = self.data.index_to_id
        for x in ('get_property', 'count', 'refresh_ids', 'set_marked_ids',
                  'multisort', 'search', 'search_getting_ids'):
            setattr(self, x, getattr(self.data, x))

        self.is_case_sensitive = getattr(backend, 'is_case_sensitive', False)
        self.custom_field_name = backend.custom_field_name

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
    def prefs(self):
        return self.new_api.backend.prefs

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
            self.new_api.reload_from_db()
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

    def is_empty(self):
        with self.new_api.read_lock:
            return not bool(self.new_api.fields['title'].table.book_col_map)

    def get_usage_count_by_id(self, field):
        return [[k, v] for k, v in self.new_api.get_usage_count_by_id(field).iteritems()]

    def field_id_map(self, field):
        return [(k, v) for k, v in self.new_api.get_id_map(field).iteritems()]

    def get_custom_items_with_ids(self, label=None, num=None):
        try:
            return [[k, v] for k, v in self.new_api.get_id_map(self.custom_field_name(label, num)).iteritems()]
        except ValueError:
            return []

    def refresh(self, field=None, ascending=True):
        self.data.refresh(field=field, ascending=ascending)

    def get_id_from_uuid(self, uuid):
        if uuid:
            return self.new_api.lookup_by_uuid(uuid)

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
        book_id = index if index_is_id else self.id(index)
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
        book_id = index if index_is_id else self.id(index)
        try:
            return self.new_api.add_format(book_id, fmt, stream, replace=replace, run_hooks=False, dbapi=self)
        except:
            raise
        else:
            self.notify('metadata', [book_id])

    def add_format_with_hooks(self, index, fmt, fpath, index_is_id=False, path=None, notify=True, replace=True):
        ''' path is ignored by the new API '''
        book_id = index if index_is_id else self.id(index)
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

    def sort(self, field, ascending, subsort=False):
        self.multisort([(field, ascending)])

    def get_field(self, index, key, default=None, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        mi = self.new_api.get_metadata(book_id, get_cover=key == 'cover')
        return mi.get(key, default)

    def cover_last_modified(self, index, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.cover_last_modified(book_id) or self.last_modified()

    def cover(self, index, index_is_id=False, as_file=False, as_image=False, as_path=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.cover(book_id, as_file=as_file, as_image=as_image, as_path=as_path)

    def copy_cover_to(self, index, dest, index_is_id=False, windows_atomic_move=None, use_hardlink=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.copy_cover_to(book_id, dest, use_hardlink=use_hardlink)

    def copy_format_to(self, index, fmt, dest, index_is_id=False, windows_atomic_move=None, use_hardlink=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.copy_format_to(book_id, fmt, dest, use_hardlink=use_hardlink)

    def delete_book(self, book_id, notify=True, commit=True, permanent=False, do_clean=True):
        self.new_api.remove_books((book_id,), permanent=permanent)
        if notify:
            self.notify('delete', [id])

    def dirtied(self, book_ids, commit=True):
        self.new_api.mark_as_dirty(book_ids)

    def dump_metadata(self, book_ids=None, remove_from_dirtied=True, commit=True, callback=None):
        self.new_api.dump_metadata(book_ids=book_ids, remove_from_dirtied=remove_from_dirtied, callback=callback)

    def authors_sort_strings(self, index, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        return list(self.new_api.author_sort_strings_for_books((book_id,))[book_id])

    def author_sort_from_book(self, index, index_is_id=False):
        return ' & '.join(self.authors_sort_strings(index, index_is_id=index_is_id))

    def authors_with_sort_strings(self, index, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        with self.new_api.read_lock:
            authors = self.new_api._field_ids_for('authors', book_id)
            adata = self.new_api._author_data(authors)
            return [(aid, adata[aid]['name'], adata[aid]['sort'], adata[aid]['link']) for aid in authors]

    def set_sort_field_for_author(self, old_id, new_sort, commit=True, notify=False):
        changed_books = self.new_api.set_sort_for_authors({old_id:new_sort})
        if notify:
            self.notify('metadata', list(changed_books))

    def set_link_field_for_author(self, aid, link, commit=True, notify=False):
        changed_books = self.new_api.set_link_for_authors({aid:link})
        if notify:
            self.notify('metadata', list(changed_books))

    def book_on_device(self, book_id):
        with self.new_api.read_lock:
            return self.new_api.fields['ondevice'].book_on_device(book_id)

    def book_on_device_string(self, book_id):
        return self.new_api.field_for('ondevice', book_id)

    def set_book_on_device_func(self, func):
        self.new_api.fields['ondevice'].set_book_on_device_func(func)

    @property
    def book_on_device_func(self):
        return self.new_api.fields['ondevice'].book_on_device_func

    def books_in_series(self, series_id):
        with self.new_api.read_lock:
            book_ids = self.new_api._books_for_field('series', series_id)
            ff = self.new_api._field_for
            return sorted(book_ids, key=lambda x:ff('series_index', x))

    def books_in_series_of(self, index, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
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

    def set(self, index, field, val, allow_case_change=False):
        book_id = self.id(index)
        try:
            return self.new_api.set_field(field, {book_id:val}, allow_case_change=allow_case_change)
        finally:
            self.notify('metadata', [book_id])

    def set_identifier(self, book_id, typ, val, notify=True, commit=True):
        with self.new_api.write_lock:
            identifiers = self.new_api._field_for('identifiers', book_id)
            typ, val = clean_identifier(typ, val)
            if typ:
                identifiers[typ] = val
                self.new_api._set_field('identifiers', {book_id:identifiers})
                self.notify('metadata', [book_id])

    def set_isbn(self, book_id, isbn, notify=True, commit=True):
        self.set_identifier(book_id, 'isbn', isbn, notify=notify, commit=commit)

    def set_tags(self, book_id, tags, append=False, notify=True, commit=True, allow_case_change=False):
        tags = tags or []
        with self.new_api.write_lock:
            if append:
                otags = self.new_api._field_for('tags', book_id)
                existing = {icu_lower(x) for x in otags}
                tags = list(otags) + [x for x in tags if icu_lower(x) not in existing]
            ret = self.new_api._set_field('tags', {book_id:tags}, allow_case_change=allow_case_change)
            if notify:
                self.notify('metadata', [book_id])
            return ret

    def set_metadata(self, book_id, mi, ignore_errors=False, set_title=True,
                     set_authors=True, commit=True, force_changes=False, notify=True):
        self.new_api.set_metadata(book_id, mi, ignore_errors=ignore_errors, set_title=set_title, set_authors=set_authors, force_changes=force_changes)
        if notify:
            self.notify('metadata', [book_id])

    def remove_all_tags(self, ids, notify=False, commit=True):
        self.new_api.set_field('tags', {book_id:() for book_id in ids})
        if notify:
            self.notify('metadata', ids)

    def _do_bulk_modify(self, field, ids, add, remove, notify):
        add = cleanup_tags(add)
        remove = cleanup_tags(remove)
        remove = set(remove) - set(add)
        if not ids or (not add and not remove):
            return

        remove = {icu_lower(x) for x in remove}
        with self.new_api.write_lock:
            val_map = {}
            for book_id in ids:
                tags = list(self.new_api._field_for(field, book_id))
                existing = {icu_lower(x) for x in tags}
                tags.extend(t for t in add if icu_lower(t) not in existing)
                tags = tuple(t for t in tags if icu_lower(t) not in remove)
                val_map[book_id] = tags
            self.new_api._set_field(field, val_map, allow_case_change=False)

        if notify:
            self.notify('metadata', ids)

    def bulk_modify_tags(self, ids, add=[], remove=[], notify=False):
        self._do_bulk_modify('tags', ids, add, remove, notify)

    def set_custom_bulk_multiple(self, ids, add=[], remove=[], label=None, num=None, notify=False):
        data = self.backend.custom_field_metadata(label, num)
        if not data['editable']:
            raise ValueError('Column %r is not editable'%data['label'])
        if data['datatype'] != 'text' or not data['is_multiple']:
            raise ValueError('Column %r is not text/multiple'%data['label'])
        field = self.custom_field_name(label, num)
        self._do_bulk_modify(field, ids, add, remove, notify)

    def unapply_tags(self, book_id, tags, notify=True):
        self.bulk_modify_tags((book_id,), remove=tags, notify=notify)

    def is_tag_used(self, tag):
        return icu_lower(tag) in {icu_lower(x) for x in self.new_api.all_field_names('tags')}

    def delete_tag(self, tag):
        self.delete_tags((tag,))

    def delete_tags(self, tags):
        with self.new_api.write_lock:
            tag_map = {icu_lower(v):k for k, v in self.new_api._get_id_map('tags').iteritems()}
            tag_ids = (tag_map.get(icu_lower(tag), None) for tag in tags)
            tag_ids = tuple(tid for tid in tag_ids if tid is not None)
            if tag_ids:
                self.new_api._remove_items('tags', tag_ids)

    def has_id(self, book_id):
        return book_id in self.new_api.all_book_ids()

    def format(self, index, fmt, index_is_id=False, as_file=False, mode='r+b', as_path=False, preserve_filename=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.format(book_id, fmt, as_file=as_file, as_path=as_path, preserve_filename=preserve_filename)

    def format_abspath(self, index, fmt, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.format_abspath(book_id, fmt)

    def format_path(self, index, fmt, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        ans = self.new_api.format_abspath(book_id, fmt)
        if ans is None:
            raise NoSuchFormat('Record %d has no format: %s'%(book_id, fmt))
        return ans

    def format_files(self, index, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        return [(v, k) for k, v in self.new_api.format_files(book_id).iteritems()]

    def format_metadata(self, book_id, fmt, allow_cache=True, update_db=False, commit=False):
        return self.new_api.format_metadata(book_id, fmt, allow_cache=allow_cache, update_db=update_db)

    def format_last_modified(self, book_id, fmt):
        m = self.format_metadata(book_id, fmt)
        if m:
            return m['mtime']

    def formats(self, index, index_is_id=False, verify_formats=True):
        book_id = index if index_is_id else self.id(index)
        ans = self.new_api.formats(book_id, verify_formats=verify_formats)
        if ans:
            return ','.join(ans)

    def has_format(self, index, fmt, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.has_format(book_id, fmt)

    def refresh_format_cache(self):
        self.new_api.refresh_format_cache()

    def refresh_ondevice(self):
        self.new_api.refresh_ondevice()

    def tags_older_than(self, tag, delta, must_have_tag=None, must_have_authors=None):
        for book_id in sorted(self.new_api.tags_older_than(tag, delta=delta, must_have_tag=must_have_tag, must_have_authors=must_have_authors)):
            yield book_id

    def sizeof_format(self, index, fmt, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.format_metadata(book_id, fmt).get('size', None)

    def get_metadata(self, index, index_is_id=False, get_cover=False, get_user_categories=True, cover_as_data=False):
        book_id = index if index_is_id else self.id(index)
        return self.new_api.get_metadata(book_id, get_cover=get_cover, get_user_categories=get_user_categories, cover_as_data=cover_as_data)

    def rename_series(self, old_id, new_name, change_index=True):
        self.new_api.rename_items('series', {old_id:new_name}, change_index=change_index)

    def get_custom(self, index, label=None, num=None, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        ans = self.new_api.field_for(self.custom_field_name(label, num), book_id)
        if isinstance(ans, tuple):
            ans = list(ans)
        return ans

    def get_custom_extra(self, index, label=None, num=None, index_is_id=False):
        data = self.backend.custom_field_metadata(label, num)
        # add future datatypes with an extra column here
        if data['datatype'] != 'series':
            return None
        book_id = index if index_is_id else self.id(index)
        return self.new_api.field_for(self.custom_field_name(label, num) + '_index', book_id)

    def get_custom_and_extra(self, index, label=None, num=None, index_is_id=False):
        book_id = index if index_is_id else self.id(index)
        data = self.backend.custom_field_metadata(label, num)
        ans = self.new_api.field_for(self.custom_field_name(label, num), book_id)
        if isinstance(ans, tuple):
            ans = list(ans)
        if data['datatype'] != 'series':
            return (ans, None)
        return (ans, self.new_api.field_for(self.custom_field_name(label, num) + '_index', book_id))

    def get_next_cc_series_num_for(self, series, label=None, num=None):
        data = self.backend.custom_field_metadata(label, num)
        if data['datatype'] != 'series':
            return None
        return self.new_api.get_next_series_num_for(series, field=self.custom_field_name(label, num))

    def is_item_used_in_multiple(self, item, label=None, num=None):
        existing_tags = self.all_custom(label=label, num=num)
        return icu_lower(item) in {icu_lower(t) for t in existing_tags}

    def delete_custom_item_using_id(self, item_id, label=None, num=None):
        self.new_api.remove_items(self.custom_field_name(label, num), (item_id,))

    def rename_custom_item(self, old_id, new_name, label=None, num=None):
        self.new_api.rename_items(self.custom_field_name(label, num), {old_id:new_name}, change_index=False)

    def delete_item_from_multiple(self, item, label=None, num=None):
        field = self.custom_field_name(label, num)
        existing = self.new_api.get_id_map(field)
        rmap = {icu_lower(v):k for k, v in existing.iteritems()}
        item_id = rmap.get(icu_lower(item), None)
        if item_id is None:
            return []
        return list(self.new_api.remove_items(field, (item_id,)))

    def set_custom(self, book_id, val, label=None, num=None, append=False,
                   notify=True, extra=None, commit=True, allow_case_change=False):
        field = self.custom_field_name(label, num)
        data = self.backend.custom_field_metadata(label, num)
        if data['datatype'] == 'composite':
            return set()
        if not data['editable']:
            raise ValueError('Column %r is not editable'%data['label'])
        if data['datatype'] == 'enumeration' and (
                val and val not in data['display']['enum_values']):
            return set()
        with self.new_api.write_lock:
            if append and data['is_multiple']:
                current = self.new_api._field_for(field, book_id)
                existing = {icu_lower(x) for x in current}
                val = current + tuple(x for x in self.new_api.fields[field].writer.adapter(val) if icu_lower(x) not in existing)
                affected_books = self.new_api._set_field(field, {book_id:val}, allow_case_change=allow_case_change)
            else:
                affected_books = self.new_api._set_field(field, {book_id:val}, allow_case_change=allow_case_change)
            if data['datatype'] == 'series':
                extra = 1.0 if extra is None else extra
                self.new_api._set_field(field + '_index', {book_id:extra})
        if notify and affected_books:
            self.notify('metadata', list(affected_books))
        return affected_books

    def set_custom_bulk(self, ids, val, label=None, num=None,
                   append=False, notify=True, extras=None):
        if extras is not None and len(extras) != len(ids):
            raise ValueError('Length of ids and extras is not the same')
        field = self.custom_field_name(label, num)
        data = self.backend.custom_field_metadata(label, num)
        if data['datatype'] == 'composite':
            return set()
        if data['datatype'] == 'enumeration' and (
                val and val not in data['display']['enum_values']):
            return
        if not data['editable']:
            raise ValueError('Column %r is not editable'%data['label'])

        if append:
            for book_id in ids:
                self.set_custom(book_id, val, label=label, num=num, append=True, notify=False)
        else:
            with self.new_api.write_lock:
                self.new_api._set_field(field, {book_id:val for book_id in ids}, allow_case_change=False)
            if extras is not None:
                self.new_api._set_field(field + '_index', {book_id:val for book_id, val in zip(ids, extras)})
        if notify:
            self.notify('metadata', list(ids))

    def delete_custom_column(self, label=None, num=None):
        self.new_api.delete_custom_column(label, num)

    def create_custom_column(self, label, name, datatype, is_multiple, editable=True, display={}):
        self.new_api.create_custom_column(label, name, datatype, is_multiple, editable=editable, display=display)

    def set_custom_column_metadata(self, num, name=None, label=None, is_editable=None, display=None, notify=True):
        changed = self.new_api.set_custom_column_metadata(num, name=name, label=label, is_editable=is_editable, display=display)
        if changed and notify:
            self.notify('metadata', [])

    # Private interface {{{
    def __iter__(self):
        for row in self.data.iterall():
            yield row

    def _get_next_series_num_for_list(self, series_indices):
        return _get_next_series_num_for_list(series_indices)

    def _get_series_values(self, val):
        return _get_series_values(val)

    # }}}

MT = lambda func: types.MethodType(func, None, LibraryDatabase)

# Legacy getter API {{{
for prop in ('author_sort', 'authors', 'comment', 'comments', 'publisher',
             'rating', 'series', 'series_index', 'tags', 'title', 'title_sort',
             'timestamp', 'uuid', 'pubdate', 'ondevice', 'metadata_last_modified', 'languages',):
    def getter(prop):
        fm = {'comment':'comments', 'metadata_last_modified':
                'last_modified', 'title_sort':'sort'}.get(prop, prop)
        def func(self, index, index_is_id=False):
            return self.get_property(index, index_is_id=index_is_id, loc=self.FIELD_MAP[fm])
        return func
    setattr(LibraryDatabase, prop, MT(getter(prop)))

for prop in ('series', 'publisher'):
    def getter(field):
        def func(self, index, index_is_id=False):
            book_id = index if index_is_id else self.id(index)
            ans = self.new_api.field_ids_for(field, book_id)
            try:
                return ans[0]
            except IndexError:
                pass
        return func
    setattr(LibraryDatabase, prop + '_id', MT(getter(prop)))

LibraryDatabase.format_hash = MT(lambda self, book_id, fmt:self.new_api.format_hash(book_id, fmt))
LibraryDatabase.index = MT(lambda self, book_id, cache=False:self.data.id_to_index(book_id))
LibraryDatabase.has_cover = MT(lambda self, book_id:self.new_api.field_for('cover', book_id))
LibraryDatabase.get_tags = MT(lambda self, book_id:set(self.new_api.field_for('tags', book_id)))
LibraryDatabase.get_identifiers = MT(
    lambda self, index, index_is_id=False: self.new_api.field_for('identifiers', index if index_is_id else self.id(index)))
LibraryDatabase.isbn = MT(
    lambda self, index, index_is_id=False: self.get_identifiers(index, index_is_id=index_is_id).get('isbn', None))
# }}}

# Legacy setter API {{{
for field in (
    '!authors', 'author_sort', 'comment', 'has_cover', 'identifiers', 'languages',
    'pubdate', '!publisher', 'rating', '!series', 'series_index', 'timestamp', 'uuid',
    'title', 'title_sort',
):
    def setter(field):
        has_case_change = field.startswith('!')
        field = {'comment':'comments', 'title_sort':'sort'}.get(field, field)
        if has_case_change:
            field = field[1:]
            acc = field == 'series'
            def func(self, book_id, val, notify=True, commit=True, allow_case_change=acc):
                ret = self.new_api.set_field(field, {book_id:val}, allow_case_change=allow_case_change)
                if notify:
                    self.notify([book_id])
                return ret
        elif field == 'has_cover':
            def func(self, book_id, val):
                self.new_api.set_field('cover', {book_id:bool(val)})
        else:
            null_field = field in {'title', 'sort', 'uuid'}
            retval = (True if field == 'sort' else None)
            def func(self, book_id, val, notify=True, commit=True):
                if not val and null_field:
                    return (False if field == 'sort' else None)
                ret = self.new_api.set_field(field, {book_id:val})
                if notify:
                    self.notify([book_id])
                return ret if field == 'languages' else retval
        return func
    setattr(LibraryDatabase, 'set_%s' % field.replace('!', ''), MT(setter(field)))

for field in ('authors', 'tags', 'publisher'):
    def renamer(field):
        def func(self, old_id, new_name):
            id_map = self.new_api.rename_items(field, {old_id:new_name})[1]
            if field == 'authors':
                return id_map[old_id]
        return func
    fname = field[:-1] if field in {'tags', 'authors'} else field
    setattr(LibraryDatabase, 'rename_%s' % fname, MT(renamer(field)))

LibraryDatabase.update_last_modified = MT(
    lambda self, book_ids, commit=False, now=None: self.new_api.update_last_modified(book_ids, now=now))

# }}}

# Legacy API to get information about many-(one, many) fields {{{
for field in ('authors', 'tags', 'publisher', 'series'):
    def getter(field):
        def func(self):
            return self.new_api.all_field_names(field)
        return func
    name = field[:-1] if field in {'authors', 'tags'} else field
    setattr(LibraryDatabase, 'all_%s_names' % name, MT(getter(field)))
LibraryDatabase.all_formats = MT(lambda self:self.new_api.all_field_names('formats'))
LibraryDatabase.all_custom = MT(lambda self, label=None, num=None:self.new_api.all_field_names(self.custom_field_name(label, num)))

for func, field in {'all_authors':'authors', 'all_titles':'title', 'all_tags2':'tags', 'all_series':'series', 'all_publishers':'publisher'}.iteritems():
    def getter(field):
        def func(self):
            return self.field_id_map(field)
        return func
    setattr(LibraryDatabase, func, MT(getter(field)))

LibraryDatabase.all_tags = MT(lambda self: list(self.all_tag_names()))
LibraryDatabase.get_all_identifier_types = MT(lambda self: list(self.new_api.fields['identifiers'].table.all_identifier_types()))
LibraryDatabase.get_authors_with_ids = MT(
    lambda self: [[aid, adata['name'], adata['sort'], adata['link']] for aid, adata in self.new_api.author_data().iteritems()])
LibraryDatabase.get_author_id = MT(
    lambda self, author: {icu_lower(v):k for k, v in self.new_api.get_id_map('authors').iteritems()}.get(icu_lower(author), None))

for field in ('tags', 'series', 'publishers', 'ratings', 'languages'):
    def getter(field):
        fname = field[:-1] if field in {'publishers', 'ratings'} else field
        def func(self):
            return [[tid, tag] for tid, tag in self.new_api.get_id_map(fname).iteritems()]
        return func
    setattr(LibraryDatabase, 'get_%s_with_ids' % field, MT(getter(field)))

for field in ('author', 'tag', 'series'):
    def getter(field):
        field = field if field == 'series' else (field+'s')
        def func(self, item_id):
            return self.new_api.get_item_name(field, item_id)
        return func
    setattr(LibraryDatabase, '%s_name' % field, MT(getter(field)))

for field in ('publisher', 'series', 'tag'):
    def getter(field):
        fname = 'tags' if field == 'tag' else field
        def func(self, item_id):
            self.new_api.remove_items(fname, (item_id,))
        return func
    setattr(LibraryDatabase, 'delete_%s_using_id' % field, MT(getter(field)))
# }}}

# Legacy field API {{{
for func in (
    'standard_field_keys', '!custom_field_keys', 'all_field_keys',
    'searchable_fields', 'sortable_field_keys',
    'search_term_to_field_key', '!custom_field_metadata',
    'all_metadata'):
    def getter(func):
        if func.startswith('!'):
            func = func[1:]
            def meth(self, include_composites=True):
                return getattr(self.field_metadata, func)(include_composites=include_composites)
        elif func == 'search_term_to_field_key':
            def meth(self, term):
                return self.field_metadata.search_term_to_field_key(term)
        else:
            def meth(self):
                return getattr(self.field_metadata, func)()
        return meth
    setattr(LibraryDatabase, func.replace('!', ''), MT(getter(func)))
LibraryDatabase.metadata_for_field = MT(lambda self, field:self.field_metadata.get(field))

# }}}

# Miscellaneous API {{{
for meth in ('get_next_series_num_for', 'has_book', 'author_sort_from_authors'):
    def getter(meth):
        def func(self, x):
            return getattr(self.new_api, meth)(x)
        return func
    setattr(LibraryDatabase, meth, MT(getter(meth)))

# Cleaning is not required anymore
LibraryDatabase.clean = LibraryDatabase.clean_custom = MT(lambda self:None)
LibraryDatabase.clean_standard_field = MT(lambda self, field, commit=False:None)
# apsw operates in autocommit mode
LibraryDatabase.commit = MT(lambda self:None)
# }}}

del MT





