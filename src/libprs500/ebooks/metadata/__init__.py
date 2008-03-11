##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
Provides metadata editing support for PDF and RTF files. For LRF metadata, use 
the L{lrf.meta} module.
"""
__docformat__ = "epytext"
__author__       = "Kovid Goyal <kovid@kovidgoyal.net>"


from libprs500 import __version__ as VERSION
from libprs500 import OptionParser

def get_parser(extension):
    ''' Return an option parser with the basic metadata options already setup'''
    parser = OptionParser(usage='%prog [options] myfile.'+extension+'\n\nRead and write metadata from an ebook file.')
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help="Set the book title", default=None)
    parser.add_option("-a", "--authors", action="store", type="string", \
                    dest="authors", help="Set the authors", default=None)
    parser.add_option("-c", "--category", action="store", type="string", \
                    dest="category", help="The category this book belongs"+\
                    " to. E.g.: History", default=None)
    parser.add_option('--comment', dest='comment', default=None, action='store',
                      help='Set the comment')
    return parser

class MetaInformation(object):
    '''Convenient encapsulation of book metadata'''
    
    @staticmethod
    def copy(mi):
        ans = MetaInformation(mi.title, mi.authors)
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'tags', 'cover_data', 'libprs_id'):
            if hasattr(mi, attr):
                setattr(ans, attr, getattr(mi, attr))
        
    
    def __init__(self, title, authors):
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
        self.cover_data   = mi.cover_data if (mi and hasattr(mi, 'cover_data')) else (None, None)
        self.libprs_id    = mi.libprs_id  if (mi and hasattr(mi, 'libprs_id')) else None
         
    
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
                     'isbn', 'libprs_id'):
            if hasattr(mi, attr):
                val = getattr(mi, attr)
                if val is not None:
                    setattr(self, attr, val)
                    
        self.tags += mi.tags
        self.tags = list(set(self.tags))
        
        if hasattr(mi, 'cover_data') and mi.cover_data[0] is not None:
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