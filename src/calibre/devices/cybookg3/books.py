__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
'''
import os, fnmatch, time

from calibre.devices.interface import BookList as _BookList

EBOOK_DIR = "eBooks"
EBOOK_TYPES = ['mobi', 'prc', 'html', 'pdf', 'rtf', 'txt']

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
        return 0
        
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
        # Get all books in all directories under the root EBOOK_DIR directory
        for path, dirs, files in os.walk(os.path.join(mountpath, EBOOK_DIR)):
            # Filter out anything that isn't in the list of supported ebook types
            for book_type in EBOOK_TYPES:
                for filename in fnmatch.filter(files, '*.%s' % (book_type)):
                    # Calibre uses a specific format for file names. They take the form
                    # title_-_author_number.extention We want to see if the file name is
                    # in this format.
                    if fnmatch.fnmatchcase(filename, '*_-_*.*'):
                        # Get the title and author from the file name
                        title, sep, author = filename.rpartition('_-_')
                        author, sep, ext = author.rpartition('_')
                        book_title = title.replace('_', ' ')
                        book_author = author.replace('_', ' ')
                    # if the filename did not match just set the title to
                    # the filename without the extension
                    else:
                        book_title = os.path.splitext(filename)[0].replace('_', ' ')
                        
                    book_path = os.path.join(path, filename)
                    self.append(Book(book_path, book_title, book_author))
            
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

