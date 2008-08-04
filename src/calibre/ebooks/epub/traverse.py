from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Recursively parse HTML files to find all linked files.
'''

import sys, os, re
from urlparse import urlparse
from urllib import unquote
from calibre import unicode_path
from calibre.ebooks.chardet import xml_to_unicode

class Link(object):
    '''
    Represents a link in a HTML file.
    '''
    
    @classmethod
    def url_to_local_path(cls, url, base):
        path = url.path
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(base, url))
    
    def __init__(self, url, base):
        '''
        :param url:  The url this link points to. Must be an unquoted unicode string.
        :param base: The base directory that relative URLs are with respect to.
                     Must be a unicode string.
        '''
        assert isinstance(url, unicode) and isinstance(base, unicode)
        self.url        = url
        self.parsed_url = urlparse(unquote(self.url))
        self.is_local   = self.parsed_url.scheme in ('', 'file')
        self.path = None
        self.fragment = self.parsed_url.fragment 
        if self.is_local:
            self.path = self.url_to_local_path(self.parsed_url, base)

    def __hash__(self):
        if self.path is None:
            return hash(self.url)
        return hash(self.path)

    def __eq__(self, other):
        if not (hasattr(other, 'url') and hasattr(other, 'path')):
            return False
        if self.path is None:
            return self.url == other.url
        return self.path == other.path 
        

class IgnoreFile(Exception):
    pass

class HTMLFile(object):
    '''
    Contains basic traversal information about an HTML file. This
    includes a recursive list of links to other files as well as
    the encoding of each file.

    You can iterate over the tree of files rooted at this file
    by calling either :method:`breadth_first` or :method:`depth_first`.

    The encoding of the file is available as :member:`encoding`.

    If the file is a binary file (i.e. if conversion to unicode fails)
    :member:`is_binary` is set to `True`.
    '''

    LINK_PAT = re.compile(
    r'<\s*a\s+.*?href\s*=\s*(?:(?:"(?P<url1>[^"]+)")|(?:\'(?P<url2>[^\']+)\')|(?P<url3>[^\s]+))',
    re.DOTALL|re.IGNORECASE)
    
    def __init__(self, path_to_html_file, level, max_levels=sys.maxint,
                 encoding=None, verbose=0):
        '''
        :param level: The level of this file. Should be 0 for the root file.
        :param max_levels: `level >= max_levels` the links in this file
                            will not be followed. 
        :param encoding: Use `encoding` to decode HTML.
        '''
        self.path  = unicode_path(path_to_html_file, abs=True)
        self.base  = os.path.dirname(self.path)
        self.level = level
        self.links = []
        self.map   = {}
        self.is_binary  = False
        try:
            with open(self.path, 'rb') as f:
                src = f.read()
        except IOError, err:
            msg = 'Could not read from file: %s with error: %s'%
                            (self.path, unicode(err))
            if level == 0:
                raise IOError(msg)
            if verbose:
                print msg
            raise IgnoreFile
        if encoding is None:
            encoding = xml_to_unicode(src[:4096], verbose=verbose)[-1]
        self.encoding = encoding

        
        try:
            src = src.decode(encoding, 'replace')
        except UnicodeDecodeError:
            self.is_binary = True
            if verbose > 1:
                print self.path, 'is a binary file.'
        else:
            self.find_links(src)
        
        if self.level < max_levels:
            rejects = []
            for link in self.links:
                if link.path is not None:
                    try:
                        self.map[link.url] = HTMLFile(link.path, level+1,
                            max_levels, encoding=encoding, verbose=verbose)
                    except IgnoreFile:
                        rejects.append(link)
            for link in rejects:
                self.links.remove(link)
                    
        
    def find_links(self, src):
        for match in self.LINK_PAT.finditer():
            url = None
            for i in ('url1', 'url2', 'url3'):
                url = match.group(i)
                if url:
                    break
            link = Link(url, self.base)
            if link not in self.links:
                self.links.append(link)

    def breadth_first(self, root=True):
        '''
        Walk over the tree of linked files (by `<a href>` links) breadth
        first.

        :param root: If `True` return `self` as the first file.
        :return: A breadth-first iterator.
        '''
        if root:
            yield self
        for link in self.links:
            if link.path is not None:
                yield self.map[link.url]

        for link in self.links:
            if link.path is not None:
                for hf in self.map[link.url].breadth_first(root=False):
                    yield hf

    def depth_first(self, root=True):
        '''
        Walk over the tree of linked files (by `<a href>` links) depth
        first.

        :param root: If `True` return `self` as the first file.
        :return: A depth-first iterator.
        '''
        if root:
            yield self
        for link in self.links:
            if link.path is not None:
                yield self.map[link.url]
                for hf in self.map[link.url].depth_first(root=False):
                    yield hf
    
if __name__ == '__main__':
    root = HTMLFile(sys.argv[1], 0, verbose=2)
    print 'Depth first...'
    for f in root.depth_first():
        print f.path
    print '\n\nBreadth first...'
    for f in root.breadth_first():
        print f.path
    
