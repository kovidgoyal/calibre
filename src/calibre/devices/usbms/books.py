# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import re
import time

from calibre.devices.interface import BookList as _BookList

class Book(object):

    def __init__(self, path, title, authors, mime):
        self.title = title
        self.authors = authors
        self.mime = mime
        self.size = os.path.getsize(path)
        try:
            self.datetime = time.gmtime(os.path.getctime(path))
        except ValueError:
            self.datetime = time.gmtime()
        self.path = path
        self.thumbnail = None
        self.tags = []

    def __eq__(self, other):
        return self.path == other.path

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', self.title).rstrip()
        return property(doc=doc, fget=fget)

    @dynamic_property
    def thumbnail(self):
        return None

    def __str__(self):
        '''
        Return a utf-8 encoded string with title author and path information
        '''
        return self.title.encode('utf-8') + " by " + \
               self.authors.encode('utf-8') + " at " + self.path.encode('utf-8')

    @property
    def db_id(self):
        '''The database id in the application database that this file corresponds to'''
        match = re.search(r'_(\d+)$', self.path.rpartition('.')[0])
        if match:
            return int(match.group(1))

class BookList(_BookList):

    def supports_tags(self):
        return False

    def set_tags(self, book, tags):
        pass
