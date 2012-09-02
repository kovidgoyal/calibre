#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.devices.interface import BookList as BL
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.utils.date import utcnow

class BookList(BL):

    def __init__(self, storage_id):
        self.storage_id = storage_id

    def supports_collections(self):
        return False

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

class JSONCodec(JsonCodec):
    pass

