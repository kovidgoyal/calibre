__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com'

'''
'''
import os, fnmatch, time

from calibre.devices.interface import BookList as _BookList

EBOOK_DIR = "eBooks"
EBOOK_TYPES = ['mobi', 'prc', 'pdf', 'txt']

class Book(object):
    def __init__(self, path, title, authors):
        self.title = title
        self.authors = authors
        self.size = os.path.getsize(path)
        self.datetime = time.gmtime(os.path.getctime(path))
        self.path = path
        self.thumbnail = None
        self.tags = []
        
    @apply
    def thumbnail():
        return None
        
    def __str__(self):
        """ Return a utf-8 encoded string with title author and path information """
        return self.title.encode('utf-8') + " by " + \
               self.authors.encode('utf-8') + " at " + self.path.encode('utf-8')


class BookList(_BookList):
    def __init__(self, mountpath):
        self._mountpath = mountpath
        _BookList.__init__(self)            
        self.return_books(mountpath)  

    def return_books(self, mountpath):
        for path, dirs, files in os.walk(os.path.join(mountpath, EBOOK_DIR)):
            for book_type in EBOOK_TYPES:
                for filename in fnmatch.filter(files, '*.%s' % (book_type)):
                    self.append(Book(os.path.join(path, filename), filename, ""))
            
    def add_book(self, path, title):
        self.append(Book(path, title, ""))

    def remove_book(self, path):
        for book in self:
            if path.endswith(book.path):
                self.remove(book)
                break
            
    def supports_tags(self):
        ''' Return True if the the device supports tags (collections) for this book list. '''
        return False
    
    def set_tags(self, book, tags):
        pass

