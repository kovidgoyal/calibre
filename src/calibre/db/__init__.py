#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

SPOOL_SIZE = 30*1024*1024

import numbers
from polyglot.builtins import iteritems, range


def _get_next_series_num_for_list(series_indices, unwrap=True):
    from calibre.utils.config_base import tweaks
    from math import ceil, floor
    if not series_indices:
        if isinstance(tweaks['series_index_auto_increment'], numbers.Number):
            return float(tweaks['series_index_auto_increment'])
        return 1.0
    if unwrap:
        series_indices = [x[0] for x in series_indices]
    if tweaks['series_index_auto_increment'] == 'next':
        return floor(series_indices[-1]) + 1
    if tweaks['series_index_auto_increment'] == 'first_free':
        for i in range(1, 10000):
            if i not in series_indices:
                return i
        # really shouldn't get here.
    if tweaks['series_index_auto_increment'] == 'next_free':
        for i in range(int(ceil(series_indices[0])), 10000):
            if i not in series_indices:
                return i
        # really shouldn't get here.
    if tweaks['series_index_auto_increment'] == 'last_free':
        for i in range(int(ceil(series_indices[-1])), 0, -1):
            if i not in series_indices:
                return i
        return series_indices[-1] + 1
    if isinstance(tweaks['series_index_auto_increment'], numbers.Number):
        return float(tweaks['series_index_auto_increment'])
    return 1.0


def _get_series_values(val):
    import re
    series_index_pat = re.compile(r'(.*)\s+\[([.0-9]+)\]$')
    if not val:
        return (val, None)
    match = series_index_pat.match(val.strip())
    if match is not None:
        idx = match.group(2)
        try:
            idx = float(idx)
            return (match.group(1).strip(), idx)
        except:
            pass
    return (val, None)


def get_data_as_dict(self, prefix=None, authors_as_string=False, ids=None, convert_to_local_tz=True):
    '''
    Return all metadata stored in the database as a dict. Includes paths to
    the cover and each format.

    :param prefix: The prefix for all paths. By default, the prefix is the absolute path
    to the library folder.
    :param ids: Set of ids to return the data for. If None return data for
    all entries in database.
    '''
    import os
    from calibre.ebooks.metadata import authors_to_string
    from calibre.utils.date import as_local_time
    backend = getattr(self, 'backend', self)  # Works with both old and legacy interfaces
    if prefix is None:
        prefix = backend.library_path
    fdata = backend.custom_column_num_map

    FIELDS = set(['title', 'sort', 'authors', 'author_sort', 'publisher',
        'rating', 'timestamp', 'size', 'tags', 'comments', 'series',
        'series_index', 'uuid', 'pubdate', 'last_modified', 'identifiers',
        'languages']).union(set(fdata))
    for x, data in iteritems(fdata):
        if data['datatype'] == 'series':
            FIELDS.add('%d_index'%x)
    data = []
    for record in self.data:
        if record is None:
            continue
        db_id = record[self.FIELD_MAP['id']]
        if ids is not None and db_id not in ids:
            continue
        x = {}
        for field in FIELDS:
            x[field] = record[self.FIELD_MAP[field]]
        if convert_to_local_tz:
            for tf in ('timestamp', 'pubdate', 'last_modified'):
                x[tf] = as_local_time(x[tf])

        data.append(x)
        x['id'] = db_id
        x['formats'] = []
        isbn = self.isbn(db_id, index_is_id=True)
        x['isbn'] = isbn if isbn else ''
        if not x['authors']:
            x['authors'] = _('Unknown')
        x['authors'] = [i.replace('|', ',') for i in x['authors'].split(',')]
        if authors_as_string:
            x['authors'] = authors_to_string(x['authors'])
        x['tags'] = [i.replace('|', ',').strip() for i in x['tags'].split(',')] if x['tags'] else []
        path = os.path.join(prefix, self.path(record[self.FIELD_MAP['id']], index_is_id=True))
        x['cover'] = os.path.join(path, 'cover.jpg')
        if not record[self.FIELD_MAP['cover']]:
            x['cover'] = None
        formats = self.formats(record[self.FIELD_MAP['id']], index_is_id=True)
        if formats:
            for fmt in formats.split(','):
                path = self.format_abspath(x['id'], fmt, index_is_id=True)
                if path is None:
                    continue
                if prefix != self.library_path:
                    path = os.path.relpath(path, self.library_path)
                    path = os.path.join(prefix, path)
                x['formats'].append(path)
                x['fmt_'+fmt.lower()] = path
            x['available_formats'] = [i.upper() for i in formats.split(',')]

    return data
