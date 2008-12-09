from __future__ import with_statement
import os
import sys
from collections import defaultdict
from types import StringTypes
from itertools import izip, count
from urlparse import urldefrag, urlparse, urlunparse
from urllib import unquote as urlunquote
from lxml import etree

XML_PARSER = etree.XMLParser(
    remove_blank_text=True, recover=True, resolve_entities=False)
XHTML_NS = 'http://www.w3.org/1999/xhtml'
OPF1_NS = 'http://openebook.org/namespaces/oeb-package/1.0/'
OPF2_NS = 'http://www.idpf.org/2007/opf'
DC09_NS = 'http://purl.org/metadata/dublin_core'
DC10_NS = 'http://purl.org/dc/elements/1.0/'
DC11_NS = 'http://purl.org/dc/elements/1.1/'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
DCTERMS_NS = 'http://purl.org/dc/terms/'
NCX_NS = 'http://www.daisy.org/z3986/2005/ncx/'
XPNSMAP = {'h': XHTML_NS, 'o1': OPF1_NS, 'o2': OPF2_NS,
           'd09': DC09_NS, 'd10': DC10_NS, 'd11': DC11_NS,
           'xsi': XSI_NS, 'dt': DCTERMS_NS, 'ncx': NCX_NS}

def XHTML(name): return '{%s}%s' % (XHTML_NS, name)
def OPF(name): return '{%s}%s' % (OPF2_NS, name)
def DC(name): return '{%s}%s' % (DC11_NS, name)
def NCX(name): return '{%s}%s' % (NCX_NS, name)

XHTML_MIME = 'application/xhtml+xml'
CSS_MIME = 'text/css'
NCX_MIME = 'application/x-dtbncx+xml'
OPF_MIME = 'application/oebps-package+xml'

OEB_STYLES = set([CSS_MIME, 'text/x-oeb1-css', 'text/x-oeb-css'])
OEB_DOCS = set([XHTML_MIME, 'text/html', 'text/x-oeb1-document',
                'text/x-oeb-document'])


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

def xpath(elem, expr):
    return elem.xpath(expr, namespaces=XPNSMAP)

URL_UNSAFE = r"""`!@#$%^&*[](){}?+=;:'",<>\| """
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


class AbstractContainer(object):
    def read_xml(self, path):
        return etree.fromstring(
            self.read(path), parser=XML_PARSER,
            base_url=os.path.dirname(path))

class DirContainer(AbstractContainer):
    def __init__(self, rootdir):
        self.rootdir = rootdir

    def read(self, path):
        path = os.path.join(self.rootdir, path)
        with open(urlunquote(path), 'rb') as f:
            return f.read()

    def write(self, path, data):
        path = os.path.join(self.rootdir, path)
        with open(urlunquote(path), 'wb') as f:
            return f.write(data)


class Metadata(object):
    TERMS = set(['contributor', 'coverage', 'creator', 'date', 'description',
                 'format', 'identifier', 'language', 'publisher', 'relation',
                 'rights', 'source', 'subject', 'title', 'type'])
    OPF1_NSMAP = {'dc': DC11_NS, 'oebpackage': OPF1_NS}
    OPF2_NSMAP = {'opf': OPF2_NS, 'dc': DC11_NS, 'dcterms': DCTERMS_NS,
                  'xsi': XSI_NS}
    
    class Item(object):
        def __init__(self, term, value, fq_attrib={}):
            if term == OPF('meta') and not value:
                fq_attrib = dict(fq_attrib)
                term = fq_attrib.pop('name')
                value = fq_attrib.pop('content')
            elif term in Metadata.TERMS and not namespace(term):
                term = DC(term)
            self.term = term
            self.value = value
            self.fq_attrib = dict(fq_attrib)
            self.attrib = attrib = {}
            for fq_attr in fq_attrib:
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

        def __repr__(self):
            return 'Item(term=%r, value=%r, attrib=%r)' \
                % (barename(self.term), self.value, self.attrib)

        def __str__(self):
            return str(self.value)

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

    def add(self, term, value, attrib):
        item = self.Item(term, value, attrib)
        items = self.items[barename(term)]
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
        def __init__(self, id, href, media_type, loader=str):
            self.id = id
            self.href = self.path = urlnormalize(href)
            self.media_type = media_type
            self.spine_position = None
            self.linear = True
            self._loader = loader
            self._data = None

        def __repr__(self):
            return 'Item(id=%r, href=%r, media_type=%r)' \
                % (self.id, self.href, self.media_type)

        def data():
            def fget(self):
                if self._data:
                    return self._data
                data = self._loader(self.href)
                if self.media_type == XHTML_MIME:
                    data = etree.fromstring(data, parser=XML_PARSER)
                    if namespace(data.tag) != XHTML_NS:
                        data.attrib['xmlns'] = XHTML_NS
                        data = etree.tostring(data)
                        data = etree.fromstring(data, parser=XML_PARSER)
                elif self.media_type.startswith('application/') \
                     and self.media_type.endswith('+xml'):
                    data = etree.fromstring(data, parser=XML_PARSER)
                return data
            def fset(self, value):
                self._data = value
            def fdel(self):
                self._data = None
            return property(fget, fset, fdel)
        data = data()

        def __cmp__(self, other):
            result = cmp(self.spine_position, other.spine_position)
            if result != 0:
                return result
            return cmp(self.id, other.id)
    
    def __init__(self, oeb):
        self.oeb = oeb
        self.items = {}
        self.hrefs = {}

    def add(self, id, href, media_type):
        item = self.Item(id, href, media_type, self.oeb.container.read)
        self.items[item.id] = item
        self.hrefs[item.href] = item
        return item

    def remove(self, id):
        href = self.items[id].href
        del self.items[id]
        del self.hrefs[href]

    def __iter__(self):
        for id in self.items:
            yield id

    def __getitem__(self, id):
        return self.items[id]

    def values(self):
        for item in self.items.values():
            yield item

    def items(self):
        for id, item in self.refs.items():
            yield id, items
    
    def __contains__(self, key):
        return id in self.items

    def to_opf1(self, parent=None):
        elem = element(parent, 'manifest')
        for item in self.items.values():
            attrib = {'id': item.id, 'href': item.href,
                      'media-type': item.media_type}
            element(elem, 'item', attrib=attrib)
        return elem            
    
    def to_opf2(self, parent=None):
        elem = element(parent, OPF('manifest'))
        for item in self.items.values():
            attrib = {'id': item.id, 'href': item.href,
                      'media-type': item.media_type}
            element(elem, OPF('item'), attrib=attrib)
        return elem


