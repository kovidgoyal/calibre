#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

def sanitize_sort_field_name(field_metadata, field):
    field = field_metadata.search_term_to_field_key(field.lower().strip())
    # translate some fields to their hidden equivalent
    field = {'title': 'sort', 'authors':'author_sort'}.get(field, field)
    return field

class View(object):

    def __init__(self, cache):
        self.cache = cache
        self.marked_ids = {}
        self._field_getters = {}
        for col, idx in cache.backend.FIELD_MAP.iteritems():
            if isinstance(col, int):
                label = self.cache.backend.custom_column_num_map[col]['label']
                label = (self.cache.backend.field_metadata.custom_field_prefix
                        + label)
                self._field_getters[idx] = partial(self.get, label)
            else:
                try:
                    self._field_getters[idx] = {
                        'id'      : self._get_id,
                        'au_map'  : self.get_author_data,
                        'ondevice': self.get_ondevice,
                        'marked'  : self.get_marked,
                    }[col]
                except KeyError:
                    self._field_getters[idx] = partial(self.get, col)

        self._map = list(self.cache.all_book_ids())
        self._map_filtered = list(self._map)

    @property
    def field_metadata(self):
        return self.cache.field_metadata

    def _get_id(self, idx, index_is_id=True):
        ans = idx if index_is_id else self.index_to_id(idx)
        return ans

    def get_field_map_field(self, row, col, index_is_id=True):
        '''
        Supports the legacy FIELD_MAP interface for getting metadata. Do not use
        in new code.
        '''
        getter = self._field_getters[col]
        return getter(row, index_is_id=index_is_id)

    def index_to_id(self, idx):
        return self._map_filtered[idx]

    def get(self, field, idx, index_is_id=True, default_value=None):
        id_ = idx if index_is_id else self.index_to_id(idx)
        return self.cache.field_for(field, id_)

    def get_ondevice(self, idx, index_is_id=True, default_value=''):
        id_ = idx if index_is_id else self.index_to_id(idx)
        self.cache.field_for('ondevice', id_, default_value=default_value)

    def get_marked(self, idx, index_is_id=True, default_value=None):
        id_ = idx if index_is_id else self.index_to_id(idx)
        return self.marked_ids.get(id_, default_value)

    def get_author_data(self, idx, index_is_id=True, default_value=()):
        '''
        Return author data for all authors of the book identified by idx as a
        tuple of dictionaries. The dictionaries should never be empty, unless
        there is a bug somewhere. The list could be empty if idx point to an
        non existent book, or book with no authors (though again a book with no
        authors should never happen).

        Each dictionary has the keys: name, sort, link. Link can be an empty
        string.

        default_value is ignored, this method always returns a tuple
        '''
        id_ = idx if index_is_id else self.index_to_id(idx)
        with self.cache.read_lock:
            ids = self.cache._field_ids_for('authors', id_)
            ans = []
            for id_ in ids:
                ans.append(self.cache._author_data(id_))
        return tuple(ans)

    def multisort(self, fields=[], subsort=False):
        fields = [(sanitize_sort_field_name(self.field_metadata, x), bool(y)) for x, y in fields]
        keys = self.field_metadata.sortable_field_keys()
        fields = [x for x in fields if x[0] in keys]
        if subsort and 'sort' not in [x[0] for x in fields]:
            fields += [('sort', True)]
        if not fields:
            fields = [('timestamp', False)]

        sorted_book_ids = self.cache.multisort(fields)
        sorted_book_ids
        # TODO: change maps


