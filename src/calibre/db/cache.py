#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import hashlib
import operator
import os
import random
import shutil
import sys
import traceback
import weakref
from collections import defaultdict
from collections.abc import MutableSet, Set
from functools import partial, wraps
from io import DEFAULT_BUFFER_SIZE, BytesIO
from queue import Queue
from threading import Lock
from time import mktime, monotonic, sleep, time
from typing import Iterable, NamedTuple, Optional, Tuple

from calibre import as_unicode, detect_ncpus, isbytestring
from calibre.constants import iswindows, preferred_encoding
from calibre.customize.ui import run_plugins_on_import, run_plugins_on_postadd, run_plugins_on_postdelete, run_plugins_on_postimport
from calibre.db import SPOOL_SIZE, _get_next_series_num_for_list
from calibre.db.annotations import merge_annotations
from calibre.db.categories import get_categories
from calibre.db.constants import COVER_FILE_NAME, DATA_DIR_NAME, NOTES_DIR_NAME
from calibre.db.errors import NoSuchBook, NoSuchFormat
from calibre.db.fields import IDENTITY, InvalidLinkTable, create_field
from calibre.db.lazy import FormatMetadata, FormatsList, ProxyMetadata
from calibre.db.listeners import EventDispatcher, EventType
from calibre.db.locking import DowngradeLockError, LockingError, SafeReadLock, create_locks, try_lock
from calibre.db.notes.connect import copy_marked_up_text
from calibre.db.search import Search
from calibre.db.tables import VirtualTable
from calibre.db.utils import type_safe_sort_key_function
from calibre.db.write import get_series_values, uniq
from calibre.ebooks import check_ebook_format
from calibre.ebooks.metadata import author_to_author_sort, string_to_authors, title_sort
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ptempfile import PersistentTemporaryFile, SpooledTemporaryFile, base_dir
from calibre.utils.config import prefs, tweaks
from calibre.utils.date import UNDEFINED_DATE, is_date_undefined, timestampfromdt, utcnow
from calibre.utils.date import now as nowf
from calibre.utils.filenames import make_long_path_useable
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import sort_key
from calibre.utils.localization import canonicalize_lang
from polyglot.builtins import cmp, iteritems, itervalues, string_or_bytes


class ExtraFile(NamedTuple):
    relpath: str
    file_path: str
    stat_result: os.stat_result


def api(f):
    f.is_cache_api = True
    return f


def read_api(f):
    f = api(f)
    f.is_read_api = True
    return f


def write_api(f):
    f = api(f)
    f.is_read_api = False
    return f


def wrap_simple(lock, func):
    @wraps(func)
    def call_func_with_lock(*args, **kwargs):
        try:
            with lock:
                return func(*args, **kwargs)
        except DowngradeLockError:
            # We already have an exclusive lock, no need to acquire a shared
            # lock. See the safe_read_lock properties' documentation for why
            # this is necessary.
            return func(*args, **kwargs)
    return call_func_with_lock


def run_import_plugins(path_or_stream, fmt):
    fmt = fmt.lower()
    if hasattr(path_or_stream, 'seek'):
        path_or_stream.seek(0)
        pt = PersistentTemporaryFile('_import_plugin.'+fmt)
        shutil.copyfileobj(path_or_stream, pt, 1024**2)
        pt.close()
        path = pt.name
    else:
        path = path_or_stream
    return run_plugins_on_import(path, fmt)


def _add_newbook_tag(mi):
    tags = prefs['new_book_tags']
    if tags:
        for tag in [t.strip() for t in tags]:
            if tag:
                if not mi.tags:
                    mi.tags = [tag]
                elif tag not in mi.tags:
                    mi.tags.append(tag)


def _add_default_custom_column_values(mi, fm):
    cols = fm.custom_field_metadata(include_composites=False)
    for cc,col in iteritems(cols):
        dv = col['display'].get('default_value', None)
        try:
            if dv is not None:
                if not mi.get_user_metadata(cc, make_copy=False):
                    mi.set_user_metadata(cc, col)
                dt = col['datatype']
                if dt == 'datetime' and icu_lower(dv) == 'now':
                    dv = nowf()
                mi.set(cc, dv)
        except:
            traceback.print_exc()


dynamic_category_preferences = frozenset({'grouped_search_make_user_categories', 'grouped_search_terms', 'user_categories'})


