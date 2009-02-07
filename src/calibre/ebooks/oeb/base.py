'''
Basic support for manipulating OEB 1.x/2.0 content and metadata.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os, sys, re, uuid
from mimetypes import types_map
from collections import defaultdict
from itertools import count
from urlparse import urldefrag, urlparse, urlunparse
from urllib import unquote as urlunquote
from lxml import etree, html
import calibre
from calibre import LoggingInterface
from calibre.translations.dynamic import translate
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.oeb.entitydefs import ENTITYDEFS

XML_NS       = 'http://www.w3.org/XML/1998/namespace'
XHTML_NS     = 'http://www.w3.org/1999/xhtml'
OEB_DOC_NS   = 'http://openebook.org/namespaces/oeb-document/1.0/'
OPF1_NS      = 'http://openebook.org/namespaces/oeb-package/1.0/'
OPF2_NS      = 'http://www.idpf.org/2007/opf'
OPF_NSES     = set([OPF1_NS, OPF2_NS])
DC09_NS      = 'http://purl.org/metadata/dublin_core'
DC10_NS      = 'http://purl.org/dc/elements/1.0/'
DC11_NS      = 'http://purl.org/dc/elements/1.1/'
DC_NSES      = set([DC09_NS, DC10_NS, DC11_NS])
XSI_NS       = 'http://www.w3.org/2001/XMLSchema-instance'
DCTERMS_NS   = 'http://purl.org/dc/terms/'
NCX_NS       = 'http://www.daisy.org/z3986/2005/ncx/'
SVG_NS       = 'http://www.w3.org/2000/svg'
XLINK_NS     = 'http://www.w3.org/1999/xlink'
CALIBRE_NS   = 'http://calibre.kovidgoyal.net/2009/metadata'
XPNSMAP      = {'h'  : XHTML_NS, 'o1' : OPF1_NS,    'o2' : OPF2_NS,
                'd09': DC09_NS,  'd10': DC10_NS,    'd11': DC11_NS,
                'xsi': XSI_NS,   'dt' : DCTERMS_NS, 'ncx': NCX_NS,
                'svg': SVG_NS,   'xl' : XLINK_NS}
OPF1_NSMAP   = {'dc': DC11_NS, 'oebpackage': OPF1_NS}
OPF2_NSMAP   = {'opf': OPF2_NS, 'dc': DC11_NS, 'dcterms': DCTERMS_NS,
                'xsi': XSI_NS, 'calibre': CALIBRE_NS}

def XML(name): 
    return '{%s}%s' % (XML_NS, name)

def XHTML(name): 
    return '{%s}%s' % (XHTML_NS, name)

def OPF(name): 
    return '{%s}%s' % (OPF2_NS, name)

def DC(name): 
    return '{%s}%s' % (DC11_NS, name)

def XSI(name): 
    return '{%s}%s' % (XSI_NS, name)

def DCTERMS(name): 
    return '{%s}%s' % (DCTERMS_NS, name)

def NCX(name): 
    return '{%s}%s' % (NCX_NS, name)

def SVG(name): 
    return '{%s}%s' % (SVG_NS, name)

def XLINK(name): 
    return '{%s}%s' % (XLINK_NS, name)

def CALIBRE(name): 
    return '{%s}%s' % (CALIBRE_NS, name)

def LINK_SELECTORS():
    results = []
    for expr in ('h:head/h:link/@href', 'h:body//h:a/@href',
                 'h:body//h:img/@src', 'h:body//h:object/@data',
                 'h:body//*/@xl:href', '//ncx:content/@src',
                 'o2:page/@href'):
        results.append(etree.XPath(expr, namespaces=XPNSMAP))
    return results

LINK_SELECTORS = LINK_SELECTORS()

EPUB_MIME      = types_map['.epub']
XHTML_MIME     = types_map['.xhtml']
CSS_MIME       = types_map['.css']
NCX_MIME       = types_map['.ncx']
OPF_MIME       = types_map['.opf']
PAGE_MAP_MIME  = 'application/oebps-page-map+xml'
OEB_DOC_MIME   = 'text/x-oeb1-document'
OEB_CSS_MIME   = 'text/x-oeb1-css'
OPENTYPE_MIME  = 'application/x-font-opentype'
GIF_MIME       = types_map['.gif']
JPEG_MIME      = types_map['.jpeg']
PNG_MIME       = types_map['.png']
SVG_MIME       = types_map['.svg']
BINARY_MIME    = 'application/octet-stream'

OEB_STYLES        = set([CSS_MIME, OEB_CSS_MIME, 'text/x-oeb-css'])
OEB_DOCS          = set([XHTML_MIME, 'text/html', OEB_DOC_MIME,
                         'text/x-oeb-document'])
OEB_RASTER_IMAGES = set([GIF_MIME, JPEG_MIME, PNG_MIME])
OEB_IMAGES        = set([GIF_MIME, JPEG_MIME, PNG_MIME, SVG_MIME])

MS_COVER_TYPE = 'other.ms-coverimage-standard'

ENTITY_RE     = re.compile(r'&([a-zA-Z_:][a-zA-Z0-9.-_:]+);')
COLLAPSE_RE   = re.compile(r'[ \t\r\n\v]+')
QNAME_RE      = re.compile(r'^[{][^{}]+[}][^{}]+$')
PREFIXNAME_RE = re.compile(r'^[^:]+[:][^:]+')
XMLDECL_RE    = re.compile(r'^\s*<[?]xml.*?[?]>')
CSSURL_RE     = re.compile(r'''url[(](?P<q>["']?)(?P<url>[^)]+)(?P=q)[)]''')

RECOVER_PARSER = etree.XMLParser(recover=True)


def element(parent, *args, **kwargs):
    if parent is not None:
        return etree.SubElement(parent, *args, **kwargs)
    return etree.Element(*args, **kwargs)

def namespace(name):
    if '}' in name:
        return name.split('}', 1)[0][1:]
    return ''

def barename(name):
    if '}' in name:
        return name.split('}', 1)[1]
    return name

def prefixname(name, nsrmap):
    if not isqname(name):
        return name
    ns = namespace(name)
    if ns not in nsrmap:
        return name
    prefix = nsrmap[ns]
    if not prefix:
        return barename(name)
    return ':'.join((prefix, barename(name)))

def isprefixname(name):
    return name and PREFIXNAME_RE.match(name) is not None

def qname(name, nsmap):
    if not isprefixname(name):
        return name
    prefix, local = name.split(':', 1)
    if prefix not in nsmap:
        return name
    return '{%s}%s' % (nsmap[prefix], local)

def isqname(name):
    return name and QNAME_RE.match(name) is not None

def XPath(expr):
    return etree.XPath(expr, namespaces=XPNSMAP)

def xpath(elem, expr):
    return elem.xpath(expr, namespaces=XPNSMAP)

def xml2str(root, pretty_print=False):
    return etree.tostring(root, encoding='utf-8', xml_declaration=True,
                          pretty_print=pretty_print)

ASCII_CHARS   = set(chr(x) for x in xrange(128))
UNIBYTE_CHARS = set(chr(x) for x in xrange(256))
URL_SAFE      = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    'abcdefghijklmnopqrstuvwxyz'
                    '0123456789' '_.-/~')
URL_UNSAFE = [ASCII_CHARS - URL_SAFE, UNIBYTE_CHARS - URL_SAFE]

def urlquote(href):
    result = []
    unsafe = 0 if isinstance(href, unicode) else 1
    unsafe = URL_UNSAFE[unsafe]
    for char in href:
        if char in unsafe:
            char = "%%%02x" % ord(char)
        result.append(char)
    return ''.join(result)

def urlnormalize(href):
    parts = urlparse(href)
    if not parts.scheme:
        path, frag = urldefrag(href)
        parts = ('', '', path, '', '', frag)
    parts = (part.replace('\\', '/') for part in parts)
    parts = (urlunquote(part) for part in parts)
    parts = (urlquote(part) for part in parts)
    return urlunparse(parts)


class OEBError(Exception):
    pass


class FauxLogger(object):
    def __getattr__(self, name):
        return self
    def __call__(self, message):
        print message

class Logger(LoggingInterface, object):
    def __getattr__(self, name):
        return object.__getattribute__(self, 'log_' + name)


class NullContainer(object):
    def read(self, path):
        raise OEBError('Attempt to read from NullContainer')

    def write(self, path):
        raise OEBError('Attempt to write to NullContainer')

    def exists(self, path):
        return False

    def namelist(self):
        return []

class DirContainer(object):
    def __init__(self, path):
        path = unicode(path)
        ext = os.path.splitext(path)[1].lower()
        if ext == '.opf':
            self.opfname = os.path.basename(path)
            self.rootdir = os.path.dirname(path)
            return
        self.rootdir = path
        for path in self.namelist():
            ext = os.path.splitext(path)[1].lower()
            if ext == '.opf':
                self.opfname = fname
                return
        self.opfname = None

    def read(self, path):
        if path is None:
            path = self.opfname
        path = os.path.join(self.rootdir, path)
        with open(urlunquote(path), 'rb') as f:
            return f.read()

    def write(self, path, data):
        path = os.path.join(self.rootdir, path)
        dir = os.path.dirname(path)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        with open(urlunquote(path), 'wb') as f:
            return f.write(data)

    def exists(self, path):
        path = os.path.join(self.rootdir, path)
        return os.path.isfile(urlunquote(path))

    def namelist(self):
        names = []
        for root, dirs, files in os.walk(self.rootdir):
            for fname in files:
                fname = os.path.join(root, fname)
                fname = fname.replace('\\', '/')
                names.append(fname)
        return names


class Metadata(object):
    DC_TERMS      = set([
                    'contributor', 'coverage', 'creator', 'date',
                    'description', 'format', 'identifier', 'language',
                    'publisher', 'relation', 'rights', 'source', 'subject',
                    'title', 'type'
                    ])
    CALIBRE_TERMS = set(['series', 'series_index', 'rating'])
    OPF_ATTRS     = {'role': OPF('role'), 'file-as': OPF('file-as'),
                     'scheme': OPF('scheme'), 'event': OPF('event'),
                     'type': XSI('type'), 'lang': XML('lang'), 'id': 'id'}
    
    class Item(object):
        
        class Attribute(object):
            
            def __init__(self, attr, allowed=None):
                if not callable(attr):
                    attr_, attr = attr, lambda term: attr_
                self.attr = attr
                self.allowed = allowed
            
            def term_attr(self, obj):
                term = obj.term
                if namespace(term) != DC11_NS:
                    term = OPF('meta')
                allowed = self.allowed
                if allowed is not None and term not in allowed:
                    raise AttributeError(
                        'attribute %r not valid for metadata term %r' \
                            % (self.attr(term), barename(obj.term)))
                return self.attr(term)
            
            def __get__(self, obj, cls):
                if obj is None: return None
                return obj.attrib.get(self.term_attr(obj), '')
            
            def __set__(self, obj, value):
                obj.attrib[self.term_attr(obj)] = value
        
        def __init__(self, term, value, attrib={}, nsmap={}, **kwargs):
            self.attrib = attrib = dict(attrib)
            self.nsmap = nsmap = dict(nsmap)
            attrib.update(kwargs)
            if namespace(term) == OPF2_NS:
                term = barename(term)
            ns = namespace(term)
            local = barename(term).lower()
            if local in Metadata.DC_TERMS and (not ns or ns in DC_NSES):
                # Anything looking like Dublin Core is coerced
                term = DC(local)
            elif local in Metadata.CALIBRE_TERMS and ns in (CALIBRE_NS, ''):
                # Ditto for Calibre-specific metadata
                term = CALIBRE(local)
            self.term = term
            self.value = value
            for attr, value in attrib.items():
                if isprefixname(value):
                    attrib[attr] = qname(value, nsmap)
                nsattr = Metadata.OPF_ATTRS.get(attr, attr)
                if nsattr == OPF('scheme') and namespace(term) != DC11_NS:
                    # The opf:meta element takes @scheme, not @opf:scheme
                    nsattr = 'scheme'
                if attr != nsattr:
                    attrib[nsattr] = attrib.pop(attr)
        
        scheme  = Attribute(lambda term: 'scheme' if \
                                term == OPF('meta') else OPF('scheme'),
                           [DC('identifier'), OPF('meta')])
        file_as = Attribute(OPF('file-as'), [DC('creator'), DC('contributor')])
        role    = Attribute(OPF('role'), [DC('creator'), DC('contributor')])
        event   = Attribute(OPF('event'), [DC('date')])
        id      = Attribute('id')
        type    = Attribute(XSI('type'), [DC('date'), DC('format'),
                                          DC('type')])
        lang    = Attribute(XML('lang'), [DC('contributor'), DC('coverage'),
                                          DC('creator'), DC('publisher'),
                                          DC('relation'), DC('rights'),
                                          DC('source'), DC('subject'),
                                          OPF('meta')])
        
        def __getitem__(self, key):
            return self.attrib[key]
        
        def __setitem__(self, key, value):
            self.attrib[key] = value
        
        def __contains__(self, key):
            return key in self.attrib
        
        def get(self, key, default=None):
            return self.attrib.get(key, default)
        
        def __repr__(self):
            return 'Item(term=%r, value=%r, attrib=%r)' \
                % (barename(self.term), self.value, self.attrib)

        def __str__(self):
            return unicode(self.value).encode('ascii', 'xmlcharrefreplace')

        def __unicode__(self):
            return unicode(self.value)

        def to_opf1(self, dcmeta=None, xmeta=None, nsrmap={}):
            attrib = {}
            for key, value in self.attrib.items():
                if namespace(key) == OPF2_NS:
                    key = barename(key)
                attrib[key] = prefixname(value, nsrmap)
            if namespace(self.term) == DC11_NS:
                name = DC(barename(self.term).title())
                elem = element(dcmeta, name, attrib=attrib)
                elem.text = self.value
            else:
                elem = element(xmeta, 'meta', attrib=attrib)
                elem.attrib['name'] = prefixname(self.term, nsrmap)
                elem.attrib['content'] = prefixname(self.value, nsrmap)
            return elem
        
        def to_opf2(self, parent=None, nsrmap={}):
            attrib = {}
            for key, value in self.attrib.items():
                attrib[key] = prefixname(value, nsrmap)
            if namespace(self.term) == DC11_NS:
                elem = element(parent, self.term, attrib=attrib)
                elem.text = self.value
            else:
                elem = element(parent, OPF('meta'), attrib=attrib)
                elem.attrib['name'] = prefixname(self.term, nsrmap)
                elem.attrib['content'] = prefixname(self.value, nsrmap)
            return elem
    
    def __init__(self, oeb):
        self.oeb = oeb
        self.items = defaultdict(list)

    def add(self, term, value, attrib={}, nsmap={}, **kwargs):
        item = self.Item(term, value, attrib, nsmap, **kwargs)
        items = self.items[barename(item.term)]
        items.append(item)
        return item

    def iterkeys(self):
        for key in self.items:
            yield key
    __iter__ = iterkeys

    def __getitem__(self, key):
        return self.items[key]

    def __contains__(self, key):
        return key in self.items

    def __getattr__(self, term):
        return self.items[term]

    @apply
    def _nsmap():
        def fget(self):
            nsmap = {}
            for term in self.items:
                for item in self.items[term]:
                    nsmap.update(item.nsmap)
            return nsmap
        return property(fget=fget)
    
    @apply
    def _opf1_nsmap():
        def fget(self):
            nsmap = self._nsmap
            for key, value in nsmap.items():
                if value in OPF_NSES or value in DC_NSES:
                    del nsmap[key]
            return nsmap
        return property(fget=fget)
    
    @apply
    def _opf2_nsmap():
        def fget(self):
            nsmap = self._nsmap
            nsmap.update(OPF2_NSMAP)
            return nsmap
        return property(fget=fget)
    
    def to_opf1(self, parent=None):
        nsmap = self._opf1_nsmap
        nsrmap = dict((value, key) for key, value in nsmap.items())
        elem = element(parent, 'metadata', nsmap=nsmap)
        dcmeta = element(elem, 'dc-metadata', nsmap=OPF1_NSMAP)
        xmeta = element(elem, 'x-metadata')
        for term in self.items:
            for item in self.items[term]:
                item.to_opf1(dcmeta, xmeta, nsrmap=nsrmap)
        if 'ms-chaptertour' not in self.items:
            chaptertour = self.Item('ms-chaptertour', 'chaptertour')
            chaptertour.to_opf1(dcmeta, xmeta, nsrmap=nsrmap)
        return elem
        
    def to_opf2(self, parent=None):
        nsmap = self._opf2_nsmap
        nsrmap = dict((value, key) for key, value in nsmap.items())
        elem = element(parent, OPF('metadata'), nsmap=nsmap)
        for term in self.items:
            for item in self.items[term]:
                item.to_opf2(elem, nsrmap=nsrmap)
        return elem


class Manifest(object):
    
    class Item(object):
    
        NUM_RE = re.compile('^(.*)([0-9][0-9.]*)(?=[.]|$)')
        META_XP = XPath('/h:html/h:head/h:meta[@http-equiv="Content-Type"]')
    
        def __init__(self, oeb, id, href, media_type,
                     fallback=None, loader=str, data=None):
            self.oeb = oeb
            self.id = id
            self.href = self.path = urlnormalize(href)
            self.media_type = media_type
            self.fallback = fallback
            self.spine_position = None
            self.linear = True
            if loader is None and data is None:
                loader = oeb.container.read
            self._loader = loader
            self._data = data

        def __repr__(self):
            return 'Item(id=%r, href=%r, media_type=%r)' \
                % (self.id, self.href, self.media_type)

        def _force_xhtml(self, data):
            # Convert to Unicode and normalize line endings
            data = self.oeb.decode(data)
            data = XMLDECL_RE.sub('', data)
            # Handle broken XHTML w/ SVG (ugh)
            if 'svg:' in data and SVG_NS not in data:
                data = data.replace(
                    '<html', '<html xmlns:svg="%s"' % SVG_NS, 1)
            if 'xlink:' in data and XLINK_NS not in data:
                data = data.replace(
                    '<html', '<html xmlns:xlink="%s"' % XLINK_NS, 1)
            # Try with more & more drastic measures to parse
            try:
                data = etree.fromstring(data)
            except etree.XMLSyntaxError:
                repl = lambda m: ENTITYDEFS.get(m.group(1), m.group(0))
                data = ENTITY_RE.sub(repl, data)
                try:
                    data = etree.fromstring(data)
                except etree.XMLSyntaxError:
                    # TODO: Factor out HTML->XML coercion
                    self.oeb.logger.warn('Parsing file %r as HTML' % self.href)
                    data = html.fromstring(data)
                    data.attrib.pop('xmlns', None)
                    for elem in data.iter(tag=etree.Comment):
                        if elem.text:
                            elem.text = elem.text.strip('-')
                    data = etree.tostring(data, encoding=unicode)
                    try:
                        data = etree.fromstring(data)
                    except etree.XMLSyntaxError:
                        data = etree.fromstring(data, parser=RECOVER_PARSER)
            # Force into the XHTML namespace
            if barename(data.tag) != 'html':
                raise OEBError(
                    'File %r does not appear to be (X)HTML' % self.href)
            elif not namespace(data.tag):
                data.attrib['xmlns'] = XHTML_NS
                data = etree.tostring(data, encoding=unicode)
                data = etree.fromstring(data)
            elif namespace(data.tag) != XHTML_NS:
                # OEB_DOC_NS, but possibly others
                ns = namespace(data.tag)
                attrib = dict(data.attrib)
                nroot = etree.Element(XHTML('html'),
                    nsmap={None: XHTML_NS}, attrib=attrib)
                for elem in data.iterdescendants():
                    if isinstance(elem.tag, basestring) and \
                       namespace(elem.tag) == ns:
                        elem.tag = XHTML(barename(elem.tag))
                for elem in data:
                    nroot.append(elem)
                data = nroot
            # Ensure has a <head/>
            head = xpath(data, '/h:html/h:head')
            head = head[0] if head else None
            if head is None:
                self.oeb.logger.warn(
                    'File %r missing <head/> element' % self.href)
                head = etree.Element(XHTML('head'))
                data.insert(0, head)
                title = etree.SubElement(head, XHTML('title'))
                title.text = self.oeb.translate(__('Unknown'))
            elif not xpath(data, '/h:html/h:head/h:title'):
                self.oeb.logger.warn(
                    'File %r missing <title/> element' % self.href)
                title = etree.SubElement(head, XHTML('title'))
                title.text = self.oeb.translate(__('Unknown'))
            # Remove any encoding-specifying <meta/> elements
            for meta in self.META_XP(data):
                meta.getparent().remove(meta)
            etree.SubElement(head, XHTML('meta'),
                attrib={'http-equiv': 'Content-Type',
                        'content': '%s; charset=utf-8' % XHTML_NS})
            # Ensure has a <body/>
            if not xpath(data, '/h:html/h:body'):
                self.oeb.logger.warn(
                    'File %r missing <body/> element' % self.href)
                etree.SubElement(data, XHTML('body'))
            return data
        
        @apply
        def data():
            def fget(self):
                if self._data is not None:
                    return self._data
                data = self._loader(self.href)
                if self.media_type in OEB_DOCS:
                    data = self._force_xhtml(data)
                elif self.media_type[-4:] in ('+xml', '/xml'):
                    data = etree.fromstring(data)
                elif self.media_type in OEB_STYLES:
                    data = self.oeb.decode(data)
                self._data = data
                return data
            def fset(self, value):
                self._data = value
            def fdel(self):
                self._data = None
            return property(fget, fset, fdel)
                
        def __str__(self):
            data = self.data
            if isinstance(data, etree._Element):
                return xml2str(data, pretty_print=self.oeb.pretty_print)
            if isinstance(data, unicode):
                return data.encode('utf-8')
            return str(data)
        
        def __eq__(self, other):
            return id(self) == id(other)
        
        def __ne__(self, other):
            return not self.__eq__(other)
        
        def __cmp__(self, other):
            result = cmp(self.spine_position, other.spine_position)
            if result != 0:
                return result
            smatch = self.NUM_RE.search(self.href)
            sref = smatch.group(1) if smatch else self.href
            snum = float(smatch.group(2)) if smatch else 0.0
            skey = (sref, snum, self.id)
            omatch = self.NUM_RE.search(other.href)
            oref = omatch.group(1) if omatch else other.href
            onum = float(omatch.group(2)) if omatch else 0.0
            okey = (oref, onum, other.id)
            return cmp(skey, okey)
        
        def relhref(self, href):
            if urlparse(href).scheme:
                return href
            if '/' not in self.href:
                return href
            base = os.path.dirname(self.href).split('/')
            target, frag = urldefrag(href)
            target = target.split('/')
            for index in xrange(min(len(base), len(target))):
                if base[index] != target[index]: break
            else:
                index += 1
            relhref = (['..'] * (len(base) - index)) + target[index:]
            relhref = '/'.join(relhref)
            if frag:
                relhref = '#'.join((relhref, frag))
            return relhref

        def abshref(self, href):
            if urlparse(href).scheme:
                return href
            path, frag = urldefrag(href)
            if not path:
                return '#'.join((self.href, frag))
            if '/' not in self.href:
                return href
            dirname = os.path.dirname(self.href)
            href = os.path.join(dirname, href)
            href = os.path.normpath(href).replace('\\', '/')
            return href
    
    def __init__(self, oeb):
        self.oeb = oeb
        self.ids = {}
        self.hrefs = {}

    def add(self, id, href, media_type, fallback=None, loader=None, data=None):
        item = self.Item(
            self.oeb, id, href, media_type, fallback, loader, data)
        self.ids[item.id] = item
        self.hrefs[item.href] = item
        return item

    def remove(self, item):
        if item in self.ids:
            item = self.ids[item]
        del self.ids[item.id]
        del self.hrefs[item.href]
        if item in self.oeb.spine:
            self.oeb.spine.remove(item)

    def generate(self, id=None, href=None):
        if id is not None:
            base = id
            index = 1
            while id in self.ids:
                id = base + str(index)
                index += 1
        if href is not None:
            href = urlnormalize(href)
            base, ext = os.path.splitext(href)
            index = 1
            while href in self.hrefs:
                href = base + str(index) + ext
                index += 1
        return id, href

    def __iter__(self):
        for id in self.ids:
            yield id

    def __getitem__(self, id):
        return self.ids[id]

    def values(self):
        for item in self.ids.values():
            yield item

    def items(self):
        for id, item in self.ids.items():
            yield id, item
    
    def __contains__(self, key):
        return key in self.ids

    def to_opf1(self, parent=None):
        elem = element(parent, 'manifest')
        for item in self.ids.values():
            media_type = item.media_type
            if media_type in OEB_DOCS:
                media_type = OEB_DOC_MIME
            elif media_type in OEB_STYLES:
                media_type = OEB_CSS_MIME
            attrib = {'id': item.id, 'href': item.href,
                      'media-type': media_type}
            if item.fallback:
                attrib['fallback'] = item.fallback
            element(elem, 'item', attrib=attrib)
        return elem
    
    def to_opf2(self, parent=None):
        elem = element(parent, OPF('manifest'))
        for item in self.ids.values():
            media_type = item.media_type
            if media_type in OEB_DOCS:
                media_type = XHTML_MIME
            elif media_type in OEB_STYLES:
                media_type = CSS_MIME
            attrib = {'id': item.id, 'href': item.href,
                      'media-type': media_type}
            if item.fallback:
                attrib['fallback'] = item.fallback
            element(elem, OPF('item'), attrib=attrib)
        return elem


class Spine(object):
    
    def __init__(self, oeb):
        self.oeb = oeb
        self.items = []

    def _linear(self, linear):
        if isinstance(linear, basestring):
            linear = linear.lower()
        if linear is None or linear in ('yes', 'true'):
            linear = True
        elif linear in ('no', 'false'):
            linear = False
        return linear
        
    def add(self, item, linear=None):
        item.linear = self._linear(linear)
        item.spine_position = len(self.items)
        self.items.append(item)
        return item
    
    def insert(self, index, item, linear):
        item.linear = self._linear(linear)
        item.spine_position = index
        self.items.insert(index, item)
        for i in xrange(index, len(self.items)):
            self.items[i].spine_position = i
        return item
    
    def remove(self, item):
        index = item.spine_position
        self.items.pop(index)
        for i in xrange(index, len(self.items)):
            self.items[i].spine_position = i
        item.spine_position = None
    
    def __iter__(self):
        for item in self.items:
            yield item

    def __getitem__(self, index):
        return self.items[index]

    def __len__(self):
        return len(self.items)

    def __contains__(self, item):
        return (item in self.items)

    def to_opf1(self, parent=None):
        elem = element(parent, 'spine')
        for item in self.items:
            if item.linear:
                element(elem, 'itemref', attrib={'idref': item.id})
        return elem

    def to_opf2(self, parent=None):
        elem = element(parent, OPF('spine'))
        for item in self.items:
            attrib = {'idref': item.id}
            if not item.linear:
                attrib['linear'] = 'no'
            element(elem, OPF('itemref'), attrib=attrib)
        return elem


class Guide(object):
    
    class Reference(object):
        
        _TYPES_TITLES = [('cover', __('Cover')),
                         ('title-page', __('Title Page')),
                         ('toc', __('Table of Contents')),
                         ('index', __('Index')),
                         ('glossary', __('Glossary')),
                         ('acknowledgements', __('Acknowledgements')),
                         ('bibliography', __('Bibliography')),
                         ('colophon', __('Colophon')),
                         ('copyright-page', __('Copyright')),
                         ('dedication', __('Dedication')),
                         ('epigraph', __('Epigraph')),
                         ('foreword', __('Foreword')),
                         ('loi', __('List of Illustrations')),
                         ('lot', __('List of Tables')),
                         ('notes', __('Notes')),
                         ('preface', __('Preface')),
                         ('text', __('Main Text'))]
        TYPES = set(t for t, _ in _TYPES_TITLES)
        TITLES = dict(_TYPES_TITLES)
        ORDER = dict((t, i) for i, (t, _) in enumerate(_TYPES_TITLES))
        
        def __init__(self, oeb, type, title, href):
            self.oeb = oeb
            if type.lower() in self.TYPES:
                type = type.lower()
            elif type not in self.TYPES and \
                 not type.startswith('other.'):
                type = 'other.' + type
            if not title and type in self.TITLES:
                title = oeb.translate(self.TITLES[type])
            self.type = type
            self.title = title
            self.href = urlnormalize(href)
        
        def __repr__(self):
            return 'Reference(type=%r, title=%r, href=%r)' \
                % (self.type, self.title, self.href)
        
        @apply
        def _order():
            def fget(self):
                return self.ORDER.get(self.type, self.type)
            return property(fget=fget)
        
        def __cmp__(self, other):
            if not isinstance(other, Guide.Reference):
                return NotImplemented
            return cmp(self._order, other._order)
        
        @apply
        def item():
            def fget(self):
                path = urldefrag(self.href)[0]
                hrefs = self.oeb.manifest.hrefs
                return hrefs.get(path, None)
            return property(fget=fget)
    
    def __init__(self, oeb):
        self.oeb = oeb
        self.refs = {}
    
    def add(self, type, title, href):
        ref = self.Reference(self.oeb, type, title, href)
        self.refs[type] = ref
        return ref
    
    def iterkeys(self):
        for type in self.refs:
            yield type
    __iter__ = iterkeys
    
    def values(self):
        return sorted(self.refs.values())
    
    def items(self):
        for type, ref in self.refs.items():
            yield type, ref
    
    def __getitem__(self, key):
        return self.refs[key]
    
    def __delitem__(self, key):
        del self.refs[key]
    
    def __contains__(self, key):
        return key in self.refs
    
    def __len__(self):
        return len(self.refs)
    
    def to_opf1(self, parent=None):
        elem = element(parent, 'guide')
        for ref in self.refs.values():
            attrib = {'type': ref.type, 'href': ref.href}
            if ref.title:
                attrib['title'] = ref.title
            element(elem, 'reference', attrib=attrib)
        return elem
    
    def to_opf2(self, parent=None):
        elem = element(parent, OPF('guide'))
        for ref in self.refs.values():
            attrib = {'type': ref.type, 'href': ref.href}
            if ref.title:
                attrib['title'] = ref.title
            element(elem, OPF('reference'), attrib=attrib)
        return elem


class TOC(object):
    # This needs beefing up to support the interface of toc.TOC
    def __init__(self, title=None, href=None, klass=None, id=None):
        self.title = title
        self.href = urlnormalize(href) if href else href
        self.klass = klass
        self.id = id
        self.nodes = []
    
    def add(self, title, href, klass=None, id=None):
        node = TOC(title, href, klass, id)
        self.nodes.append(node)
        return node

    def iterdescendants(self):
        for node in self.nodes:
            yield node
            for child in node.iterdescendants():
                yield child
    
    def __iter__(self):
        for node in self.nodes:
            yield node
    
    def __getitem__(self, index):
        return self.nodes[index]

    def autolayer(self):
        prev = None
        for node in list(self.nodes):
            if prev and urldefrag(prev.href)[0] == urldefrag(node.href)[0]:
                self.nodes.remove(node)
                prev.nodes.append(node)
            else:
                prev = node
    
    def depth(self, level=0):
        if self.nodes:
            return self.nodes[0].depth(level+1)
        return level

    def to_opf1(self, tour):
        for node in self.nodes:
            element(tour, 'site', attrib={
                'title': node.title, 'href': node.href})
            node.to_opf1(tour)
        return tour
    
    def to_ncx(self, parent, depth=1):
        for node in self.nodes:
            id = node.id or unicode(uuid.uuid4())
            attrib = {'id': id, 'playOrder': '0'}
            if node.klass:
                attrib['class'] = node.klass
            point = element(parent, NCX('navPoint'), attrib=attrib)
            label = etree.SubElement(point, NCX('navLabel'))
            element(label, NCX('text')).text = node.title
            href = node.href if depth > 1 else urldefrag(node.href)[0]
            element(point, NCX('content'), src=href)
            node.to_ncx(point, depth+1)
        return parent


class PageList(object):
    
    class Page(object):
        def __init__(self, name, href, type='normal', klass=None, id=None):
            self.name = name
            self.href = urlnormalize(href)
            self.type = type
            self.id = id
            self.klass = klass
    
    def __init__(self):
        self.pages = []
    
    def add(self, name, href, type='normal', klass=None, id=None):
        page = self.Page(name, href, type, klass, id)
        self.pages.append(page)
        return page

    def __len__(self):
        return len(self.pages)
    
    def __iter__(self):
        for page in self.pages:
            yield page
    
    def __getitem__(self, index):
        return self.pages[index]
    
    def to_ncx(self, parent=None):
        plist = element(parent, NCX('pageList'), id=str(uuid.uuid4()))
        values = dict((t, count(1)) for t in ('front', 'normal', 'special'))
        for page in self.pages:
            id = page.id or unicode(uuid.uuid4())
            type = page.type
            value = str(values[type].next())
            attrib = {'id': id, 'value': value, 'type': type, 'playOrder': '0'}
            if page.klass:
                attrib['class'] = page.klass
            ptarget = element(plist, NCX('pageTarget'), attrib=attrib)
            label = element(ptarget, NCX('navLabel'))
            element(label, NCX('text')).text = page.name
            element(ptarget, NCX('content'), src=page.href)
        return plist
    
    def to_page_map(self):
        pmap = etree.Element(OPF('page-map'), nsmap={None: OPF2_NS})
        for page in self.pages:
            element(pmap, OPF('page'), name=page.name, href=page.href)
        return pmap


class OEBBook(object):
    
    def __init__(self, encoding=None, pretty_print=False, logger=FauxLogger()):
        self.encoding = encoding
        self.pretty_print = pretty_print
        self.logger = logger
        self.version = '2.0'
        self.container = NullContainer()
        self.metadata = Metadata(self)
        self.uid = None
        self.manifest = Manifest(self)
        self.spine = Spine(self)
        self.guide = Guide(self)
        self.toc = TOC()
        self.pages = PageList()

    @classmethod
    def generate(cls, opts):
        encoding = opts.encoding
        pretty_print = opts.pretty_print
        return cls(encoding=encoding, pretty_print=pretty_print)
    
    def translate(self, text):
        lang = str(self.metadata.language[0])
        lang = lang.split('-', 1)[0].lower()
        return translate(lang, text)
    
    def decode(self, data):
        if isinstance(data, unicode):
            return data
        if data[:2] in ('\xff\xfe', '\xfe\xff'):
            try:
                return data.decode('utf-16')
            except UnicodeDecodeError:
                pass
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            pass
        if self.encoding is not None:
            try:
                return data.decode(self.encoding)
            except UnicodeDecodeError:
                pass
        data, _ = xml_to_unicode(data)
        data = data.replace('\r\n', '\n')
        data = data.replace('\r', '\n')
        return data
    
    def to_opf1(self):
        package = etree.Element('package',
            attrib={'unique-identifier': self.uid.id})
        self.metadata.to_opf1(package)
        self.manifest.to_opf1(package)
        self.spine.to_opf1(package)
        tours = element(package, 'tours')
        tour = element(tours, 'tour',
            attrib={'id': 'chaptertour', 'title': 'Chapter Tour'})
        self.toc.to_opf1(tour)
        self.guide.to_opf1(package)
        return {OPF_MIME: ('content.opf', package)}

    def _update_playorder(self, ncx):
        hrefs = set(xpath(ncx, '//ncx:content/@src'))
        playorder = {}
        next = 1
        selector = XPath('h:body//*[@id or @name]')
        for item in self.spine:
            base = item.href
            if base in hrefs:
                playorder[base] = next
                next += 1
            for elem in selector(item.data):
                added = False
                for attr in ('id', 'name'):
                    id = elem.get(attr)
                    if not id:
                        continue
                    href = '#'.join([base, id])
                    if href in hrefs:
                        playorder[href] = next
                        added = True
                if added:
                    next += 1
        selector = XPath('ncx:content/@src')
        for elem in xpath(ncx, '//*[@playOrder and ./ncx:content[@src]]'):
            href = selector(elem)[0]
            order = playorder.get(href, 0)
            elem.attrib['playOrder'] = str(order)
        return
    
    def _to_ncx(self):
        lang = unicode(self.metadata.language[0])
        ncx = etree.Element(NCX('ncx'),
            attrib={'version': '2005-1', XML('lang'): lang},
            nsmap={None: NCX_NS})
        head = etree.SubElement(ncx, NCX('head'))
        etree.SubElement(head, NCX('meta'),
            name='dtb:uid', content=unicode(self.uid))
        etree.SubElement(head, NCX('meta'),
            name='dtb:depth', content=str(self.toc.depth()))
        generator = ''.join(['calibre (', calibre.__version__, ')'])
        etree.SubElement(head, NCX('meta'),
            name='dtb:generator', content=generator)
        etree.SubElement(head, NCX('meta'),
            name='dtb:totalPageCount', content=str(len(self.pages)))
        maxpnum = etree.SubElement(head, NCX('meta'),
            name='dtb:maxPageNumber', content='0')
        title = etree.SubElement(ncx, NCX('docTitle'))
        text = etree.SubElement(title, NCX('text'))
        text.text = unicode(self.metadata.title[0])
        navmap = etree.SubElement(ncx, NCX('navMap'))
        self.toc.to_ncx(navmap)
        if len(self.pages) > 0:
            plist = self.pages.to_ncx(ncx)
            value = max(int(x) for x in xpath(plist, '//@value'))
            maxpnum.attrib['content'] = str(value)
        self._update_playorder(ncx)
        return ncx
    
    def to_opf2(self, page_map=False):
        results = {}
        package = etree.Element(OPF('package'),
            attrib={'version': '2.0', 'unique-identifier': self.uid.id},
            nsmap={None: OPF2_NS})
        self.metadata.to_opf2(package)
        manifest = self.manifest.to_opf2(package)
        spine = self.spine.to_opf2(package)
        self.guide.to_opf2(package)
        results[OPF_MIME] = ('content.opf', package)
        id, href = self.manifest.generate('ncx', 'toc.ncx')
        etree.SubElement(manifest, OPF('item'), id=id, href=href,
                         attrib={'media-type': NCX_MIME})
        spine.attrib['toc'] = id
        results[NCX_MIME] = (href, self._to_ncx())
        if page_map and len(self.pages) > 0:
            id, href = self.manifest.generate('page-map', 'page-map.xml')
            etree.SubElement(manifest, OPF('item'), id=id, href=href,
                             attrib={'media-type': PAGE_MAP_MIME})
            spine.attrib['page-map'] = id
            results[PAGE_MAP_MIME] = (href, self.pages.to_page_map())
        return results