class Spine(object):
    def __init__(self, oeb):
        self.oeb = oeb
        self.items = []

    def add(self, item, linear):
        if isinstance(linear, StringTypes):
            linear = linear.lower()
        if linear is None or linear in ('yes', 'true'):
            linear = True
        elif linear in ('no', 'false'):
            linear = False
        item.linear = linear
        item.spine_position = len(self.items)
        self.items.append(item)
        return item
    
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
        def __init__(self, type, title, href):
            self.type = type
            self.title = title
            self.href = urlnormalize(href)

        def __repr__(self):
            return 'Reference(type=%r, title=%r, href=%r)' \
                % (self.type, self.title, self.href)
    
    def __init__(self, oeb):
        self.oeb = oeb
        self.refs = {}

    def add(self, type, title, href):
        ref = self.Reference(type, title, href)
        self.refs[type] = ref
        return ref

    def by_type(self, type):
        return self.ref_types[type]

    def iterkeys(self):
        for type in self.refs:
            yield type
    __iter__ = iterkeys

    def values(self):
        for ref in self.refs.values():
            yield ref

    def items(self):
        for type, ref in self.refs.items():
            yield type, ref
    
    def __getitem__(self, index):
        return self.refs[index]

    def __contains__(self, key):
        return key in self.refs

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


class Toc(object):
    def __init__(self, title=None, href=None, klass=None, id=None):
        self.title = title
        self.href = urlnormalize(href) if href else href
        self.klass = klass
        self.id = id
        self.nodes = []
    
    def add(self, title, href, klass=None, id=None):
        node = Toc(title, href, klass, id)
        self.nodes.append(node)
        return node
    
    def __iter__(self):
        for node in self.nodes:
            yield node
    
    def __getitem__(self, index):
        return self.nodes[index]
    
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
    
    def to_ncx(self, parent, playorder=None, depth=1):
        if not playorder: playorder = [0]
        for node in self.nodes:
            playorder[0] += 1
            point = etree.SubElement(parent,
                NCX('navPoint'), attrib={'playOrder': str(playorder[0])})
            if self.klass:
                point.attrib['class'] = self.klass
            if self.id:
                point.attrib['id'] = self.id
            label = etree.SubElement(point, NCX('navLabel'))
            etree.SubElement(label, NCX('text')).text = node.title
            href = node.href if depth > 1 else urldefrag(node.href)[0]
            child = etree.SubElement(point,
                NCX('content'), attrib={'src': href})
            node.to_ncx(point, playorder, depth+1)
        return parent


