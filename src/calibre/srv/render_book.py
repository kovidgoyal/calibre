#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import sys, os, json
from base64 import standard_b64encode, standard_b64decode
from collections import defaultdict, OrderedDict
from itertools import count
from functools import partial
from future_builtins import map
from urlparse import urlparse

from cssutils import replaceUrls

from calibre.ebooks.oeb.base import (
    OEB_DOCS, OEB_STYLES, rewrite_links, XPath, urlunquote, XLINK, XHTML_NS, OPF, XHTML, EPUB_NS)
from calibre.ebooks.oeb.iterator.book import extract_book
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.cover import set_epub_cover, find_cover_image
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.utils.short_uuid import uuid4
from calibre.utils.logging import default_log

RENDER_VERSION = 1

BLANK_JPEG = b'\xff\xd8\xff\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03\x03\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\x08\n\n\t\x08\t\t\n\x0c\x0f\x0c\n\x0b\x0e\x0b\t\t\r\x11\r\x0e\x0f\x10\x10\x11\x10\n\x0c\x12\x13\x12\x10\x13\x0f\x10\x10\x10\xff\xc9\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xcc\x00\x06\x00\x10\x10\x05\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9'  # noqa

def encode_component(x):
    return standard_b64encode(x.encode('utf-8')).decode('ascii')

def decode_component(x):
    return standard_b64decode(x).decode('utf-8')

def encode_url(name, frag=''):
    name = encode_component(name)
    if frag:
        name += '#' + frag
    return name

def decode_url(x):
    parts = x.split('#', 1)
    return decode_component(parts[0]), parts[1] if len(parts) > 1 else ''

