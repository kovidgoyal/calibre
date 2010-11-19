#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


'''
Input plugin for HTML or OPF ebooks.
'''

import os, re, sys, uuid, tempfile
from urlparse import urlparse, urlunparse
from urllib import unquote
from functools import partial
from itertools import izip

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.chardet import xml_to_unicode
from calibre.customize.conversion import OptionRecommendation
from calibre.constants import islinux, isfreebsd, iswindows
from calibre import unicode_path
from calibre.utils.localization import get_lang
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.conversion.utils import PreProcessor

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
        path = unquote(path)
        if isabs or os.path.isabs(path):
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

        self.is_binary = level > 0 and not bool(self.HTML_PAT.search(src[:4096]))
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


def get_filelist(htmlfile, dir, opts, log):
    '''
    Build list of files referenced by html file or try to detect and use an
    OPF file instead.
    '''
    log.info('Building file list...')
    filelist = traverse(htmlfile, max_levels=int(opts.max_levels),
                        verbose=opts.verbose,
                        encoding=opts.input_encoding)\
                [0 if opts.breadth_first else 1]
    if opts.verbose:
        log.debug('\tFound files...')
        for f in filelist:
            log.debug('\t\t', f)
    return filelist


class HTMLInput(InputFormatPlugin):

    name        = 'HTML Input'
    author      = 'Kovid Goyal'
    description = 'Convert HTML and OPF files to an OEB'
    file_types  = set(['opf', 'html', 'htm', 'xhtml', 'xhtm', 'shtm', 'shtml'])

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

        OptionRecommendation(name='dont_package',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Normally this input plugin re-arranges all the input '
                'files into a standard folder hierarchy. Only use this option '
                'if you know what you are doing as it can result in various '
                'nasty side effects in the rest of of the conversion pipeline.'
                )
        ),

    ])

    def convert(self, stream, opts, file_ext, log,
                accelerators):
        self._is_case_sensitive = None
        basedir = os.getcwd()
        self.opts = opts

        fname = None
        if hasattr(stream, 'name'):
            basedir = os.path.dirname(stream.name)
            fname = os.path.basename(stream.name)

        if file_ext != 'opf':
            if opts.dont_package:
                raise ValueError('The --dont-package option is not supported for an HTML input file')
            from calibre.ebooks.metadata.html import get_metadata
            mi = get_metadata(stream)
            if fname:
                from calibre.ebooks.metadata.meta import metadata_from_filename
                fmi = metadata_from_filename(fname)
                fmi.smart_update(mi)
                mi = fmi
            oeb = self.create_oebbook(stream.name, basedir, opts, log, mi)
            return oeb

        from calibre.ebooks.conversion.plumber import create_oebbook
        return create_oebbook(log, stream.name, opts, self,
                encoding=opts.input_encoding)

    def is_case_sensitive(self, path):
        if getattr(self, '_is_case_sensitive', None) is not None:
            return self._is_case_sensitive
        if not path or not os.path.exists(path):
            return islinux or isfreebsd
        self._is_case_sensitive = not (os.path.exists(path.lower()) \
                and os.path.exists(path.upper()))
        return self._is_case_sensitive

    def create_oebbook(self, htmlpath, basedir, opts, log, mi):
        from calibre.ebooks.conversion.plumber import create_oebbook
        from calibre.ebooks.oeb.base import DirContainer, \
            rewrite_links, urlnormalize, urldefrag, BINARY_MIME, OEB_STYLES, \
            xpath
        from calibre import guess_type
        import cssutils
        self.OEB_STYLES = OEB_STYLES
        oeb = create_oebbook(log, None, opts, self,
                encoding=opts.input_encoding, populate=False)
        self.oeb = oeb

        metadata = oeb.metadata
        if mi.title:
            metadata.add('title', mi.title)
        if mi.authors:
            for a in mi.authors:
                metadata.add('creator', a, attrib={'role':'aut'})
        if mi.publisher:
            metadata.add('publisher', mi.publisher)
        if mi.isbn:
            metadata.add('identifier', mi.isbn, attrib={'scheme':'ISBN'})
        if not metadata.language:
            oeb.logger.warn(u'Language not specified')
            metadata.add('language', get_lang().replace('_', '-'))
        if not metadata.creator:
            oeb.logger.warn('Creator not specified')
            metadata.add('creator', self.oeb.translate(__('Unknown')))
        if not metadata.title:
            oeb.logger.warn('Title not specified')
            metadata.add('title', self.oeb.translate(__('Unknown')))
        bookid = str(uuid.uuid4())
        metadata.add('identifier', bookid, id='uuid_id', scheme='uuid')
        for ident in metadata.identifier:
            if 'id' in ident.attrib:
                self.oeb.uid = metadata.identifier[0]
                break

        filelist = get_filelist(htmlpath, basedir, opts, log)
        filelist = [f for f in filelist if not f.is_binary]
        htmlfile_map = {}
        for f in filelist:
            path = f.path
            oeb.container = DirContainer(os.path.dirname(path), log)
            bname = os.path.basename(path)
            id, href = oeb.manifest.generate(id='html',
                    href=ascii_filename(bname))
            htmlfile_map[path] = href
            item = oeb.manifest.add(id, href, 'text/html')
            item.html_input_href = bname
            oeb.spine.add(item, True)

        self.added_resources = {}
        self.log = log
        self.log('Normalizing filename cases')
        for path, href in htmlfile_map.items():
            if not self.is_case_sensitive(path):
                path = path.lower()
            self.added_resources[path] = href
        self.urlnormalize, self.DirContainer = urlnormalize, DirContainer
        self.urldefrag = urldefrag
        self.guess_type, self.BINARY_MIME = guess_type, BINARY_MIME

        self.log('Rewriting HTML links')
        for f in filelist:
            path = f.path
            dpath = os.path.dirname(path)
            oeb.container = DirContainer(dpath, log)
            item = oeb.manifest.hrefs[htmlfile_map[path]]
            rewrite_links(item.data, partial(self.resource_adder, base=dpath))

        for item in oeb.manifest.values():
            if item.media_type in self.OEB_STYLES:
                dpath = None
                for path, href in self.added_resources.items():
                    if href == item.href:
                        dpath = os.path.dirname(path)
                        break
                cssutils.replaceUrls(item.data,
                        partial(self.resource_adder, base=dpath))

        toc = self.oeb.toc
        self.oeb.auto_generated_toc = True
        titles = []
        headers = []
        for item in self.oeb.spine:
            if not item.linear: continue
            html = item.data
            title = ''.join(xpath(html, '/h:html/h:head/h:title/text()'))
            title = re.sub(r'\s+', ' ', title.strip())
            if title:
                titles.append(title)
            headers.append('(unlabled)')
            for tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'strong'):
                expr = '/h:html/h:body//h:%s[position()=1]/text()'
                header = ''.join(xpath(html, expr % tag))
                header = re.sub(r'\s+', ' ', header.strip())
                if header:
                    headers[-1] = header
                    break
        use = titles
        if len(titles) > len(set(titles)):
            use = headers
        for title, item in izip(use, self.oeb.spine):
            if not item.linear: continue
            toc.add(title, item.href)

        oeb.container = DirContainer(os.getcwdu(), oeb.log)
        return oeb

    def link_to_local_path(self, link_, base=None):
        if not isinstance(link_, unicode):
            try:
                link_ = link_.decode('utf-8', 'error')
            except:
                self.log.warn('Failed to decode link %r. Ignoring'%link_)
                return None, None
        try:
            l = Link(link_, base if base else os.getcwdu())
        except:
            self.log.exception('Failed to process link: %r'%link_)
            return None, None
        if l.path is None:
            # Not a local resource
            return None, None
        link = l.path.replace('/', os.sep).strip()
        frag = l.fragment
        if not link:
            return None, None
        return link, frag

    def resource_adder(self, link_, base=None):
        link, frag = self.link_to_local_path(link_, base=base)
        if link is None:
            return link_
        try:
            if base and not os.path.isabs(link):
                link = os.path.join(base, link)
            link = os.path.abspath(link)
        except:
            return link_
        if not os.access(link, os.R_OK):
            return link_
        if os.path.isdir(link):
            self.log.warn(link_, 'is a link to a directory. Ignoring.')
            return link_
        if not self.is_case_sensitive(tempfile.gettempdir()):
            link = link.lower()
        if link not in self.added_resources:
            bhref = os.path.basename(link)
            id, href = self.oeb.manifest.generate(id='added',
                    href=bhref)
            self.oeb.log.debug('Added', link)
            self.oeb.container = self.DirContainer(os.path.dirname(link),
                    self.oeb.log)
            # Load into memory
            guessed = self.guess_type(href)[0]
            media_type = guessed or self.BINARY_MIME

            item = self.oeb.manifest.add(id, href, media_type)
            item.html_input_href = bhref
            if guessed in self.OEB_STYLES:
                item.override_css_fetch = partial(
                        self.css_import_handler, os.path.dirname(link))
            item.data
            self.added_resources[link] = href

        nlink = self.added_resources[link]
        if frag:
            nlink = '#'.join((nlink, frag))
        return nlink

    def css_import_handler(self, base, href):
        link, frag = self.link_to_local_path(href, base=base)
        if link is None or not os.access(link, os.R_OK) or os.path.isdir(link):
            return (None, None)
        try:
            raw = open(link, 'rb').read().decode('utf-8', 'replace')
            raw = self.oeb.css_preprocessor(raw, add_namespace=True)
        except:
            self.log.exception('Failed to read CSS file: %r'%link)
            return (None, None)
        return (None, raw)

    def preprocess_html(self, options, html):
        self.options = options
        preprocessor = PreProcessor(self.options, log=getattr(self, 'log', None))
        return preprocessor(html)

