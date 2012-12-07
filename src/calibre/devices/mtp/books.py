#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.devices.interface import BookList as BL
from calibre.ebooks.metadata import title_sort
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.utils.date import utcnow

class BookList(BL):

    def __init__(self, storage_id):
        self.storage_id = storage_id

    def supports_collections(self):
        return False

    def add_book(self, book, replace_metadata=True):
        try:
            b = self.index(book)
        except (ValueError, IndexError):
            b = None
        if b is None:
            self.append(book)
            return book
        if replace_metadata:
            self[b].smart_update(book, replace_metadata=True)
            return self[b]
        return None

    def remove_book(self, book):
        self.remove(book)

class Book(Metadata):

    def __init__(self, storage_id, lpath, other=None):
        Metadata.__init__(self, _('Unknown'), other=other)
        self.storage_id, self.lpath = storage_id, lpath
        self.lpath = self.path = self.lpath.replace(os.sep, '/')
        self.mtp_relpath = tuple([icu_lower(x) for x in self.lpath.split('/')])
        self.datetime = utcnow().timetuple()
        self.thumbail = None

    def matches_file(self, mtp_file):
        return (self.storage_id == mtp_file.storage_id and
                self.mtp_relpath == mtp_file.mtp_relpath)

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and (self.storage_id ==
            other.storage_id and self.mtp_relpath == other.mtp_relpath))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.storage_id, self.mtp_relpath))

    @property
    def title_sorter(self):
        ans = getattr(self, 'title_sort', None)
        if not ans or self.is_null('title_sort') or ans == _('Unknown'):
            ans = ''
        return ans or title_sort(self.title or '')

class JSONCodec(JsonCodec):
    pass

