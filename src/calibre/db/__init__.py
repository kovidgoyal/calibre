#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

SPOOL_SIZE = 30*1024*1024

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
    1. From initialize_dynamic(): set_saved_searches,
                    load_user_template_functions. Also add custom
                    columns/categories/searches info into
                    self.field_metadata. Finally, implement metadata dirtied
                    functionality.
    2. Catching DatabaseException and sqlite.Error when creating new
    libraries/switching/on calibre startup.
    3. From refresh in the legacy interface: Rember to flush the composite
    column template cache.
    4. Replace the metadatabackup thread with the new implementation when using the new backend.
'''
