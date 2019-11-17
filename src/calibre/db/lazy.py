#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref
from functools import wraps
from collections import MutableMapping, MutableSequence
from copy import deepcopy

from calibre.ebooks.metadata.book.base import Metadata, SIMPLE_GET, TOP_LEVEL_IDENTIFIERS, NULL_VALUES, ALL_METADATA_FIELDS
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.utils.date import utcnow
from polyglot.builtins import unicode_type, native_string_type

# Lazy format metadata retrieval {{{
'''
Avoid doing stats on all files in a book when getting metadata for that book.
Speeds up calibre startup with large libraries/libraries on a network share,
with a composite custom column.
'''


def resolved(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if getattr(self, '_must_resolve', True):
            self._resolve()
            self._must_resolve = False
        return f(self, *args, **kwargs)
    return wrapper


class MutableBase(object):

    @resolved
    def __str__(self):
        return native_string_type(self._values)

    @resolved
    def __repr__(self):
        return repr(self._values)

    @resolved
    def __unicode__(self):
        return unicode_type(self._values)

    @resolved
    def __len__(self):
        return len(self._values)

    @resolved
    def __iter__(self):
        return iter(self._values)

    @resolved
    def __contains__(self, key):
        return key in self._values

    @resolved
    def __getitem__(self, fmt):
        return self._values[fmt]

    @resolved
    def __setitem__(self, key, val):
        self._values[key] = val

    @resolved
    def __delitem__(self, key):
        del self._values[key]


class FormatMetadata(MutableBase, MutableMapping):

    def __init__(self, db, id_, formats):
        self._dbwref = weakref.ref(db)
        self._id = id_
        self._formats = formats

    def _resolve(self):
        db = self._dbwref()
        self._values = {}
        for f in self._formats:
            try:
                self._values[f] = db.format_metadata(self._id, f)
            except:
                pass


class FormatsList(MutableBase, MutableSequence):

    def __init__(self, formats, format_metadata):
        self._formats = formats
        self._format_metadata = format_metadata

    def _resolve(self):
        self._values = [f for f in self._formats if f in self._format_metadata]

    @resolved
    def insert(self, idx, val):
        self._values.insert(idx, val)

# }}}


# Lazy metadata getters {{{
ga = object.__getattribute__
sa = object.__setattr__


def simple_getter(field, default_value=None):
    def func(dbref, book_id, cache):
        try:
            return cache[field]
        except KeyError:
            db = dbref()
            cache[field] = ret = db.field_for(field, book_id, default_value=default_value)
            return ret
    return func


def pp_getter(field, postprocess, default_value=None):
    def func(dbref, book_id, cache):
        try:
            return cache[field]
        except KeyError:
            db = dbref()
            cache[field] = ret = postprocess(db.field_for(field, book_id, default_value=default_value))
            return ret
    return func


def adata_getter(field):
    def func(dbref, book_id, cache):
        try:
            author_ids, adata = cache['adata']
        except KeyError:
            db = dbref()
            with db.safe_read_lock:
                author_ids = db._field_ids_for('authors', book_id)
                adata = db._author_data(author_ids)
            cache['adata'] = (author_ids, adata)
        k = 'sort' if field == 'author_sort_map' else 'link'
        return {adata[i]['name']:adata[i][k] for i in author_ids}
    return func


def dt_getter(field):
    def func(dbref, book_id, cache):
        try:
            return cache[field]
        except KeyError:
            db = dbref()
            cache[field] = ret = db.field_for(field, book_id, default_value=utcnow())
            return ret
    return func


def item_getter(field, default_value=None, key=0):
    def func(dbref, book_id, cache):
        try:
            return cache[field]
        except KeyError:
            db = dbref()
            ret = cache[field] = db.field_for(field, book_id, default_value=default_value)
            try:
                return ret[key]
            except (IndexError, KeyError):
                return default_value
    return func


def fmt_getter(field):
    def func(dbref, book_id, cache):
        try:
            format_metadata = cache['format_metadata']
        except KeyError:
            db = dbref()
            format_metadata = {}
            for fmt in db.formats(book_id, verify_formats=False):
                m = db.format_metadata(book_id, fmt)
                if m:
                    format_metadata[fmt] = m
        if field == 'formats':
            return sorted(format_metadata) or None
        return format_metadata
    return func


def approx_fmts_getter(dbref, book_id, cache):
    try:
        return cache['formats']
    except KeyError:
        db = dbref()
        cache['formats'] = ret = list(db.field_for('formats', book_id))
        return ret


def series_index_getter(field='series'):
    def func(dbref, book_id, cache):
        try:
            series = getters[field](dbref, book_id, cache)
        except KeyError:
            series = custom_getter(field, dbref, book_id, cache)
        if series:
            try:
                return cache[field + '_index']
            except KeyError:
                db = dbref()
                cache[field + '_index'] = ret = db.field_for(field + '_index', book_id, default_value=1.0)
                return ret
    return func


def has_cover_getter(dbref, book_id, cache):
    try:
        return cache['has_cover']
    except KeyError:
        db = dbref()
        cache['has_cover'] = ret = _('Yes') if db.field_for('cover', book_id, default_value=False) else ''
        return ret


fmt_custom = lambda x:list(x) if isinstance(x, tuple) else x


def custom_getter(field, dbref, book_id, cache):
    try:
        return cache[field]
    except KeyError:
        db = dbref()
        cache[field] = ret = fmt_custom(db.field_for(field, book_id))
        return ret


def composite_getter(mi, field, dbref, book_id, cache, formatter, template_cache):
    try:
        return cache[field]
    except KeyError:
        cache[field] = 'RECURSIVE_COMPOSITE FIELD (Metadata) ' + field
        try:
            db = dbref()
            with db.safe_read_lock:
                try:
                    fo = db.fields[field]
                except KeyError:
                    ret = cache[field] = _('Invalid field: %s') % field
                else:
                    ret = cache[field] = fo._render_composite_with_cache(book_id, mi, formatter, template_cache)
        except Exception:
            import traceback
            traceback.print_exc()
            return 'ERROR WHILE EVALUATING: %s' % field
        return ret


def virtual_libraries_getter(dbref, book_id, cache):
    try:
        return cache['virtual_libraries']
    except KeyError:
        db = dbref()
        vls = db.virtual_libraries_for_books((book_id,))[book_id]
        ret = cache['virtual_libraries'] = ', '.join(vls)
        return ret


def user_categories_getter(proxy_metadata):
    cache = ga(proxy_metadata, '_cache')
    try:
        return cache['user_categories']
    except KeyError:
        db = ga(proxy_metadata, '_db')()
        book_id = ga(proxy_metadata, '_book_id')
        ret = cache['user_categories'] = db.user_categories_for_books((book_id,), {book_id:proxy_metadata})[book_id]
        return ret


getters = {
    'title':simple_getter('title', _('Unknown')),
    'title_sort':simple_getter('sort', _('Unknown')),
    'authors':pp_getter('authors', list, (_('Unknown'),)),
    'author_sort':simple_getter('author_sort', _('Unknown')),
    'uuid':simple_getter('uuid', 'dummy'),
    'book_size':simple_getter('size', 0),
    'ondevice_col':simple_getter('ondevice', ''),
    'languages':pp_getter('languages', list),
    'language':item_getter('languages', default_value=NULL_VALUES['language']),
    'db_approx_formats': approx_fmts_getter,
    'has_cover': has_cover_getter,
    'tags':pp_getter('tags', list, (_('Unknown'),)),
    'series_index':series_index_getter(),
    'application_id':lambda x, book_id, y: book_id,
    'id':lambda x, book_id, y: book_id,
    'virtual_libraries':virtual_libraries_getter,
}

for field in ('comments', 'publisher', 'identifiers', 'series', 'rating'):
    getters[field] = simple_getter(field)

for field in ('author_sort_map', 'author_link_map'):
    getters[field] = adata_getter(field)

for field in ('timestamp', 'pubdate', 'last_modified'):
    getters[field] = dt_getter(field)

for field in TOP_LEVEL_IDENTIFIERS:
    getters[field] = item_getter('identifiers', key=field)

for field in ('formats', 'format_metadata'):
    getters[field] = fmt_getter(field)
# }}}


class ProxyMetadata(Metadata):

    def __init__(self, db, book_id, formatter=None):
        sa(self, 'template_cache', db.formatter_template_cache)
        sa(self, 'formatter', SafeFormat() if formatter is None else formatter)
        sa(self, '_db', weakref.ref(db))
        sa(self, '_book_id', book_id)
        sa(self, '_cache', {'cover_data':(None,None), 'device_collections':[]})
        sa(self, '_user_metadata', db.field_metadata)

    def __getattribute__(self, field):
        getter = getters.get(field, None)
        if getter is not None:
            return getter(ga(self, '_db'), ga(self, '_book_id'), ga(self, '_cache'))
        if field in SIMPLE_GET:
            if field == 'user_categories':
                return user_categories_getter(self)
            return ga(self, '_cache').get(field, None)
        try:
            return ga(self, field)
        except AttributeError:
            pass
        um = ga(self, '_user_metadata')
        d = um.get(field, None)
        if d is not None:
            dt = d['datatype']
            if dt != 'composite':
                if field.endswith('_index') and dt == 'float':
                    return series_index_getter(field[:-6])(ga(self, '_db'), ga(self, '_book_id'), ga(self, '_cache'))
                return custom_getter(field, ga(self, '_db'), ga(self, '_book_id'), ga(self, '_cache'))
            return composite_getter(self, field, ga(self, '_db'), ga(self, '_book_id'), ga(self, '_cache'), ga(self, 'formatter'), ga(self, 'template_cache'))

        try:
            return ga(self, '_cache')[field]
        except KeyError:
            raise AttributeError('Metadata object has no attribute named: %r' % field)

    def __setattr__(self, field, val, extra=None):
        cache = ga(self, '_cache')
        cache[field] = val
        if extra is not None:
            cache[field + '_index'] = val

    def get_user_metadata(self, field, make_copy=False):
        um = ga(self, '_user_metadata')
        try:
            ans = um[field]
        except KeyError:
            pass
        else:
            if make_copy:
                ans = deepcopy(ans)
            return ans

    def get_extra(self, field, default=None):
        um = ga(self, '_user_metadata')
        if field + '_index' in um:
            try:
                return getattr(self, field + '_index')
            except AttributeError:
                return default
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def custom_field_keys(self):
        um = ga(self, '_user_metadata')
        return iter(um.custom_field_keys())

    def get_standard_metadata(self, field, make_copy=False):
        field_metadata = ga(self, '_user_metadata')
        if field in field_metadata and field_metadata[field]['kind'] == 'field':
            if make_copy:
                return deepcopy(field_metadata[field])
            return field_metadata[field]
        return None

    def all_field_keys(self):
        um = ga(self, '_user_metadata')
        return frozenset(ALL_METADATA_FIELDS.union(frozenset(um)))

    @property
    def _proxy_metadata(self):
        return self
