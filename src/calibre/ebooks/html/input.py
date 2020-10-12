#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''
Input plugin for HTML or OPF ebooks.
'''

import os, re, sys,  errno as gerrno

from calibre.ebooks.oeb.base import urlunquote
from calibre.ebooks.chardet import detect_xml_encoding
from calibre.constants import iswindows
from calibre import unicode_path, as_unicode, replace_entities
from polyglot.builtins import unicode_type
from polyglot.urllib import urlparse, urlunparse


class Link(object):

    '''
    Represents a link in a HTML file.
    '''

    @classmethod
    def url_to_local_path(cls, url, base):
        path = url.path
        isabs = False
        if iswindows and path.startswith('/'):
            path = path[1:]
            isabs = True
        path = urlunparse(('', '', path, url.params, url.query, ''))
        path = urlunquote(path)
        if isabs or os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(base, path))

    def __init__(self, url, base):
        '''
        :param url:  The url this link points to. Must be an unquoted unicode string.
        :param base: The base directory that relative URLs are with respect to.
                     Must be a unicode string.
        '''
        assert isinstance(url, unicode_type) and isinstance(base, unicode_type)
        self.url         = url
        self.parsed_url  = urlparse(self.url)
        self.is_local    = self.parsed_url.scheme in ('', 'file')
        self.is_internal = self.is_local and not bool(self.parsed_url.path)
        self.path        = None
        self.fragment    = urlunquote(self.parsed_url.fragment)
        if self.is_local and not self.is_internal:
            self.path = self.url_to_local_path(self.parsed_url, base)

    def __hash__(self):
        if self.path is None:
            return hash(self.url)
        return hash(self.path)

    def __eq__(self, other):
        return self.path == getattr(other, 'path', other)

    def __str__(self):
        return 'Link: %s --> %s'%(self.url, self.path)


class IgnoreFile(Exception):

    def __init__(self, msg, errno):
        Exception.__init__(self, msg)
        self.doesnt_exist = errno == gerrno.ENOENT
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
    HTML_PAT_BIN  = re.compile(br'<\s*html', re.IGNORECASE)
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
                src = header = f.read(4096)
                encoding = detect_xml_encoding(src)[1]
                if encoding:
                    try:
                        header = header.decode(encoding, errors='replace')
                    except ValueError:
                        pass
                self.is_binary = False
                if level > 0:
                    pat = self.HTML_PAT_BIN if isinstance(header, bytes) else self.HTML_PAT
                    self.is_binary = not bool(pat.search(header))
                if not self.is_binary:
                    src += f.read()
        except IOError as err:
            msg = 'Could not read from file: %s with error: %s'%(self.path, as_unicode(err))
            if level == 0:
                raise IOError(msg)
            raise IgnoreFile(msg, err.errno)

        if not src:
            if level == 0:
                raise ValueError('The file %s is empty'%self.path)
            self.is_binary = True

        if not self.is_binary:
            if not encoding:
                encoding = detect_xml_encoding(src[:4096], verbose=verbose)[1]
                self.encoding = encoding
            else:
                self.encoding = encoding

            src = src.decode(encoding, 'replace')
            match = self.TITLE_PAT.search(src)
            self.title = match.group(1) if match is not None else self.title
            self.find_links(src)

    def __eq__(self, other):
        return self.path == getattr(other, 'path', other)

    def __hash__(self):
        return hash(self.path)

    def __str__(self):
        return 'HTMLFile:%d:%s:%s'%(self.level, 'b' if self.is_binary else 'a', self.path)

    def __repr__(self):
        return unicode_type(self)

    def find_links(self, src):
        for match in self.LINK_PAT.finditer(src):
            url = None
            for i in ('url1', 'url2', 'url3'):
                url = match.group(i)
                if url:
                    break
            url = replace_entities(url)
            try:
                link = self.resolve(url)
            except ValueError:
                # Unparseable URL, ignore
                continue
            if link not in self.links:
                self.links.append(link)

    def resolve(self, url):
        return Link(url, self.base)


def depth_first(root, flat, visited=None):
    yield root
    if visited is None:
        visited = set()
    visited.add(root)
    for link in root.links:
        if link.path is not None and link not in visited:
            try:
                index = flat.index(link)
            except ValueError:  # Can happen if max_levels is used
                continue
            hf = flat[index]
            if hf not in visited:
                yield hf
                visited.add(hf)
                for hf in depth_first(hf, flat, visited):
                    if hf not in visited:
                        yield hf
                        visited.add(hf)


def traverse(path_to_html_file, max_levels=sys.maxsize, verbose=0, encoding=None):
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
                except IgnoreFile as err:
                    rejects.append(link)
                    if not err.doesnt_exist or verbose > 1:
                        print(repr(err))
            for link in rejects:
                hf.links.remove(link)

        next_level = list(nl)
    orec = sys.getrecursionlimit()
    sys.setrecursionlimit(500000)
    try:
        return flat, list(depth_first(flat[0], flat))
    finally:
        sys.setrecursionlimit(orec)


def get_filelist(htmlfile, dir, opts, log):
    '''
    Build list of files referenced by html file or try to detect and use an
    OPF file instead.
    '''
    log.info('Building file list...')
    filelist = traverse(htmlfile, max_levels=int(opts.max_levels),
                        verbose=opts.verbose,
                        encoding=opts.input_encoding)[0 if opts.breadth_first else 1]
    if opts.verbose:
        log.debug('\tFound files...')
        for f in filelist:
            log.debug('\t\t', f)
    return filelist
