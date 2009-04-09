#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''
Input plugin for HTML or OPF ebooks.
'''

import os, re, sys, cStringIO
from urlparse import urlparse, urlunparse
from urllib import unquote

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks.metadata.opf2 import OPF, OPFCreator
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.chardet import xml_to_unicode
from calibre.customize.conversion import OptionRecommendation
from calibre import unicode_path

class Link(object):
    '''
    Represents a link in a HTML file.
    '''

    @classmethod
    def url_to_local_path(cls, url, base):
        path = urlunparse(('', '', url.path, url.params, url.query, ''))
        path = unquote(path)
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(base, path))

    def __init__(self, url, base):
        '''
        :param url:  The url this link points to. Must be an unquoted unicode string.
        :param base: The base directory that relative URLs are with respect to.
                     Must be a unicode string.
        '''
        assert isinstance(url, unicode) and isinstance(base, unicode)
        self.url         = url
        self.parsed_url  = urlparse(self.url)
        self.is_local    = self.parsed_url.scheme in ('', 'file')
        self.is_internal = self.is_local and not bool(self.parsed_url.path)
        self.path        = None
        self.fragment    = unquote(self.parsed_url.fragment)
        if self.is_local and not self.is_internal:
            self.path = self.url_to_local_path(self.parsed_url, base)

    def __hash__(self):
        if self.path is None:
            return hash(self.url)
        return hash(self.path)

    def __eq__(self, other):
        return self.path == getattr(other, 'path', other)

    def __str__(self):
        return u'Link: %s --> %s'%(self.url, self.path)


class IgnoreFile(Exception):

    def __init__(self, msg, errno):
        Exception.__init__(self, msg)
        self.doesnt_exist = errno == 2
        self.errno = errno

class HTMLFile(object):
    '''
    Contains basic information about an HTML file. This
    includes a list of links to other files as well as
    the encoding of each file. Also tries to detect if the file is not a HTML
    file in which case :member:`is_binary` is set to True.

    The encoding of the file is available as :member:`encoding`.
    '''

    HTML_PAT  = re.compile(r'<\s*html', re.IGNORECASE)
    TITLE_PAT = re.compile('<title>([^<>]+)</title>', re.IGNORECASE)
    LINK_PAT  = re.compile(
    r'<\s*a\s+.*?href\s*=\s*(?:(?:"(?P<url1>[^"]+)")|(?:\'(?P<url2>[^\']+)\')|(?P<url3>[^\s>]+))',
    re.DOTALL|re.IGNORECASE)

    def __init__(self, path_to_html_file, level, encoding, verbose, referrer=None):
        '''
        :param level: The level of this file. Should be 0 for the root file.
        :param encoding: Use `encoding` to decode HTML.
        :param referrer: The :class:`HTMLFile` that first refers to this file.
        '''
        self.path     = unicode_path(path_to_html_file, abs=True)
        self.title    = os.path.splitext(os.path.basename(self.path))[0]
        self.base     = os.path.dirname(self.path)
        self.level    = level
        self.referrer = referrer
        self.links    = []

        try:
            with open(self.path, 'rb') as f:
                src = f.read()
        except IOError, err:
            msg = 'Could not read from file: %s with error: %s'%(self.path, unicode(err))
            if level == 0:
                raise IOError(msg)
            raise IgnoreFile(msg, err.errno)

        self.is_binary = not bool(self.HTML_PAT.search(src[:1024]))
        if not self.is_binary:
            if encoding is None:
                encoding = xml_to_unicode(src[:4096], verbose=verbose)[-1]
                self.encoding = encoding
            else:
                self.encoding = encoding

            src = src.decode(encoding, 'replace')
            match = self.TITLE_PAT.search(src)
            self.title = match.group(1) if match is not None else self.title
            self.find_links(src)



    def __eq__(self, other):
        return self.path == getattr(other, 'path', other)

    def __str__(self):
        return u'HTMLFile:%d:%s:%s'%(self.level, 'b' if self.is_binary else 'a', self.path)

    def __repr__(self):
        return str(self)


    def find_links(self, src):
        for match in self.LINK_PAT.finditer(src):
            url = None
            for i in ('url1', 'url2', 'url3'):
                url = match.group(i)
                if url:
                    break
            link = self.resolve(url)
            if link not in self.links:
                self.links.append(link)

    def resolve(self, url):
        return Link(url, self.base)


def depth_first(root, flat, visited=set([])):
    yield root
    visited.add(root)
    for link in root.links:
        if link.path is not None and link not in visited:
            try:
                index = flat.index(link)
            except ValueError: # Can happen if max_levels is used
                continue
            hf = flat[index]
            if hf not in visited:
                yield hf
                visited.add(hf)
                for hf in depth_first(hf, flat, visited):
                    if hf not in visited:
                        yield hf
                        visited.add(hf)


def traverse(path_to_html_file, max_levels=sys.maxint, verbose=0, encoding=None):
    '''
    Recursively traverse all links in the HTML file.

    :param max_levels: Maximum levels of recursion. Must be non-negative. 0
                       implies that no links in the root HTML file are followed.
    :param encoding:   Specify character encoding of HTML files. If `None` it is
                       auto-detected.
    :return:           A pair of lists (breadth_first, depth_first). Each list contains
                       :class:`HTMLFile` objects.
    '''
    assert max_levels >= 0
    level = 0
    flat =  [HTMLFile(path_to_html_file, level, encoding, verbose)]
    next_level = list(flat)
    while level < max_levels and len(next_level) > 0:
        level += 1
        nl = []
        for hf in next_level:
            rejects = []
            for link in hf.links:
                if link.path is None or link.path in flat:
                    continue
                try:
                    nf = HTMLFile(link.path, level, encoding, verbose, referrer=hf)
                    if nf.is_binary:
                        raise IgnoreFile('%s is a binary file'%nf.path, -1)
                    nl.append(nf)
                    flat.append(nf)
                except IgnoreFile, err:
                    rejects.append(link)
                    if not err.doesnt_exist or verbose > 1:
                        print repr(err)
            for link in rejects:
                hf.links.remove(link)

        next_level = list(nl)
    orec = sys.getrecursionlimit()
    sys.setrecursionlimit(500000)
    try:
        return flat, list(depth_first(flat[0], flat))
    finally:
        sys.setrecursionlimit(orec)


def opf_traverse(opf_reader, verbose=0, encoding=None):
    '''
    Return a list of :class:`HTMLFile` objects in the order specified by the
    `<spine>` element of the OPF.

    :param opf_reader: An :class:`calibre.ebooks.metadata.opf2.OPF` instance.
    :param encoding:   Specify character encoding of HTML files. If `None` it is
                       auto-detected.
    '''
    if not opf_reader.spine:
        raise ValueError('OPF does not have a spine')
    flat = []
    for path in opf_reader.spine.items():
        path = os.path.abspath(path)
        if path not in flat:
            flat.append(os.path.abspath(path))
    for item in opf_reader.manifest:
        if 'html' in item.mime_type:
            path = os.path.abspath(item.path)
            if path not in flat:
                flat.append(path)
    for i, path in enumerate(flat):
        if not os.path.exists(path):
            path = path.replace('&', '%26')
            if os.path.exists(path):
                flat[i] = path
                for item in opf_reader.itermanifest():
                    item.set('href', item.get('href').replace('&', '%26'))
    ans = []
    for path in flat:
        if os.path.exists(path):
            ans.append(HTMLFile(path, 0, encoding, verbose))
        else:
            print 'WARNING: OPF spine item %s does not exist'%path
    ans = [f for f in ans if not f.is_binary]
    return ans

def search_for_opf(dir):
    for f in os.listdir(dir):
        if f.lower().endswith('.opf'):
            return OPF(open(os.path.join(dir, f), 'rb'), dir)

def get_filelist(htmlfile, dir, opts, log):
    '''
    Build list of files referenced by html file or try to detect and use an
    OPF file instead.
    '''
    print 'Building file list...'
    opf = search_for_opf(dir)
    filelist = None
    if opf is not None:
        try:
            filelist = opf_traverse(opf, verbose=opts.verbose,
                    encoding=opts.input_encoding)
        except:
            pass
    if not filelist:
        filelist = traverse(htmlfile, max_levels=int(opts.max_levels),
                            verbose=opts.verbose,
                            encoding=opts.input_encoding)\
                    [0 if opts.breadth_first else 1]
    if opts.verbose:
        log.debug('\tFound files...')
        for f in filelist:
            log.debug('\t\t', f)
    return opf, filelist


class HTMLInput(InputFormatPlugin):

    name        = 'HTML Input'
    author      = 'Kovid Goyal'
    description = 'Convert HTML and OPF files to an OEB'
    file_types  = set(['opf', 'html', 'htm', 'xhtml', 'xhtm'])

    options = set([
        OptionRecommendation(name='breadth_first',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Traverse links in HTML files breadth first. Normally, '
                    'they are traversed depth first.'
                   )
        ),

        OptionRecommendation(name='max_levels',
            recommended_value=5, level=OptionRecommendation.LOW,
            help=_('Maximum levels of recursion when following links in '
                   'HTML files. Must be non-negative. 0 implies that no '
                   'links in the root HTML file are followed. Default is '
                   '%default.'
                   )
        ),

    ])

    def convert(self, stream, opts, file_ext, log,
                accelerators):
        basedir = os.getcwd()
        if hasattr(stream, 'name'):
            basedir = os.path.dirname(stream.name)
        if file_ext == 'opf':
            opf = OPF(stream, basedir)
            filelist = opf_traverse(opf, verbose=opts.verbose,
                    encoding=opts.input_encoding)
            mi = MetaInformation(opf)
        else:
            opf, filelist = get_filelist(stream.name, basedir, opts, log)
            mi = MetaInformation(opf)
            mi.smart_update(get_metadata(stream, 'html'))

        mi = OPFCreator(os.getcwdu(), mi)
        mi.guide = None
        entries = [(f.path, 'application/xhtml+xml') for f in filelist]
        mi.create_manifest(entries)
        mi.create_spine([f.path for f in filelist])

        tocbuf = cStringIO.StringIO()
        mi.render(open('metadata.opf', 'wb'), tocbuf, 'toc.ncx')
        toc = tocbuf.getvalue()
        if toc:
            open('toc.ncx', 'wb').write(toc)

        from calibre.ebooks.conversion.plumber import create_oebbook
        return create_oebbook(log, os.path.abspath('metadata.opf'))




