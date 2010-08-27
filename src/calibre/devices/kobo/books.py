__license__   = 'GPL v3'
__copyright__ = '2010, Timothy Legge <timlegge at gmail.com>'
'''
'''

import os
import time

from calibre.devices.usbms.books import Book as Book_

class Book(Book_):

    def __init__(self, prefix, lpath, title, authors, mime, date, ContentType,
                 thumbnail_name, other=None):
        Book_.__init__(self, prefix, lpath)

        self.title = title
        if not authors:
            self.authors = ['']
        else:
            self.authors = [authors]
        self.mime = mime
        try:
            self.size = os.path.getsize(self.path)
        except OSError:
            self.size = 0
        try:
            if ContentType == '6':
                self.datetime = time.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
            else:
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

