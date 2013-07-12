#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref
from functools import partial
from itertools import izip, imap

from calibre.ebooks.metadata import title_sort
from calibre.utils.config_base import tweaks

def sanitize_sort_field_name(field_metadata, field):
    field = field_metadata.search_term_to_field_key(field.lower().strip())
    # translate some fields to their hidden equivalent
    field = {'title': 'sort', 'authors':'author_sort'}.get(field, field)
    return field

class MarkedVirtualField(object):

    def __init__(self, marked_ids):
        self.marked_ids = marked_ids

    def iter_searchable_values(self, get_metadata, candidates, default_value=None):
        for book_id in candidates:
            yield self.marked_ids.get(book_id, default_value), {book_id}

class TableRow(object):

    def __init__(self, book_id, view):
        self.book_id = book_id
        self.view = weakref.ref(view)
        self.column_count = view.column_count

    def __getitem__(self, obj):
        view = self.view()
        if isinstance(obj, slice):
            return [view._field_getters[c](self.book_id)
                    for c in xrange(*obj.indices(len(view._field_getters)))]
        else:
            return view._field_getters[obj](self.book_id)

    def __len__(self):
        return self.column_count

    def __iter__(self):
        for i in xrange(self.column_count):
            yield self[i]

def format_is_multiple(x, sep=',', repl=None):
    if not x:
        return None
    if repl is not None:
        x = (y.replace(sep, repl) for y in x)
    return sep.join(x)

def format_identifiers(x):
    if not x:
        return None
    return ','.join('%s:%s'%(k, v) for k, v in x.iteritems())

