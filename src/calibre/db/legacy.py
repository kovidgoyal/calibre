#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from functools import partial

from calibre.db.backend import DB
from calibre.db.cache import Cache
from calibre.db.view import View

class LibraryDatabase(object):

    ''' Emulate the old LibraryDatabase2 interface '''

    PATH_LIMIT = DB.PATH_LIMIT
    WINDOWS_LIBRARY_PATH_LIMIT = DB.WINDOWS_LIBRARY_PATH_LIMIT

    @classmethod
    def exists_at(cls, path):
        return path and os.path.exists(os.path.join(path, 'metadata.db'))

    def __init__(self, library_path,
            default_prefs=None, read_only=False, is_second_db=False,
            progress_callback=lambda x, y:True, restore_all_prefs=False):

        self.is_second_db = is_second_db  # TODO: Use is_second_db

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

    def close(self):
        self.backend.close()

    def break_cycles(self):
        self.data.cache.backend = None
        self.data.cache = None
        self.data = self.backend = self.new_api = self.field_metadata = self.prefs = self.listeners = self.refresh_ondevice = None

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

    def last_modified(self):
        return self.backend.last_modified()

    @property
    def custom_column_num_map(self):
        return self.backend.custom_column_num_map

    @property
    def custom_column_label_map(self):
        return self.backend.custom_column_label_map

    @property
    def FIELD_MAP(self):
        return self.backend.FIELD_MAP

    def all_ids(self):
        for book_id in self.data.cache.all_book_ids():
            yield book_id
    # }}}


