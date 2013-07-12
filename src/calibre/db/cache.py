#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, traceback, random, shutil
from io import BytesIO
from collections import defaultdict
from functools import wraps, partial

from calibre import isbytestring
from calibre.constants import iswindows, preferred_encoding
from calibre.customize.ui import run_plugins_on_import, run_plugins_on_postimport
from calibre.db import SPOOL_SIZE, _get_next_series_num_for_list
from calibre.db.categories import get_categories
from calibre.db.locking import create_locks
from calibre.db.errors import NoSuchFormat
from calibre.db.fields import create_field
from calibre.db.search import Search
from calibre.db.tables import VirtualTable
from calibre.db.write import get_series_values
from calibre.db.lazy import FormatMetadata, FormatsList
from calibre.ebooks import check_ebook_format
from calibre.ebooks.metadata import string_to_authors, author_to_author_sort
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ptempfile import (base_dir, PersistentTemporaryFile,
                               SpooledTemporaryFile)
from calibre.utils.config import prefs
from calibre.utils.date import now as nowf, utcnow, UNDEFINED_DATE
from calibre.utils.icu import sort_key

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
    def ans(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)
    return ans

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


class Cache(object):

    def __init__(self, backend):
        self.backend = backend
        self.fields = {}
        self.composites = set()
        self.read_lock, self.write_lock = create_locks()
        self.format_metadata_cache = defaultdict(dict)
        self.formatter_template_cache = {}
        self.dirtied_cache = {}
        self.dirtied_sequence = 0
        self._search_api = Search(self.field_metadata.get_search_terms())

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

        self.initialize_dynamic()

    @write_api
    def initialize_dynamic(self):
        # Reconstruct the user categories, putting them into field_metadata
        # Assumption is that someone else will fix them if they change.
        self.field_metadata.remove_dynamic_categories()
        for user_cat in sorted(self._pref('user_categories', {}).iterkeys(), key=sort_key):
            cat_name = '@' + user_cat  # add the '@' to avoid name collision
            self.field_metadata.add_user_category(label=cat_name, name=user_cat)

        # add grouped search term user categories
        muc = frozenset(self._pref('grouped_search_make_user_categories', []))
        for cat in sorted(self._pref('grouped_search_terms', {}).iterkeys(), key=sort_key):
            if cat in muc:
                # There is a chance that these can be duplicates of an existing
                # user category. Print the exception and continue.
                try:
                    self.field_metadata.add_user_category(label=u'@' + cat, name=cat)
                except:
                    traceback.print_exc()

        # TODO: Saved searches
        # if len(saved_searches().names()):
        #     self.field_metadata.add_search_category(label='search', name=_('Searches'))

        self.field_metadata.add_grouped_search_terms(
                                    self._pref('grouped_search_terms', {}))

        self._search_api.change_locations(self.field_metadata.get_search_terms())

        self.dirtied_cache = {x:i for i, (x,) in enumerate(
            self.backend.conn.execute('SELECT book FROM metadata_dirtied'))}
        if self.dirtied_cache:
            self.dirtied_sequence = max(self.dirtied_cache.itervalues())+1

    @write_api
    def initialize_template_cache(self):
        self.formatter_template_cache = {}

    @write_api
    def refresh(self):
        self._initialize_template_cache()
        for field in self.fields.itervalues():
            if hasattr(field, 'clear_cache'):
                field.clear_cache()  # Clear the composite cache
            if hasattr(field, 'table'):
                field.table.read(self.backend)  # Reread data from metadata.db

    @property
    def field_metadata(self):
        return self.backend.field_metadata

    def _get_metadata(self, book_id, get_user_categories=True):  # {{{
        mi = Metadata(None, template_cache=self.formatter_template_cache)
        author_ids = self._field_ids_for('authors', book_id)
        adata = self._author_data(author_ids)
        aut_list = [adata[i] for i in author_ids]
        aum = []
        aus = {}
        aul = {}
        for rec in aut_list:
            aut = rec['name']
            aum.append(aut)
            aus[aut] = rec['sort']
            aul[aut] = rec['link']
        mi.title       = self._field_for('title', book_id,
                default_value=_('Unknown'))
        mi.authors     = aum
        mi.author_sort = self._field_for('author_sort', book_id,
                default_value=_('Unknown'))
        mi.author_sort_map = aus
        mi.author_link_map = aul
        mi.comments    = self._field_for('comments', book_id)
        mi.publisher   = self._field_for('publisher', book_id)
        n = nowf()
        mi.timestamp   = self._field_for('timestamp', book_id, default_value=n)
        mi.pubdate     = self._field_for('pubdate', book_id, default_value=n)
        mi.uuid        = self._field_for('uuid', book_id,
                default_value='dummy')
        mi.title_sort  = self._field_for('sort', book_id,
                default_value=_('Unknown'))
        mi.book_size   = self._field_for('size', book_id, default_value=0)
        mi.ondevice_col = self._field_for('ondevice', book_id, default_value='')
        mi.last_modified = self._field_for('last_modified', book_id,
                default_value=n)
        formats = self._field_for('formats', book_id)
        mi.format_metadata = {}
        mi.languages = list(self._field_for('languages', book_id))
        if not formats:
            good_formats = None
        else:
            mi.format_metadata = FormatMetadata(self, book_id, formats)
            good_formats = FormatsList(formats, mi.format_metadata)
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
        composites = []
        for key, meta in self.field_metadata.custom_iteritems():
            mi.set_user_metadata(key, meta)
            if meta['datatype'] == 'composite':
                composites.append(key)
            else:
                val = self._field_for(key, book_id)
                if isinstance(val, tuple):
                    val = list(val)
                extra = self._field_for(key+'_index', book_id)
                mi.set(key, val=val, extra=extra)
        for key in composites:
            mi.set(key, val=self._composite_for(key, book_id, mi))

        user_cat_vals = {}
        if get_user_categories:
            user_cats = self.backend.prefs['user_categories']
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

    # Cache Layer API {{{

    @api
    def init(self):
        '''
        Initialize this cache with data from the backend.
        '''
        with self.write_lock:
            self.backend.read_tables()

            for field, table in self.backend.tables.iteritems():
                self.fields[field] = create_field(field, table)
                if table.metadata['datatype'] == 'composite':
                    self.composites.add(field)

            self.fields['ondevice'] = create_field('ondevice',
                    VirtualTable('ondevice'))

            for name, field in self.fields.iteritems():
                if name[0] == '#' and name.endswith('_index'):
                    field.series_field = self.fields[name[:-len('_index')]]
                elif name == 'series_index':
                    field.series_field = self.fields['series']
                elif name == 'authors':
                    field.author_sort_field = self.fields['author_sort']
                elif name == 'title':
                    field.title_sort_field = self.fields['sort']

    @read_api
    def field_for(self, name, book_id, default_value=None):
        '''
        Return the value of the field ``name`` for the book identified by
        ``book_id``. If no such book exists or it has no defined value for the
        field ``name`` or no such field exists, then ``default_value`` is returned.

        default_value is not used for title, title_sort, authors, author_sort
        and series_index. This is because these always have values in the db.
        default_value is used for all custom columns.

        The returned value for is_multiple fields are always tuples, even when
        no values are found (in other words, default_value is ignored). The
        exception is identifiers for which the returned value is always a dict.

        WARNING: For is_multiple fields this method returns tuples, the old
        interface generally returned lists.

        WARNING: For is_multiple fields the order of items is always in link
        order (order in which they were entered), whereas the old db had them
        in random order for fields other than author.
        '''
        if self.composites and name in self.composites:
            return self.composite_for(name, book_id,
                    default_value=default_value)
        try:
            field = self.fields[name]
        except KeyError:
            return default_value
        if field.is_multiple:
            default_value = {} if name == 'identifiers' else ()
        try:
            return field.for_book(book_id, default_value=default_value)
        except (KeyError, IndexError):
            return default_value

    @read_api
    def composite_for(self, name, book_id, mi=None, default_value=''):
        try:
            f = self.fields[name]
        except KeyError:
            return default_value

        if mi is None:
            return f.get_value_with_cache(book_id, partial(self._get_metadata,
                get_user_categories=False))
        else:
            return f.render_composite(book_id, mi)

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
        return type(self.fields['uuid'])

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
            return frozenset(self.fields[field].table.id_map.itervalues())
        except AttributeError:
            raise ValueError('%s is not a many-one or many-many field' % field)

    @read_api
    def get_usage_count_by_id(self, field):
        try:
            return {k:len(v) for k, v in self.fields[field].table.col_book_map.iteritems()}
        except AttributeError:
            raise ValueError('%s is not a many-one or many-many field' % field)

    @read_api
    def get_id_map(self, field):
        try:
            return self.fields[field].table.id_map.copy()
        except AttributeError:
            if field == 'title':
                return self.fields[field].table.book_col_map.copy()
            raise ValueError('%s is not a many-one or many-many field' % field)

    @read_api
    def author_data(self, author_ids):
        '''
        Return author data as a dictionary with keys: name, sort, link

        If no authors with the specified ids are found an empty dictionary is
        returned. If author_ids is None, data for all authors is returned.
        '''
        af = self.fields['authors']
        if author_ids is None:
            author_ids = tuple(af.table.id_map)
        return {aid:af.author_data(aid) for aid in author_ids if aid in af.table.id_map}

    @read_api
    def format_metadata(self, book_id, fmt, allow_cache=True):
        if not fmt:
            return {}
        fmt = fmt.upper()
        if allow_cache:
            x = self.format_metadata_cache[book_id].get(fmt, None)
            if x is not None:
                return x
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return {}

        ans = {}
        if path and name:
            ans = self.backend.format_metadata(book_id, fmt, name, path)
            self.format_metadata_cache[book_id][fmt] = ans
        return ans

    @read_api
    def pref(self, name, default=None):
        return self.backend.prefs.get(name, default)

    @write_api
    def set_pref(self, name, val):
        self.backend.prefs.set(name, val)

    @api
    def get_metadata(self, book_id,
            get_cover=False, get_user_categories=True, cover_as_data=False):
        '''
        Return metadata for the book identified by book_id as a :class:`Metadata` object.
        Note that the list of formats is not verified. If get_cover is True,
        the cover is returned, either a path to temp file as mi.cover or if
        cover_as_data is True then as mi.cover_data.
        '''

        with self.read_lock:
            mi = self._get_metadata(book_id, get_user_categories=get_user_categories)

        if get_cover:
            if cover_as_data:
                cdata = self.cover(book_id)
                if cdata:
                    mi.cover_data = ('jpeg', cdata)
            else:
                mi.cover = self.cover(book_id, as_path=True)

        return mi

    @api
    def cover(self, book_id,
            as_file=False, as_image=False, as_path=False):
        '''
        Return the cover image or None. By default, returns the cover as a
        bytestring.

        WARNING: Using as_path will copy the cover to a temp file and return
        the path to the temp file. You should delete the temp file when you are
        done with it.

        :param as_file: If True return the image as an open file object (a SpooledTemporaryFile)
        :param as_image: If True return the image as a QImage object
        :param as_path: If True return the image as a path pointing to a
                        temporary file
        '''
        if as_file:
            ret = SpooledTemporaryFile(SPOOL_SIZE)
            if not self.copy_cover_to(book_id, ret):
                return
            ret.seek(0)
        elif as_path:
            pt = PersistentTemporaryFile('_dbcover.jpg')
            with pt:
                if not self.copy_cover_to(book_id, pt):
                    return
            ret = pt.name
        else:
            buf = BytesIO()
            if not self.copy_cover_to(book_id, buf):
                return
            ret = buf.getvalue()
            if as_image:
                from PyQt4.Qt import QImage
                i = QImage()
                i.loadFromData(ret)
                ret = i
        return ret

    @read_api
    def copy_cover_to(self, book_id, dest, use_hardlink=False):
        '''
        Copy the cover to the file like object ``dest``. Returns False
        if no cover exists or dest is the same file as the current cover.
        dest can also be a path in which case the cover is
        copied to it iff the path is different from the current path (taking
        case sensitivity into account).
        '''
        try:
            path = self._field_for('path', book_id).replace('/', os.sep)
        except AttributeError:
            return False

        return self.backend.copy_cover_to(path, dest,
                                              use_hardlink=use_hardlink)

    @read_api
    def copy_format_to(self, book_id, fmt, dest, use_hardlink=False):
        '''
        Copy the format ``fmt`` to the file like object ``dest``. If the
        specified format does not exist, raises :class:`NoSuchFormat` error.
        dest can also be a path, in which case the format is copied to it, iff
        the path is different from the current path (taking case sensitivity
        into account).
        '''
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except (KeyError, AttributeError):
            raise NoSuchFormat('Record %d has no %s file'%(book_id, fmt))

        return self.backend.copy_format_to(book_id, fmt, name, path, dest,
                                               use_hardlink=use_hardlink)

    @read_api
    def format_abspath(self, book_id, fmt):
        '''
        Return absolute path to the ebook file of format `format`

        Currently used only in calibredb list, the viewer and the catalogs (via
        get_data_as_dict()).

        Apart from the viewer, I don't believe any of the others do any file
        I/O with the results of this call.
        '''
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return None
        if name and path:
            return self.backend.format_abspath(book_id, fmt, name, path)

    @read_api
    def has_format(self, book_id, fmt):
        'Return True iff the format exists on disk'
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
            path = self._field_for('path', book_id).replace('/', os.sep)
        except:
            return False
        return self.backend.has_format(book_id, fmt, name, path)

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
        Return the ebook format as a bytestring or `None` if the format doesn't exist,
        or we don't have permission to write to the ebook file.

        :param as_file: If True the ebook format is returned as a file object. Note
                        that the file object is a SpooledTemporaryFile, so if what you want to
                        do is copy the format to another file, use :method:`copy_format_to`
                        instead for performance.
        :param as_path: Copies the format file to a temp file and returns the
                        path to the temp file
        :param preserve_filename: If True and returning a path the filename is
                                  the same as that used in the library. Note that using
                                  this means that repeated calls yield the same
                                  temp file (which is re-created each time)
        '''
        ext = ('.'+fmt.lower()) if fmt else ''
        if as_path:
            if preserve_filename:
                with self.read_lock:
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
            with self.read_lock:
                try:
                    fname = self.fields['formats'].format_fname(book_id, fmt)
                except:
                    return None
                fname += ext

            ret = SpooledTemporaryFile(SPOOL_SIZE)
            try:
                self.copy_format_to(book_id, fmt, ret)
            except NoSuchFormat:
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
    def multisort(self, fields, ids_to_sort=None):
        '''
        Return a list of sorted book ids. If ids_to_sort is None, all book ids
        are returned.

        fields must be a list of 2-tuples of the form (field_name,
        ascending=True or False). The most significant field is the first
        2-tuple.
        '''
        all_book_ids = frozenset(self._all_book_ids() if ids_to_sort is None
                else ids_to_sort)
        get_metadata = partial(self._get_metadata, get_user_categories=False)
        lang_map = self.fields['languages'].book_value_map

        fm = {'title':'sort', 'authors':'author_sort'}

        def sort_key(field):
            'Handle series type fields'
            idx = field + '_index'
            is_series = idx in self.fields
            ans = self.fields[fm.get(field, field)].sort_keys_for_books(
                get_metadata, lang_map, all_book_ids,)
            if is_series:
                idx_ans = self.fields[idx].sort_keys_for_books(
                    get_metadata, lang_map, all_book_ids)
                ans = {k:(v, idx_ans[k]) for k, v in ans.iteritems()}
            return ans

        sort_keys = tuple(sort_key(field[0]) for field in fields)

        if len(sort_keys) == 1:
            sk = sort_keys[0]
            return sorted(all_book_ids, key=lambda i:sk[i], reverse=not
                    fields[0][1])
        else:
            return sorted(all_book_ids, key=partial(SortKey, fields, sort_keys))

    @read_api
    def search(self, query, restriction, virtual_fields=None):
        return self._search_api(self, query, restriction,
                                virtual_fields=virtual_fields)

    @read_api
    def get_categories(self, sort='name', book_ids=None, icon_map=None):
        return get_categories(self, sort=sort, book_ids=book_ids,
                              icon_map=icon_map)

    @write_api
    def update_last_modified(self, book_ids, now=None):
        if now is None:
            now = nowf()
        if book_ids:
            f = self.fields['last_modified']
            f.writer.set_books({book_id:now for book_id in book_ids}, self.backend)

    @write_api
    def mark_as_dirty(self, book_ids):
        self._update_last_modified(book_ids)
        already_dirtied = set(self.dirtied_cache).intersection(book_ids)
        new_dirtied = book_ids - already_dirtied
        already_dirtied = {book_id:self.dirtied_sequence+i for i, book_id in enumerate(already_dirtied)}
        if already_dirtied:
            self.dirtied_sequence = max(already_dirtied.itervalues()) + 1
        self.dirtied_cache.update(already_dirtied)
        if new_dirtied:
            self.backend.conn.executemany('INSERT OR IGNORE INTO metadata_dirtied (book) VALUES (?)',
                                    ((x,) for x in new_dirtied))
            new_dirtied = {book_id:self.dirtied_sequence+i for i, book_id in enumerate(new_dirtied)}
            self.dirtied_sequence = max(new_dirtied.itervalues()) + 1
            self.dirtied_cache.update(new_dirtied)

    @write_api
    def set_field(self, name, book_id_to_val_map, allow_case_change=True, do_path_update=True):
        f = self.fields[name]
        is_series = f.metadata['datatype'] == 'series'
        update_path = name in {'title', 'authors'}
        if update_path and iswindows:
            paths = (x for x in (self._field_for('path', book_id) for book_id in book_id_to_val_map) if x)
            self.backend.windows_check_if_files_in_use(paths)

        if is_series:
            bimap, simap = {}, {}
            for k, v in book_id_to_val_map.iteritems():
                if isinstance(v, basestring):
                    v, sid = get_series_values(v)
                else:
                    v = sid = None
                if name.startswith('#') and sid is None:
                    sid = 1.0  # The value will be set to 1.0 in the db table
                bimap[k] = v
                if sid is not None:
                    simap[k] = sid
            book_id_to_val_map = bimap

        dirtied = f.writer.set_books(
            book_id_to_val_map, self.backend, allow_case_change=allow_case_change)

        if is_series and simap:
            sf = self.fields[f.name+'_index']
            dirtied |= sf.writer.set_books(simap, self.backend, allow_case_change=False)

        if dirtied and self.composites:
            for name in self.composites:
                self.fields[name].pop_cache(dirtied)

        if dirtied and update_path and do_path_update:
            self._update_path(dirtied, mark_as_dirtied=False)

        self._mark_as_dirty(dirtied)

        return dirtied

    @write_api
    def update_path(self, book_ids, mark_as_dirtied=True):
        for book_id in book_ids:
            title = self._field_for('title', book_id, default_value=_('Unknown'))
            author = self._field_for('authors', book_id, default_value=(_('Unknown'),))[0]
            self.backend.update_path(book_id, title, author, self.fields['path'], self.fields['formats'])
            if mark_as_dirtied:
                self._mark_as_dirty(book_ids)

    @read_api
    def get_a_dirtied_book(self):
        if self.dirtied_cache:
            return random.choice(tuple(self.dirtied_cache.iterkeys()))
        return None

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
                    mi = self._get_metadata(book_id)
                    # Always set cover to cover.jpg. Even if cover doesn't exist,
                    # no harm done. This way no need to call dirtied when
                    # cover is set/removed
                    mi.cover = 'cover.jpg'
            except:
                # This almost certainly means that the book has been deleted while
                # the backup operation sat in the queue.
                pass
        return mi, sequence

    @write_api
    def clear_dirtied(self, book_id, sequence):
        '''
        Clear the dirtied indicator for the books. This is used when fetching
        metadata, creating an OPF, and writing a file are separated into steps.
        The last step is clearing the indicator
        '''
        dc_sequence = self.dirtied_cache.get(book_id, None)
        if dc_sequence is None or sequence is None or dc_sequence == sequence:
            self.backend.conn.execute('DELETE FROM metadata_dirtied WHERE book=?',
                    (book_id,))
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
        except EnvironmentError:
            return None

    @write_api
    def dump_metadata(self, book_ids=None, remove_from_dirtied=True,
            callback=None):
        '''
        Write metadata for each record to an individual OPF file. If callback
        is not None, it is called once at the start with the number of book_ids
        being processed. And once for every book_id, with arguments (book_id,
        mi, ok).
        '''
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
        ''' Set the cover for this book.  data can be either a QImage,
        QPixmap, file object or bytestring. It can also be None, in which
        case any existing cover is removed. '''

        for book_id, data in book_id_data_map.iteritems():
            try:
                path = self._field_for('path', book_id).replace('/', os.sep)
            except AttributeError:
                self._update_path((book_id,))
                path = self._field_for('path', book_id).replace('/', os.sep)

            self.backend.set_cover(book_id, path, data)
        return self._set_field('cover', {
            book_id:(0 if data is None else 1) for book_id, data in book_id_data_map.iteritems()})

    @write_api
    def set_metadata(self, book_id, mi, ignore_errors=False, force_changes=False,
                     set_title=True, set_authors=True):
        '''
        Set metadata for the book `id` from the `Metadata` object `mi`

        Setting force_changes=True will force set_metadata to update fields even
        if mi contains empty values. In this case, 'None' is distinguished from
        'empty'. If mi.XXX is None, the XXX is not replaced, otherwise it is.
        The tags, identifiers, and cover attributes are special cases. Tags and
        identifiers cannot be set to None so then will always be replaced if
        force_changes is true. You must ensure that mi contains the values you
        want the book to have. Covers are always changed if a new cover is
        provided, but are never deleted. Also note that force_changes has no
        effect on setting title or authors.
        '''

        try:
            # Handle code passing in an OPF object instead of a Metadata object
            mi = mi.to_book_metadata()
        except (AttributeError, TypeError):
            pass

        def set_field(name, val, **kwargs):
            self._set_field(name, {book_id:val}, **kwargs)

        path_changed = False
        if set_title and mi.title:
            path_changed = True
            set_field('title', mi.title, do_path_update=False)
        if set_authors:
            path_changed = True
            if not mi.authors:
                mi.authors = [_('Unknown')]
            authors = []
            for a in mi.authors:
                authors += string_to_authors(a)
            set_field('authors', authors, do_path_update=False)

        if path_changed:
            self._update_path({book_id})

        def protected_set_field(name, val, **kwargs):
            try:
                set_field(name, val, **kwargs)
            except:
                if ignore_errors:
                    traceback.print_exc()
                else:
                    raise

        for field in ('rating', 'series_index', 'timestamp'):
            val = getattr(mi, field)
            if val is not None:
                protected_set_field(field, val)

        # force_changes has no effect on cover manipulation
        cdata = mi.cover_data[1]
        if cdata is None and isinstance(mi.cover, basestring) and mi.cover and os.access(mi.cover, os.R_OK):
            with lopen(mi.cover, 'rb') as f:
                raw = f.read()
                if raw:
                    cdata = raw
        if cdata is not None:
            self._set_cover({book_id: cdata})

        for field in ('author_sort', 'publisher', 'series', 'tags', 'comments',
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
            for key, val in mi_idents.iteritems():
                if val and val.strip():  # Don't delete an existing identifier
                    identifiers[icu_lower(key)] = val
            protected_set_field('identifiers', identifiers)

        user_mi = mi.get_all_user_metadata(make_copy=False)
        fm = self.field_metadata
        for key in user_mi.iterkeys():
            if (key in fm and
                    user_mi[key]['datatype'] == fm[key]['datatype'] and
                    (user_mi[key]['datatype'] != 'text' or
                     user_mi[key]['is_multiple'] == fm[key]['is_multiple'])):
                val = mi.get(key, None)
                if force_changes or val is not None:
                    protected_set_field(key, val)
                    idx = key + '_index'
                    if idx in self.fields:
                        extra = mi.get_extra(key)
                        if extra is not None or force_changes:
                            protected_set_field(idx, extra)

    @write_api
    def add_format(self, book_id, fmt, stream_or_path, replace=True, run_hooks=True, dbapi=None):
        if run_hooks:
            # Run import plugins
            npath = run_import_plugins(stream_or_path, fmt)
            fmt = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
            stream_or_path = lopen(npath, 'rb')
            fmt = check_ebook_format(stream_or_path, fmt)

        fmt = (fmt or '').upper()
        self.format_metadata_cache[book_id].pop(fmt, None)
        try:
            name = self.fields['formats'].format_fname(book_id, fmt)
        except:
            name = None

        if name and not replace:
            return False

        path = self._field_for('path', book_id).replace('/', os.sep)
        title = self._field_for('title', book_id, default_value=_('Unknown'))
        author = self._field_for('authors', book_id, default_value=(_('Unknown'),))[0]
        stream = stream_or_path if hasattr(stream_or_path, 'read') else lopen(stream_or_path, 'rb')
        size, fname = self.backend.add_format(book_id, fmt, stream, title, author, path)
        del stream

        max_size = self.fields['formats'].table.update_fmt(book_id, fmt, fname, size, self.backend)
        self.fields['size'].table.update_sizes({book_id: max_size})
        self._update_last_modified((book_id,))

        if run_hooks:
            # Run post import plugins
            run_plugins_on_postimport(dbapi or self, book_id, fmt)
            stream_or_path.close()

        return True

    @write_api
    def remove_formats(self, formats_map, db_only=False):
        table = self.fields['formats'].table
        formats_map = {book_id:frozenset((f or '').upper() for f in fmts) for book_id, fmts in formats_map.iteritems()}
        size_map = table.remove_formats(formats_map, self.backend)
        self.fields['size'].table.update_sizes(size_map)

        for book_id, fmts in formats_map.iteritems():
            for fmt in fmts:
                self.format_metadata_cache[book_id].pop(fmt, None)

        if not db_only:
            for book_id, fmts in formats_map.iteritems():
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
                        self.backend.remove_format(book_id, fmt, name, path)

        self._update_last_modified(tuple(formats_map.iterkeys()))

    @read_api
    def get_next_series_num_for(self, series):
        books = ()
        sf = self.fields['series']
        if series:
            q = icu_lower(series)
            for val, book_ids in sf.iter_searchable_values(self._get_metadata, frozenset(self.all_book_ids())):
                if q == icu_lower(val):
                    books = book_ids
                    break
        series_indices = sorted(self._field_for('series_index', book_id) for book_id in books)
        return _get_next_series_num_for_list(tuple(series_indices), unwrap=False)

    @read_api
    def author_sort_from_authors(self, authors):
        '''Given a list of authors, return the author_sort string for the authors,
        preferring the author sort associated with the author over the computed
        string. '''
        table = self.fields['authors'].table
        result = []
        rmap = {icu_lower(v):k for k, v in table.id_map.iteritems()}
        for aut in authors:
            aid = rmap.get(icu_lower(aut), None)
            result.append(author_to_author_sort(aut) if aid is None else table.asort_map[aid])
        return ' & '.join(result)

    @read_api
    def has_book(self, mi):
        title = mi.title
        if title:
            if isbytestring(title):
                title = title.decode(preferred_encoding, 'replace')
            q = icu_lower(title)
            for title in self.fields['title'].table.book_col_map.itervalues():
                if q == icu_lower(title):
                    return True
        return False

    @write_api
    def create_book_entry(self, mi, cover=None, add_duplicates=True, force_id=None, apply_import_tags=True, preserve_uuid=False):
        if mi.tags:
            mi.tags = list(mi.tags)
        if apply_import_tags:
            _add_newbook_tag(mi)
        if not add_duplicates and self._has_book(mi):
            return
        series_index = (self._get_next_series_num_for(mi.series) if mi.series_index is None else mi.series_index)
        if not mi.authors:
            mi.authors = (_('Unknown'),)
        aus = mi.author_sort if mi.author_sort else self._author_sort_from_authors(mi.authors)
        mi.title = mi.title or _('Unknown')
        if isbytestring(aus):
            aus = aus.decode(preferred_encoding, 'replace')
        if isbytestring(mi.title):
            mi.title = mi.title.decode(preferred_encoding, 'replace')
        conn = self.backend.conn
        if force_id is None:
            conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                         (mi.title, series_index, aus))
        else:
            conn.execute('INSERT INTO books(id, title, series_index, author_sort) VALUES (?, ?, ?, ?)',
                         (force_id, mi.title, series_index, aus))
        book_id = conn.last_insert_rowid()

        mi.timestamp = utcnow() if mi.timestamp is None else mi.timestamp
        mi.pubdate = UNDEFINED_DATE if mi.pubdate is None else mi.pubdate
        if cover is not None:
            mi.cover, mi.cover_data = None, (None, cover)
        self._set_metadata(book_id, mi, ignore_errors=True)
        if preserve_uuid and mi.uuid:
            self._set_field('uuid', {book_id:mi.uuid})
        # Update the caches for fields from the books table
        self.fields['size'].table.book_col_map[book_id] = 0
        row = next(conn.execute('SELECT sort, series_index, author_sort, uuid, has_cover FROM books WHERE id=?', (book_id,)))
        for field, val in zip(('sort', 'series_index', 'author_sort', 'uuid', 'cover'), row):
            if field == 'cover':
                val = bool(val)
            elif field == 'uuid':
                self.fields[field].table.uuid_to_id_map[val] = book_id
            self.fields[field].table.book_col_map[book_id] = val

        return book_id

    @write_api
    def add_books(self, books, add_duplicates=True, apply_import_tags=True, preserve_uuid=False, run_hooks=True, dbapi=None):
        duplicates, ids = [], []
        for mi, format_map in books:
            book_id = self._create_book_entry(mi, add_duplicates=add_duplicates, apply_import_tags=apply_import_tags, preserve_uuid=preserve_uuid)
            if book_id is None:
                duplicates.append((mi, format_map))
            else:
                ids.append(book_id)
                for fmt, stream_or_path in format_map.iteritems():
                    self._add_format(book_id, fmt, stream_or_path, dbapi=dbapi, run_hooks=run_hooks)
        return ids, duplicates

    @write_api
    def remove_books(self, book_ids, permanent=False):
        path_map = {}
        for book_id in book_ids:
            try:
                path = self._field_for('path', book_id).replace('/', os.sep)
            except:
                path = None
            path_map[book_id] = path
        self.backend.remove_books(path_map, permanent=permanent)
        for field in self.fields.itervalues():
            try:
                table = field.table
            except AttributeError:
                continue  # Some fields like ondevice do not have tables
            else:
                table.remove_books(book_ids, self.backend)

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


    # }}}

class SortKey(object):  # {{{

    def __init__(self, fields, sort_keys, book_id):
        self.orders = tuple(1 if f[1] else -1 for f in fields)
        self.sort_key = tuple(sk[book_id] for sk in sort_keys)

    def __cmp__(self, other):
        for i, order in enumerate(self.orders):
            ans = cmp(self.sort_key[i], other.sort_key[i])
            if ans != 0:
                return ans * order
        return 0
# }}}



