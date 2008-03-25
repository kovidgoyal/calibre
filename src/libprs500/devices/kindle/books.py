__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
'''
import re, time, functools
import os


from libprs500.devices.interface import BookList as _BookList
from libprs500.devices import strftime as _strftime

strftime = functools.partial(_strftime, zone=time.localtime)
MIME_MAP   = { 
                "azw" : "application/azw", 
                "prc" : "application/prc", 
                "txt" : "text/plain",
                'mobi': 'application/mobi', 
              }

def sortable_title(title):
    return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', title).rstrip()

class Book(object):
    
    @apply
    def title_sorter():
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            src = self.title
            return src
        def fset(self, val):
            self.elem.setAttribute('titleSorter', sortable_title(unicode(val)))
        return property(doc=doc, fget=fget, fset=fset)
    
    @apply
    def thumbnail():
        return 0
        
    
    @apply
    def path():
        doc = """ Absolute path to book on device. Setting not supported. """
        def fget(self):  
            return self.mountpath + self.rpath
        return property(fget=fget, doc=doc)
    
    @apply
    def db_id():
        doc = '''The database id in the application database that this file corresponds to'''
        def fget(self):
            match = re.search(r'_(\d+)$', self.rpath.rpartition('.')[0])
            if match:
                return int(match.group(1))
        return property(fget=fget, doc=doc)
    
    def __init__(self, mountpath, title, authors ):
        self.mountpath = mountpath
        self.title = title
        self.authors = authors
        self.mime = ""
        self.rpath = "documents//" + title
        self.id = 0
        self.sourceid = 0
        self.size = 0
        self.datetime = time.gmtime()
        self.tags = []
        
    
    def __str__(self):
        """ Return a utf-8 encoded string with title author and path information """
        return self.title.encode('utf-8') + " by " + \
               self.authors.encode('utf-8') + " at " + self.path.encode('utf-8')


class BookList(_BookList):
    _mountpath = ""
    
    def __init__(self, mountpath):
        self._mountpath = mountpath
        _BookList.__init__(self)            
        self.return_books(mountpath)   
       
    def return_books(self,mountpath):
        docs = mountpath + "documents"
        for f in os.listdir(docs):
            m =  re.match(".*azw", f)
            if m:
                self.append_book(mountpath,f)
            m =  re.match(".*prc", f)
            if m:
                self.append_book(mountpath,f)
            m =  re.match(".*txt", f)
            if m:
                self.append_book(mountpath,f)
      
    def append_book(self,mountpath,f):
        b = Book(mountpath,f,"")
        b.size = os.stat(mountpath + "//documents//" + f)[6]
        b.datetime = time.gmtime(os.stat(mountpath + "//documents//" + f)[8])
        b.rpath = "//documents//" + f
        self.append(b)
                 
    def supports_tags(self):
        return False
     
    def add_book(self, name, size, ctime):
        book = Book(self._mountpath, name, "")
        book.datetime = time.gmtime(ctime)
        book.size = size
        '''remove book if already in db'''
        self.remove_book(self._mountpath + "//documents//" + name)
        self.append(book)
       
            
    def remove_book(self, path):
        for book in self:
            if path.startswith(book.mountpath):
                if path.endswith(book.rpath):
                    self.remove(book)
                    break
    
  
