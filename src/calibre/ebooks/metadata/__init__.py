__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Provides metadata editing support for PDF and RTF files. For LRF metadata, use 
the L{lrf.meta} module.
"""
__docformat__ = "epytext"
__author__       = "Kovid Goyal <kovid@kovidgoyal.net>"


from calibre import __version__ as VERSION
from calibre import OptionParser

def get_parser(extension):
    ''' Return an option parser with the basic metadata options already setup'''
    parser = OptionParser(usage='%prog [options] myfile.'+extension+'\n\nRead and write metadata from an ebook file.')
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help=_("Set the book title"), default=None)
    parser.add_option("-a", "--authors", action="store", type="string", \
                    dest="authors", help=_("Set the authors"), default=None)
    parser.add_option("-c", "--category", action="store", type="string", \
                    dest="category", help=_("The category this book belongs to. E.g.: History"), default=None)
    parser.add_option('--comment', dest='comment', default=None, action='store',
                      help=_('Set the comment'))
    return parser

class MetaInformation(object):
    '''Convenient encapsulation of book metadata'''
    
    @staticmethod
    def copy(mi):
        ans = MetaInformation(mi.title, mi.authors)
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'tags', 'cover_data', 'application_id',
                     'manifest', 'spine', 'toc', 'cover'):
            if hasattr(mi, attr):
                setattr(ans, attr, getattr(mi, attr))
        
    
    def __init__(self, title, authors=['Unknown']):
        '''
        @param title: title or "Unknown" or a MetaInformation object
        @param authors: List of strings or []
        '''
        mi = None
        if isinstance(title, MetaInformation):
            mi = title
            title = mi.title
            authors = mi.authors
        self.title = title
        self.author = authors # Needed for backward compatibility
        #: List of strings or []
        self.authors = authors
        #: Sort text for author
        self.author_sort  = None if not mi else mi.author_sort
        self.title_sort   = None if not mi else mi.title_sort
        self.comments     = None if not mi else mi.comments
        self.category     = None if not mi else mi.category
        self.publisher    = None if not mi else mi.publisher
        self.series       = None if not mi else mi.series
        self.series_index = None if not mi else mi.series_index
        self.rating       = None if not mi else mi.rating
        self.isbn         = None if not mi else mi.isbn
        self.tags         = []  if not mi else mi.tags
        #: mi.cover_data = (ext, data)
        self.cover_data   = mi.cover_data if (mi and hasattr(mi, 'cover_data')) else (None, None)
        self.application_id    = mi.application_id  if (mi and hasattr(mi, 'application_id')) else None
        self.manifest = getattr(mi, 'manifest', None) 
        self.toc      = getattr(mi, 'toc', None)
        self.spine    = getattr(mi, 'spine', None)
        self.cover    = getattr(mi, 'cover', None)
    
    def smart_update(self, mi):
        '''
        Merge the information in C{mi} into self. In case of conflicts, the information
        in C{mi} takes precedence, unless the information in mi is NULL.
        '''
        if mi.title and mi.title.lower() != 'unknown':
            self.title = mi.title
            
        if mi.authors and mi.authors[0].lower() != 'unknown':
            self.authors = mi.authors
            
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'application_id', 'manifest', 'spine', 'toc', 'cover'):
            if hasattr(mi, attr):
                val = getattr(mi, attr)
                if val is not None:
                    setattr(self, attr, val)
                    
        self.tags += mi.tags
        self.tags = list(set(self.tags))
        
        if getattr(mi, 'cover_data', None) and mi.cover_data[0] is not None:
            self.cover_data = mi.cover_data
            
            
    def __str__(self):
        ans = u''
        ans += u'Title    : ' + unicode(self.title) + u'\n'
        ans += u'Author   : ' + (', '.join(self.authors) if self.authors is not None else u'None')
        ans += ((' (' + self.author_sort + ')') if self.author_sort else '') + u'\n'
        ans += u'Publisher: '+ unicode(self.publisher) + u'\n' 
        ans += u'Category : ' + unicode(self.category) + u'\n'
        ans += u'Comments : ' + unicode(self.comments) + u'\n'
        ans += u'ISBN     : '     + unicode(self.isbn) + u'\n'
        return ans.strip()
    
    def __nonzero__(self):
        return bool(self.title or self.author or self.comments or self.category)
