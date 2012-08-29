__license__   = 'GPL v3'
__copyright__ = '2010, Timothy Legge <timlegge at gmail.com>'
'''
'''

import os
import time

from calibre.utils.date import parse_date
from calibre.devices.usbms.books import Book as Book_

class Book(Book_):

    def __init__(self, prefix, lpath, title, authors, mime, date, ContentType,
                 thumbnail_name, size=None, other=None):
        Book_.__init__(self, prefix, lpath)

        self.title = title
        if not authors:
            self.authors = ['']
        else:
            self.authors = [authors]

        if not title:
            self.title = _('Unknown')

        self.mime = mime

        self.size = size # will be set later if None

        if ContentType == '6' and date is not None:
            try:
                self.datetime = time.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
            except:
                try:
                    self.datetime = parse_date(date,
                            assume_utc=True).timetuple()
                except:
                    try:
                        self.datetime = time.gmtime(os.path.getctime(self.path))
                    except:
                        self.datetime = time.gmtime()
        else:
            try:
                self.datetime = time.gmtime(os.path.getctime(self.path))
            except:
                self.datetime = time.gmtime()

        if thumbnail_name is not None:
            self.thumbnail = ImageWrapper(thumbnail_name)
        self.tags = []
        if other:
            self.smart_update(other)

class ImageWrapper(object):
    def __init__(self, image_path):
        self.image_path = image_path