class View(object):

    ''' A table view of the database, with rows and columns. Also supports
    filtering and sorting.  '''

    def __init__(self, cache):
        self.cache = cache
        self.marked_ids = {}
        self.search_restriction_book_count = 0
        self.search_restriction = self.base_restriction = ''
        self.search_restriction_name = self.base_restriction_name = ''
        self._field_getters = {}
        self.column_count = len(cache.backend.FIELD_MAP)
        for col, idx in cache.backend.FIELD_MAP.iteritems():
            label, fmt = col, lambda x:x
            func = {
                    'id': self._get_id,
                    'au_map': self.get_author_data,
                    'ondevice': self.get_ondevice,
                    'marked': self.get_marked,
                    'series_sort':self.get_series_sort,
                }.get(col, self._get)
            if isinstance(col, int):
                label = self.cache.backend.custom_column_num_map[col]['label']
                label = (self.cache.backend.field_metadata.custom_field_prefix
                        + label)
            if label.endswith('_index'):
                try:
                    num = int(label.partition('_')[0])
                except ValueError:
                    pass  # series_index
                else:
                    label = self.cache.backend.custom_column_num_map[num]['label']
                    label = (self.cache.backend.field_metadata.custom_field_prefix
                            + label + '_index')

            fm = self.field_metadata[label]
            fm
            if label == 'authors':
                fmt = partial(format_is_multiple, repl='|')
            elif label in {'tags', 'languages', 'formats'}:
                fmt = format_is_multiple
            elif label == 'cover':
                fmt = bool
            elif label == 'identifiers':
                fmt = format_identifiers
            elif fm['datatype'] == 'text' and fm['is_multiple']:
                sep = fm['is_multiple']['cache_to_list']
                if sep not in {'&','|'}:
                    sep = '|'
                fmt = partial(format_is_multiple, sep=sep)
            self._field_getters[idx] = partial(func, label, fmt=fmt) if func == self._get else func

        self._map = tuple(sorted(self.cache.all_book_ids()))
        self._map_filtered = tuple(self._map)

    def get_property(self, id_or_index, index_is_id=False, loc=-1):
        book_id = id_or_index if index_is_id else self._map_filtered[id_or_index]
        return self._field_getters[loc](book_id)

    @property
    def field_metadata(self):
        return self.cache.field_metadata

    def _get_id(self, idx, index_is_id=True):
        if index_is_id and idx not in self.cache.all_book_ids():
            raise IndexError('No book with id %s present'%idx)
        return idx if index_is_id else self.index_to_id(idx)

    def __getitem__(self, row):
        return TableRow(self._map_filtered[row], self)

    def __len__(self):
        return len(self._map_filtered)

    def __iter__(self):
        for book_id in self._map_filtered:
            yield TableRow(book_id, self)

    def iterall(self):
        for book_id in self.iterallids():
            yield TableRow(book_id, self)

    def iterallids(self):
        for book_id in sorted(self._map):
            yield book_id

    def get_field_map_field(self, row, col, index_is_id=True):
        '''
        Supports the legacy FIELD_MAP interface for getting metadata. Do not use
        in new code.
        '''
        getter = self._field_getters[col]
        return getter(row, index_is_id=index_is_id)

    def index_to_id(self, idx):
        return self._map_filtered[idx]

    def _get(self, field, idx, index_is_id=True, default_value=None, fmt=lambda x:x):
        id_ = idx if index_is_id else self.index_to_id(idx)
        if index_is_id and id_ not in self.cache.all_book_ids():
            raise IndexError('No book with id %s present'%idx)
        return fmt(self.cache.field_for(field, id_, default_value=default_value))

    def get_series_sort(self, idx, index_is_id=True, default_value=''):
        book_id = idx if index_is_id else self.index_to_id(idx)
        with self.cache.read_lock:
            lang_map = self.cache.fields['languages'].book_value_map
            lang = lang_map.get(book_id, None) or None
            if lang:
                lang = lang[0]
            return title_sort(self.cache._field_for('series', book_id, default_value=''),
                              order=tweaks['title_series_sorting'], lang=lang)

    def get_ondevice(self, idx, index_is_id=True, default_value=''):
        id_ = idx if index_is_id else self.index_to_id(idx)
        return self.cache.field_for('ondevice', id_, default_value=default_value)

    def get_marked(self, idx, index_is_id=True, default_value=None):
        id_ = idx if index_is_id else self.index_to_id(idx)
        return self.marked_ids.get(id_, default_value)

    def get_author_data(self, idx, index_is_id=True, default_value=None):
        id_ = idx if index_is_id else self.index_to_id(idx)
        with self.cache.read_lock:
            ids = self.cache._field_ids_for('authors', id_)
            adata = self.cache._author_data(ids)
            ans = [':::'.join((adata[aid]['name'], adata[aid]['sort'], adata[aid]['link'])) for aid in ids if aid in adata]
        return ':#:'.join(ans) if ans else default_value

    def multisort(self, fields=[], subsort=False, only_ids=None):
        fields = [(sanitize_sort_field_name(self.field_metadata, x), bool(y)) for x, y in fields]
        keys = self.field_metadata.sortable_field_keys()
        fields = [x for x in fields if x[0] in keys]
        if subsort and 'sort' not in [x[0] for x in fields]:
            fields += [('sort', True)]
        if not fields:
            fields = [('timestamp', False)]

        sorted_book_ids = self.cache.multisort(fields, ids_to_sort=only_ids)
        if only_ids is None:
            self._map = tuple(sorted_book_ids)
            if len(self._map_filtered) == len(self._map):
                self._map_filtered = tuple(self._map)
            else:
                fids = frozenset(self._map_filtered)
                self._map_filtered = tuple(i for i in self._map if i in fids)
        else:
            smap = {book_id:i for i, book_id in enumerate(sorted_book_ids)}
            only_ids.sort(key=smap.get)

    def search(self, query, return_matches=False):
        ans = self.search_getting_ids(query, self.search_restriction,
                                      set_restriction_count=True)
        if return_matches:
            return ans
        self._map_filtered = tuple(ans)

    def _build_restriction_string(self, restriction):
        if self.base_restriction:
            if restriction:
                return u'(%s) and (%s)' % (self.base_restriction, restriction)
            else:
                return self.base_restriction
        else:
            return restriction

    def search_getting_ids(self, query, search_restriction,
                           set_restriction_count=False, use_virtual_library=True):
        if use_virtual_library:
            search_restriction = self._build_restriction_string(search_restriction)
        q = ''
        if not query or not query.strip():
            q = search_restriction
        else:
            q = query
            if search_restriction:
                q = u'(%s) and (%s)' % (search_restriction, query)
        if not q:
            if set_restriction_count:
                self.search_restriction_book_count = len(self._map)
            return list(self._map)
        matches = self.cache.search(
            query, search_restriction, virtual_fields={'marked':MarkedVirtualField(self.marked_ids)})
        rv = [x for x in self._map if x in matches]
        if set_restriction_count and q == search_restriction:
            self.search_restriction_book_count = len(rv)
        return rv

    def get_search_restriction(self):
        return self.search_restriction

    def set_search_restriction(self, s):
        self.search_restriction = s

    def get_base_restriction(self):
        return self.base_restriction

    def set_base_restriction(self, s):
        self.base_restriction = s

    def get_base_restriction_name(self):
        return self.base_restriction_name

    def set_base_restriction_name(self, s):
        self.base_restriction_name = s

    def get_search_restriction_name(self):
        return self.search_restriction_name

    def set_search_restriction_name(self, s):
        self.search_restriction_name = s

    def search_restriction_applied(self):
        return bool(self.search_restriction) or bool(self.base_restriction)

    def get_search_restriction_book_count(self):
        return self.search_restriction_book_count

    def set_marked_ids(self, id_dict):
        '''
        ids in id_dict are "marked". They can be searched for by
        using the search term ``marked:true``. Pass in an empty dictionary or
        set to clear marked ids.

        :param id_dict: Either a dictionary mapping ids to values or a set
        of ids. In the latter case, the value is set to 'true' for all ids. If
        a mapping is provided, then the search can be used to search for
        particular values: ``marked:value``
        '''
        if not hasattr(id_dict, 'items'):
            # Simple list. Make it a dict of string 'true'
            self.marked_ids = dict.fromkeys(id_dict, u'true')
        else:
            # Ensure that all the items in the dict are text
            self.marked_ids = dict(izip(id_dict.iterkeys(), imap(unicode,
                id_dict.itervalues())))

    def refresh(self, field=None, ascending=True):
        self._map = tuple(self.cache.all_book_ids())
        self._map_filtered = tuple(self._map)
        if field is not None:
            self.sort(field, ascending)
        if self.search_restriction or self.base_restriction:
            self.search('', return_matches=False)