class Cache:

    '''
    An in-memory cache of the metadata.db file from a calibre library.
    This class also serves as a threadsafe API for accessing the database.
    The in-memory cache is maintained in normal form for maximum performance.

    SQLITE is simply used as a way to read and write from metadata.db robustly.
    All table reading/sorting/searching/caching logic is re-implemented. This
    was necessary for maximum performance and flexibility.
    '''
    EventType = EventType
    fts_indexing_sleep_time = 4  # seconds

    def __init__(self, backend, library_database_instance=None):
        self.shutting_down = False
        self.is_doing_rebuild_or_vacuum = False
        self.backend = backend
        self.library_database_instance = (None if library_database_instance is None else
                                          weakref.ref(library_database_instance))
        self.event_dispatcher = EventDispatcher()
        self.fields = {}
        self.composites = {}
        self.read_lock, self.write_lock = create_locks()
        self.format_metadata_cache = defaultdict(dict)
        self.formatter_template_cache = {}
        self.dirtied_cache = {}
        self.link_maps_cache = {}
        self.extra_files_cache = {}
        self.vls_for_books_cache = None
        self.vls_for_books_lib_in_process = None
        self.vls_cache_lock = Lock()
        self.dirtied_sequence = 0
        self.cover_caches = set()
        self.clear_search_cache_count = 0

        # Implement locking for all simple read/write API methods
        # An unlocked version of the method is stored with the name starting
        # with a leading underscore. Use the unlocked versions when the lock
        # has already been acquired.
        for name in dir(self):
            func = getattr(self, name)
            ira = getattr(func, 'is_read_api', None)
            if ira is not None:
                # Save original function
                setattr(self, '_'+name, func)
                # Wrap it in a lock
                lock = self.read_lock if ira else self.write_lock
                setattr(self, name, wrap_simple(lock, func))

        self._search_api = Search(self, 'saved_searches', self.field_metadata.get_search_terms())
        self.initialize_dynamic()
        self.initialize_fts()

    @property
    def new_api(self):
        return self

    @property
    def library_id(self):
        return self.backend.library_id

    @property
    def dbpath(self):
        return self.backend.dbpath

    @property
    def is_fat_filesystem(self):
        return self.backend.is_fat_filesystem

    @property
    def safe_read_lock(self):
        ''' A safe read lock is a lock that does nothing if the thread already
        has a write lock, otherwise it acquires a read lock. This is necessary
        to prevent DowngradeLockErrors, which can happen when updating the
        search cache in the presence of composite columns. Updating the search
        cache holds an exclusive lock, but searching a composite column
        involves reading field values via ProxyMetadata which tries to get a
        shared lock. There may be other scenarios that trigger this as well.

        This property returns a new lock object on every access. This lock
        object is not recursive (for performance) and must only be used in a
        with statement as ``with cache.safe_read_lock:`` otherwise bad things
        will happen.'''
        return SafeReadLock(self.read_lock)

    @write_api
    def ensure_has_search_category(self, fail_on_existing=True):
        if len(self._search_api.saved_searches.names()) > 0:
            self.field_metadata.add_search_category(label='search', name=_('Saved searches'), fail_on_existing=fail_on_existing)

    def _initialize_dynamic_categories(self):
        # Reconstruct the user categories, putting them into field_metadata
        fm = self.field_metadata
        fm.remove_dynamic_categories()
        for user_cat in sorted(self._pref('user_categories', {}), key=sort_key):
            cat_name = '@' + user_cat  # add the '@' to avoid name collision
            while cat_name:
                try:
                    fm.add_user_category(label=cat_name, name=user_cat)
                except ValueError:
                    break  # Can happen since we are removing dots and adding parent categories ourselves
                cat_name = cat_name.rpartition('.')[0]

        # add grouped search term user categories
        muc = frozenset(self._pref('grouped_search_make_user_categories', []))
        for cat in sorted(self._pref('grouped_search_terms', {}), key=sort_key):
            if cat in muc:
                # There is a chance that these can be duplicates of an existing
                # user category. Print the exception and continue.
                try:
                    self.field_metadata.add_user_category(label='@' + cat, name=cat)
                except ValueError:
                    traceback.print_exc()
        self._ensure_has_search_category()

        self.field_metadata.add_grouped_search_terms(
                                    self._pref('grouped_search_terms', {}))
        self._refresh_search_locations()

    @write_api
    def initialize_dynamic(self):
        self.backend.dirty_books_with_dirtied_annotations()
        self.dirtied_cache = {x:i for i, x in enumerate(self.backend.dirtied_books())}
        if self.dirtied_cache:
            self.dirtied_sequence = max(itervalues(self.dirtied_cache))+1
        self._initialize_dynamic_categories()

    @write_api
    def initialize_template_cache(self):
        self.formatter_template_cache = {}

    @write_api
    def set_user_template_functions(self, user_template_functions):
        self.backend.set_user_template_functions(user_template_functions)

    @write_api
    def clear_composite_caches(self, book_ids=None):
        for field in itervalues(self.composites):
            field.clear_caches(book_ids=book_ids)

    @write_api
    def clear_search_caches(self, book_ids=None):
        self.clear_search_cache_count += 1
        self._search_api.update_or_clear(self, book_ids)
        self.vls_for_books_cache = None
        self.vls_for_books_lib_in_process = None

    @write_api
    def clear_extra_files_cache(self, book_id=None):
        if book_id is None:
            self.extra_files_cache = {}
        else:
            self.extra_files_cache.pop(book_id, None)

    @read_api
    def last_modified(self):
        return self.backend.last_modified()

    @write_api
    def clear_caches(self, book_ids=None, template_cache=True, search_cache=True):
        if template_cache:
            self._initialize_template_cache()  # Clear the formatter template cache
        for field in itervalues(self.fields):
            if hasattr(field, 'clear_caches'):
                field.clear_caches(book_ids=book_ids)  # Clear the composite cache and ondevice caches
        if book_ids:
            for book_id in book_ids:
                self.format_metadata_cache.pop(book_id, None)
        else:
            self.format_metadata_cache.clear()
        if search_cache:
            self._clear_search_caches(book_ids)
        self._clear_link_map_cache(book_ids)

    @write_api
    def clear_link_map_cache(self, book_ids=None):
        if book_ids is None:
            self.link_maps_cache = {}
        else:
            for book in book_ids:
                self.link_maps_cache.pop(book, None)

    @write_api
    def reload_from_db(self, clear_caches=True):
        if clear_caches:
            self._clear_caches()
        with self.backend.conn:  # Prevent other processes, such as calibredb from interrupting the reload by locking the db
            self.backend.prefs.load_from_db()
            self._search_api.saved_searches.load_from_db()
            for field in itervalues(self.fields):
                if hasattr(field, 'table'):
                    field.table.read(self.backend)  # Reread data from metadata.db

    @property
    def field_metadata(self):
        return self.backend.field_metadata

    def _get_metadata(self, book_id, get_user_categories=True):  # {{{
        mi = Metadata(None, template_cache=self.formatter_template_cache)

        mi._proxy_metadata = ProxyMetadata(self, book_id, formatter=mi.formatter)

        author_ids = self._field_ids_for('authors', book_id)
        adata = self._author_data(author_ids)
        aut_list = [adata[i] for i in author_ids]
        aum = []
        aus = {}
        for rec in aut_list:
            aut = rec['name']
            aum.append(aut)
            aus[aut] = rec['sort']
        mi.title       = self._field_for('title', book_id,
                default_value=_('Unknown'))
        mi.authors     = aum
        mi.author_sort = self._field_for('author_sort', book_id,
                default_value=_('Unknown'))
        mi.author_sort_map = aus
        mi.comments    = self._field_for('comments', book_id)
        mi.publisher   = self._field_for('publisher', book_id)
        n = utcnow()
        mi.timestamp   = self._field_for('timestamp', book_id, default_value=n)
        mi.pubdate     = self._field_for('pubdate', book_id, default_value=n)
        mi.uuid        = self._field_for('uuid', book_id,
                default_value='dummy')
        mi.title_sort  = self._field_for('sort', book_id,
                default_value=_('Unknown'))
        mi.last_modified = self._field_for('last_modified', book_id,
                default_value=n)
        formats = self._field_for('formats', book_id)
        mi.format_metadata = {}
        mi.languages = list(self._field_for('languages', book_id))
        if not formats:
            good_formats = None
        else:
            mi.format_metadata = FormatMetadata(self, book_id, formats)
            good_formats = FormatsList(sorted(formats), mi.format_metadata)
        # These three attributes are returned by the db2 get_metadata(),
        # however, we dont actually use them anywhere other than templates, so
        # they have been removed, to avoid unnecessary overhead. The templates
        # all use _proxy_metadata.
        # mi.book_size   = self._field_for('size', book_id, default_value=0)
        # mi.ondevice_col = self._field_for('ondevice', book_id, default_value='')
        # mi.db_approx_formats = formats
        mi.formats = good_formats
        mi.has_cover = _('Yes') if self._field_for('cover', book_id,
                default_value=False) else ''
        mi.tags = list(self._field_for('tags', book_id, default_value=()))
        mi.series = self._field_for('series', book_id)
        if mi.series:
            mi.series_index = self._field_for('series_index', book_id,
                    default_value=1.0)
        mi.rating = self._field_for('rating', book_id)
        mi.set_identifiers(self._field_for('identifiers', book_id,
            default_value={}))
        mi.application_id = book_id
        mi.id = book_id
        for key, meta in self.field_metadata.custom_iteritems():
            mi.set_user_metadata(key, meta)
            if meta['datatype'] != 'composite':
                # composites are evaluated on demand in metadata.book.base
                # because their value is None
                val = self._field_for(key, book_id)
                if isinstance(val, tuple):
                    val = list(val)
                extra = self._field_for(key+'_index', book_id)
                mi.set(key, val=val, extra=extra)

        mi.link_maps = self._get_all_link_maps_for_book(book_id)

        user_cat_vals = {}
        if get_user_categories:
            user_cats = self._pref('user_categories', {})
            for ucat in user_cats:
                res = []
                for name,cat,ign in user_cats[ucat]:
                    v = mi.get(cat, None)
                    if isinstance(v, list):
                        if name in v:
                            res.append([name,cat])
                    elif name == v:
                        res.append([name,cat])
                user_cat_vals[ucat] = res
        mi.user_categories = user_cat_vals

        return mi
    # }}}

    @api
    def init(self):
        '''
        Initialize this cache with data from the backend.
        '''
        with self.write_lock:
            self.backend.read_tables()
            bools_are_tristate = self.backend.prefs['bools_are_tristate']

            for field, table in iteritems(self.backend.tables):
                self.fields[field] = create_field(field, table, bools_are_tristate,
                                          self.backend.get_template_functions)
                if table.metadata['datatype'] == 'composite':
                    self.composites[field] = self.fields[field]

            self.fields['ondevice'] = create_field('ondevice',
                    VirtualTable('ondevice'), bools_are_tristate,
                    self.backend.get_template_functions)

            for name, field in iteritems(self.fields):
                if name[0] == '#' and name.endswith('_index'):
                    field.series_field = self.fields[name[:-len('_index')]]
                    self.fields[name[:-len('_index')]].index_field = field
                elif name == 'series_index':
                    field.series_field = self.fields['series']
                    self.fields['series'].index_field = field
                elif name == 'authors':
                    field.author_sort_field = self.fields['author_sort']
                elif name == 'title':
                    field.title_sort_field = self.fields['sort']
        if self.backend.prefs['update_all_last_mod_dates_on_start']:
            self.update_last_modified(self.all_book_ids())
            self.backend.prefs.set('update_all_last_mod_dates_on_start', False)

    # FTS API {{{
    def initialize_fts(self):
        self.fts_queue_thread = None
        self.fts_measuring_rate = None
        self.fts_num_done_since_start = 0
        self.fts_job_queue = Queue()
        self.fts_indexing_left = self.fts_indexing_total = 0
        fts = self.backend.initialize_fts(weakref.ref(self))
        if self.is_fts_enabled():
            self.start_fts_pool()
        return fts

    def start_fts_pool(self):
        from threading import Event, Thread
        self.fts_dispatch_stop_event = Event()
        self.fts_queue_thread = Thread(name='FTSQueue', target=Cache.dispatch_fts_jobs, args=(
            self.fts_job_queue, self.fts_dispatch_stop_event, weakref.ref(self)), daemon=True)
        self.fts_queue_thread.start()
        self.backend.fts.pool.initialize()
        self.backend.fts.pool.initialized.wait()
        self.queue_next_fts_job()

    @read_api
    def is_fts_enabled(self):
        return self.backend.fts_enabled

    @write_api
    def fts_start_measuring_rate(self, measure=True):
        self.fts_measuring_rate = monotonic() if measure else None
        self.fts_num_done_since_start = 0

    def _update_fts_indexing_numbers(self, job_time=None):
        # this is called when new formats are added and when a format is
        # indexed, but NOT when books or formats are deleted, so total may not
        # be up to date.
        nl = self.backend.fts.number_dirtied()
        nt = self.backend.get('SELECT COUNT(*) FROM main.data')[0][0] or 0
        if not nl:
            self._fts_start_measuring_rate(measure=False)
        if job_time is not None and self.fts_measuring_rate is not None:
            self.fts_num_done_since_start += 1
        if (self.fts_indexing_left, self.fts_indexing_total) != (nl, nt) or job_time is not None:
            self.fts_indexing_left = nl
            self.fts_indexing_total = nt
            self.event_dispatcher(EventType.indexing_progress_changed, *self._fts_indexing_progress())

    @read_api
    def fts_indexing_progress(self):
        rate = None
        if self.fts_measuring_rate is not None and self.fts_num_done_since_start > 4:
            rate = self.fts_num_done_since_start / (monotonic() - self.fts_measuring_rate)
        return self.fts_indexing_left, self.fts_indexing_total, rate

    @write_api
    def enable_fts(self, enabled=True, start_pool=True):
        fts = self.backend.enable_fts(weakref.ref(self) if enabled else None)
        if fts and start_pool:  # used in the tests
            self.start_fts_pool()
        if not fts and self.fts_queue_thread:
            self.fts_job_queue.put(None)
            self.fts_queue_thread = None
            self.fts_job_queue = Queue()
        if fts:
            self._update_fts_indexing_numbers()
        return fts

    @write_api
    def fts_unindex(self, book_id, fmt=None):
        self.backend.fts_unindex(book_id, fmt=fmt)

    @staticmethod
    def dispatch_fts_jobs(queue, stop_dispatch, dbref):
        from .fts.text import is_fmt_ok

        def do_one():
            self = dbref()
            if self is None:
                return False
            start_time = monotonic()
            with self.read_lock:
                if not self.backend.fts_enabled:
                    return False
                book_id, fmt = self.backend.get_next_fts_job()
                if book_id is None:
                    return False
                path = self._format_abspath(book_id, fmt)
            if not path or not is_fmt_ok(fmt):
                with self.write_lock:
                    self.backend.remove_dirty_fts(book_id, fmt)
                    self._update_fts_indexing_numbers()
                return True

            with self.read_lock, open(path, 'rb') as src, PersistentTemporaryFile(suffix=f'.{fmt.lower()}') as pt:
                sz = 0
                h = hashlib.sha1()
                while True:
                    chunk = src.read(DEFAULT_BUFFER_SIZE)
                    if not chunk:
                        break
                    sz += len(chunk)
                    h.update(chunk)
                    pt.write(chunk)
            with self.write_lock:
                queued = self.backend.queue_fts_job(book_id, fmt, pt.name, sz, h.hexdigest(), start_time)
                if not queued:  # means a dirtied book was removed from the dirty list because the text has not changed
                    self._update_fts_indexing_numbers(monotonic() - start_time)
                return self.backend.fts_has_idle_workers

        def loop_while_more_available():
            self = dbref()
            if not self or not self.backend.fts_enabled:
                return
            has_more = True
            while has_more and not self.shutting_down and self.backend.fts_enabled and not stop_dispatch.is_set():
                try:
                    has_more = do_one()
                except Exception:
                    if self.backend.fts_enabled:
                        traceback.print_exc()
                sleep(self.fts_indexing_sleep_time)

        while not getattr(dbref(), 'shutting_down', True):
            x = queue.get()
            if x is None:
                break
            loop_while_more_available()

    @write_api
    def queue_next_fts_job(self):
        if not self.backend.fts_enabled:
            return
        self.fts_job_queue.put(True)
        self._update_fts_indexing_numbers()

    @write_api
    def commit_fts_result(self, book_id, fmt, fmt_size, fmt_hash, text, err_msg, start_time):
        ans = self.backend.commit_fts_result(book_id, fmt, fmt_size, fmt_hash, text, err_msg)
        self._update_fts_indexing_numbers(monotonic() - start_time)
        return ans

    @write_api
    def reindex_fts_book(self, book_id, *fmts):
        if not self.is_fts_enabled():
            return
        if not fmts:
            fmts = self._formats(book_id)
        self.backend.reindex_fts_book(book_id, *fmts)
        self._queue_next_fts_job()

    @api
    def reindex_fts(self):
        if not self.is_fts_enabled():
            return
        with self.write_lock:
            self._shutdown_fts()
        self._shutdown_fts(stage=2)
        with self.write_lock:
            self.backend.reindex_fts()
            fts = self.initialize_fts()
            fts.initialize(self.backend.conn)  # ensure fts is pre-initialized needed for the tests
            self._queue_next_fts_job()
        return fts

    @write_api
    def set_fts_num_of_workers(self, num):
        existing = self.backend.fts_num_of_workers
        if num != existing:
            self.backend.fts_num_of_workers = num
            if num > existing:
                self._queue_next_fts_job()
            return True
        return False

    @write_api
    def set_fts_speed(self, slow=True):
        orig = self.fts_indexing_sleep_time
        if slow:
            self.fts_indexing_sleep_time = Cache.fts_indexing_sleep_time
            changed = self._set_fts_num_of_workers(1)
        else:
            self.fts_indexing_sleep_time = 0.1
            changed = self._set_fts_num_of_workers(max(1, detect_ncpus()))
        changed = changed or orig != self.fts_indexing_sleep_time
        if changed and self.fts_measuring_rate is not None:
            self._fts_start_measuring_rate()
        return changed

    @write_api  # we need to use write locking as SQLITE gives a locked table error if multiple FTS queries are made at the same time
    def fts_search(
        self,
        fts_engine_query,
        use_stemming=True,
        highlight_start=None,
        highlight_end=None,
        snippet_size=None,
        restrict_to_book_ids=None,
        return_text=True,
        result_type=tuple,
        process_each_result=None,
    ):
        return result_type(self.backend.fts_search(
            fts_engine_query,
            use_stemming=use_stemming,
            highlight_start=highlight_start,
            highlight_end=highlight_end,
            snippet_size=snippet_size,
            return_text=return_text,
            restrict_to_book_ids=restrict_to_book_ids,
            process_each_result=process_each_result,
        ))

    # }}}

    # Notes API {{{
    @read_api
    def notes_for(self, field, item_id) -> str:
        ' Return the notes document or an empty string if not found '
        return self.backend.notes_for(field, item_id)

    @read_api
    def notes_data_for(self, field, item_id) -> str:
        ' Return all notes data as a dict or None if note does not exist '
        return self.backend.notes_data_for(field, item_id)

    @read_api
    def get_all_items_that_have_notes(self, field_name=None) -> set[int] | dict[str, set[int]]:
        ' Return all item_ids for items that have notes in the specified field or all fields if field_name is None '
        return self.backend.get_all_items_that_have_notes(field_name)

    @read_api
    def field_supports_notes(self, field=None) -> bool:
        ' Return True iff the specified field supports notes. If field is None return frozenset of all fields that support notes. '
        if field is None:
            return self.backend.notes.allowed_fields
        return field in self.backend.notes.allowed_fields

    @read_api
    def items_with_notes_in_book(self, book_id: int) -> dict[str, dict[int, str]]:
        ' Return a dict of field to items that have associated notes for that field for the specified book '
        ans = {}
        for k in self.backend.notes.allowed_fields:
            try:
                field = self.fields[k]
            except KeyError:
                continue
            v = {}
            for item_id in field.ids_for_book(book_id):
                if self.backend.notes_for(k, item_id):
                    v[item_id] = field.table.id_map[item_id]
            if v:
                ans[k] = v
        return ans

    @write_api
    def set_notes_for(self, field, item_id, doc: str, searchable_text: str = copy_marked_up_text, resource_hashes=(), remove_unused_resources=False) -> int:
        '''
        Set the notes document. If the searchable text is different from the document, specify it as searchable_text. If the document
        references resources their hashes must be present in resource_hashes. Set remove_unused_resources to True to cleanup unused
        resources, note that updating a note automatically cleans up resources pertaining to that note anyway.
        '''
        return self.backend.set_notes_for(field, item_id, doc, searchable_text, resource_hashes, remove_unused_resources)

    @write_api
    def add_notes_resource(self, path_or_stream_or_data, name: str, mtime: float = None) -> int:
        ' Add the specified resource so it can be referenced by notes and return its content hash '
        return self.backend.add_notes_resource(path_or_stream_or_data, name, mtime)

    @read_api
    def get_notes_resource(self, resource_hash) -> Optional[dict]:
        ' Return a dict containing the resource data and name or None if no resource with the specified hash is found '
        return self.backend.get_notes_resource(resource_hash)

    @read_api
    def notes_resources_used_by(self, field, item_id):
        ' Return the set of resource hashes of all resources used by the note for the specified item '
        return frozenset(self.backend.notes_resources_used_by(field, item_id))

    @write_api
    def unretire_note_for(self, field, item_id) -> int:
        ' Unretire a previously retired note for the specified item. Notes are retired when an item is removed from the database '
        return self.backend.unretire_note_for(field, item_id)

    @read_api
    def export_note(self, field, item_id) -> str:
        ' Export the note as a single HTML document with embedded images as data: URLs '
        return self.backend.export_note(field, item_id)

    @write_api
    def import_note(self, field, item_id, path_to_html_file, path_is_data=False):
        ' Import a previously exported note or an arbitrary HTML file as the note for the specified item '
        if path_is_data:
            html = path_to_html_file
            ctime = mtime = time()
            basedir = base_dir()
        else:
            with open(path_to_html_file, 'rb') as f:
                html = f.read()
                st = os.stat(f.fileno())
                ctime, mtime = st.st_ctime, st.st_mtime
            basedir = os.path.dirname(os.path.abspath(path_to_html_file))
        return self.backend.import_note(field, item_id, html, basedir, ctime, mtime)

    @write_api  # we need to use write locking as SQLITE gives a locked table error if multiple FTS queries are made at the same time
    def search_notes(
        self,
        fts_engine_query='',
        use_stemming=True,
        highlight_start=None,
        highlight_end=None,
        snippet_size=None,
        restrict_to_fields=(),
        return_text=True,
        result_type=tuple,
        process_each_result=None,
        limit=None,
    ):
        ' Search the text of notes using an FTS index. If the query is empty return all notes. '
        return result_type(self.backend.search_notes(
            fts_engine_query,
            use_stemming=use_stemming,
            highlight_start=highlight_start,
            highlight_end=highlight_end,
            snippet_size=snippet_size,
            return_text=return_text,
            restrict_to_fields=restrict_to_fields,
            process_each_result=process_each_result,
            limit=limit,
        ))
    # }}}

    # Cache Layer API {{{

    @write_api
    def add_listener(self, event_callback_function, check_already_added=False):
        '''
        Register a callback function that will be called after certain actions are
        taken on this database. The function must take three arguments:
        (:class:`EventType`, library_id, event_type_specific_data)
        '''
        self.event_dispatcher.library_id = getattr(self, 'server_library_id', self.library_id)
        if check_already_added and event_callback_function in self.event_dispatcher:
            return False
        self.event_dispatcher.add_listener(event_callback_function)
        return True

    @write_api
    def remove_listener(self, event_callback_function):
        self.event_dispatcher.remove_listener(event_callback_function)

    @read_api
    def field_for(self, name, book_id, default_value=None):
        '''
        Return the value of the field ``name`` for the book identified
        by ``book_id``. If no such book exists or it has no defined
        value for the field ``name`` or no such field exists, then
        ``default_value`` is returned.

        ``default_value`` is not used for title, title_sort, authors, author_sort
        and series_index. This is because these always have values in the db.
        ``default_value`` is used for all custom columns.

        The returned value for is_multiple fields are always tuples, even when
        no values are found (in other words, default_value is ignored). The
        exception is identifiers for which the returned value is always a dictionary.
        The returned tuples are always in link order, that is, the order in
        which they were created.
        '''
        if self.composites and name in self.composites:
            return self.composite_for(name, book_id,
                    default_value=default_value)
        try:
            field = self.fields[name]
        except KeyError:
            return default_value
        if field.is_multiple:
            default_value = field.default_value
        try:
            return field.for_book(book_id, default_value=default_value)
        except (KeyError, IndexError):
            return default_value

    @read_api
    def fast_field_for(self, field_obj, book_id, default_value=None):
        ' Same as field_for, except that it avoids the extra lookup to get the field object '
        if field_obj.is_composite:
            return field_obj.get_value_with_cache(book_id, self._get_proxy_metadata)
        if field_obj.is_multiple:
            default_value = field_obj.default_value
        try:
            return field_obj.for_book(book_id, default_value=default_value)
        except (KeyError, IndexError):
            return default_value

    @read_api
    def all_field_for(self, field, book_ids, default_value=None):
        ' Same as field_for, except that it operates on multiple books at once '
        field_obj = self.fields[field]
        return {book_id:self._fast_field_for(field_obj, book_id, default_value=default_value) for book_id in book_ids}

    @read_api
    def composite_for(self, name, book_id, mi=None, default_value=''):
        try:
            f = self.fields[name]
        except KeyError:
            return default_value

        if mi is None:
            return f.get_value_with_cache(book_id, self._get_proxy_metadata)
        else:
            return f._render_composite_with_cache(book_id, mi, mi.formatter, mi.template_cache)

    @read_api
    def field_ids_for(self, name, book_id):
        '''
        Return the ids (as a tuple) for the values that the field ``name`` has on the book
        identified by ``book_id``. If there are no values, or no such book, or
        no such field, an empty tuple is returned.
        '''
        try:
            return self.fields[name].ids_for_book(book_id)
        except (KeyError, IndexError):
            return ()

    @read_api
    def books_for_field(self, name, item_id):
        '''
        Return all the books associated with the item identified by
        ``item_id``, where the item belongs to the field ``name``.

        Returned value is a set of book ids, or the empty set if the item
        or the field does not exist.
        '''
        try:
            return self.fields[name].books_for(item_id)
        except (KeyError, IndexError):
            return set()

    @read_api
    def all_book_ids(self, type=frozenset):
        '''
        Frozen set of all known book ids.
        '''
        return type(self.fields['uuid'].table.book_col_map)

    @read_api
    def all_field_ids(self, name):
        '''
        Frozen set of ids for all values in the field ``name``.
        '''
        return frozenset(iter(self.fields[name]))

    @read_api
    def all_field_names(self, field):
        ''' Frozen set of all fields names (should only be used for many-one and many-many fields) '''
        if field == 'formats':
            return frozenset(self.fields[field].table.col_book_map)

        try:
            return frozenset(self.fields[field].table.id_map.values())
        except AttributeError:
            raise ValueError('%s is not a many-one or many-many field' % field)

    @read_api
    def get_usage_count_by_id(self, field):
        ''' Return a mapping of id to usage count for all values of the specified
        field, which must be a many-one or many-many field. '''
        try:
            return {k:len(v) for k, v in iteritems(self.fields[field].table.col_book_map)}
        except AttributeError:
            raise ValueError('%s is not a many-one or many-many field' % field)

    @read_api
    def get_id_map(self, field):
        ''' Return a mapping of id numbers to values for the specified field.
        The field must be a many-one or many-many field, otherwise a ValueError
        is raised. '''
        try:
            return self.fields[field].table.id_map.copy()
        except AttributeError:
            if field == 'title':
                return self.fields[field].table.book_col_map.copy()
            raise ValueError('%s is not a many-one or many-many field' % field)

    @read_api
    def get_item_name(self, field, item_id):
        ''' Return the item name for the item specified by item_id in the
        specified field. See also :meth:`get_id_map`.'''
        return self.fields[field].table.id_map[item_id]

    @read_api
    def get_item_id(self, field, item_name, case_sensitive=False):
        ''' Return the item id for item_name or None if not found.
        This function is very slow if doing lookups for multiple names use either get_item_ids() or get_item_name_map().
        Similarly, case sensitive lookups are faster than case insensitive ones. '''
        field = self.fields[field]
        if hasattr(field, 'item_ids_for_names'):
            d = field.item_ids_for_names(self.backend, (item_name,), case_sensitive)
            for v in d.values():
                return v

    @read_api
    def get_item_ids(self, field, item_names, case_sensitive=False):
        ' Return a dict mapping item_name to the item id or None '
        field = self.fields[field]
        if hasattr(field, 'item_ids_for_names'):
            return field.item_ids_for_names(self.backend, item_names, case_sensitive)
        return dict.fromkeys(item_names)

    @read_api
    def get_item_name_map(self, field, normalize_func=None):
        ' Return mapping of item values to ids '
        if normalize_func is None:
            return {v:k for k, v in self.fields[field].table.id_map.items()}
        return {normalize_func(v):k for k, v in self.fields[field].table.id_map.items()}

    @read_api
    def author_data(self, author_ids=None):
        '''
        Return author data as a dictionary with keys: name, sort, link

        If no authors with the specified ids are found an empty dictionary is
        returned. If author_ids is None, data for all authors is returned.
        '''
        af = self.fields['authors']
        if author_ids is None:
            return {aid:af.author_data(aid) for aid in af.table.id_map}
        return {aid:af.author_data(aid) for aid in author_ids if aid in af.table.id_map}

    @read_api
    def format_hash(self, book_id, fmt):
        ''' Return the hash of the specified format for the specified book. The
        kind of hash is backend dependent, but is usually SHA-256. '''
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            raise NoSuchFormat('Record %d has no fmt: %s'%(book_id, fmt))
        return self.backend.format_hash(book_id, fmt, name, path)

    @api
    def format_metadata(self, book_id, fmt, allow_cache=True, update_db=False):
        '''
        Return the path, size and mtime for the specified format for the specified book.
        You should not use path unless you absolutely have to,
        since accessing it directly breaks the threadsafe guarantees of this API. Instead use
        the :meth:`copy_format_to` method.

        :param allow_cache: If ``True`` cached values are used, otherwise a
            slow filesystem access is done. The cache values could be out of date
            if access was performed to the filesystem outside of this API.

        :param update_db: If ``True`` The max_size field of the database is updated for this book.
        '''
        if not fmt:
            return {}
        fmt = fmt.upper()
        # allow_cache and update_db are mutually exclusive. Give priority to update_db
        if allow_cache and not update_db:
            x = self.format_metadata_cache[book_id].get(fmt, None)
            if x is not None:
                return x
        with self.safe_read_lock:
            try:
                name = self.fields['formats'].format_fname(book_id, fmt)
                path = self._field_for('path', book_id).replace('/', os.sep)
            except:
                return {}

            ans = {}
            if path and name:
                ans = self.backend.format_metadata(book_id, fmt, name, path)
                self.format_metadata_cache[book_id][fmt] = ans
        if update_db and 'size' in ans:
            with self.write_lock:
                max_size = self.fields['formats'].table.update_fmt(book_id, fmt, name, ans['size'], self.backend)
                self.fields['size'].table.update_sizes({book_id: max_size})

        return ans

    @read_api
    def format_files(self, book_id):
        field = self.fields['formats']
        fmts = field.table.book_col_map.get(book_id, ())
        return {fmt:field.format_fname(book_id, fmt) for fmt in fmts}

    @read_api
    def format_db_size(self, book_id, fmt):
        field = self.fields['formats']
        return field.format_size(book_id, fmt)

    @read_api
    def pref(self, name, default=None, namespace=None):
        ' Return the value for the specified preference or the value specified as ``default`` if the preference is not set. '
        if namespace is not None:
            return self.backend.prefs.get_namespaced(namespace, name, default)
        return self.backend.prefs.get(name, default)

    @write_api
    def set_pref(self, name, val, namespace=None):
        ' Set the specified preference to the specified value. See also :meth:`pref`. '
        if namespace is not None:
            self.backend.prefs.set_namespaced(namespace, name, val)
            return
        self.backend.prefs.set(name, val)
        if name in ('grouped_search_terms', 'virtual_libraries'):
            self._clear_search_caches()
        if name in dynamic_category_preferences:
            self._initialize_dynamic_categories()

    @api
    def get_metadata(self, book_id,
            get_cover=False, get_user_categories=True, cover_as_data=False):
        '''
        Return metadata for the book identified by book_id as a :class:`calibre.ebooks.metadata.book.base.Metadata` object.
        Note that the list of formats is not verified. If get_cover is True,
        the cover is returned, either a path to temp file as mi.cover or if
        cover_as_data is True then as mi.cover_data.
        '''

        # Check if virtual_libraries_for_books rebuilt its cache. If it did then
        # we must clear the composite caches so the new data can be taken into
        # account. Clearing the caches requires getting a write lock, so it must
        # be done outside of the closure of _get_metadata().
        composite_cache_needs_to_be_cleared = False
        with self.safe_read_lock:
            vl_cache_was_none = self.vls_for_books_cache is None
            mi = self._get_metadata(book_id, get_user_categories=get_user_categories)
            if vl_cache_was_none and self.vls_for_books_cache is not None:
                composite_cache_needs_to_be_cleared = True
        if composite_cache_needs_to_be_cleared:
            try:
                self.clear_composite_caches()
            except LockingError:
                # We can't clear the composite caches because a read lock is set.
                # As a consequence the value of a composite column that calls
                # virtual_libraries() might be wrong. Oh well. Log and keep running.
                print('Couldn\'t get write lock after vls_for_books_cache was loaded', file=sys.stderr)
                traceback.print_exc()

        if get_cover:
            if cover_as_data:
                cdata = self.cover(book_id)
                if cdata:
                    mi.cover_data = ('jpeg', cdata)
            else:
                mi.cover = self.cover(book_id, as_path=True)

        return mi

    @read_api
    def get_proxy_metadata(self, book_id):
        ''' Like :meth:`get_metadata` except that it returns a ProxyMetadata
        object that only reads values from the database on demand. This is much
        faster than get_metadata when only a small number of fields need to be
        accessed from the returned metadata object. '''
        return ProxyMetadata(self, book_id)

    @api
    def cover(self, book_id,
            as_file=False, as_image=False, as_path=False, as_pixmap=False):
        '''
        Return the cover image or None. By default, returns the cover as a
        bytestring.

        WARNING: Using as_path will copy the cover to a temp file and return
        the path to the temp file. You should delete the temp file when you are
        done with it.

        :param as_file: If True return the image as an open file object (a SpooledTemporaryFile)
        :param as_image: If True return the image as a QImage object
        :param as_pixmap: If True return the image as a QPixmap object
        :param as_path: If True return the image as a path pointing to a
                        temporary file
        '''
        if as_file:
            ret = SpooledTemporaryFile(SPOOL_SIZE)
            if not self.copy_cover_to(book_id, ret):
                ret.close()
                return
            ret.seek(0)
        elif as_path:
            pt = PersistentTemporaryFile('_dbcover.jpg')
            with pt:
                if not self.copy_cover_to(book_id, pt):
                    return
            ret = pt.name
        elif as_pixmap or as_image:
            from qt.core import QImage, QPixmap
            ret = QImage() if as_image else QPixmap()
            with self.safe_read_lock:
                path = self._format_abspath(book_id, '__COVER_INTERNAL__')
                if path:
                    ret.load(path)
        else:
            buf = BytesIO()
            if not self.copy_cover_to(book_id, buf):
                return
            ret = buf.getvalue()
        return ret

    @read_api
    def cover_or_cache(self, book_id, timestamp, as_what='bytes'):
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except AttributeError:
            return False, None, None
        return self.backend.cover_or_cache(path, timestamp, as_what)

    @read_api
    def cover_last_modified(self, book_id):
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except AttributeError:
            return
        return self.backend.cover_last_modified(path)

    @read_api
    def copy_cover_to(self, book_id, dest, use_hardlink=False, report_file_size=None):
        '''
        Copy the cover to the file like object ``dest``. Returns False
        if no cover exists or dest is the same file as the current cover.
        dest can also be a path in which case the cover is
        copied to it if and only if the path is different from the current path (taking
        case sensitivity into account).
        '''
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except AttributeError:
            return False

        return self.backend.copy_cover_to(path, dest, use_hardlink=use_hardlink,
                                          report_file_size=report_file_size)

    @write_api
    def compress_covers(self, book_ids, jpeg_quality=100, progress_callback=None):
        '''
        Compress the cover images for the specified books. A compression quality of 100
        will perform lossless compression, otherwise lossy compression.

        The progress callback will be called with the book_id and the old and new sizes
        for each book that has been processed. If an error occurs, the new size will
        be a string with the error details.
        '''
        jpeg_quality = max(10, min(jpeg_quality, 100))
        path_map = {}
        for book_id in book_ids:
            try:
                path_map[book_id] = self._field_for('path', book_id).replace('/', os.sep)
            except AttributeError:
                continue
        self.backend.compress_covers(path_map, jpeg_quality, progress_callback)

    @read_api
    def copy_format_to(self, book_id, fmt, dest, use_hardlink=False, report_file_size=None):
        '''
        Copy the format ``fmt`` to the file like object ``dest``. If the
        specified format does not exist, raises :class:`NoSuchFormat` error.
        dest can also be a path (to a file), in which case the format is copied to it, iff
        the path is different from the current path (taking case sensitivity
        into account).
        '''
        fmt = (fmt or '').upper()
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except (KeyError, AttributeError):
            raise NoSuchFormat('Record %d has no %s file'%(book_id, fmt))

        return self.backend.copy_format_to(book_id, fmt, name, path, dest,
                                               use_hardlink=use_hardlink, report_file_size=report_file_size)

    @read_api
    def format_abspath(self, book_id, fmt):
        '''
        Return absolute path to the e-book file of format `format`. You should
        almost never use this, as it breaks the threadsafe promise of this API.
        Instead use, :meth:`copy_format_to`.

        Currently used only in calibredb list, the viewer, edit book,
        compare_format to original format, open with, bulk metadata edit and
        the catalogs (via get_data_as_dict()).

        Apart from the viewer, open with and edit book, I don't believe any of
        the others do any file write I/O with the results of this call.
        '''
        fmt = (fmt or '').upper()
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return None
        if path:
            if fmt == '__COVER_INTERNAL__':
                return self.backend.cover_abspath(book_id, path)
            else:
                try:
                    name = self.fields['formats'].format_fname(book_id, fmt)
                except:
                    return None
                if name:
                    return self.backend.format_abspath(book_id, fmt, name, path)

    @read_api
    def has_format(self, book_id, fmt):
        'Return True iff the format exists on disk'
        fmt = (fmt or '').upper()
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return False
        return self.backend.has_format(book_id, fmt, name, path)

    @api
    def save_original_format(self, book_id, fmt):
        ' Save a copy of the specified format as ORIGINAL_FORMAT, overwriting any existing ORIGINAL_FORMAT. '
        fmt = fmt.upper()
        if 'ORIGINAL' in fmt:
            raise ValueError('Cannot save original of an original fmt')
        fmtfile = self.format(book_id, fmt, as_file=True)
        if fmtfile is None:
            return False
        with fmtfile:
            nfmt = 'ORIGINAL_'+fmt
            return self.add_format(book_id, nfmt, fmtfile, run_hooks=False)

    @write_api
    def restore_original_format(self, book_id, original_fmt):
        ''' Restore the specified format from the previously saved
        ORIGINAL_FORMAT, if any. Return True on success. The ORIGINAL_FORMAT is
        deleted after a successful restore. '''
        original_fmt = original_fmt.upper()
        fmt = original_fmt.partition('_')[2]
        try:
            ofmt_name = self.fields['formats'].format_fname(book_id, original_fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except Exception:
            return False
        if self.backend.is_format_accessible(book_id, original_fmt, ofmt_name, path):
            self.add_format(book_id, fmt, BytesIO(), run_hooks=False)
            fmt_name = self.fields['formats'].format_fname(book_id, fmt)
            file_size = self.backend.rename_format_file(book_id, ofmt_name, original_fmt, fmt_name, fmt, path)
            self.fields['formats'].table.update_fmt(book_id, fmt, fmt_name, file_size, self.backend)
            self._remove_formats({book_id:(original_fmt,)})
            return True
        return False

    @read_api
    def formats(self, book_id, verify_formats=True):
        '''
        Return tuple of all formats for the specified book. If verify_formats
        is True, verifies that the files exist on disk.
        '''
        ans = self.field_for('formats', book_id)
        if verify_formats and ans:
            try:
                path = self._field_for('path', book_id).replace('/', os.sep)
            except:
                return ()

            def verify(fmt):
                try:
                    name = self.fields['formats'].format_fname(book_id, fmt)
                except:
                    return False
                return self.backend.has_format(book_id, fmt, name, path)

            ans = tuple(x for x in ans if verify(x))
        return ans

    @api
    def format(self, book_id, fmt, as_file=False, as_path=False, preserve_filename=False):
        '''
        Return the e-book format as a bytestring or `None` if the format doesn't exist,
        or we don't have permission to write to the e-book file.

        :param as_file: If True the e-book format is returned as a file object. Note
                        that the file object is a SpooledTemporaryFile, so if what you want to
                        do is copy the format to another file, use :meth:`copy_format_to`
                        instead for performance.
        :param as_path: Copies the format file to a temp file and returns the
                        path to the temp file
        :param preserve_filename: If True and returning a path the filename is
                                  the same as that used in the library. Note that using
                                  this means that repeated calls yield the same
                                  temp file (which is re-created each time)
        '''
        fmt = (fmt or '').upper()
        ext = ('.'+fmt.lower()) if fmt else ''
        if as_path:
            if preserve_filename:
                with self.safe_read_lock:
                    try:
                        fname = self.fields['formats'].format_fname(book_id, fmt)
                    except:
                        return None
                    fname += ext

                bd = base_dir()
                d = os.path.join(bd, 'format_abspath')
                try:
                    os.makedirs(d)
                except:
                    pass
                ret = os.path.join(d, fname)
                try:
                    self.copy_format_to(book_id, fmt, ret)
                except NoSuchFormat:
                    return None
            else:
                with PersistentTemporaryFile(ext) as pt:
                    try:
                        self.copy_format_to(book_id, fmt, pt)
                    except NoSuchFormat:
                        return None
                    ret = pt.name
        elif as_file:
            with self.safe_read_lock:
                try:
                    fname = self.fields['formats'].format_fname(book_id, fmt)
                except:
                    return None
                fname += ext

            ret = SpooledTemporaryFile(SPOOL_SIZE)
            try:
                self.copy_format_to(book_id, fmt, ret)
            except NoSuchFormat:
                ret.close()
                return None
            ret.seek(0)
            # Various bits of code try to use the name as the default
            # title when reading metadata, so set it
            ret.name = fname
        else:
            buf = BytesIO()
            try:
                self.copy_format_to(book_id, fmt, buf)
            except NoSuchFormat:
                return None

            ret = buf.getvalue()

        return ret

    @read_api
    def newly_added_book_ids(self, count=5, book_ids=None) -> list[int]:
        ids_to_sort = self._all_book_ids(list) if book_ids is None else list(book_ids)
        ids_to_sort.sort(reverse=True)
        return ids_to_sort[:count]

    @read_api
    def size_stats(self) -> dict[str, int]:
        return self.backend.size_stats()

    @read_api
    def multisort(self, fields, ids_to_sort=None, virtual_fields=None):
        '''
        Return a list of sorted book ids. If ids_to_sort is None, all book ids
        are returned.

        fields must be a list of 2-tuples of the form (field_name,
        ascending=True or False). The most significant field is the first
        2-tuple.
        '''
        ids_to_sort = self._all_book_ids() if ids_to_sort is None else ids_to_sort
        get_metadata = self._get_proxy_metadata
        lang_map = self.fields['languages'].book_value_map
        virtual_fields = virtual_fields or {}

        fm = {'title':'sort', 'authors':'author_sort'}

        def sort_key_func(field):
            'Handle series type fields, virtual fields and the id field'
            idx = field + '_index'
            is_series = idx in self.fields
            try:
                func = self.fields[fm.get(field, field)].sort_keys_for_books(get_metadata, lang_map)
            except KeyError:
                if field == 'id':
                    return IDENTITY
                else:
                    return virtual_fields[fm.get(field, field)].sort_keys_for_books(get_metadata, lang_map)
            if is_series:
                idx_func = self.fields[idx].sort_keys_for_books(get_metadata, lang_map)

                def skf(book_id):
                    return (func(book_id), idx_func(book_id))
                return skf
            return func

        # Sort only once on any given field
        fields = uniq(fields, operator.itemgetter(0))

        if len(fields) == 1:
            keyfunc = sort_key_func(fields[0][0])
            reverse = not fields[0][1]
            try:
                return sorted(ids_to_sort, key=keyfunc, reverse=reverse)
            except Exception as err:
                print('Failed to sort database on field:', fields[0][0], 'with error:', err, file=sys.stderr)
                try:
                    return sorted(ids_to_sort, key=type_safe_sort_key_function(keyfunc), reverse=reverse)
                except Exception as err:
                    print('Failed to type-safe sort database on field:', fields[0][0], 'with error:', err, file=sys.stderr)
                    return sorted(ids_to_sort, reverse=reverse)
        sort_key_funcs = tuple(sort_key_func(field) for field, order in fields)
        orders = tuple(1 if order else -1 for _, order in fields)
        Lazy = object()  # Lazy load the sort keys for sub-sort fields

        class SortKey:

            __slots__ = 'book_id', 'sort_key'

            def __init__(self, book_id):
                self.book_id = book_id
                # Calculate only the first sub-sort key since that will always be used
                self.sort_key = [key(book_id) if i == 0 else Lazy for i, key in enumerate(sort_key_funcs)]

            def compare_to_other(self, other):
                for i, (order, self_key, other_key) in enumerate(zip(orders, self.sort_key, other.sort_key)):
                    if self_key is Lazy:
                        self_key = self.sort_key[i] = sort_key_funcs[i](self.book_id)
                    if other_key is Lazy:
                        other_key = other.sort_key[i] = sort_key_funcs[i](other.book_id)
                    ans = cmp(self_key, other_key)
                    if ans != 0:
                        return ans * order
                return 0

            def __eq__(self, other):
                return self.compare_to_other(other) == 0

            def __ne__(self, other):
                return self.compare_to_other(other) != 0

            def __lt__(self, other):
                return self.compare_to_other(other) < 0

            def __le__(self, other):
                return self.compare_to_other(other) <= 0

            def __gt__(self, other):
                return self.compare_to_other(other) > 0

            def __ge__(self, other):
                return self.compare_to_other(other) >= 0

        return sorted(ids_to_sort, key=SortKey)

    @read_api
    def search(self, query, restriction='', virtual_fields=None, book_ids=None):
        '''
        Search the database for the specified query, returning a set of matched book ids.

        :param restriction: A restriction that is ANDed to the specified query. Note that
            restrictions are cached, therefore the search for a AND b will be slower than a with restriction b.

        :param virtual_fields: Used internally (virtual fields such as on_device to search over).

        :param book_ids: If not None, a set of book ids for which books will
            be searched instead of searching all books.
        '''
        return self._search_api(self, query, restriction, virtual_fields=virtual_fields, book_ids=book_ids)

    @read_api
    def books_in_virtual_library(self, vl, search_restriction=None, virtual_fields=None):
        ' Return the set of books in the specified virtual library '
        vl = self._pref('virtual_libraries', {}).get(vl) if vl else None
        if not vl and not search_restriction:
            return self.all_book_ids()
        # We utilize the search restriction cache to speed this up
        srch = partial(self._search, virtual_fields=virtual_fields)
        if vl:
            if search_restriction:
                return frozenset(srch('', vl) & srch('', search_restriction))
            return frozenset(srch('', vl))
        return frozenset(srch('', search_restriction))

    @read_api
    def number_of_books_in_virtual_library(self, vl=None, search_restriction=None):
        if not vl and not search_restriction:
            return len(self.fields['uuid'].table.book_col_map)
        return len(self.books_in_virtual_library(vl, search_restriction))

    @api
    def get_categories(self, sort='name', book_ids=None, already_fixed=None,
                       first_letter_sort=False, uncollapsed_categories=None):
        ' Used internally to implement the Tag Browser '
        try:
            with self.safe_read_lock:
                return get_categories(self, sort=sort, book_ids=book_ids,
                                      first_letter_sort=first_letter_sort,
                                      uncollapsed_categories=uncollapsed_categories)
        except InvalidLinkTable as err:
            bad_field = err.field_name
            if bad_field == already_fixed:
                raise
            with self.write_lock:
                self.fields[bad_field].table.fix_link_table(self.backend)
            return self.get_categories(sort=sort, book_ids=book_ids, already_fixed=bad_field)

    @write_api
    def update_last_modified(self, book_ids, now=None):
        if book_ids:
            if now is None:
                now = nowf()
            f = self.fields['last_modified']
            f.writer.set_books({book_id:now for book_id in book_ids}, self.backend)
            if self.composites:
                self._clear_composite_caches(book_ids)
            self._clear_search_caches(book_ids)

    @write_api
    def mark_as_dirty(self, book_ids):
        self._update_last_modified(book_ids)
        already_dirtied = set(self.dirtied_cache).intersection(book_ids)
        new_dirtied = book_ids - already_dirtied
        already_dirtied = {book_id:self.dirtied_sequence+i for i, book_id in enumerate(already_dirtied)}
        if already_dirtied:
            self.dirtied_sequence = max(itervalues(already_dirtied)) + 1
        self.dirtied_cache.update(already_dirtied)
        if new_dirtied:
            self.backend.dirty_books(new_dirtied)
            new_dirtied = {book_id:self.dirtied_sequence+i for i, book_id in enumerate(new_dirtied)}
            self.dirtied_sequence = max(itervalues(new_dirtied)) + 1
            self.dirtied_cache.update(new_dirtied)

    @write_api
    def commit_dirty_cache(self):
        if self.dirtied_cache:
            self.backend.dirty_books(self.dirtied_cache)

    @write_api
    def check_dirtied_annotations(self):
        if not self.backend.dirty_books_with_dirtied_annotations():
            return
        book_ids = set(self.backend.dirtied_books())
        new_dirtied = book_ids - set(self.dirtied_cache)
        if new_dirtied:
            new_dirtied = {book_id:self.dirtied_sequence+i for i, book_id in enumerate(new_dirtied)}
            self.dirtied_sequence = max(itervalues(new_dirtied)) + 1
            self.dirtied_cache.update(new_dirtied)

    @write_api
    def set_field(self, name, book_id_to_val_map, allow_case_change=True, do_path_update=True):
        '''
        Set the values of the field specified by ``name``. Returns the set of all book ids that were affected by the change.

        :param book_id_to_val_map: Mapping of book_ids to values that should be applied.
        :param allow_case_change: If True, the case of many-one or many-many fields will be changed.
            For example, if a  book has the tag ``tag1`` and you set the tag for another book to ``Tag1``
            then the both books will have the tag ``Tag1`` if allow_case_change is True, otherwise they will
            both have the tag ``tag1``.
        :param do_path_update: Used internally, you should never change it.
        '''
        f = self.fields[name]
        is_series = f.metadata['datatype'] == 'series'
        update_path = name in {'title', 'authors'}
        if update_path and iswindows:
            paths = (x for x in (self._field_for('path', book_id) for book_id in book_id_to_val_map) if x)
            self.backend.windows_check_if_files_in_use(paths)

        if is_series:
            bimap, simap = {}, {}
            sfield = self.fields[name + '_index']
            for k, v in iteritems(book_id_to_val_map):
                if isinstance(v, string_or_bytes):
                    v, sid = get_series_values(v)
                else:
                    v = sid = None
                if sid is None and name.startswith('#'):
                    sid = self._fast_field_for(sfield, k)
                    sid = 1.0 if sid is None else sid  # The value to be set the db link table
                bimap[k] = v
                if sid is not None:
                    simap[k] = sid
            book_id_to_val_map = bimap

        dirtied = f.writer.set_books(
            book_id_to_val_map, self.backend, allow_case_change=allow_case_change)

        if is_series and simap:
            sf = self.fields[f.name+'_index']
            dirtied |= sf.writer.set_books(simap, self.backend, allow_case_change=False)

        if dirtied:
            if update_path and do_path_update:
                self._update_path(dirtied, mark_as_dirtied=False)
            self._mark_as_dirty(dirtied)
            self._clear_link_map_cache(dirtied)
            self.event_dispatcher(EventType.metadata_changed, name, dirtied)
        return dirtied

    @write_api
    def update_path(self, book_ids, mark_as_dirtied=True):
        for book_id in book_ids:
            title = self._field_for('title', book_id, default_value=_('Unknown'))
            try:
                author = self._field_for('authors', book_id, default_value=(_('Unknown'),))[0]
            except IndexError:
                author = _('Unknown')
            self.backend.update_path(book_id, title, author, self.fields['path'], self.fields['formats'])
            self.format_metadata_cache.pop(book_id, None)
            if mark_as_dirtied:
                self._mark_as_dirty(book_ids)
            self._clear_link_map_cache(book_ids)

    @read_api
    def get_a_dirtied_book(self):
        if self.dirtied_cache:
            return random.choice(tuple(self.dirtied_cache))
        return None

    def _metadata_as_object_for_dump(self, book_id):
        mi = self._get_metadata(book_id)
        # Always set cover to cover.jpg. Even if cover doesn't exist,
        # no harm done. This way no need to call dirtied when
        # cover is set/removed
        mi.cover = 'cover.jpg'
        mi.all_annotations = self._all_annotations_for_book(book_id)
        return mi

    @read_api
    def get_metadata_for_dump(self, book_id):
        mi = None
        # get the current sequence number for this book to pass back to the
        # backup thread. This will avoid double calls in the case where the
        # thread has not done the work between the put and the get_metadata
        sequence = self.dirtied_cache.get(book_id, None)
        if sequence is not None:
            try:
                # While a book is being created, the path is empty. Don't bother to
                # try to write the opf, because it will go to the wrong folder.
                if self._field_for('path', book_id):
                    mi = self._metadata_as_object_for_dump(book_id)
            except:
                # This almost certainly means that the book has been deleted while
                # the backup operation sat in the queue.
                traceback.print_exc()
        return mi, sequence

    @write_api
    def clear_dirtied(self, book_id, sequence):
        # Clear the dirtied indicator for the books. This is used when fetching
        # metadata, creating an OPF, and writing a file are separated into steps.
        # The last step is clearing the indicator
        dc_sequence = self.dirtied_cache.get(book_id, None)
        if dc_sequence is None or sequence is None or dc_sequence == sequence:
            self.backend.mark_book_as_clean(book_id)
            self.dirtied_cache.pop(book_id, None)

    @write_api
    def write_backup(self, book_id, raw):
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return

        self.backend.write_backup(path, raw)

    @read_api
    def dirty_queue_length(self):
        return len(self.dirtied_cache)

    @read_api
    def read_backup(self, book_id):
        ''' Return the OPF metadata backup for the book as a bytestring or None
        if no such backup exists.  '''
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return

        try:
            return self.backend.read_backup(path)
        except OSError:
            return None

    @write_api
    def dump_metadata(self, book_ids=None, remove_from_dirtied=True,
            callback=None):
        # Write metadata for each record to an individual OPF file. If callback
        # is not None, it is called once at the start with the number of book_ids
        # being processed. And once for every book_id, with arguments (book_id,
        # mi, ok).
        if book_ids is None:
            book_ids = set(self.dirtied_cache)

        if callback is not None:
            callback(len(book_ids), True, False)

        for book_id in book_ids:
            if self._field_for('path', book_id) is None:
                if callback is not None:
                    callback(book_id, None, False)
                continue
            mi, sequence = self._get_metadata_for_dump(book_id)
            if mi is None:
                if callback is not None:
                    callback(book_id, mi, False)
                continue
            try:
                raw = metadata_to_opf(mi)
                self._write_backup(book_id, raw)
                if remove_from_dirtied:
                    self._clear_dirtied(book_id, sequence)
            except:
                pass
            if callback is not None:
                callback(book_id, mi, True)

    @write_api
    def set_cover(self, book_id_data_map):
        ''' Set the cover for this book. The data can be either a QImage,
        QPixmap, file object or bytestring. It can also be None, in which
        case any existing cover is removed. '''

        for book_id, data in iteritems(book_id_data_map):
            try:
                path = self._field_for('path', book_id).replace('/', os.sep)
            except AttributeError:
                self._update_path((book_id,))
                path = self._field_for('path', book_id).replace('/', os.sep)

            self.backend.set_cover(book_id, path, data)
        for cc in self.cover_caches:
            cc.invalidate(book_id_data_map)
        return self._set_field('cover', {
            book_id:(0 if data is None else 1) for book_id, data in iteritems(book_id_data_map)})

    @write_api
    def add_cover_cache(self, cover_cache):
        if not callable(cover_cache.invalidate):
            raise ValueError('Cover caches must have an invalidate method')
        self.cover_caches.add(cover_cache)

    @write_api
    def remove_cover_cache(self, cover_cache):
        self.cover_caches.discard(cover_cache)

    @write_api
    def set_metadata(self, book_id, mi, ignore_errors=False, force_changes=False,
                     set_title=True, set_authors=True, allow_case_change=False):
        '''
        Set metadata for the book `id` from the `Metadata` object `mi`

        Setting force_changes=True will force set_metadata to update fields even
        if mi contains empty values. In this case, 'None' is distinguished from
        'empty'. If mi.XXX is None, the XXX is not replaced, otherwise it is.
        The tags, identifiers, and cover attributes are special cases. Tags and
        identifiers cannot be set to None so they will always be replaced if
        force_changes is true. You must ensure that mi contains the values you
        want the book to have. Covers are always changed if a new cover is
        provided, but are never deleted. Also note that force_changes has no
        effect on setting title or authors.
        '''
        dirtied = set()

        try:
            # Handle code passing in an OPF object instead of a Metadata object
            mi = mi.to_book_metadata()
        except (AttributeError, TypeError):
            pass

        def set_field(name, val):
            dirtied.update(self._set_field(name, {book_id:val}, do_path_update=False, allow_case_change=allow_case_change))

        path_changed = False
        if set_title and mi.title:
            path_changed = True
            set_field('title', mi.title)
        authors_changed = False
        if set_authors:
            path_changed = True
            if not mi.authors:
                mi.authors = [_('Unknown')]
            authors = []
            for a in mi.authors:
                authors += string_to_authors(a)
            set_field('authors', authors)
            authors_changed = True

        if path_changed:
            self._update_path({book_id})

        def protected_set_field(name, val):
            try:
                set_field(name, val)
            except:
                if ignore_errors:
                    traceback.print_exc()
                else:
                    raise

        # force_changes has no effect on cover manipulation
        try:
            cdata = mi.cover_data[1]
            if cdata is None and isinstance(mi.cover, string_or_bytes) and mi.cover and os.access(mi.cover, os.R_OK):
                with open(mi.cover, 'rb') as f:
                    cdata = f.read() or None
            if cdata is not None:
                self._set_cover({book_id: cdata})
        except:
            if ignore_errors:
                traceback.print_exc()
            else:
                raise

        try:
            with self.backend.conn:  # Speed up set_metadata by not operating in autocommit mode
                for field in ('rating', 'series_index', 'timestamp'):
                    val = getattr(mi, field)
                    if val is not None:
                        protected_set_field(field, val)

                val = mi.get('author_sort', None)
                if authors_changed and (not val or mi.is_null('author_sort')):
                    val = self._author_sort_from_authors(mi.authors)
                if authors_changed or (force_changes and val is not None) or not mi.is_null('author_sort'):
                    protected_set_field('author_sort', val)

                for field in ('publisher', 'series', 'tags', 'comments',
                    'languages', 'pubdate'):
                    val = mi.get(field, None)
                    if (force_changes and val is not None) or not mi.is_null(field):
                        protected_set_field(field, val)

                val = mi.get('title_sort', None)
                if (force_changes and val is not None) or not mi.is_null('title_sort'):

                    protected_set_field('sort', val)

                # identifiers will always be replaced if force_changes is True
                mi_idents = mi.get_identifiers()
                if force_changes:
                    protected_set_field('identifiers', mi_idents)
                elif mi_idents:
                    identifiers = self._field_for('identifiers', book_id, default_value={})
                    for key, val in iteritems(mi_idents):
                        if val and val.strip():  # Don't delete an existing identifier
                            identifiers[icu_lower(key)] = val
                    protected_set_field('identifiers', identifiers)

                user_mi = mi.get_all_user_metadata(make_copy=False)
                fm = self.field_metadata
                for key in user_mi:
                    if (key in fm and user_mi[key]['datatype'] == fm[key]['datatype'] and (
                        user_mi[key]['datatype'] != 'text' or (
                            user_mi[key]['is_multiple'] == fm[key]['is_multiple']))):
                        val = mi.get(key, None)
                        if force_changes or val is not None:
                            protected_set_field(key, val)
                            idx = key + '_index'
                            if idx in self.fields:
                                extra = mi.get_extra(key)
                                if extra is not None or force_changes:
                                    protected_set_field(idx, extra)
        except:
            # sqlite will rollback the entire transaction, thanks to the with
            # statement, so we have to re-read everything form the db to ensure
            # the db and Cache are in sync
            self._reload_from_db()
            raise
        return dirtied

    def _do_add_format(self, book_id, fmt, stream, name=None, mtime=None):
        path = self._field_for('path', book_id)
        if path is None:
            # Theoretically, this should never happen, but apparently it
            # does: https://www.mobileread.com/forums/showthread.php?t=233353
            self._update_path({book_id}, mark_as_dirtied=False)
            path = self._field_for('path', book_id)

        path = path.replace('/', os.sep)
        title = self._field_for('title', book_id, default_value=_('Unknown'))
        try:
            author = self._field_for('authors', book_id, default_value=(_('Unknown'),))[0]
        except IndexError:
            author = _('Unknown')

        size, fname = self.backend.add_format(book_id, fmt, stream, title, author, path, name, mtime=mtime)
        return size, fname

    @api
    def add_format(self, book_id, fmt, stream_or_path, replace=True, run_hooks=True, dbapi=None):
        '''
        Add a format to the specified book. Return True if the format was added successfully.

        :param replace: If True replace existing format, otherwise if the format already exists, return False.
        :param run_hooks: If True, file type plugins are run on the format before and after being added.
        :param dbapi: Internal use only.
        '''
        needs_close = False
        if run_hooks:
            # Run import plugins, the write lock is not held to cater for
            # broken plugins that might spin the event loop by popping up a
            # message in the GUI during the processing.
            npath = run_import_plugins(stream_or_path, fmt)
            fmt = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
            stream_or_path = open(make_long_path_useable(npath), 'rb')
            needs_close = True
            fmt = check_ebook_format(stream_or_path, fmt)

        with self.write_lock:
            if not self._has_id(book_id):
                raise NoSuchBook(book_id)
            fmt = (fmt or '').upper()
            self.format_metadata_cache[book_id].pop(fmt, None)
            try:
                name = self.fields['formats'].format_fname(book_id, fmt)
            except Exception:
                name = None

            if name and not replace:
                if needs_close:
                    stream_or_path.close()
                return False

            if hasattr(stream_or_path, 'read'):
                stream = stream_or_path
            else:
                stream = open(make_long_path_useable(stream_or_path), 'rb')
                needs_close = True
            try:
                size, fname = self._do_add_format(book_id, fmt, stream, name)
            finally:
                if needs_close:
                    stream.close()
            del stream

            max_size = self.fields['formats'].table.update_fmt(book_id, fmt, fname, size, self.backend)
            self.fields['size'].table.update_sizes({book_id: max_size})
            self._update_last_modified((book_id,))
            self.event_dispatcher(EventType.format_added, book_id, fmt)

        if run_hooks:
            # Run post import plugins, the write lock is released so the plugin
            # can call api without a locking violation.
            run_plugins_on_postimport(dbapi or self, book_id, fmt)
            stream_or_path.close()

        self.queue_next_fts_job()
        return True

    @write_api
    def remove_formats(self, formats_map, db_only=False):
        '''
        Remove the specified formats from the specified books.

        :param formats_map: A mapping of book_id to a list of formats to be removed from the book.
        :param db_only: If True, only remove the record for the format from the db, do not delete the actual format file from the filesystem.
        :return: A map of book id to set of formats actually deleted from the filesystem for that book
        '''
        table = self.fields['formats'].table
        formats_map = {book_id:frozenset((f or '').upper() for f in fmts) for book_id, fmts in iteritems(formats_map)}
        removed_map = {}

        for book_id, fmts in iteritems(formats_map):
            for fmt in fmts:
                self.format_metadata_cache[book_id].pop(fmt, None)

        if not db_only:
            removes = defaultdict(set)
            metadata_map = {}
            for book_id, fmts in iteritems(formats_map):
                try:
                    path = self._field_for('path', book_id).replace('/', os.sep)
                except:
                    continue
                for fmt in fmts:
                    try:
                        name = self.fields['formats'].format_fname(book_id, fmt)
                    except:
                        continue
                    if name and path:
                        removes[book_id].add((fmt, name, path))
                if removes[book_id]:
                    metadata_map[book_id] = {'title': self._field_for('title', book_id), 'authors': self._field_for('authors', book_id)}
            if removes:
                removed_map = self.backend.remove_formats(removes, metadata_map)

        size_map = table.remove_formats(formats_map, self.backend)
        self.fields['size'].table.update_sizes(size_map)

        for book_id, fmts in iteritems(formats_map):
            for fmt in fmts:
                run_plugins_on_postdelete(self, book_id, fmt)

        self._update_last_modified(tuple(formats_map))
        self.event_dispatcher(EventType.formats_removed, formats_map)
        return removed_map

    @read_api
    def get_next_series_num_for(self, series, field='series', current_indices=False):
        '''
        Return the next series index for the specified series, taking into account the various preferences that
        control next series number generation.

        :param field: The series-like field (defaults to the builtin series column)
        :param current_indices: If True, returns a mapping of book_id to current series_index value instead.
        '''
        books = ()
        sf = self.fields[field]
        if series:
            q = icu_lower(series)
            for val, book_ids in sf.iter_searchable_values(self._get_proxy_metadata, frozenset(self._all_book_ids())):
                if q == icu_lower(val):
                    books = book_ids
                    break
        idf = sf.index_field
        index_map = {book_id:self._fast_field_for(idf, book_id, default_value=1.0) for book_id in books}
        if current_indices:
            return index_map
        series_indices = sorted(index_map.values(), key=lambda s: s or 0)
        return _get_next_series_num_for_list(tuple(series_indices), unwrap=False)

    @read_api
    def author_sort_from_authors(self, authors, key_func=icu_lower):
        '''Given a list of authors, return the author_sort string for the authors,
        preferring the author sort associated with the author over the computed
        string. '''
        table = self.fields['authors'].table
        result = []
        rmap = {key_func(v):k for k, v in iteritems(table.id_map)}
        for aut in authors:
            aid = rmap.get(key_func(aut), None)
            result.append(author_to_author_sort(aut) if aid is None else table.asort_map[aid])
        return ' & '.join(_f for _f in result if _f)

    @read_api
    def data_for_has_book(self):
        ''' Return data suitable for use in :meth:`has_book`. This can be used for an
        implementation of :meth:`has_book` in a worker process without access to the
        db. '''
        try:
            return {icu_lower(title) for title in itervalues(self.fields['title'].table.book_col_map)}
        except TypeError:
            # Some non-unicode titles in the db
            return {icu_lower(as_unicode(title)) for title in itervalues(self.fields['title'].table.book_col_map)}

    @read_api
    def has_book(self, mi):
        ''' Return True iff the database contains an entry with the same title
        as the passed in Metadata object. The comparison is case-insensitive.
        See also :meth:`data_for_has_book`.  '''
        title = mi.title
        if title:
            if isbytestring(title):
                title = title.decode(preferred_encoding, 'replace')
            q = icu_lower(title).strip()
            for title in itervalues(self.fields['title'].table.book_col_map):
                if q == icu_lower(title):
                    return True
        return False

    @read_api
    def has_id(self, book_id):
        ' Return True iff the specified book_id exists in the db '''
        return book_id in self.fields['title'].table.book_col_map

    @write_api
    def create_book_entry(self, mi, cover=None, add_duplicates=True, force_id=None, apply_import_tags=True, preserve_uuid=False):
        if mi.tags:
            mi.tags = list(mi.tags)
        if apply_import_tags:
            _add_newbook_tag(mi)
            _add_default_custom_column_values(mi, self.field_metadata)
        if not add_duplicates and self._has_book(mi):
            return
        series_index = (self._get_next_series_num_for(mi.series) if mi.series_index is None else mi.series_index)
        try:
            series_index = float(series_index)
        except Exception:
            try:
                series_index = float(self._get_next_series_num_for(mi.series))
            except Exception:
                series_index = 1.0
        if not mi.authors:
            mi.authors = (_('Unknown'),)
        aus = mi.author_sort if not mi.is_null('author_sort') else self._author_sort_from_authors(mi.authors)
        mi.title = mi.title or _('Unknown')
        if mi.is_null('title_sort'):
            mi.title_sort = title_sort(mi.title, lang=mi.languages[0] if mi.languages else None)
        if isbytestring(aus):
            aus = aus.decode(preferred_encoding, 'replace')
        if isbytestring(mi.title):
            mi.title = mi.title.decode(preferred_encoding, 'replace')
        if force_id is None:
            self.backend.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                         (mi.title, series_index, aus))
        else:
            self.backend.execute('INSERT INTO books(id, title, series_index, author_sort) VALUES (?, ?, ?, ?)',
                         (force_id, mi.title, series_index, aus))
        book_id = self.backend.last_insert_rowid()
        self.event_dispatcher(EventType.book_created, book_id)

        mi.timestamp = utcnow() if (mi.timestamp is None or is_date_undefined(mi.timestamp)) else mi.timestamp
        mi.pubdate = UNDEFINED_DATE if mi.pubdate is None else mi.pubdate
        if cover is not None:
            mi.cover, mi.cover_data = None, (None, cover)
        self._set_metadata(book_id, mi, ignore_errors=True)
        lm = getattr(mi, 'link_maps', None)
        if lm:
            for field, link_map in lm.items():
                if self._has_link_map(field):
                    self._set_link_map(field, link_map, only_set_if_no_existing_link=True)
        if preserve_uuid and mi.uuid:
            self._set_field('uuid', {book_id:mi.uuid})
        # Update the caches for fields from the books table
        self.fields['size'].table.book_col_map[book_id] = 0
        row = next(self.backend.execute('SELECT sort, series_index, author_sort, uuid, has_cover FROM books WHERE id=?', (book_id,)))
        for field, val in zip(('sort', 'series_index', 'author_sort', 'uuid', 'cover'), row):
            if field == 'cover':
                val = bool(val)
            elif field == 'uuid':
                self.fields[field].table.uuid_to_id_map[val] = book_id
            self.fields[field].table.book_col_map[book_id] = val

        return book_id

    @api
    def add_books(self, books, add_duplicates=True, apply_import_tags=True, preserve_uuid=False, run_hooks=True, dbapi=None):
        '''
        Add the specified books to the library. Books should be an iterable of
        2-tuples, each 2-tuple of the form :code:`(mi, format_map)` where mi is a
        Metadata object and format_map is a dictionary of the form :code:`{fmt: path_or_stream}`,
        for example: :code:`{'EPUB': '/path/to/file.epub'}`.

        Returns a pair of lists: :code:`ids, duplicates`. ``ids`` contains the book ids for all newly created books in the
        database. ``duplicates`` contains the :code:`(mi, format_map)` for all books that already exist in the database
        as per the simple duplicate detection heuristic used by :meth:`has_book`.
        '''
        duplicates, ids = [], []
        for mi, format_map in books:
            book_id = self.create_book_entry(mi, add_duplicates=add_duplicates, apply_import_tags=apply_import_tags, preserve_uuid=preserve_uuid)
            if book_id is None:
                duplicates.append((mi, format_map))
            else:
                fmt_map = {}
                ids.append(book_id)
                for fmt, stream_or_path in format_map.items():
                    if self.add_format(book_id, fmt, stream_or_path, dbapi=dbapi, run_hooks=run_hooks):
                        fmt_map[fmt.lower()] = getattr(stream_or_path, 'name', stream_or_path) or '<stream>'
                run_plugins_on_postadd(dbapi or self, book_id, fmt_map)
        return ids, duplicates

    @write_api
    def remove_books(self, book_ids, permanent=False):
        ''' Remove the books specified by the book_ids from the database and delete
        their format files. If ``permanent`` is False, then the format files
        are placed in the per-library trash directory. '''
        path_map = {}
        for book_id in book_ids:
            try:
                path = self._field_for('path', book_id).replace('/', os.sep)
            except Exception:
                path = None
            path_map[book_id] = path
            if not permanent and path:
                # ensure metadata.opf is written and up-to-date so we can restore the book
                try:
                    mi = self._metadata_as_object_for_dump(book_id)
                    raw = metadata_to_opf(mi)
                    self.backend.write_backup(path, raw)
                except Exception:
                    traceback.print_exc()
        self.backend.remove_books(path_map, permanent=permanent)
        for field in itervalues(self.fields):
            try:
                table = field.table
            except AttributeError:
                continue  # Some fields like ondevice do not have tables
            else:
                table.remove_books(book_ids, self.backend)
        self._search_api.discard_books(book_ids)
        self._clear_caches(book_ids=book_ids, template_cache=False, search_cache=False)
        for cc in self.cover_caches:
            cc.invalidate(book_ids)
        self.event_dispatcher(EventType.books_removed, book_ids)

    @read_api
    def author_sort_strings_for_books(self, book_ids):
        val_map = {}
        for book_id in book_ids:
            authors = self._field_ids_for('authors', book_id)
            adata = self._author_data(authors)
            val_map[book_id] = tuple(adata[aid]['sort'] for aid in authors)
        return val_map

    @write_api
    def rename_items(self, field, item_id_to_new_name_map, change_index=True, restrict_to_book_ids=None):
        '''
        Rename items from a many-one or many-many field such as tags or series.

        :param change_index: When renaming in a series-like field also change the series_index values.
        :param restrict_to_book_ids: An optional set of book ids for which the rename is to be performed, defaults to all books.
        '''
        f = self.fields[field]
        affected_books = set()
        try:
            sv = f.metadata['is_multiple']['ui_to_list']
        except (TypeError, KeyError, AttributeError):
            sv = None

        if restrict_to_book_ids is not None:
            # We have a VL. Only change the item name for those books
            if not isinstance(restrict_to_book_ids, (Set, MutableSet)):
                restrict_to_book_ids = frozenset(restrict_to_book_ids)
            id_map = {}
            default_process_map = {}
            for old_id, new_name in iteritems(item_id_to_new_name_map):
                new_names = tuple(x.strip() for x in new_name.split(sv)) if sv else (new_name,)
                # Get a list of books in the VL with the item
                books_with_id = f.books_for(old_id)
                books_to_process = books_with_id & restrict_to_book_ids
                if len(books_with_id) == len(books_to_process):
                    # All the books with the ID are in the VL, so we can use
                    # the normal processing
                    default_process_map[old_id] = new_name
                elif books_to_process:
                    affected_books.update(books_to_process)
                    newvals = {}
                    for book_id in books_to_process:
                        # Get the current values, remove the one being renamed, then add
                        # the new value(s) back.
                        vals = self._field_for(field, book_id)
                        # Check for is_multiple
                        if isinstance(vals, tuple):
                            # We must preserve order.
                            vals = list(vals)
                            # Don't need to worry about case here because we
                            # are fetching its one-true spelling. But lets be
                            # careful anyway
                            try:
                                dex = vals.index(self._get_item_name(field, old_id))
                                # This can put the name back with a different case
                                vals[dex] = new_names[0]
                                # now add any other items if they aren't already there
                                if len(new_names) > 1:
                                    set_vals = {icu_lower(x) for x in vals}
                                    for v in new_names[1:]:
                                        lv = icu_lower(v)
                                        if lv not in set_vals:
                                            vals.append(v)
                                            set_vals.add(lv)
                                newvals[book_id] = vals
                            except Exception:
                                traceback.print_exc()
                        else:
                            newvals[book_id] = new_names[0]
                    # Allow case changes
                    self._set_field(field, newvals)
                    id_map[old_id] = self._get_item_id(field, new_names[0])
            if default_process_map:
                ab, idm = self._rename_items(field, default_process_map, change_index=change_index)
                affected_books.update(ab)
                id_map.update(idm)
            self.event_dispatcher(EventType.items_renamed, field, affected_books, id_map)
            return affected_books, id_map

        try:
            func = f.table.rename_item
        except AttributeError:
            raise ValueError('Cannot rename items for one-one fields: %s' % field)
        moved_books = set()
        id_map = {}
        for item_id, new_name in item_id_to_new_name_map.items():
            new_names = tuple(x.strip() for x in new_name.split(sv)) if sv else (new_name,)
            books, new_id = func(item_id, new_names[0], self.backend)
            affected_books.update(books)
            id_map[item_id] = new_id
            if new_id != item_id:
                moved_books.update(books)
            if len(new_names) > 1:
                # Add the extra items to the books
                extra = new_names[1:]
                self._set_field(field, {book_id:self._fast_field_for(f, book_id) + extra for book_id in books})

        if affected_books:
            if field == 'authors':
                self._set_field('author_sort',
                                {k:' & '.join(v) for k, v in iteritems(self._author_sort_strings_for_books(affected_books))})
                self._update_path(affected_books, mark_as_dirtied=False)
            elif change_index and hasattr(f, 'index_field') and tweaks['series_index_auto_increment'] != 'no_change':
                for book_id in moved_books:
                    self._set_field(f.index_field.name, {book_id:self._get_next_series_num_for(self._fast_field_for(f, book_id), field=field)})
            self._mark_as_dirty(affected_books)
            self._clear_link_map_cache(affected_books)
        self.event_dispatcher(EventType.items_renamed, field, affected_books, id_map)
        return affected_books, id_map

    @write_api
    def remove_items(self, field, item_ids, restrict_to_book_ids=None):
        ''' Delete all items in the specified field with the specified ids.
        Returns the set of affected book ids. ``restrict_to_book_ids`` is an
        optional set of books ids. If specified the items will only be removed
        from those books. '''
        field = self.fields[field]
        if restrict_to_book_ids is not None and not isinstance(restrict_to_book_ids, (MutableSet, Set)):
            restrict_to_book_ids = frozenset(restrict_to_book_ids)
        affected_books = field.table.remove_items(item_ids, self.backend,
                                                  restrict_to_book_ids=restrict_to_book_ids)
        if affected_books:
            if hasattr(field, 'index_field'):
                self._set_field(field.index_field.name, {bid:1.0 for bid in affected_books})
            else:
                self._mark_as_dirty(affected_books)
            self._clear_link_map_cache(affected_books)
        self.event_dispatcher(EventType.items_removed, field, affected_books, item_ids)
        return affected_books

    @write_api
    def add_custom_book_data(self, name, val_map, delete_first=False):
        ''' Add data for name where val_map is a map of book_ids to values. If
        delete_first is True, all previously stored data for name will be
        removed. '''
        missing = frozenset(val_map) - self._all_book_ids()
        if missing:
            raise ValueError('add_custom_book_data: no such book_ids: %d'%missing)
        self.backend.add_custom_data(name, val_map, delete_first)

    @read_api
    def get_custom_book_data(self, name, book_ids=(), default=None):
        ''' Get data for name. By default returns data for all book_ids, pass
        in a list of book ids if you only want some data. Returns a map of
        book_id to values. If a particular value could not be decoded, uses
        default for it. '''
        return self.backend.get_custom_book_data(name, book_ids, default)

    @write_api
    def delete_custom_book_data(self, name, book_ids=()):
        ''' Delete data for name. By default deletes all data, if you only want
        to delete data for some book ids, pass in a list of book ids. '''
        self.backend.delete_custom_book_data(name, book_ids)

    @read_api
    def get_ids_for_custom_book_data(self, name):
        ''' Return the set of book ids for which name has data. '''
        return self.backend.get_ids_for_custom_book_data(name)

    @read_api
    def conversion_options(self, book_id, fmt='PIPE'):
        return self.backend.conversion_options(book_id, fmt)

    @read_api
    def has_conversion_options(self, ids, fmt='PIPE'):
        return self.backend.has_conversion_options(ids, fmt)

    @write_api
    def delete_conversion_options(self, book_ids, fmt='PIPE'):
        return self.backend.delete_conversion_options(book_ids, fmt)

    @write_api
    def set_conversion_options(self, options, fmt='PIPE'):
        ''' options must be a map of the form {book_id:conversion_options} '''
        return self.backend.set_conversion_options(options, fmt)

    @write_api
    def refresh_format_cache(self):
        self.fields['formats'].table.read(self.backend)
        self.format_metadata_cache.clear()

    @write_api
    def refresh_ondevice(self):
        self.fields['ondevice'].clear_caches()
        self.clear_search_caches()
        self.clear_composite_caches()

    @read_api
    def books_matching_device_book(self, lpath):
        ans = set()
        for book_id, (_, _, _, _, lpaths) in self.fields['ondevice'].cache.items():
            if lpath in lpaths:
                ans.add(book_id)
        return ans

    @read_api
    def tags_older_than(self, tag, delta=None, must_have_tag=None, must_have_authors=None):
        '''
        Return the ids of all books having the tag ``tag`` that are older than
        the specified time. tag comparison is case insensitive.

        :param delta: A timedelta object or None. If None, then all ids with
            the tag are returned.

        :param must_have_tag: If not None the list of matches will be
            restricted to books that have this tag

        :param must_have_authors: A list of authors. If not None the list of
            matches will be restricted to books that have these authors (case
            insensitive).

        '''
        tag_map = {icu_lower(v):k for k, v in iteritems(self._get_id_map('tags'))}
        tag = icu_lower(tag.strip())
        mht = icu_lower(must_have_tag.strip()) if must_have_tag else None
        tag_id, mht_id = tag_map.get(tag, None), tag_map.get(mht, None)
        ans = set()
        if mht_id is None and mht:
            return ans
        if tag_id is not None:
            tagged_books = self._books_for_field('tags', tag_id)
            if mht_id is not None and tagged_books:
                tagged_books = tagged_books.intersection(self._books_for_field('tags', mht_id))
            if tagged_books:
                if must_have_authors is not None:
                    amap = {icu_lower(v):k for k, v in iteritems(self._get_id_map('authors'))}
                    books = None
                    for author in must_have_authors:
                        abooks = self._books_for_field('authors', amap.get(icu_lower(author), None))
                        books = abooks if books is None else books.intersection(abooks)
                        if not books:
                            break
                    tagged_books = tagged_books.intersection(books or set())
                if delta is None:
                    ans = tagged_books
                else:
                    now = nowf()
                    for book_id in tagged_books:
                        ts = self._field_for('timestamp', book_id)
                        if (now - ts) > delta:
                            ans.add(book_id)
        return ans

    @write_api
    def set_sort_for_authors(self, author_id_to_sort_map, update_books=True):
        sort_map = self.fields['authors'].table.set_sort_names(author_id_to_sort_map, self.backend)
        changed_books = set()
        if update_books:
            val_map = {}
            for author_id in sort_map:
                books = self._books_for_field('authors', author_id)
                changed_books |= books
                for book_id in books:
                    authors = self._field_ids_for('authors', book_id)
                    adata = self._author_data(authors)
                    sorts = [adata[x]['sort'] for x in authors]
                    val_map[book_id] = ' & '.join(sorts)
            if val_map:
                self._set_field('author_sort', val_map)
        if changed_books:
            self._mark_as_dirty(changed_books)
            self._clear_link_map_cache(changed_books)
        return changed_books

    @write_api
    def set_link_for_authors(self, author_id_to_link_map):
        link_map = self.fields['authors'].table.set_links(author_id_to_link_map, self.backend)
        changed_books = set()
        for author_id in link_map:
            changed_books |= self._books_for_field('authors', author_id)
        if changed_books:
            self._mark_as_dirty(changed_books)
            self._clear_link_map_cache(changed_books)
        return changed_books

    @read_api
    def has_link_map(self, field):
        return hasattr(getattr(self.fields.get(field), 'table', None), 'link_map')

    @read_api
    def get_link_map(self, for_field):
        '''
        Return a dictionary of links for the supplied field.

        :param for_field: the lookup name of the field for which the link map is desired

        :return: {field_value:link_value, ...} for non-empty links
        '''
        if for_field not in self.fields:
            raise ValueError(f'Lookup name {for_field} is not a valid name')
        table = self.fields[for_field].table
        lm = getattr(table, 'link_map', None)
        if lm is None:
            raise ValueError(f"Lookup name {for_field} doesn't have a link map")
        lm = table.link_map
        vm = table.id_map
        ans = {vm.get(fid):v for fid,v in lm.items() if v}
        ans.pop(None, None)
        return ans

    @read_api
    def link_for(self, field, item_id):
        '''
        Return the link, if any, for the specified item or None if no link is found
        '''
        f = self.fields.get(field)
        if f is not None:
            table = f.table
            lm = getattr(table, 'link_map', None)
            if lm is not None:
                return lm.get(item_id)

    @read_api
    def get_all_link_maps_for_book(self, book_id):
        '''
        Returns all links for all fields referenced by book identified by book_id.
        If book_id doesn't exist then the method returns {}.

        Example: Assume author A has link X, author B has link Y, tag S has link
        F, and tag T has link G. If book 1 has author A and tag T,
        this method returns {'authors':{'A':'X'}, 'tags':{'T', 'G'}}.
        If book 2's author is neither A nor B and has no tags, this method returns {}.

        :param book_id: the book id in question.

        :return: {field: {field_value, link_value}, ...  for all fields with a field_value having a non-empty link value for that book

        '''
        if not self._has_id(book_id):
            # Works for book_id is None.
            return {}
        cached = self.link_maps_cache.get(book_id)
        if cached is not None:
            return cached
        links = {}
        def add_links_for_field(f):
            field_ids = self._field_ids_for(f, book_id)
            if field_ids:
                table = self.fields[f].table
                lm = table.link_map
                id_link_map = {fid:lm.get(fid) for fid in field_ids}
                vm = table.id_map
                d = {vm.get(fid):v for fid, v in id_link_map.items() if v}
                d.pop(None, None)
                if d:
                    links[f] = d
        for field in ('authors', 'publisher', 'series', 'tags'):
            add_links_for_field(field)
        for field in self.field_metadata.custom_field_keys(include_composites=False):
            if self._has_link_map(field):
                add_links_for_field(field)
        self.link_maps_cache[book_id] = links
        return links

    @write_api
    def set_link_map(self, field, value_to_link_map, only_set_if_no_existing_link=False):
        '''
        Sets links for item values in field.
        Note: this method doesn't change values not in the value_to_link_map

        :param field: the lookup name
        :param value_to_link_map: dict(field_value:link, ...). Note that these are values, not field ids.

        :return: books changed by setting the link

        '''
        if field not in self.fields:
            raise ValueError(f'Lookup name {field} is not a valid name')
        table = getattr(self.fields[field], 'table', None)
        if table is None:
            raise ValueError(f"Lookup name {field} doesn't have a link map")
        # Clear the links for book cache as we don't know what will be affected
        self.link_maps_cache = {}

        fids = self._get_item_ids(field, value_to_link_map)
        if only_set_if_no_existing_link:
            lm = table.link_map
            id_to_link_map = {fid:value_to_link_map[k] for k, fid in fids.items() if fid is not None and not lm.get(fid)}
        else:
            id_to_link_map = {fid:value_to_link_map[k] for k, fid in fids.items() if fid is not None}
        result_map = table.set_links(id_to_link_map, self.backend)
        changed_books = set()
        for id_ in result_map:
            changed_books |= self._books_for_field(field, id_)
        if changed_books:
            self._mark_as_dirty(changed_books)
            self._clear_link_map_cache(changed_books)
        return changed_books

    @read_api
    def lookup_by_uuid(self, uuid):
        return self.fields['uuid'].table.lookup_by_uuid(uuid)

    @write_api
    def delete_custom_column(self, label=None, num=None):
        self.backend.delete_custom_column(label, num)

    @write_api
    def create_custom_column(self, label, name, datatype, is_multiple, editable=True, display={}):
        return self.backend.create_custom_column(label, name, datatype, is_multiple, editable=editable, display=display)

    @write_api
    def set_custom_column_metadata(self, num, name=None, label=None, is_editable=None,
                                   display=None, update_last_modified=False):
        changed = self.backend.set_custom_column_metadata(num, name=name, label=label, is_editable=is_editable, display=display)
        if changed:
            if update_last_modified:
                self._update_last_modified(self._all_book_ids())
            else:
                self.backend.prefs.set('update_all_last_mod_dates_on_start', True)
        return changed

    @read_api
    def get_books_for_category(self, category, item_id_or_composite_value):
        f = self.fields[category]
        if hasattr(f, 'get_books_for_val'):
            # Composite field
            return f.get_books_for_val(item_id_or_composite_value, self._get_proxy_metadata, self._all_book_ids())
        return self._books_for_field(f.name, int(item_id_or_composite_value))

    @read_api
    def split_if_is_multiple_composite(self, f, val):
        '''
        If f is a composite column lookup key and the column is is_multiple then
        split v into unique non-empty values. The comparison is case sensitive.
        Order is not preserved. Return a list() for compatibility with proxy
        metadata field getters, for example tags.
        '''
        fm = self.field_metadata.get(f, None)
        if fm and fm['datatype'] == 'composite' and fm['is_multiple']:
            sep = fm['is_multiple'].get('cache_to_list', ',')
            return list({v.strip() for v in val.split(sep) if v.strip()})
        return val

    @read_api
    def data_for_find_identical_books(self):
        ''' Return data that can be used to implement
        :meth:`find_identical_books` in a worker process without access to the
        db. See db.utils for an implementation. '''
        at = self.fields['authors'].table
        author_map = defaultdict(set)
        for aid, author in iteritems(at.id_map):
            author_map[icu_lower(author)].add(aid)
        return (author_map, at.col_book_map.copy(), self.fields['title'].table.book_col_map.copy(), self.fields['languages'].book_value_map.copy())

    @read_api
    def update_data_for_find_identical_books(self, book_id, data):
        author_map, author_book_map, title_map, lang_map = data
        title_map[book_id] = self._field_for('title', book_id)
        lang_map[book_id] = self._field_for('languages', book_id)
        at = self.fields['authors'].table
        for aid in at.book_col_map.get(book_id, ()):
            author_map[icu_lower(at.id_map[aid])].add(aid)
            try:
                author_book_map[aid].add(book_id)
            except KeyError:
                author_book_map[aid] = {book_id}

    @read_api
    def find_identical_books(self, mi, search_restriction='', book_ids=None):
        ''' Finds books that have a superset of the authors in mi and the same
        title (title is fuzzy matched). See also :meth:`data_for_find_identical_books`. '''
        from calibre.db.utils import fuzzy_title
        identical_book_ids = set()
        langq = tuple(x for x in map(canonicalize_lang, mi.languages or ()) if x and x != 'und')
        if mi.authors:
            try:
                quathors = mi.authors[:20]  # Too many authors causes parsing of the search expression to fail
                query = ' and '.join('authors:"=%s"'%(a.replace('"', '')) for a in quathors)
                qauthors = mi.authors[20:]
            except ValueError:
                return identical_book_ids
            try:
                book_ids = self._search(query, restriction=search_restriction, book_ids=book_ids)
            except:
                traceback.print_exc()
                return identical_book_ids
            if qauthors and book_ids:
                matches = set()
                qauthors = {icu_lower(x) for x in qauthors}
                for book_id in book_ids:
                    aut = self._field_for('authors', book_id)
                    if aut:
                        aut = {icu_lower(x) for x in aut}
                        if aut.issuperset(qauthors):
                            matches.add(book_id)
                book_ids = matches

            for book_id in book_ids:
                fbook_title = self._field_for('title', book_id)
                fbook_title = fuzzy_title(fbook_title)
                mbook_title = fuzzy_title(mi.title)
                if fbook_title == mbook_title:
                    bl = self._field_for('languages', book_id)
                    if not langq or not bl or bl == langq:
                        identical_book_ids.add(book_id)
        return identical_book_ids

    @read_api
    def get_top_level_move_items(self):
        all_paths = {self._field_for('path', book_id).partition('/')[0] for book_id in self._all_book_ids()}
        return self.backend.get_top_level_move_items(all_paths)

    @write_api
    def move_library_to(self, newloc, progress=None, abort=None):
        def progress_callback(item_name, item_count, total):
            try:
                if progress is not None:
                    progress(item_name, item_count, total)
            except Exception:
                traceback.print_exc()

        all_paths = {self._field_for('path', book_id).partition('/')[0] for book_id in self._all_book_ids()}
        self.backend.move_library_to(all_paths, newloc, progress=progress_callback, abort=abort)

    @read_api
    def saved_search_names(self):
        return self._search_api.saved_searches.names()

    @read_api
    def saved_search_lookup(self, name):
        return self._search_api.saved_searches.lookup(name)

    @write_api
    def saved_search_set_all(self, smap):
        self._search_api.saved_searches.set_all(smap)
        self._clear_search_caches()

    @write_api
    def saved_search_delete(self, name):
        self._search_api.saved_searches.delete(name)
        self._clear_search_caches()

    @write_api
    def saved_search_add(self, name, val):
        self._search_api.saved_searches.add(name, val)

    @write_api
    def saved_search_rename(self, old_name, new_name):
        self._search_api.saved_searches.rename(old_name, new_name)
        self._clear_search_caches()

    @write_api
    def change_search_locations(self, newlocs):
        self._search_api.change_locations(newlocs)

    @write_api
    def refresh_search_locations(self):
        self._search_api.change_locations(self.field_metadata.get_search_terms())

    @write_api
    def dump_and_restore(self, callback=None, sql=None):
        return self.backend.dump_and_restore(callback=callback, sql=sql)

    @write_api
    def vacuum(self, include_fts_db=False, include_notes_db=True):
        self.is_doing_rebuild_or_vacuum = True
        try:
            self.backend.vacuum(include_fts_db, include_notes_db)
        finally:
            self.is_doing_rebuild_or_vacuum = False

    def __del__(self):
        self.close()

    def _shutdown_fts(self, stage=1):
        if stage == 1:
            self.backend.shutdown_fts()
            if self.fts_queue_thread is not None:
                self.fts_job_queue.put(None)
            if hasattr(self, 'fts_dispatch_stop_event'):
                self.fts_dispatch_stop_event.set()
            return
        # the fts supervisor thread could be in the middle of committing a
        # result to the db, so holding a lock here will cause a deadlock
        if self.fts_queue_thread is not None:
            self.fts_queue_thread.join()
            self.fts_queue_thread = None
        self.backend.join_fts()

    @api
    def close(self):
        with self.write_lock:
            if hasattr(self, 'close_called'):
                return
            self.close_called = True
            self.shutting_down = True
            self.event_dispatcher.close()
            self._shutdown_fts()
            try:
                from calibre.customize.ui import available_library_closed_plugins
            except ImportError:
                pass  # happens during interpreter shutdown
            else:
                for plugin in available_library_closed_plugins():
                    try:
                        plugin.run(self)
                    except Exception:
                        traceback.print_exc()
        self._shutdown_fts(stage=2)
        with self.write_lock:
            self.backend.close()

    @property
    def is_closed(self):
        return self.backend.is_closed

    @write_api
    def clear_trash_bin(self):
        self.backend.clear_trash_dir()

    @read_api
    def list_trash_entries(self):
        books, formats = self.backend.list_trash_entries()
        ff = []
        for e in formats:
            if self._has_id(e.book_id):
                ff.append(e)
                e.cover_path = self.format_abspath(e.book_id, '__COVER_INTERNAL__')
        return books, formats

    @read_api
    def copy_format_from_trash(self, book_id, fmt, dest):
        fmt = fmt.upper()
        fpath = self.backend.path_for_trash_format(book_id, fmt)
        if not fpath:
            raise ValueError(f'No format {fmt} found in book {book_id}')
        shutil.copyfile(fpath, dest)

    @write_api
    def move_format_from_trash(self, book_id, fmt):
        ''' Undelete a format from the trash directory '''
        if not self._has_id(book_id):
            raise ValueError(f'A book with the id {book_id} does not exist')
        fmt = fmt.upper()
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
        except Exception:
            name = None
        fpath = self.backend.path_for_trash_format(book_id, fmt)
        if not fpath:
            raise ValueError(f'No format {fmt} found in book {book_id}')
        size, fname = self._do_add_format(book_id, fmt, fpath, name)
        self.format_metadata_cache.pop(book_id, None)
        max_size = self.fields['formats'].table.update_fmt(book_id, fmt, fname, size, self.backend)
        self.fields['size'].table.update_sizes({book_id: max_size})
        self.event_dispatcher(EventType.format_added, book_id, fmt)
        self.backend.remove_trash_formats_dir_if_empty(book_id)

    @read_api
    def copy_book_from_trash(self, book_id, dest: str):
        self.backend.copy_book_from_trash(book_id, dest)

    @write_api
    def move_book_from_trash(self, book_id):
        ''' Undelete a book from the trash directory '''
        if self._has_id(book_id):
            raise ValueError(f'A book with the id {book_id} already exists')
        mi, annotations, formats = self.backend.get_metadata_for_trash_book(book_id)
        mi.cover = None
        self._create_book_entry(mi, add_duplicates=True,
                force_id=book_id, apply_import_tags=False, preserve_uuid=True)
        path = self._field_for('path', book_id).replace('/', os.sep)
        self.backend.move_book_from_trash(book_id, path)
        self.format_metadata_cache.pop(book_id, None)
        f = self.fields['formats'].table
        max_size = 0
        for (fmt, size, fname) in formats:
            max_size = max(max_size, f.update_fmt(book_id, fmt, fname, size, self.backend))
        self.fields['size'].table.update_sizes({book_id: max_size})
        cover = self.backend.cover_abspath(book_id, path)
        if cover and os.path.exists(cover):
            self._set_field('cover', {book_id:1})
        if annotations:
            self._restore_annotations(book_id, annotations)

    @write_api
    def delete_trash_entry(self, book_id, category):
        " Delete an entry from the trash. Here category is 'b' for books and 'f' for formats. "
        self.backend.delete_trash_entry(book_id, category)

    @write_api
    def expire_old_trash(self):
        ' Expire entries from the trash that are too old '
        self.backend.expire_old_trash()

    @write_api
    def restore_book(self, book_id, mi, last_modified, path, formats, annotations=()):
        ''' Restore the book entry in the database for a book that already exists on the filesystem '''
        cover, mi.cover = mi.cover, None
        self._create_book_entry(mi, add_duplicates=True,
                force_id=book_id, apply_import_tags=False, preserve_uuid=True)
        self._update_last_modified((book_id,), last_modified)
        if cover and os.path.exists(cover):
            self._set_field('cover', {book_id:1})
        f = self.fields['formats'].table
        for (fmt, size, fname) in formats:
            f.update_fmt(book_id, fmt, fname, size, self.backend)
        self.fields['path'].table.set_path(book_id, path, self.backend)
        if annotations:
            self._restore_annotations(book_id, annotations)

    @read_api
    def virtual_libraries_for_books(self, book_ids, virtual_fields=None):
        # use a primitive lock to ensure that only one thread is updating
        # the cache and that recursive calls don't do the update. This
        # method can recurse via self._search()
        with try_lock(self.vls_cache_lock) as got_lock:
            # Using a list is slightly faster than a set.
            c = defaultdict(list)
            if not got_lock:
                # We get here if resolving the books in a VL triggers another VL
                # cache calculation. This can be 'real' recursion, for example a
                # VL expression using a template that calls virtual_libraries(),
                # or a search using a location of 'all' that causes evaluation
                # of a composite that uses virtual_libraries(). The first case
                # is an error and the exception message should appear somewhere.
                # However, the error can seem nondeterministic. It might not be
                # raised if the use is via a composite and that composite is
                # evaluated before it is used in the search. The second case is
                # also an error but if the composite isn't used in a VL then the
                # eventual answer will be correct because get_metadata() will
                # clear the caches.
                raise ValueError(_('Recursion detected while processing Virtual library "%s"')
                                 % self.vls_for_books_lib_in_process)
            if self.vls_for_books_cache is None:
                libraries = self._pref('virtual_libraries', {})
                for lib, expr in libraries.items():
                    book = None
                    self.vls_for_books_lib_in_process = lib
                    try:
                        for book in self._search(expr, virtual_fields=virtual_fields):
                            c[book].append(lib)
                    except Exception as e:
                        if book:
                            c[book].append(_('[Error in Virtual library {0}: {1}]').format(lib, str(e)))
                self.vls_for_books_cache = {b:tuple(sorted(libs, key=sort_key)) for b, libs in c.items()}
        if not book_ids:
            book_ids = self._all_book_ids()
        # book_ids is usually 1 long. The loop will be faster than a comprehension
        r = {}
        default = ()
        for b in book_ids:
            r[b] = self.vls_for_books_cache.get(b, default)
        return r

    @read_api
    def user_categories_for_books(self, book_ids, proxy_metadata_map=None):
        ''' Return the user categories for the specified books.
        proxy_metadata_map is optional and is useful for a performance boost,
        in contexts where a ProxyMetadata object for the books already exists.
        It should be a mapping of book_ids to their corresponding ProxyMetadata
        objects.
        '''
        user_cats = self._pref('user_categories', {})
        pmm = proxy_metadata_map or {}
        ans = {}

        for book_id in book_ids:
            proxy_metadata = pmm.get(book_id) or self._get_proxy_metadata(book_id)
            user_cat_vals = ans[book_id] = {}
            for ucat, categories in iteritems(user_cats):
                user_cat_vals[ucat] = res = []
                for name, cat, ign in categories:
                    try:
                        field_obj = self.fields[cat]
                    except KeyError:
                        continue

                    if field_obj.is_composite:
                        v = field_obj.get_value_with_cache(book_id, lambda x:proxy_metadata)
                    else:
                        v = self._fast_field_for(field_obj, book_id)

                    if isinstance(v, (list, tuple)):
                        if name in v:
                            res.append([name, cat])
                    elif name == v:
                        res.append([name, cat])
        return ans

    @write_api
    def embed_metadata(self, book_ids, only_fmts=None, report_error=None, report_progress=None):
        ''' Update metadata in all formats of the specified book_ids to current metadata in the database. '''
        field = self.fields['formats']
        from calibre.customize.ui import apply_null_metadata
        from calibre.ebooks.metadata.meta import set_metadata
        from calibre.ebooks.metadata.opf2 import pretty_print
        if only_fmts:
            only_fmts = {f.lower() for f in only_fmts}

        def doit(fmt, mi, stream):
            with apply_null_metadata, pretty_print:
                set_metadata(stream, mi, stream_type=fmt, report_error=report_error)
            stream.seek(0, os.SEEK_END)
            return stream.tell()

        for i, book_id in enumerate(book_ids):
            fmts = field.table.book_col_map.get(book_id, ())
            if not fmts:
                continue
            mi = self._get_metadata(book_id)
            buf = BytesIO()
            if not self._copy_cover_to(book_id, buf):
                return
            cdata = buf.getvalue()
            if cdata:
                mi.cover_data = ('jpeg', cdata)
            try:
                path = self._field_for('path', book_id).replace('/', os.sep)
            except:
                continue
            for fmt in fmts:
                if only_fmts is not None and fmt.lower() not in only_fmts:
                    continue
                try:
                    name = self.fields['formats'].format_fname(book_id, fmt)
                except:
                    continue
                if name and path:
                    try:
                        new_size = self.backend.apply_to_format(book_id, path, name, fmt, partial(doit, fmt, mi))
                    except Exception as e:
                        if report_error is not None:
                            tb = traceback.format_exc()
                            if iswindows and isinstance(e, PermissionError) and e.filename and isinstance(e.filename, str):
                                from calibre_extensions import winutil
                                try:
                                    p = winutil.get_processes_using_files(e.filename)
                                except OSError:
                                    pass
                                else:
                                    path_map = {x['path']: x for x in p}
                                    tb = _('Could not open the file: "{}". It is already opened in the following programs:').format(e.filename)
                                    for path, x in path_map.items():
                                        tb += '\n' + f'{x["app_name"]}: {path}'
                            report_error(mi, fmt, tb)
                            new_size = None
                        else:
                            raise
                    if new_size is not None:
                        self.format_metadata_cache[book_id].get(fmt, {})['size'] = new_size
                        max_size = self.fields['formats'].table.update_fmt(book_id, fmt, name, new_size, self.backend)
                        self.fields['size'].table.update_sizes({book_id: max_size})
            if report_progress is not None:
                report_progress(i+1, len(book_ids), mi)

    @read_api
    def get_last_read_positions(self, book_id, fmt, user):
        fmt = fmt.upper()
        ans = []
        for device, cfi, epoch, pos_frac in self.backend.execute(
                'SELECT device,cfi,epoch,pos_frac FROM last_read_positions WHERE book=? AND format=? AND user=?',
                (book_id, fmt, user)):
            ans.append({'device':device, 'cfi': cfi, 'epoch':epoch, 'pos_frac':pos_frac})
        return ans

    @write_api
    def set_last_read_position(self, book_id, fmt, user='_', device='_', cfi=None, epoch=None, pos_frac=0):
        fmt = fmt.upper()
        device = device or '_'
        user = user or '_'
        if not cfi:
            self.backend.execute(
                'DELETE FROM last_read_positions WHERE book=? AND format=? AND user=? AND device=?',
                (book_id, fmt, user, device))
        else:
            self.backend.execute(
                'INSERT OR REPLACE INTO last_read_positions(book,format,user,device,cfi,epoch,pos_frac) VALUES (?,?,?,?,?,?,?)',
                (book_id, fmt, user, device, cfi, epoch or time(), pos_frac))

    @read_api
    def export_library(self, library_key, exporter, progress=None, abort=None):
        from polyglot.binary import as_hex_unicode
        key_prefix = as_hex_unicode(library_key)
        book_ids = self._all_book_ids()
        total = len(book_ids) + 2
        has_fts = self.is_fts_enabled()
        if has_fts:
            total += 1
        poff = 0
        def report_progress(fname):
            nonlocal poff
            if progress is not None:
                progress(fname, poff, total)
            poff += 1

        report_progress('metadata.db')
        pt = PersistentTemporaryFile('-export.db')
        pt.close()
        self.backend.backup_database(pt.name)
        dbkey = key_prefix + ':::' + 'metadata.db'
        with open(pt.name, 'rb') as f:
            exporter.add_file(f, dbkey)
        os.remove(pt.name)
        if has_fts:
            report_progress('full-text-search.db')
            pt = PersistentTemporaryFile('-export.db')
            pt.close()
            self.backend.backup_fts_database(pt.name)
            ftsdbkey = key_prefix + ':::full-text-search.db'
            with open(pt.name, 'rb') as f:
                exporter.add_file(f, ftsdbkey)
            os.remove(pt.name)
        notesdbkey = key_prefix + ':::notes.db'
        with PersistentTemporaryFile('-export.db') as pt:
            self.backend.export_notes_data(pt)
            pt.flush()
            pt.seek(0)
            report_progress('notes.db')
            exporter.add_file(pt, notesdbkey)

        format_metadata = {}
        extra_files = {}
        metadata = {'format_data':format_metadata, 'metadata.db':dbkey, 'notes.db': notesdbkey, 'total':total, 'extra_files': extra_files}
        if has_fts:
            metadata['full-text-search.db'] = ftsdbkey
        for i, book_id in enumerate(book_ids):
            if abort is not None and abort.is_set():
                return
            if progress is not None:
                report_progress(self._field_for('title', book_id))
            format_metadata[book_id] = fm = {}
            for fmt in self._formats(book_id):
                mdata = self.format_metadata(book_id, fmt)
                key = f'{key_prefix}:{book_id}:{fmt}'
                fm[fmt] = key
                mtime = mdata.get('mtime')
                if mtime is not None:
                    mtime = timestampfromdt(mtime)
                with exporter.start_file(key, mtime=mtime) as dest:
                    self._copy_format_to(book_id, fmt, dest)
            cover_key = '{}:{}:{}'.format(key_prefix, book_id, '.cover')
            with exporter.start_file(cover_key) as dest:
                if not self.copy_cover_to(book_id, dest):
                    dest.discard()
                else:
                    fm['.cover'] = cover_key
            bp = self.field_for('path', book_id)
            extra_files[book_id] = ef = {}
            if bp:
                for (relpath, fobj, stat_result) in self.backend.iter_extra_files(book_id, bp, self.fields['formats']):
                    key = f'{key_prefix}:{book_id}:.|{relpath}'
                    with exporter.start_file(key, mtime=stat_result.st_mtime) as dest:
                        shutil.copyfileobj(fobj, dest)
                    ef[relpath] = key
        exporter.set_metadata(library_key, metadata)
        if progress is not None:
            progress(_('Completed'), total, total)

    @read_api
    def annotations_map_for_book(self, book_id, fmt, user_type='local', user='viewer'):
        '''
        Return a map of annotation type -> annotation data for the specified book_id, format, user and user_type.
        '''
        ans = {}
        for annot in self.backend.annotations_for_book(book_id, fmt, user_type, user):
            ans.setdefault(annot['type'], []).append(annot)
        return ans

    @read_api
    def all_annotations_for_book(self, book_id):
        '''
        Return a tuple containing all annotations for the specified book_id as a dict with keys:
        `format`, `user_type`, `user`, `annotation`. Here, annotation is the annotation data.
        '''
        return tuple(self.backend.all_annotations_for_book(book_id))

    @read_api
    def annotation_count_for_book(self, book_id):
        '''
        Return the number of annotations for the specified book available in the database.
        '''
        return self.backend.annotation_count_for_book(book_id)

    @read_api
    def all_annotation_users(self):
        '''
        Return a tuple of all (user_type, user name) that have annotations.
        '''
        return tuple(self.backend.all_annotation_users())

    @read_api
    def all_annotation_types(self):
        '''
        Return a tuple of all annotation types in the database.
        '''
        return tuple(self.backend.all_annotation_types())

    @read_api
    def all_annotations(self, restrict_to_user=None, limit=None, annotation_type=None, ignore_removed=False, restrict_to_book_ids=None):
        '''
        Return a tuple of all annotations matching the specified criteria.
        `ignore_removed` controls whether removed (deleted) annotations are also returned. Removed annotations are just a skeleton
        used for merging of annotations.
        '''
        return tuple(self.backend.all_annotations(restrict_to_user, limit, annotation_type, ignore_removed, restrict_to_book_ids))

    @read_api
    def search_annotations(
        self,
        fts_engine_query,
        use_stemming=True,
        highlight_start=None,
        highlight_end=None,
        snippet_size=None,
        annotation_type=None,
        restrict_to_book_ids=None,
        restrict_to_user=None,
        ignore_removed=False
    ):
        '''
        Return of a tuple of annotations matching the specified Full-text query.
        '''
        return tuple(self.backend.search_annotations(
            fts_engine_query, use_stemming, highlight_start, highlight_end,
            snippet_size, annotation_type, restrict_to_book_ids, restrict_to_user,
            ignore_removed
        ))

    @write_api
    def delete_annotations(self, annot_ids):
        '''
        Delete annotations with the specified ids.
        '''
        self.backend.delete_annotations(annot_ids)

    @write_api
    def update_annotations(self, annot_id_map):
        '''
        Update annotations.
        '''
        self.backend.update_annotations(annot_id_map)

    @write_api
    def restore_annotations(self, book_id, annotations):
        from calibre.utils.date import EPOCH
        from calibre.utils.iso8601 import parse_iso8601
        umap = defaultdict(list)
        for adata in annotations:
            key = adata['user_type'], adata['user'], adata['format']
            a = adata['annotation']
            ts = (parse_iso8601(a['timestamp']) - EPOCH).total_seconds()
            umap[key].append((a, ts))
        for (user_type, user, fmt), annots_list in iteritems(umap):
            self._set_annotations_for_book(book_id, fmt, annots_list, user_type=user_type, user=user)

    @write_api
    def set_annotations_for_book(self, book_id, fmt, annots_list, user_type='local', user='viewer'):
        '''
        Set all annotations for the specified book_id, fmt, user_type and user.
        '''
        self.backend.set_annotations_for_book(book_id, fmt, annots_list, user_type, user)

    @write_api
    def merge_annotations_for_book(self, book_id, fmt, annots_list, user_type='local', user='viewer'):
        '''
        Merge the specified annotations into the existing annotations for book_id, fm, user_type, and user.
        '''
        from calibre.utils.date import EPOCH
        from calibre.utils.iso8601 import parse_iso8601
        amap = self._annotations_map_for_book(book_id, fmt, user_type=user_type, user=user)
        merge_annotations(annots_list, amap)
        alist = []
        for val in itervalues(amap):
            for annot in val:
                ts = (parse_iso8601(annot['timestamp']) - EPOCH).total_seconds()
                alist.append((annot, ts))
        self._set_annotations_for_book(book_id, fmt, alist, user_type=user_type, user=user)

    @write_api
    def reindex_annotations(self):
        self.backend.reindex_annotations()

    @read_api
    def are_paths_inside_book_dir(self, book_id, paths, sub_path=''):
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return set()
        return {x for x in paths if self.backend.is_path_inside_book_dir(x, path, sub_path)}

    @write_api
    def add_extra_files(self, book_id, map_of_relpath_to_stream_or_path, replace=True, auto_rename=False):
        ' Add extra data files '
        path = self._field_for('path', book_id).replace('/', os.sep)
        added = {}
        for relpath, stream_or_path in map_of_relpath_to_stream_or_path.items():
            added[relpath] = bool(self.backend.add_extra_file(relpath, stream_or_path, path, replace, auto_rename))
        self._clear_extra_files_cache(book_id)
        return added

    @write_api
    def rename_extra_files(self, book_id, map_of_relpath_to_new_relpath, replace=False):
        ' Rename extra data files '
        path = self._field_for('path', book_id).replace('/', os.sep)
        renamed = set()
        for relpath, newrelpath in map_of_relpath_to_new_relpath.items():
            if self.backend.rename_extra_file(relpath, newrelpath, path, replace):
                renamed.add(relpath)
        self._clear_extra_files_cache(book_id)
        return renamed

    @write_api
    def merge_extra_files(self, dest_id, src_ids, replace=False):
        ' Merge the extra files from src_ids into dest_id. Conflicting files are auto-renamed unless replace=True in which case they are replaced. '
        added = set()
        path = self._field_for('path', dest_id)
        if path:
            path = path.replace('/', os.sep)
            for src_id in src_ids:
                book_path = self._field_for('path', src_id)
                if book_path:
                    book_path = book_path.replace('/', os.sep)
                    for (relpath, file_path, stat_result) in self.backend.iter_extra_files(
                            src_id, book_path, self.fields['formats'], yield_paths=True):
                        added.add(self.backend.add_extra_file(relpath, file_path, path, replace=replace, auto_rename=True))
        self._clear_extra_files_cache(dest_id)
        return added

    @write_api
    def remove_extra_files(self, book_id: int, relpaths: Iterable[str], permanent=False) -> dict[str, Exception | None]:
        '''
        Delete the specified extra files, either to Recycle Bin or permanently.
        '''
        path = self._field_for('path', book_id)
        if path:
            self._clear_extra_files_cache(book_id)
            return self.backend.remove_extra_files(path, relpaths, permanent)
        return dict.fromkeys(relpaths)

    @read_api
    def list_extra_files(self, book_id, use_cache=False, pattern='') -> Tuple[ExtraFile, ...]:
        '''
        Get information about extra files in the book's directory.

        :param book_id: the database book id for the book
        :param pattern: the pattern of filenames to search for. Empty pattern matches all extra files. Patterns must use / as separator.
                        Use the DATA_FILE_PATTERN constant to match files inside the data directory.

        :return: A tuple of all extra files matching the specified pattern. Each element of the tuple is
                 ExtraFile(relpath, file_path, stat_result). Where relpath is the relative path of the file
                 to the book directory using / as a separator.
                 stat_result is the result of calling os.stat() on the file.
        '''
        ans = self.extra_files_cache.setdefault(book_id, {}).get(pattern)
        if ans is None or not use_cache:
            ans = []
            path = self._field_for('path', book_id)
            if path:
                for (relpath, file_path, stat_result) in self.backend.iter_extra_files(
                    book_id, path, self.fields['formats'], yield_paths=True, pattern=pattern
                ):
                    ans.append(ExtraFile(relpath, file_path, stat_result))
            self.extra_files_cache[book_id][pattern] = ans = tuple(ans)
        return ans

    @read_api
    def copy_extra_file_to(self, book_id, relpath, stream_or_path):
        path = self._field_for('path', book_id).replace('/', os.sep)
        self.backend.copy_extra_file_to(book_id, path, relpath, stream_or_path)

    @write_api
    def merge_book_metadata(self, dest_id, src_ids, replace_cover=False, save_alternate_cover=False):
        dest_mi = self.get_metadata(dest_id)
        merged_identifiers = self._field_for('identifiers', dest_id) or {}
        orig_dest_comments = dest_mi.comments
        dest_cover = orig_dest_cover = self.cover(dest_id)
        had_orig_cover = bool(dest_cover)
        alternate_covers = []
        from calibre.utils.date import is_date_undefined

        def is_null_date(x):
            return x is None or is_date_undefined(x)

        for src_id in src_ids:
            src_mi = self.get_metadata(src_id)

            if src_mi.comments and orig_dest_comments != src_mi.comments:
                if not dest_mi.comments:
                    dest_mi.comments = src_mi.comments
                else:
                    dest_mi.comments = str(dest_mi.comments) + '\n\n' + str(src_mi.comments)
            if src_mi.title and dest_mi.is_null('title'):
                dest_mi.title = src_mi.title
                dest_mi.title_sort = src_mi.title_sort
            if (src_mi.authors and src_mi.authors[0] != _('Unknown')) and (not dest_mi.authors or dest_mi.authors[0] == _('Unknown')):
                dest_mi.authors = src_mi.authors
                dest_mi.author_sort = src_mi.author_sort
            if src_mi.tags:
                if not dest_mi.tags:
                    dest_mi.tags = src_mi.tags
                else:
                    dest_mi.tags.extend(src_mi.tags)
            if not dest_cover or replace_cover:
                src_cover = self.cover(src_id)
                if src_cover:
                    if save_alternate_cover and dest_cover:
                        alternate_covers.append(dest_cover)
                    dest_cover = src_cover
                    replace_cover = False
            elif save_alternate_cover:
                src_cover = self.cover(src_id)
                if src_cover:
                    alternate_covers.append(src_cover)
            if not dest_mi.publisher:
                dest_mi.publisher = src_mi.publisher
            if not dest_mi.rating:
                dest_mi.rating = src_mi.rating
            if not dest_mi.series:
                dest_mi.series = src_mi.series
                dest_mi.series_index = src_mi.series_index
            if is_null_date(dest_mi.pubdate) and not is_null_date(src_mi.pubdate):
                dest_mi.pubdate = src_mi.pubdate

            src_identifiers = (src_mi.get_identifiers() or {}).copy()
            src_identifiers.update(merged_identifiers)
            merged_identifiers = src_identifiers.copy()

        if merged_identifiers:
            dest_mi.set_identifiers(merged_identifiers)
        self._set_metadata(dest_id, dest_mi, ignore_errors=False)

        if dest_cover and (not had_orig_cover or dest_cover is not orig_dest_cover):
            self._set_cover({dest_id: dest_cover})
        if alternate_covers:
            existing = {x[0] for x in self._list_extra_files(dest_id)}
            h, ext = os.path.splitext(COVER_FILE_NAME)
            template = f'{DATA_DIR_NAME}/{h}-{{:03d}}{ext}'
            for cdata in alternate_covers:
                for i in range(1, 1000):
                    q = template.format(i)
                    if q not in existing:
                        existing.add(q)
                        self._add_extra_files(dest_id, {q: BytesIO(cdata)}, replace=False, auto_rename=True)
                        break

        for key in self.field_metadata:  # loop thru all defined fields
            fm = self.field_metadata[key]
            if not fm['is_custom']:
                continue
            dt = fm['datatype']
            label = fm['label']
            try:
                field = self.field_metadata.label_to_key(label)
            except ValueError:
                continue
            # Get orig_dest_comments before it gets changed
            if dt == 'comments':
                orig_dest_value = self._field_for(field, dest_id)

            for src_id in src_ids:
                dest_value = self._field_for(field, dest_id)
                src_value = self._field_for(field, src_id)
                if (dt == 'comments' and src_value and src_value != orig_dest_value):
                    if not dest_value:
                        self._set_field(field, {dest_id: src_value})
                    else:
                        dest_value = str(dest_value) + '\n\n' + str(src_value)
                        self._set_field(field, {dest_id: dest_value})
                if (dt in {'bool', 'int', 'float', 'rating', 'datetime'} and dest_value is None):
                    self._set_field(field, {dest_id: src_value})
                if (dt == 'series' and not dest_value and src_value):
                    src_index = self._field_for(field + '_index', src_id)
                    self._set_field(field, {dest_id:src_value})
                    self._set_field(field + '_index', {dest_id:src_index})
                if ((dt == 'enumeration' or (dt == 'text' and not fm['is_multiple'])) and not dest_value):
                    self._set_field(field, {dest_id:src_value})
                if (dt == 'text' and fm['is_multiple'] and src_value):
                    if not dest_value:
                        dest_value = src_value
                    else:
                        dest_value = list(dest_value)
                        dest_value.extend(src_value)
                    self._set_field(field, {dest_id: dest_value})