class Oeb(object):
    def __init__(self, opfpath, container=None):
        if not container:
            container = DirContainer(os.path.dirname(opfpath))
            opfpath = os.path.basename(opfpath)
        self.container = container
        opf = self._read_opf(opfpath)
        self._all_from_opf(opf)
    
    def _convert_opf1(self, opf):
        nroot = etree.Element(OPF('package'),
            nsmap={None: OPF2_NS}, version="2.0", **dict(opf.attrib))
        metadata = etree.SubElement(nroot, OPF('metadata'),
            nsmap={'opf': OPF2_NS, 'dc': DC11_NS,
                   'xsi': XSI_NS, 'dcterms': DCTERMS_NS})
        for prefix in ('d11', 'd10', 'd09'):
            elements = xpath(opf, 'metadata/dc-metadata/%s:*' % prefix)
            if elements: break
        for element in elements:
            if not element.text: continue
            tag = barename(element.tag).lower()
            element.tag = '{%s}%s' % (DC11_NS, tag)
            for name in element.attrib:
                if name in ('role', 'file-as', 'scheme'):
                    nsname = '{%s}%s' % (OPF2_NS, name)
                    element.attrib[nsname] = element.attrib[name]
                    del element.attrib[name]
            metadata.append(element)
        for element in opf.xpath('metadata/x-metadata/meta'):
            metadata.append(element)
        for item in opf.xpath('manifest/item'):
            media_type = item.attrib['media-type']
            if media_type in OEB_DOCS:
                media_type = XHTML_MIME
            elif media_type in OEB_STYLES:
                media_type = CSS_MIME
            item.attrib['media-type'] = media_type
        for tag in ('manifest', 'spine', 'tours', 'guide'):
            for element in opf.xpath(tag):
                nroot.append(element)
        return etree.fromstring(etree.tostring(nroot), parser=XML_PARSER)
    
    def _read_opf(self, opfpath):
        opf = self.container.read_xml(opfpath)
        version = float(opf.get('version', 1.0))
        if version < 2.0:
            opf = self._convert_opf1(opf)
        return opf
    
    def _metadata_from_opf(self, opf):
        uid = opf.attrib['unique-identifier']
        self.metadata = metadata = Metadata(self)        
        for elem in xpath(opf, '/o2:package/o2:metadata/*'):
            if elem.text or elem.attrib:
                metadata.add(elem.tag, elem.text, elem.attrib)
        for item in metadata.identifier:
            if item.id == uid:
                self.uid = item
                break
    
    def _manifest_from_opf(self, opf):
        self.manifest = manifest = Manifest(self)
        for elem in xpath(opf, '/o2:package/o2:manifest/o2:item'):
            manifest.add(elem.get('id'), elem.get('href'),
                         elem.get('media-type'))
    
    def _spine_from_opf(self, opf):
        self.spine = spine = Spine(self)
        for elem in xpath(opf, '/o2:package/o2:spine/o2:itemref'):
            item = self.manifest[elem.get('idref')]
            spine.add(item, elem.get('linear'))
        extras = []
        for item in self.manifest.values():
            if item.media_type == XHTML_MIME \
               and item not in spine:
                extras.append(item)
        extras.sort()
        for item in extras:
            spine.add(item, False)

    def _guide_from_opf(self, opf):
        self.guide = guide = Guide(self)
        for elem in xpath(opf, '/o2:package/o2:guide/o2:reference'):
            guide.add(elem.get('type'), elem.get('title'), elem.get('href'))

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
            return False
        id = result[0]
        ncx = self.manifest[id].data
        self.manifest.remove(id)
        title = xpath(ncx, 'ncx:docTitle/ncx:text/text()')[0]
        self.toc = toc = Toc(title)
        navmaps = xpath(ncx, 'ncx:navMap')
        for navmap in navmaps:
            self._toc_from_navpoint(toc, navmap)
        return True

    def _toc_from_tour(self, opf):
        result = xpath(opf, '/o2:package/o2:tours/o2:tour')
        if not result:
            return False
        tour = result[0]
        self.toc = toc = Toc(tour.get('title'))
        sites = xpath(tour, 'o2:site')
        for site in sites:
            toc.add(site.get('title'), site.get('href'))
        return True

    def _toc_from_html(self, opf):
        if 'toc' not in self.guide:
            return False
        self.toc = toc = Toc()
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
        self.toc = toc = Toc()
        titles = []
        headers = []
        for item in self.spine:
            if not item.linear: continue
            html = item.data
            title = xpath(html, '/h:html/h:head/h:title/text()')
            if title: titles.append(title[0])
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
            
    def _all_from_opf(self, opf):
        self._metadata_from_opf(opf)
        self._manifest_from_opf(opf)
        self._spine_from_opf(opf)
        self._guide_from_opf(opf)
        self._toc_from_opf(opf)

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

    def _generate_ncx_item(self):
        id = 'ncx'
        index = 0
        while id in self.manifest:
            id = 'ncx' + str(index)
            index = index + 1
        href = 'toc'
        index = 0
        while (href + '.ncx') in self.manifest.hrefs:
            href = 'toc' + str(index)
        href += '.ncx'
        return (id, href)
        
    def _to_ncx(self):
        ncx = etree.Element(NCX('ncx'), attrib={'version': '2005-1'},
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
        id, href = self._generate_ncx_item()
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
        oeb = Oeb(arg)
        for name, doc in oeb.to_opf1().values():
            print etree.tostring(doc, pretty_print=True)
        for name, doc in oeb.to_opf2().values():
            print etree.tostring(doc, pretty_print=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
