#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

"""
Provides abstraction for metadata reading.writing from a variety of ebook formats. 
"""
import os, mimetypes, sys
from urllib import unquote, quote
from urlparse import urlparse


from calibre.constants import __version__ as VERSION
from calibre import relpath
from calibre.utils.config import OptionParser

def string_to_authors(raw):
    raw = raw.replace('&&', u'\uffff')
    authors = [a.strip().replace(u'\uffff', '&') for a in raw.split('&')]
    return authors

def authors_to_string(authors):
    return ' & '.join([a.replace('&', '&&') for a in authors])

def author_to_author_sort(author):
    tokens = author.split()
    tokens = tokens[-1:] + tokens[:-1]
    if len(tokens) > 1:
        tokens[0] += ','
    return ' '.join(tokens)

def authors_to_sort_string(authors):
    return ' & '.join(map(author_to_author_sort, authors))

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

class Resource(object):
    '''
    Represents a resource (usually a file on the filesystem or a URL pointing 
    to the web. Such resources are commonly referred to in OPF files.
    
    They have the interface:
    
    :member:`path`
    :member:`mime_type`
    :method:`href`
    
    '''
    
    def __init__(self, href_or_path, basedir=os.getcwd(), is_path=True):
        self._href = None
        self._basedir = basedir
        self.path = None
        self.fragment = ''
        try:
            self.mime_type = mimetypes.guess_type(href_or_path)[0]
        except:
            self.mime_type = None
        if self.mime_type is None:
            self.mime_type = 'application/octet-stream'
        if is_path:
            path = href_or_path
            if not os.path.isabs(path):
                path = os.path.abspath(os.path.join(basedir, path))
            if isinstance(path, str):
                path = path.decode(sys.getfilesystemencoding())
            self.path = path
        else:
            url = urlparse(href_or_path)
            if url[0] not in ('', 'file'):
                self._href = href_or_path
            else:
                pc = url[2]
                if isinstance(pc, unicode):
                    pc = pc.encode('utf-8')
                pc = unquote(pc).decode('utf-8')
                self.path = os.path.abspath(os.path.join(basedir, pc.replace('/', os.sep)))
                self.fragment = unquote(url[-1])
        
    
    def href(self, basedir=None):
        '''
        Return a URL pointing to this resource. If it is a file on the filesystem
        the URL is relative to `basedir`.
        
        `basedir`: If None, the basedir of this resource is used (see :method:`set_basedir`).
        If this resource has no basedir, then the current working directory is used as the basedir.
        '''
        if basedir is None:
            if self._basedir:
                basedir = self._basedir
            else:
                basedir = os.getcwd()
        if self.path is None:
            return self._href
        f = self.fragment.encode('utf-8') if isinstance(self.fragment, unicode) else self.fragment
        frag = '#'+quote(f) if self.fragment else ''
        if self.path == basedir:
            return ''+frag
        try:
            rpath = relpath(self.path, basedir)
        except OSError: # On windows path and basedir could be on different drives
            rpath = self.path
        if isinstance(rpath, unicode):
            rpath = rpath.encode('utf-8')
        return quote(rpath.replace(os.sep, '/'))+frag
    
    def set_basedir(self, path):
        self._basedir = path
        
    def basedir(self):
        return self._basedir
    
    def __repr__(self):
        return 'Resource(%s, %s)'%(repr(self.path), repr(self.href()))
        
        
class ResourceCollection(object):
    
    def __init__(self):
        self._resources = []
        
    def __iter__(self):
        for r in self._resources:
            yield r
            
    def __len__(self):
        return len(self._resources)
    
    def __getitem__(self, index):
        return self._resources[index]
    
    def __bool__(self):
        return len(self._resources) > 0
    
    def __str__(self):
        resources = map(repr, self)
        return '[%s]'%', '.join(resources)
    
    def __repr__(self):
        return str(self)
    
    def append(self, resource):
        if not isinstance(resource, Resource):
            raise ValueError('Can only append objects of type Resource')
        self._resources.append(resource)
        
    def remove(self, resource):
        self._resources.remove(resource)
    
    def replace(self, start, end, items):
        'Same as list[start:end] = items'
        self._resources[start:end] = items
        
    @staticmethod
    def from_directory_contents(top, topdown=True):
        collection = ResourceCollection()
        for spec in os.walk(top, topdown=topdown):
            path = os.path.abspath(os.path.join(spec[0], spec[1]))
            res = Resource.from_path(path)
            res.set_basedir(top)
            collection.append(res)
        return collection
    
    def set_basedir(self, path):
        for res in self:
            res.set_basedir(path)
        


