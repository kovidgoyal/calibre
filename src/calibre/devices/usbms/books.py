# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import re
import time

from calibre.ebooks.metadata import MetaInformation
from calibre.devices.mime import mime_type_ext
from calibre.devices.interface import BookList as _BookList
from calibre.constants import filesystem_encoding

class Book(MetaInformation):

    BOOK_ATTRS = ['lpath', 'size', 'mime']

    JSON_ATTRS = [
        'lpath', 'title', 'authors', 'mime', 'size', 'tags', 'author_sort',
        'title_sort', 'comments', 'category', 'publisher', 'series',
        'series_index', 'rating', 'isbn', 'language', 'application_id',
        'book_producer', 'lccn', 'lcc', 'ddc', 'rights', 'publication_type',
        'uuid'
    ]

    def __init__(self, prefix, lpath, size=None, other=None):
        from calibre.ebooks.metadata.meta import path_to_ext

        MetaInformation.__init__(self, '')

        self.path = os.path.join(prefix, lpath)
        if os.sep == '\\':
            self.path = self.path.replace('/', '\\')
            self.lpath = lpath.replace('\\', '/')
        else:
            self.lpath = lpath
        self.mime = mime_type_ext(path_to_ext(lpath))
        self.size = None # will be set later
        self.datetime = time.gmtime()

        if other:
            self.smart_update(other)

    def __eq__(self, other):
        spath = self.path
        opath = other.path

        if not isinstance(self.path, unicode):
            try:
                spath = unicode(self.path)
            except:
                try:
                    spath = self.path.decode(filesystem_encoding)
                except:
                    spath = self.path
        if not isinstance(other.path, unicode):
            try:
                opath = unicode(other.path)
            except:
                try:
                    opath = other.path.decode(filesystem_encoding)
                except:
                    opath = other.path

        return spath == opath

    @dynamic_property
    def db_id(self):
        doc = '''The database id in the application database that this file corresponds to'''
        def fget(self):
            match = re.search(r'_(\d+)$', self.lpath.rpartition('.')[0])
            if match:
                return int(match.group(1))
            return None
        return property(fget=fget, doc=doc)

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', self.title).rstrip()
        return property(doc=doc, fget=fget)

    @dynamic_property
    def thumbnail(self):
        return None

    def smart_update(self, other):
        '''
        Merge the information in C{other} into self. In case of conflicts, the information
        in C{other} takes precedence, unless the information in C{other} is NULL.
        '''

        MetaInformation.smart_update(self, other)

        for attr in self.BOOK_ATTRS:
            if hasattr(other, attr):
                val = getattr(other, attr, None)
                setattr(self, attr, val)

    def to_json(self):
        json = {}
        for attr in self.JSON_ATTRS:
            json[attr] = getattr(self, attr)
        return json

class BookList(_BookList):

    def supports_tags(self):
        return True

    def set_tags(self, book, tags):
        book.tags = tags

    def add_book(self, book, replace_metadata):
        if book not in self:
            self.append(book)
            return True

    def remove_book(self, book):
        self.remove(book)