class Container(ContainerBase):

    tweak_mode = True

    def __init__(self, path_to_ebook, tdir, log=None, book_hash=None):
        log = log or default_log
        book_fmt, opfpath, input_fmt = extract_book(path_to_ebook, tdir, log=log)
        ContainerBase.__init__(self, tdir, opfpath, log)
        excluded_names = {
            name for name, mt in self.mime_map.iteritems() if
            name == self.opf_name or mt == guess_type('a.ncx') or name.startswith('META-INF/') or
            name == 'mimetype'
        }
        raster_cover_name, titlepage_name = self.create_cover_page(input_fmt.lower())

        self.book_render_data = data = {
            'version': RENDER_VERSION,
            'toc':get_toc(self).as_dict,
            'spine':[name for name, is_linear in self.spine_names],
            'link_uid': uuid4(),
            'book_hash': book_hash,
            'is_comic': input_fmt.lower() in {'cbc', 'cbz', 'cbr', 'cb7'},
            'raster_cover_name': raster_cover_name,
            'title_page_name': titlepage_name,
        }
        # Mark the spine as dirty since we have to ensure it is normalized
        for name in data['spine']:
            self.parsed(name), self.dirty(name)
        self.virtualized_names = set()
        self.virtualize_resources()
        def manifest_data(name):
            mt = (self.mime_map.get(name) or 'application/octet-stream').lower()
            return {
                'size':os.path.getsize(self.name_path_map[name]),
                'is_virtualized': name in self.virtualized_names,
                'mimetype':mt,
                'is_html': mt in OEB_DOCS
            }
        data['files'] = {name:manifest_data(name) for name in set(self.name_path_map) - excluded_names}
        self.commit()
        for name in excluded_names:
            os.remove(self.name_path_map[name])
        with lopen(os.path.join(self.root, 'calibre-book-manifest.json'), 'wb') as f:
            f.write(json.dumps(self.book_render_data, ensure_ascii=False).encode('utf-8'))

    def create_cover_page(self, input_fmt):
        if input_fmt == 'epub':
            def cover_path(action, data):
                if action == 'write_image':
                    data.write(BLANK_JPEG)
            return set_epub_cover(self, cover_path, (lambda *a: None))
        from calibre.ebooks.oeb.transforms.cover import CoverManager
        raster_cover_name = find_cover_image(self, strict=True)
        if raster_cover_name is None:
            item = self.generate_item(name='cover.jpeg', id_prefix='cover')
            raster_cover_name = self.href_to_name(item.get('href'), self.opf_name)
        with self.open(raster_cover_name, 'wb') as dest:
            dest.write(BLANK_JPEG)
        item = self.generate_item(name='titlepage.html', id_prefix='titlepage')
        titlepage_name = self.href_to_name(item.get('href'), self.opf_name)
        templ = CoverManager.SVG_TEMPLATE
        raw = templ % self.name_to_href(raster_cover_name, titlepage_name)
        with self.open(titlepage_name, 'wb') as f:
            f.write(raw.encode('utf-8'))
        spine = self.opf_xpath('//opf:spine')[0]
        ref = spine.makeelement(OPF('itemref'), idref=item.get('id'))
        self.insert_into_xml(spine, ref, index=0)
        self.dirty(self.opf_name)
        return raster_cover_name, titlepage_name

    def virtualize_resources(self):

        changed = set()
        link_uid = self.book_render_data['link_uid']
        resource_template = link_uid + '|{}|'
        xlink_xpath = XPath('//*[@xl:href]')
        link_xpath = XPath('//h:a[@href]')

        def link_replacer(base, url):
            if url.startswith('#'):
                frag = urlunquote(url[1:])
                if not frag:
                    return url
                changed.add(base)
                return resource_template.format(encode_url(base, frag))
            purl = urlparse(url)
            if purl.netloc or purl.query:
                return url
            if purl.scheme and purl.scheme != 'file':
                return url
            if not purl.path or purl.path.startswith('/'):
                return url
            url, frag = purl.path, purl.fragment
            name = self.href_to_name(url, base)
            if name:
                frag = urlunquote(frag)
                url = resource_template.format(encode_url(name, frag))
                changed.add(base)
            return url

        for name, mt in self.mime_map.iteritems():
            mt = mt.lower()
            if mt in OEB_STYLES:
                replaceUrls(self.parsed(name), partial(link_replacer, name))
                self.virtualized_names.add(name)
            elif mt in OEB_DOCS:
                self.virtualized_names.add(name)
                root = self.parsed(name)
                rewrite_links(root, partial(link_replacer, name))
                for a in link_xpath(root):
                    href = a.get('href')
                    if href.startswith(link_uid):
                        a.set('href', 'javascript:void(0)')
                        parts = decode_url(href.split('|')[1])
                        a.set('data-' + link_uid, json.dumps({'name':parts[0], 'frag':parts[1]}, ensure_ascii=False))
                    else:
                        a.set('target', '_blank')
                    changed.add(name)
            elif mt == 'image/svg+xml':
                self.virtualized_names.add(name)
                changed = False
                xlink = XLINK('href')
                for elem in xlink_xpath(self.parsed(name)):
                    elem.set(xlink, link_replacer(name, elem.get(xlink)))

        tuple(map(self.dirty, changed))

    def serialize_item(self, name):
        mt = (self.mime_map[name] or '').lower()
        if mt not in OEB_DOCS:
            return ContainerBase.serialize_item(self, name)
        root = self.parsed(name)
        return json.dumps(html_as_dict(root), ensure_ascii=False, separators=(',', ':')).encode('utf-8')

def split_name(name):
    l, r = name.partition('}')[::2]
    if r:
        return l[1:], r
    return None, l

boolean_attributes = frozenset('allowfullscreen,async,autofocus,autoplay,checked,compact,controls,declare,default,defaultchecked,defaultmuted,defaultselected,defer,disabled,enabled,formnovalidate,hidden,indeterminate,inert,ismap,itemscope,loop,multiple,muted,nohref,noresize,noshade,novalidate,nowrap,open,pauseonexit,readonly,required,reversed,scoped,seamless,selected,sortable,truespeed,typemustmatch,visible'.split(','))  # noqa

EPUB_TYPE_MAP = {k:'doc-' + k for k in (
    'abstract acknowledgements afterword appendix biblioentry bibliography biblioref chapter colophon conclusion cover credit'
    ' credits dedication epigraph epilogue errata footnote footnotes forward glossary glossref index introduction noteref notice'
    ' pagebreak pagelist part preface prologue pullquote qna locator subtitle title toc').split(' ')}