def import_library(library_key, importer, library_path, progress=None, abort=None):
    from calibre.db.backend import DB
    metadata = importer.metadata[library_key]
    total = metadata['total']
    poff = 0
    def report_progress(fname):
        nonlocal poff
        if progress is not None:
            progress(fname, poff, total)
            poff += 1
    report_progress('metadata.db')
    if abort is not None and abort.is_set():
        return
    importer.save_file(metadata['metadata.db'], 'metadata.db for ' + library_path, os.path.join(library_path, 'metadata.db'))
    if 'full-text-search.db' in metadata:
        if progress is not None:
            progress('full-text-search.db', 1, total)
        if abort is not None and abort.is_set():
            return
        poff += 1
        importer.save_file(metadata['full-text-search.db'], 'full-text-search.db for ' + library_path,
                           os.path.join(library_path, 'full-text-search.db'))
    if abort is not None and abort.is_set():
        return
    if 'notes.db' in metadata:
        import zipfile
        notes_dir = os.path.join(library_path, NOTES_DIR_NAME)
        os.makedirs(notes_dir, exist_ok=True)
        with importer.start_file(metadata['notes.db'], 'notes.db for ' + library_path) as stream:
            stream.check_hash = False
            with zipfile.ZipFile(stream) as zf:
                for zi in zf.infolist():
                    tpath = zf._extract_member(zi, notes_dir, None)
                    date_time = mktime(zi.date_time + (0, 0, -1))
                    os.utime(tpath, (date_time, date_time))
    if abort is not None and abort.is_set():
        return
    if importer.corrupted_files:
        raise ValueError('Corrupted files:\n' + '\n'.join(importer.corrupted_files))
    cache = Cache(DB(library_path, load_user_formatter_functions=False))
    cache.init()

    format_data = {int(book_id):data for book_id, data in iteritems(metadata['format_data'])}
    extra_files = {int(book_id):data for book_id, data in metadata.get('extra_files', {}).items()}
    for i, (book_id, fmt_key_map) in enumerate(iteritems(format_data)):
        if abort is not None and abort.is_set():
            return
        title = cache._field_for('title', book_id)
        if progress is not None:
            progress(title, i + poff, total)
        cache._update_path((book_id,), mark_as_dirtied=False)
        for fmt, fmtkey in fmt_key_map.items():
            if fmt == '.cover':
                with importer.start_file(fmtkey, _('Cover for %s') % title) as stream:
                    path = cache._field_for('path', book_id).replace('/', os.sep)
                    cache.backend.set_cover(book_id, path, stream, no_processing=True)
            else:
                with importer.start_file(fmtkey, _('{0} format for {1}').format(fmt.upper(), title)) as stream:
                    size, fname = cache._do_add_format(book_id, fmt, stream, mtime=stream.mtime)
                    cache.fields['formats'].table.update_fmt(book_id, fmt, fname, size, cache.backend)
        for relpath, efkey in extra_files.get(book_id, {}).items():
            with importer.start_file(efkey, _('Extra file {0} for book {1}').format(relpath, title)) as stream:
                path = cache._field_for('path', book_id).replace('/', os.sep)
                cache.backend.add_extra_file(relpath, stream, path)
        cache.dump_metadata({book_id})
        if importer.corrupted_files:
            raise ValueError('Corrupted files:\n' + '\n'.join(importer.corrupted_files))
    if progress is not None:
        progress(_('Completed'), total, total)
    return cache
# }}}
