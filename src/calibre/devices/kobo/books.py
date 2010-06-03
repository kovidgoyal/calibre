__license__   = 'GPL v3'
__copyright__ = '2010, Timothy Legge <timlegge at gmail.com>'
'''
'''

import os
import re
import time

from calibre.ebooks.metadata import MetaInformation
from calibre.devices.interface import BookList as _BookList
from calibre.constants import filesystem_encoding, preferred_encoding
from calibre import isbytestring

class Book(MetaInformation):

    BOOK_ATTRS = ['lpath', 'size', 'mime', 'device_collections']

    JSON_ATTRS = [
        'lpath', 'title', 'authors', 'mime', 'size', 'tags', 'author_sort',
        'title_sort', 'comments', 'category', 'publisher', 'series',
        'series_index', 'rating', 'isbn', 'language', 'application_id',
        'book_producer', 'lccn', 'lcc', 'ddc', 'rights', 'publication_type',
        'uuid',
    ]

    def __init__(self, mountpath, path, title, authors, mime, date, ContentType, ImageID, other=None):

        MetaInformation.__init__(self, '')
        self.device_collections = []

	self.title = title
	if not authors:
		self.authors = ['']
	else:
	        self.authors = [authors]
        self.mime = mime
	self.path = path
	try:
	        self.size = os.path.getsize(path)
	except OSError:
		self.size = 0
        try:
	    if ContentType == '6':
		self.datetime = time.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
	    else:
                self.datetime = time.gmtime(os.path.getctime(path))
        except ValueError:
             self.datetime = time.gmtime()
	except OSError:
             self.datetime = time.gmtime()
        self.lpath = path

	self.thumbnail = ImageWrapper(mountpath + '.kobo/images/' + ImageID + ' - iPhoneThumbnail.parsed')
        self.tags = []
        if other:
            self.smart_update(other)

    def __eq__(self, other):
        return self.path == getattr(other, 'path', None)

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
            val = getattr(self, attr)
            if isbytestring(val):
                 enc = filesystem_encoding if attr == 'lpath' else preferred_encoding
                 val = val.decode(enc, 'replace')
            elif isinstance(val, (list, tuple)):
                val = [x.decode(preferred_encoding, 'replace') if
                        isbytestring(x) else x for x in val]
            json[attr] = val
        return json

class ImageWrapper(object):
    def __init__(self, image_path):
	self.image_path = image_path