class MetaInformation(object):
    '''Convenient encapsulation of book metadata'''
    
    @staticmethod
    def copy(mi):
        ans = MetaInformation(mi.title, mi.authors)
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'tags', 'cover_data', 'application_id', 'guide',
                     'manifest', 'spine', 'toc', 'cover', 'language', 'book_producer'):
            if hasattr(mi, attr):
                setattr(ans, attr, getattr(mi, attr))
        
    def __init__(self, title, authors=[_('Unknown')]):
        '''
        @param title: title or "Unknown" or a MetaInformation object
        @param authors: List of strings or []
        '''
        mi = None
        if hasattr(title, 'title') and hasattr(title, 'authors'):
            mi = title
            title = mi.title
            authors = mi.authors
        self.title = title
        self.author = authors # Needed for backward compatibility
        #: List of strings or []
        self.authors = authors
        self.tags = getattr(mi, 'tags', [])
        #: mi.cover_data = (ext, data)
        self.cover_data   = getattr(mi, 'cover_data', (None, None))
        
        for x in ('author_sort', 'title_sort', 'comments', 'category', 'publisher', 
                  'series', 'series_index', 'rating', 'isbn', 'language',
                  'application_id', 'manifest', 'toc', 'spine', 'guide', 'cover',
                  'book_producer',
                  ):
            setattr(self, x, getattr(mi, x, None))
    
    def smart_update(self, mi):
        '''
        Merge the information in C{mi} into self. In case of conflicts, the information
        in C{mi} takes precedence, unless the information in mi is NULL.
        '''
        if mi.title and mi.title != _('Unknown'):
            self.title = mi.title
            
        if mi.authors and mi.authors[0] != _('Unknown'):
            self.authors = mi.authors
            
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'application_id', 'manifest', 'spine', 'toc', 
                     'cover', 'language', 'guide', 'book_producer'):
            if hasattr(mi, attr):
                val = getattr(mi, attr)
                if val is not None:
                    setattr(self, attr, val)
                    
        self.tags += mi.tags
        self.tags = list(set(self.tags))
        
        if getattr(mi, 'cover_data', None) and mi.cover_data[0] is not None:
            self.cover_data = mi.cover_data
            
            
    def __unicode__(self):
        ans = u''
        ans += u'Title    : ' + unicode(self.title) + u'\n'
        if self.authors:
            ans += u'Author   : ' + (', '.join(self.authors) if self.authors is not None else u'None')
            ans += ((' (' + self.author_sort + ')') if self.author_sort else '') + u'\n'
        if self.publisher:
            ans += u'Publisher: '+ unicode(self.publisher) + u'\n'
        if self.book_producer:
            ans += u'Producer : '+ unicode(self.book_producer) + u'\n'
        if self.category: 
            ans += u'Category : ' + unicode(self.category) + u'\n'
        if self.comments:
            ans += u'Comments : ' + unicode(self.comments) + u'\n'
        if self.isbn:
            ans += u'ISBN     : '     + unicode(self.isbn) + u'\n'
        if self.tags:
            ans += u'Tags     : ' + u', '.join([unicode(t) for t in self.tags]) + '\n'
        if self.series:
            ans += u'Series   : '+unicode(self.series) + ' #%d\n'%self.series_index  
        if self.language:
            ans += u'Language : '     + unicode(self.language) + u'\n'
        return ans.strip()
    
    def to_html(self):
        ans = [(_('Title'), unicode(self.title))]
        ans += [(_('Author(s)'), (authors_to_string(self.authors) if self.authors else _('Unknown')))]
        ans += [(_('Publisher'), unicode(self.publisher))]
        ans += [(_('Producer'), unicode(self.book_producer))]
        ans += [(_('Category'), unicode(self.category))]
        ans += [(_('Comments'), unicode(self.comments))]
        ans += [('ISBN', unicode(self.isbn))]
        ans += [(_('Tags'), u', '.join([unicode(t) for t in self.tags]))]
        ans += [(_('Series'), unicode(self.series))]
        ans += [(_('Language'), unicode(self.language))]
        for i, x in enumerate(ans):
            ans[i] = u'<tr><td><b>%s</b></td><td>%s</td></tr>'%x
        return u'<table>%s</table>'%u'\n'.join(ans)
        
        
    
    def __str__(self):
        return self.__unicode__().encode('utf-8')
    
    def __nonzero__(self):
        return bool(self.title or self.author or self.comments or self.category)
