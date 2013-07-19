#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

SPOOL_SIZE = 30*1024*1024

def _get_next_series_num_for_list(series_indices, unwrap=True):
    from calibre.utils.config_base import tweaks
    from math import ceil, floor
    if not series_indices:
        if isinstance(tweaks['series_index_auto_increment'], (int, float)):
            return float(tweaks['series_index_auto_increment'])
        return 1.0
    if unwrap:
        series_indices = [x[0] for x in series_indices]
    if tweaks['series_index_auto_increment'] == 'next':
        return floor(series_indices[-1]) + 1
    if tweaks['series_index_auto_increment'] == 'first_free':
        for i in xrange(1, 10000):
            if i not in series_indices:
                return i
        # really shouldn't get here.
    if tweaks['series_index_auto_increment'] == 'next_free':
        for i in xrange(int(ceil(series_indices[0])), 10000):
            if i not in series_indices:
                return i
        # really shouldn't get here.
    if tweaks['series_index_auto_increment'] == 'last_free':
        for i in xrange(int(ceil(series_indices[-1])), 0, -1):
            if i not in series_indices:
                return i
        return series_indices[-1] + 1
    if isinstance(tweaks['series_index_auto_increment'], (int, float)):
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

def get_data_as_dict(self, prefix=None, authors_as_string=False, ids=None):
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
    backend = getattr(self, 'backend', self)  # Works with both old and legacy interfaces
    if prefix is None:
        prefix = backend.library_path
    fdata = backend.custom_column_num_map

    FIELDS = set(['title', 'sort', 'authors', 'author_sort', 'publisher',
        'rating', 'timestamp', 'size', 'tags', 'comments', 'series',
        'series_index', 'uuid', 'pubdate', 'last_modified', 'identifiers',
        'languages']).union(set(fdata))
    for x, data in fdata.iteritems():
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

'''
Rewrite of the calibre database backend.

Broad Objectives:

    * Use the sqlite db only as a datastore. i.e. do not do
      sorting/searching/concatenation or anything else in sqlite. Instead
      mirror the sqlite tables in memory, create caches and lookup maps from
      them and create a set_* API that updates the memory caches and the sqlite
      correctly.

    * Move from keeping a list of books in memory as a cache to a per table
      cache. This allows much faster search and sort operations at the expense
      of slightly slower lookup operations. That slowdown can be mitigated by
      keeping lots of maps and updating them in the set_* API. Also
      get_categories becomes blazingly fast.

    * Separate the database layer from the cache layer more cleanly. Rather
      than having the db layer refer to the cache layer and vice versa, the
      cache layer will refer to the db layer only and the new API will be
      defined on the cache layer.

    * Get rid of index_is_id and other poor design decisions

    * Minimize the API as much as possible and define it cleanly

    * Do not change the on disk format of metadata.db at all (this is for
      backwards compatibility)

    * Get rid of the need for a separate db access thread by switching to apsw
      to access sqlite, which is thread safe

    * The new API will have methods to efficiently do bulk operations and will
      use shared/exclusive/pending locks to serialize access to the in-mem data
      structures. Use the same locking scheme as sqlite itself does.

How this will proceed:

    1. Create the new API
    2. Create a test suite for it
    3. Write a replacement for LibraryDatabase2 that uses the new API
       internally
    4. Lots of testing of calibre with the new LibraryDatabase2
    5. Gradually migrate code to use the (much faster) new api wherever possible (the new api
       will be exposed via db.new_api)

    I plan to work on this slowly, in parallel to normal calibre development
    work.

Various things that require other things before they can be migrated:
    1. From initialize_dynamic(): Also add custom
                    columns/categories/searches info into
                    self.field_metadata.
    2. Catching DatabaseException and sqlite.Error when creating new
    libraries/switching/on calibre startup.
    3. Port library/restore.py
    4. Replace the metadatabackup thread with the new implementation when using the new backend.
    5. grep the sources for TODO
    6. Check that content server reloading on metadata,db change, metadata
    backup, refresh gui on calibredb add and moving libraries all work (check
    them on windows as well for file locking issues)
'''
