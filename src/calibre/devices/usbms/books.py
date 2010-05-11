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
        self.lpath = lpath
        self.mime = mime_type_ext(path_to_ext(lpath))
        self.size = os.stat(self.path).st_size if size == None else size
        self.db_id = None
        try:
            self.datetime = time.gmtime(os.path.getctime(self.path))
        except ValueError:
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
                    spath = self.path.decode('utf-8')
                except:
                    spath = self.path
        if not isinstance(other.path, unicode):
            try:
                opath = unicode(other.path)
            except:
                try:
                    opath = other.path.decode('utf-8')
                except:
                    opath = other.path

        return spath == opath

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', self.title).rstrip()
        return property(doc=doc, fget=fget)

    @dynamic_property
    def thumbnail(self):
        return None

#    def __str__(self):
#        '''
#        Return a utf-8 encoded string with title author and path information
#        '''
#        return self.title.encode('utf-8') + " by " + \
#               self.authors.encode('utf-8') + " at " + self.path.encode('utf-8')

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