for k in 'figure term definition directory list list-item table row cell'.split(' '):
    EPUB_TYPE_MAP[k] = k

EPUB_TYPE_MAP['help'] = 'doc-tip'

def map_epub_type(epub_type, attribs, elem):
    val = EPUB_TYPE_MAP.get(epub_type.lower())
    if val:
        role = None
        in_attribs = None
        for i, x in enumerate(attribs):
            if x[0] == 'role':
                role = x[1]
                in_attribs = i
                break
        else:
            role = elem.get('role')
        roles = OrderedDict([(k, True) for k in role.split()]) if role else OrderedDict()
        if val not in roles:
            roles[val] = True
        role = ' '.join(roles.iterkeys())
        if in_attribs is None:
            attribs.append(['role', role])
        else:
            attribs[i] = ['role', role]

def serialize_elem(elem, nsmap):
    ns, name = split_name(elem.tag)
    nl = name.lower()
    if ns == EPUB_NS:
        ns, name = None, 'epub-' + name
    if nl == 'meta':
        return  # Filter out <meta> tags as they have unknown side-effects
    if name.lower() in {'img', 'script', 'link', 'image', 'style'}:
        name = nl
    ans = {'n':name}
    if elem.text:
        ans['x'] = elem.text
    if elem.tail:
        ans['l'] = elem.tail
    if ns:
        ns = nsmap[ns]
        if ns:
            ans['s'] = ns
    attribs = []
    for attr, val in elem.items():
        attr_ns, aname = split_name(attr)
        al = aname.lower()
        if not attr_ns and al in boolean_attributes:
            if val and val.lower() in (al, ''):
                attribs.append([al, al])
            continue
        if attr_ns == EPUB_NS and al == 'type':
            map_epub_type(val, attribs, elem)
            continue
        attrib = [aname, val]
        if attr_ns:
            attr_ns = nsmap[attr_ns]
            if attr_ns:
                attrib.append(attr_ns)
        attribs.append(attrib)
    if attribs:
        ans['a'] = attribs
    return ans

def ensure_head(root):
    # Make sure we have only a single <head>
    heads = list(root.iterchildren(XHTML('head')))
    if len(heads) != 1:
        if not heads:
            root.insert(0, root.makeelement(XHTML('head')))
            return
        head = heads[0]
        for eh in heads[1:]:
            for child in eh.iterchildren('*'):
                head.append(child)

def ensure_body(root):
    # Make sure we have only a single <body>
    bodies = list(root.iterchildren(XHTML('body')))
    if len(bodies) != 1:
        if not bodies:
            root.append(root.makeelement(XHTML('body')))
            return
        body = bodies[0]
        for b in bodies[1:]:
            div = root.makeelement(XHTML('div'))
            div.attrib.update(b.attrib)
            div.text = b.text
            for child in b:
                div.append(child)
            body.append(div)

def html_as_dict(root):
    ensure_head(root), ensure_body(root)
    for child in tuple(root.iterchildren('*')):
        if child.tag.partition('}')[-1] not in ('head', 'body'):
            root.remove(child)
    root.text = root.tail = None
    nsmap = defaultdict(count().next)
    nsmap[XHTML_NS]
    tags = [serialize_elem(root, nsmap)]
    tree = [0]
    stack = [(root, tree)]
    while stack:
        elem, node = stack.pop()
        for i, child in enumerate(elem.iterchildren('*')):
            cnode = serialize_elem(child, nsmap)
            if cnode is not None:
                tags.append(cnode)
                child_tree_node = [len(tags)-1]
                node.append(child_tree_node)
                stack.append((child, child_tree_node))
    ns_map = [ns for ns, nsnum in sorted(nsmap.iteritems(), key=lambda x: x[1])]
    return {'ns_map':ns_map, 'tag_map':tags, 'tree':tree}

def render(pathtoebook, output_dir, book_hash=None):
    Container(pathtoebook, output_dir, book_hash=book_hash)

if __name__ == '__main__':
    c = Container(sys.argv[-2], sys.argv[-1])
