'''
Basic support for manipulating OEB 1.x/2.0 content and metadata.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os
import sys
from collections import defaultdict
from types import StringTypes
from itertools import izip, count, chain
from urlparse import urldefrag, urlparse, urlunparse
from urllib import unquote as urlunquote
import logging
import re
import uuid
import copy
from lxml import etree
from lxml import html
from calibre import LoggingInterface
from calibre.translations.dynamic import translate
from calibre.startup import get_lang
from calibre.ebooks.oeb.entitydefs import ENTITYDEFS

XML_NS = 'http://www.w3.org/XML/1998/namespace'
XHTML_NS = 'http://www.w3.org/1999/xhtml'
OPF1_NS = 'http://openebook.org/namespaces/oeb-package/1.0/'
OPF2_NS = 'http://www.idpf.org/2007/opf'
DC09_NS = 'http://purl.org/metadata/dublin_core'
DC10_NS = 'http://purl.org/dc/elements/1.0/'
DC11_NS = 'http://purl.org/dc/elements/1.1/'
DC_NSES = set([DC09_NS, DC10_NS, DC11_NS])
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
DCTERMS_NS = 'http://purl.org/dc/terms/'
NCX_NS = 'http://www.daisy.org/z3986/2005/ncx/'
SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'
XPNSMAP = {'h': XHTML_NS, 'o1': OPF1_NS, 'o2': OPF2_NS,
           'd09': DC09_NS, 'd10': DC10_NS, 'd11': DC11_NS,
           'xsi': XSI_NS, 'dt': DCTERMS_NS, 'ncx': NCX_NS,
           'svg': SVG_NS, 'xl': XLINK_NS}
DC_PREFIXES = ('d11', 'd10', 'd09')

def XML(name): return '{%s}%s' % (XML_NS, name)
def XHTML(name): return '{%s}%s' % (XHTML_NS, name)
def OPF(name): return '{%s}%s' % (OPF2_NS, name)
def DC(name): return '{%s}%s' % (DC11_NS, name)
def NCX(name): return '{%s}%s' % (NCX_NS, name)
def SVG(name): return '{%s}%s' % (SVG_NS, name)
def XLINK(name): return '{%s}%s' % (XLINK_NS, name)

EPUB_MIME = 'application/epub+zip'
XHTML_MIME = 'application/xhtml+xml'
CSS_MIME = 'text/css'
NCX_MIME = 'application/x-dtbncx+xml'
OPF_MIME = 'application/oebps-package+xml'
OEB_DOC_MIME = 'text/x-oeb1-document'
OEB_CSS_MIME = 'text/x-oeb1-css'
OPENTYPE_MIME = 'font/opentype'
GIF_MIME = 'image/gif'
JPEG_MIME = 'image/jpeg'
PNG_MIME = 'image/png'
SVG_MIME = 'image/svg+xml'
BINARY_MIME = 'application/octet-stream'

OEB_STYLES = set([CSS_MIME, OEB_CSS_MIME, 'text/x-oeb-css'])
OEB_DOCS = set([XHTML_MIME, 'text/html', OEB_DOC_MIME, 'text/x-oeb-document'])
OEB_RASTER_IMAGES = set([GIF_MIME, JPEG_MIME, PNG_MIME])
OEB_IMAGES = set([GIF_MIME, JPEG_MIME, PNG_MIME, SVG_MIME])

MS_COVER_TYPE = 'other.ms-coverimage-standard'

ENTITY_RE = re.compile(r'&([a-zA-Z_:][a-zA-Z0-9.-_:]+);')
COLLAPSE_RE = re.compile(r'[ \t\r\n\v]+')

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
    prefix = nsrmap[namespace(name)]
    if not prefix:
        return barename(name)
    return ':'.join((prefix, barename(name)))

def XPath(expr):
    return etree.XPath(expr, namespaces=XPNSMAP)

def xpath(elem, expr):
    return elem.xpath(expr, namespaces=XPNSMAP)

def xml2str(root):
    return etree.tostring(root, encoding='utf-8', xml_declaration=True)

ASCII_CHARS = set(chr(x) for x in xrange(128))
URL_SAFE = set(u'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
               u'abcdefghijklmnopqrstuvwxyz'
               u'0123456789' u'_.-/~')
URL_UNSAFE = ASCII_CHARS - URL_SAFE
def urlquote(href):
    result = []
    for char in href:
        if char in URL_UNSAFE:
            char = "%%%02x" % ord(char)
        result.append(char)
    return ''.join(result)

def urlnormalize(href):
    parts = urlparse(href)
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


class AbstractContainer(object):
    def read_xml(self, path):
        return etree.fromstring(
            self.read(path), base_url=os.path.dirname(path))

class DirContainer(AbstractContainer):
    def __init__(self, rootdir):
        self.rootdir = rootdir

    def read(self, path):
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

class DirWriter(object):
    def __init__(self, version=2.0):
        self.version = version

    def dump(self, oeb, path):
        if not os.path.isdir(path):
            os.mkdir(path)
        output = DirContainer(path)
        for item in oeb.manifest.values():
            output.write(item.href, str(item))
        metadata = oeb.to_opf2() if self.version == 2 else oeb.to_opf1()
        for href, data in metadata.values():
            output.write(href, xml2str(data))
        return


class Metadata(object):
    TERMS = set(['contributor', 'coverage', 'creator', 'date', 'description',
                 'format', 'identifier', 'language', 'publisher', 'relation',
                 'rights', 'source', 'subject', 'title', 'type'])
    ATTRS = set(['role', 'file-as', 'scheme'])
    OPF1_NSMAP = {'dc': DC11_NS, 'oebpackage': OPF1_NS}
    OPF2_NSMAP = {'opf': OPF2_NS, 'dc': DC11_NS, 'dcterms': DCTERMS_NS,
                  'xsi': XSI_NS}
    
    class Item(object):
        def __init__(self, term, value, fq_attrib={}, **kwargs):
            self.fq_attrib = fq_attrib = dict(fq_attrib)
            fq_attrib.update(kwargs)
            if barename(term).lower() in Metadata.TERMS and \
               (not namespace(term) or namespace(term) in DC_NSES):
                # Anything looking like Dublin Core is coerced
                term = DC(barename(term).lower())
            elif namespace(term) == OPF2_NS:
                term = barename(term)
            self.term = term
            self.value = value
            self.attrib = attrib = {}
            for fq_attr in fq_attrib:
                if fq_attr in Metadata.ATTRS:
                    attr = fq_attr
                    fq_attr = OPF(fq_attr)
                    fq_attrib[fq_attr] = fq_attrib.pop(attr)
                else:
                    attr = barename(fq_attr)
                attrib[attr] = fq_attrib[fq_attr]
        
        def __getattr__(self, name):
            name = name.replace('_', '-')
            try:
                return self.attrib[name]
            except KeyError:
                raise AttributeError(
                    '%r object has no attribute %r' \
                        % (self.__class__.__name__, name))
        
        def __getitem__(self, key):
            return self.attrib[key]
        
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

        def to_opf1(self, dcmeta=None, xmeta=None):
            if namespace(self.term) == DC11_NS:
                name = DC(barename(self.term).title())
                elem = element(dcmeta, name, attrib=self.attrib)
                elem.text = self.value
            else:
                elem = element(xmeta, 'meta', attrib=self.attrib)
                elem.attrib['name'] = self.term
                elem.attrib['content'] = self.value
            return elem
        
        def to_opf2(self, parent=None):
            if namespace(self.term) == DC11_NS:
                elem = element(parent, self.term, attrib=self.fq_attrib)
                elem.text = self.value
            else:
                elem = element(parent, OPF('meta'), attrib=self.fq_attrib)
                elem.attrib['name'] = self.term
                elem.attrib['content'] = self.value
            return elem
    
    def __init__(self, oeb):
        self.oeb = oeb
        self.items = defaultdict(list)

    def add(self, term, value, attrib={}, **kwargs):
        item = self.Item(term, value, attrib, **kwargs)
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

    def to_opf1(self, parent=None):
        elem = element(parent, 'metadata')
        dcmeta = element(elem, 'dc-metadata', nsmap=self.OPF1_NSMAP)
        xmeta = element(elem, 'x-metadata')
        for term in self.items:
            for item in self.items[term]:
                item.to_opf1(dcmeta, xmeta)
        if 'ms-chaptertour' not in self.items:
            chaptertour = self.Item('ms-chaptertour', 'chaptertour')
            chaptertour.to_opf1(dcmeta, xmeta)
        return elem
        
    def to_opf2(self, parent=None):
        elem = element(parent, OPF('metadata'), nsmap=self.OPF2_NSMAP)
        for term in self.items:
            for item in self.items[term]:
                item.to_opf2(elem)
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
            # Possibly decode in user-specified encoding
            if self.oeb.encoding is not None:
                data = data.decode(self.oeb.encoding, 'replace')
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
                    self.oeb.logger.warn('Parsing file %r as HTML' % self.href)
                    data = html.fromstring(data)
                    data.attrib.pop('xmlns', None)
                    data = etree.tostring(data, encoding=unicode)
                    data = etree.fromstring(data)
            # Force into the XHTML namespace
            if namespace(data.tag) != XHTML_NS:
                data.attrib['xmlns'] = XHTML_NS
                data = etree.tostring(data, encoding=unicode)
                data = etree.fromstring(data)
            # Remove any encoding-specifying <meta/> elements
            for meta in self.META_XP(data):
                meta.getparent().remove(meta)
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
            # Ensure has a <body/>
            if not xpath(data, '/h:html/h:body'):
                self.oeb.logger.warn(
                    'File %r missing <body/> element' % self.href)
                etree.SubElement(data, XHTML('body'))
            return data
        
        def data():
            def fget(self):
                if self._data is not None:
                    return self._data
                data = self._loader(self.href)
                if self.media_type in OEB_DOCS:
                    data = self._force_xhtml(data)
                elif self.media_type[-4:] in ('+xml', '/xml'):
                    data = etree.fromstring(data)
                self._data = data
                return data
            def fset(self, value):
                self._data = value
            def fdel(self):
                self._data = None
            return property(fget, fset, fdel)
        data = data()
        
        def __str__(self):
            data = self.data
            if isinstance(data, etree._Element):
                return xml2str(data)
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

    def generate(self, id, href):
        href = urlnormalize(href)
        base = id
        index = 1
        while id in self.ids:
            id = base + str(index)
            index += 1
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
                      'media-type': item.media_type}
            if item.fallback:
                attrib['fallback'] = item.fallback
            element(elem, OPF('item'), attrib=attrib)
        return elem


class Spine(object):
    def __init__(self, oeb):
        self.oeb = oeb
        self.items = []

    def _linear(self, linear):
        if isinstance(linear, StringTypes):
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
        ORDER = dict((t, i) for (t, _), i in izip(_TYPES_TITLES, count(0)))
        
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
        
        def _order():
            def fget(self):
                return self.ORDER.get(self.type, self.type)
            return property(fget=fget)
        _order = _order()
        
        def __cmp__(self, other):
            if not isinstance(other, Guide.Reference):
                return NotImplemented
            return cmp(self._order, other._order)
        
        def item():
            def fget(self):
                path, frag = urldefrag(self.href)
                hrefs = self.oeb.manifest.hrefs
                return hrefs.get(path, None)
            return property(fget=fget)
        item = item()
    
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
    
    def to_ncx(self, parent, order=None, depth=1):
        if not order: order = [0]
        for node in self.nodes:
            order[0] += 1
            playOrder = str(order[0])
            id = self.id or 'np' + playOrder
            point = etree.SubElement(parent,
                NCX('navPoint'), id=id, playOrder=playOrder)
            if self.klass:
                point.attrib['class'] = node.klass
            label = etree.SubElement(point, NCX('navLabel'))
            etree.SubElement(label, NCX('text')).text = node.title
            href = node.href if depth > 1 else urldefrag(node.href)[0]
            child = etree.SubElement(point,
                NCX('content'), attrib={'src': href})
            node.to_ncx(point, order, depth+1)
        return parent

    
class OEBBook(object):
    def __init__(self, opfpath=None, container=None, encoding=None,
                 logger=FauxLogger()):
        if opfpath and not container:
            container = DirContainer(os.path.dirname(opfpath))
            opfpath = os.path.basename(opfpath)
        self.container = container
        self.encoding = encoding
        self.logger = logger
        if opfpath or container:
            opf = self._read_opf(opfpath)
            self._all_from_opf(opf)
    
    def _clean_opf(self, opf):
        for elem in opf.iter():
            if isinstance(elem.tag, basestring) \
               and namespace(elem.tag) in ('', OPF1_NS):
                elem.tag = OPF(barename(elem.tag))
        attrib = dict(opf.attrib)
        nroot = etree.Element(OPF('package'),
            nsmap={None: OPF2_NS}, attrib=attrib)
        metadata = etree.SubElement(nroot, OPF('metadata'),
            nsmap={'opf': OPF2_NS, 'dc': DC11_NS,
                   'xsi': XSI_NS, 'dcterms': DCTERMS_NS})
        dc = lambda prefix: xpath(opf, 'o2:metadata//%s:*' % prefix)
        for element in chain(*(dc(prefix) for prefix in DC_PREFIXES)):
            if not element.text: continue
            tag = barename(element.tag).lower()
            element.tag = '{%s}%s' % (DC11_NS, tag)
            for name in element.attrib:
                if name in ('role', 'file-as', 'scheme'):
                    nsname = '{%s}%s' % (OPF2_NS, name)
                    element.attrib[nsname] = element.attrib[name]
                    del element.attrib[name]
            metadata.append(element)
        for element in xpath(opf, 'o2:metadata//o2:meta'):
            metadata.append(element)
        for tag in ('o2:manifest', 'o2:spine', 'o2:tours', 'o2:guide'):
            for element in xpath(opf, tag):
                nroot.append(element)
        return nroot
    
    def _read_opf(self, opfpath):
        opf = self.container.read(opfpath)
        try:
            opf = etree.fromstring(opf)
        except etree.XMLSyntaxError:
            repl = lambda m: ENTITYDEFS.get(m.group(1), m.group(0))
            opf = ENTITY_RE.sub(repl, opf)
            opf = etree.fromstring(opf)
            self.logger.warn('OPF contains invalid HTML named entities')
        ns = namespace(opf.tag)
        if ns not in ('', OPF1_NS, OPF2_NS):
            raise OEBError('Invalid namespace %r for OPF document' % ns)
        opf = self._clean_opf(opf)
        return opf
    
    def _metadata_from_opf(self, opf):
        uid = opf.get('unique-identifier', 'calibre-uuid')
        self.uid = None
        self.metadata = metadata = Metadata(self)
        ignored = (OPF('dc-metadata'), OPF('x-metadata'))
        for elem in xpath(opf, '/o2:package/o2:metadata//*'):
            if elem.tag in ignored: continue
            term = elem.tag
            value = elem.text
            if term == OPF('meta'):
                term = elem.attrib.pop('name', None)
                value = elem.attrib.pop('content', None)
            if value:
                value = COLLAPSE_RE.sub(' ', value.strip())
            if term and (value or elem.attrib):
                metadata.add(term, value, elem.attrib)
        haveuuid = haveid = False
        for ident in metadata.identifier:
            if unicode(ident).startswith('urn:uuid:'):
                haveuuid = True
            if 'id' in ident.attrib:
                haveid = True
        if not haveuuid and haveid:
            bookid = "urn:uuid:%s" % str(uuid.uuid4())
            metadata.add('identifier', bookid, id='calibre-uuid')
        for item in metadata.identifier:
            if item.id == uid:
                self.uid = item
                break
        else:
            self.logger.warn(u'Unique-identifier %r not found' % uid)
            for ident in metadata.identifier:
                if 'id' in ident.attrib:
                    self.uid = metadata.identifier[0]
                    break
        if not metadata.language:
            self.logger.warn(u'Language not specified')
            metadata.add('language', get_lang())
        if not metadata.creator:
            self.logger.warn('Creator not specified')
            metadata.add('creator', self.translate(__('Unknown')))
        if not metadata.title:
            self.logger.warn('Title not specified')
            metadata.add('title', self.translate(__('Unknown')))
    
    def _manifest_from_opf(self, opf):
        self.manifest = manifest = Manifest(self)
        for elem in xpath(opf, '/o2:package/o2:manifest/o2:item'):
            id = elem.get('id')
            href = elem.get('href')
            media_type = elem.get('media-type', None)
            if media_type is None:
                media_type = elem.get('mediatype', BINARY_MIME)
            fallback = elem.get('fallback')
            if href in manifest.hrefs:
                self.logger.warn(u'Duplicate manifest entry for %r' % href)
                continue
            if not self.container.exists(href):
                self.logger.warn(u'Manifest item %r not found' % href)
                continue
            if id in manifest.ids:
                self.logger.warn(u'Duplicate manifest id %r' % id)
                id, href = manifest.generate(id, href)
            manifest.add(id, href, media_type, fallback)
    
    def _spine_from_opf(self, opf):
        self.spine = spine = Spine(self)
        for elem in xpath(opf, '/o2:package/o2:spine/o2:itemref'):
            idref = elem.get('idref')
            if idref not in self.manifest:
                self.logger.warn(u'Spine item %r not found' % idref)
                continue
            item = self.manifest[idref]
            spine.add(item, elem.get('linear'))
        extras = []
        for item in self.manifest.values():
            if item.media_type == XHTML_MIME \
               and item not in spine:
                extras.append(item)
        extras.sort()
        for item in extras:
            spine.add(item, False)
        if len(spine) == 0:
            raise OEBError("Spine is empty")

    def _guide_from_opf(self, opf):
        self.guide = guide = Guide(self)
        for elem in xpath(opf, '/o2:package/o2:guide/o2:reference'):
            href = elem.get('href')
            path, frag = urldefrag(href)
            if path not in self.manifest.hrefs:
                self.logger.warn(u'Guide reference %r not found' % href)
                continue
            guide.add(elem.get('type'), elem.get('title'), href)

    def _toc_from_navpoint(self, toc, navpoint):
        children = xpath(navpoint, 'ncx:navPoint')
        for child in children:
            title = ''.join(xpath(child, 'ncx:navLabel/ncx:text/text()'))
            href = xpath(child, 'ncx:content/@src')[0]
            id = child.get('id')
            klass = child.get('class')
            node = toc.add(title, href, id=id, klass=klass)
            self._toc_from_navpoint(node, child)
            
    def _toc_from_ncx(self, opf):
        result = xpath(opf, '/o2:package/o2:spine/@toc')
        if not result:
            expr = '/o2:package/o2:manifest/o2:item[@media-type="%s"]/@id'
            result = xpath(opf, expr % NCX_MIME)
            if len(result) != 1:
                return False
        id = result[0]
        if id not in self.manifest.ids:
            return False
        item = self.manifest.ids[id]
        ncx = item.data
        self.manifest.remove(item)
        title = xpath(ncx, 'ncx:docTitle/ncx:text/text()')
        title = title[0].strip() if title else unicode(self.metadata.title)
        self.toc = toc = TOC(title)
        navmaps = xpath(ncx, 'ncx:navMap')
        for navmap in navmaps:
            self._toc_from_navpoint(toc, navmap)
        return True

    def _toc_from_tour(self, opf):
        result = xpath(opf, '/o2:package/o2:tours/o2:tour')
        if not result:
            return False
        tour = result[0]
        self.toc = toc = TOC(tour.get('title'))
        sites = xpath(tour, 'o2:site')
        for site in sites:
            toc.add(site.get('title'), site.get('href'))
        return True

    def _toc_from_html(self, opf):
        if 'toc' not in self.guide:
            return False
        self.toc = toc = TOC()
        itempath, frag = urldefrag(self.guide['toc'].href)
        item = self.manifest.hrefs[itempath]
        html = item.data
        if frag:
            elems = xpath(html, './/*[@id="%s"]' % frag)
            if not elems:
                elems = xpath(html, './/*[@name="%s"]' % frag)
            elem = elems[0] if elems else html
            while elem != html and not xpath(elem, './/h:a[@href]'):
                elem = elem.getparent()
            html = elem
        titles = defaultdict(list)
        order = []
        for anchor in xpath(html, './/h:a[@href]'):
            href = anchor.attrib['href']
            path, frag = urldefrag(href)
            if not path:
                href = '#'.join((itempath, frag))
            title = ' '.join(xpath(anchor, './/text()'))
            href = urlnormalize(href)
            if href not in titles:
                order.append(href)
            titles[href].append(title)
        for href in order:
            toc.add(' '.join(titles[href]), href)
        return True
    
    def _toc_from_spine(self, opf):
        self.toc = toc = TOC()
        titles = []
        headers = []
        for item in self.spine:
            if not item.linear: continue
            html = item.data
            title = xpath(html, '/h:html/h:head/h:title/text()')
            title = title[0].strip() if title else None
            if title: titles.append(title)
            headers.append('(unlabled)')
            for tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'strong'):
                expr = '/h:html/h:body//h:%s[position()=1]/text()' % (tag,)
                header = xpath(html, expr)
                if header:
                    headers[-1] = header[0]
                    break
        use = titles
        if len(titles) > len(set(titles)):
            use = headers
        for title, item in izip(use, self.spine):
            if not item.linear: continue
            toc.add(title, item.href)
        return True
    
    def _toc_from_opf(self, opf):
        if self._toc_from_ncx(opf): return
        if self._toc_from_tour(opf): return
        if self._toc_from_html(opf): return
        self._toc_from_spine(opf)

    def _ensure_cover_image(self):
        cover = None
        hcover = self.spine[0]
        if 'cover' in self.guide:
            href = self.guide['cover'].href
            item = self.manifest.hrefs[href]
            media_type = item.media_type
            if media_type in OEB_RASTER_IMAGES:
                cover = item
            elif media_type in OEB_DOCS:
                hcover = item
        html = hcover.data
        if cover is not None:
            pass
        elif self.metadata.cover:
            id = str(self.metadata.cover[0])
            cover = self.manifest.ids[id]
        elif MS_COVER_TYPE in self.guide:
            href = self.guide[MS_COVER_TYPE].href
            cover = self.manifest.hrefs[href]
        elif xpath(html, '//h:img[position()=1]'):
            img = xpath(html, '//h:img[position()=1]')[0]
            href = hcover.abshref(img.get('src'))
            cover = self.manifest.hrefs[href]
        elif xpath(html, '//h:object[position()=1]'):
            object = xpath(html, '//h:object[position()=1]')[0]
            href = hcover.abshref(object.get('data'))
            cover = self.manifest.hrefs[href]
        elif xpath(html, '//svg:svg[position()=1]'):
            svg = copy.deepcopy(xpath(html, '//svg:svg[position()=1]')[0])
            href = os.path.splitext(hcover.href)[0] + '.svg'
            id, href = self.manifest.generate(hcover.id, href)
            cover = self.manifest.add(id, href, SVG_MIME, data=svg)
        if cover and not self.metadata.cover:
            self.metadata.add('cover', cover.id)
            
    def _all_from_opf(self, opf):
        self._metadata_from_opf(opf)
        self._manifest_from_opf(opf)
        self._spine_from_opf(opf)
        self._guide_from_opf(opf)
        self._toc_from_opf(opf)
        self._ensure_cover_image()

    def translate(self, text):
        lang = str(self.metadata.language[0])
        lang = lang.split('-', 1)[0].lower()
        return translate(lang, text)
    
    def to_opf1(self):
        package = etree.Element('package',
            attrib={'unique-identifier': self.uid.id})
        metadata = self.metadata.to_opf1(package)
        manifest = self.manifest.to_opf1(package)
        spine = self.spine.to_opf1(package)
        tours = element(package, 'tours')
        tour = element(tours, 'tour',
            attrib={'id': 'chaptertour', 'title': 'Chapter Tour'})
        self.toc.to_opf1(tour)
        guide = self.guide.to_opf1(package)
        return {OPF_MIME: ('content.opf', package)}

    def _to_ncx(self):
        lang = unicode(self.metadata.language[0])
        ncx = etree.Element(NCX('ncx'),
            attrib={'version': '2005-1', XML('lang'): lang},
            nsmap={None: NCX_NS})
        head = etree.SubElement(ncx, NCX('head'))
        etree.SubElement(head, NCX('meta'),
            attrib={'name': 'dtb:uid', 'content': unicode(self.uid)})
        etree.SubElement(head, NCX('meta'),
            attrib={'name': 'dtb:depth', 'content': str(self.toc.depth())})
        etree.SubElement(head, NCX('meta'),
            attrib={'name': 'dtb:totalPageCount', 'content': '0'})
        etree.SubElement(head, NCX('meta'),
            attrib={'name': 'dtb:maxPageNumber', 'content': '0'})
        title = etree.SubElement(ncx, NCX('docTitle'))
        text = etree.SubElement(title, NCX('text'))
        text.text = unicode(self.metadata.title[0])
        navmap = etree.SubElement(ncx, NCX('navMap'))
        self.toc.to_ncx(navmap)
        return ncx
    
    def to_opf2(self):
        package = etree.Element(OPF('package'),
            attrib={'version': '2.0', 'unique-identifier': self.uid.id},
            nsmap={None: OPF2_NS})
        metadata = self.metadata.to_opf2(package)
        manifest = self.manifest.to_opf2(package)
        id, href = self.manifest.generate('ncx', 'toc.ncx')
        etree.SubElement(manifest, OPF('item'),
            attrib={'id': id, 'href': href, 'media-type': NCX_MIME})
        spine = self.spine.to_opf2(package)
        spine.attrib['toc'] = id
        guide = self.guide.to_opf2(package)
        ncx = self._to_ncx()
        return {OPF_MIME: ('content.opf', package),
                NCX_MIME: (href, ncx)}


def main(argv=sys.argv):
    for arg in argv[1:]:
        oeb = OEBBook(arg)
        for name, doc in oeb.to_opf1().values():
            print etree.tostring(doc, pretty_print=True)
        for name, doc in oeb.to_opf2().values():
            print etree.tostring(doc, pretty_print=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
