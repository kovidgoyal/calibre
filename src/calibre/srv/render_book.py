#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import sys, os, json, re
from base64 import standard_b64encode, standard_b64decode
from collections import defaultdict, OrderedDict
from itertools import count
from functools import partial
from future_builtins import map
from urlparse import urlparse
from urllib import quote

from cssutils import replaceUrls
from cssutils.css import CSSRule

from calibre import prepare_string_for_xml, force_unicode
from calibre.ebooks import parse_css_length
from calibre.ebooks.oeb.base import (
    OEB_DOCS, OEB_STYLES, rewrite_links, XPath, urlunquote, XLINK, XHTML_NS, OPF, XHTML, EPUB_NS)
from calibre.ebooks.oeb.iterator.book import extract_book
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.cover import set_epub_cover, find_cover_image
from calibre.ebooks.oeb.polish.css import transform_css
from calibre.ebooks.oeb.polish.utils import extract
from calibre.ebooks.css_transform_rules import StyleDeclaration
from calibre.ebooks.oeb.polish.toc import get_toc, get_landmarks
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
    return decode_component(parts[0]), (parts[1] if len(parts) > 1 else '')


absolute_units = frozenset('px mm cm pt in pc q'.split())
length_factors = {'mm':2.8346456693, 'cm':28.346456693, 'in': 72, 'pc': 12, 'q':0.708661417325}


def convert_fontsize(length, unit, base_font_size=16.0, dpi=96.0):
    ' Convert font size to rem so that font size scaling works. Assumes the document has the specified base font size in px '
    if unit == 'px':
        return length/base_font_size
    pt_to_px = dpi / 72.0
    pt_to_rem = pt_to_px / base_font_size
    return length * length_factors.get(unit, 1) * pt_to_rem


def transform_declaration(decl):
    decl = StyleDeclaration(decl)
    changed = False
    for prop, parent_prop in tuple(decl):
        if prop.name in {'page-break-before', 'page-break-after', 'page-break-inside'}:
            changed = True
            name = prop.name.partition('-')[2]
            for prefix in ('', '-webkit-column-'):
                # Note that Firefox does not support break-after at all
                # https://bugzil.la/549114
                decl.set_property(prefix + name, prop.value, prop.priority)
            decl.remove_property(prop, parent_prop)
        elif prop.name == 'font-size':
            l, unit = parse_css_length(prop.value)
            if unit in absolute_units:
                changed = True
                l = convert_fontsize(l, unit)
                decl.change_property(prop, parent_prop, str(l) + 'rem')
    return changed


def transform_sheet(sheet):
    changed = False
    for rule in sheet.cssRules.rulesOfType(CSSRule.STYLE_RULE):
        if transform_declaration(rule.style):
            changed = True
    return changed


def check_for_maths(root):
    for x in root.iterdescendants('{*}math'):
        return True
    for s in root.iterdescendants(XHTML('script')):
        if s.get('type') == 'text/x-mathjax-config':
            return True
    return False


def has_ancestor(elem, q):
    while elem is not None:
        elem = elem.getparent()
        if elem is q:
            return True
    return False


def anchor_map(root):
    ans = []
    seen = set()
    for elem in root.xpath('//*[@id or @name]'):
        eid = elem.get('id')
        if not eid and elem.tag.endswith('}a'):
            eid = elem.get('name')
            if eid:
                elem.set('id', eid)
        if eid and eid not in seen:
            ans.append(eid)
            seen.add(eid)
    return ans


def get_length(root):
    strip_space = re.compile(r'\s+')
    ans = 0
    ignore_tags = frozenset('script style title noscript'.split())

    def count(elem):
        num = 0
        tname = elem.tag.rpartition('}')[-1].lower()
        if elem.text and tname not in ignore_tags:
            num += len(strip_space.sub('', elem.text))
        if elem.tail:
            num += len(strip_space.sub('', elem.tail))
        if tname in 'img svg':
            num += 2000
        return num

    for body in root.iterdescendants(XHTML('body')):
        ans += count(body)
        for elem in body.iterdescendants('*'):
            ans += count(elem)
    return ans


def toc_anchor_map(toc):
    ans = defaultdict(list)
    seen_map = defaultdict(set)

    def process_node(node):
        name = node['dest']
        if name and node['id'] not in seen_map[name]:
            ans[name].append({'id':node['id'], 'frag':node['frag']})
            seen_map[name].add(node['id'])
        tuple(map(process_node, node['children']))

    process_node(toc)
    return dict(ans)


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
        toc = get_toc(self).to_dict(count())
        spine = [name for name, is_linear in self.spine_names]
        spineq = frozenset(spine)
        landmarks = [l for l in get_landmarks(self) if l['dest'] in spineq]

        self.book_render_data = data = {
            'version': RENDER_VERSION,
            'toc':toc,
            'spine':spine,
            'link_uid': uuid4(),
            'book_hash': book_hash,
            'is_comic': input_fmt.lower() in {'cbc', 'cbz', 'cbr', 'cb7'},
            'raster_cover_name': raster_cover_name,
            'title_page_name': titlepage_name,
            'has_maths': False,
            'total_length': 0,
            'spine_length': 0,
            'toc_anchor_map': toc_anchor_map(toc),
            'landmarks': landmarks,
        }
        # Mark the spine as dirty since we have to ensure it is normalized
        for name in data['spine']:
            self.parsed(name), self.dirty(name)
        self.transform_css()
        self.virtualized_names = set()
        self.virtualize_resources()

        def manifest_data(name):
            mt = (self.mime_map.get(name) or 'application/octet-stream').lower()
            ans = {
                'size':os.path.getsize(self.name_path_map[name]),
                'is_virtualized': name in self.virtualized_names,
                'mimetype':mt,
                'is_html': mt in OEB_DOCS,
            }
            if ans['is_html']:
                root = self.parsed(name)
                ans['length'] = l = get_length(root)
                self.book_render_data['total_length'] += l
                if name in data['spine']:
                    self.book_render_data['spine_length'] += l
                ans['has_maths'] = hm = check_for_maths(root)
                if hm:
                    self.book_render_data['has_maths'] = True
                ans['anchor_map'] = anchor_map(root)
            return ans
        data['files'] = {name:manifest_data(name) for name in set(self.name_path_map) - excluded_names}
        self.commit()
        for name in excluded_names:
            os.remove(self.name_path_map[name])
        with lopen(os.path.join(self.root, 'calibre-book-manifest.json'), 'wb') as f:
            f.write(json.dumps(self.book_render_data, ensure_ascii=False).encode('utf-8'))

    def create_cover_page(self, input_fmt):
        templ = '''
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
        <head><style>
        html, body, img { height: 100vh; display: block; margin: 0; padding: 0; border-width: 0; }
        img {
            width: auto; height: auto;
            margin-left: auto; margin-right: auto;
            max-width: 100vw; max-height: 100vh
        }
        </style></head><body><img src="%s"/></body></html>
        '''
        if input_fmt == 'epub':
            def cover_path(action, data):
                if action == 'write_image':
                    data.write(BLANK_JPEG)
            return set_epub_cover(self, cover_path, (lambda *a: None), options={'template':templ})
        raster_cover_name = find_cover_image(self, strict=True)
        if raster_cover_name is None:
            item = self.generate_item(name='cover.jpeg', id_prefix='cover')
            raster_cover_name = self.href_to_name(item.get('href'), self.opf_name)
        with self.open(raster_cover_name, 'wb') as dest:
            dest.write(BLANK_JPEG)
        item = self.generate_item(name='titlepage.html', id_prefix='titlepage')
        titlepage_name = self.href_to_name(item.get('href'), self.opf_name)
        raw = templ % prepare_string_for_xml(self.name_to_href(raster_cover_name, titlepage_name), True)
        with self.open(titlepage_name, 'wb') as f:
            f.write(raw.encode('utf-8'))
        spine = self.opf_xpath('//opf:spine')[0]
        ref = spine.makeelement(OPF('itemref'), idref=item.get('id'))
        self.insert_into_xml(spine, ref, index=0)
        self.dirty(self.opf_name)
        return raster_cover_name, titlepage_name

    def transform_css(self):
        transform_css(self, transform_sheet=transform_sheet, transform_style=transform_declaration)
        # Firefox flakes out sometimes when dynamically creating <style> tags,
        # so convert them to external stylesheets to ensure they never fail
        style_xpath = XPath('//h:style')
        for name, mt in tuple(self.mime_map.iteritems()):
            mt = mt.lower()
            if mt in OEB_DOCS:
                head = ensure_head(self.parsed(name))
                for style in style_xpath(self.parsed(name)):
                    if style.text and (style.get('type') or 'text/css').lower() == 'text/css':
                        in_head = has_ancestor(style, head)
                        if not in_head:
                            extract(style)
                            head.append(style)
                        css = style.text
                        style.clear()
                        style.tag = XHTML('link')
                        style.set('type', 'text/css')
                        style.set('rel', 'stylesheet')
                        sname = self.add_file(name + '.css', css.encode('utf-8'), modify_name_if_needed=True)
                        style.set('href', self.name_to_href(sname, name))

    def virtualize_resources(self):

        changed = set()
        link_uid = self.book_render_data['link_uid']
        resource_template = link_uid + '|{}|'
        xlink_xpath = XPath('//*[@xl:href]')
        link_xpath = XPath('//h:a[@href]')
        res_link_xpath = XPath('//h:link[@href]')

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
                if self.has_name(name):
                    frag = urlunquote(frag)
                    url = resource_template.format(encode_url(name, frag))
                else:
                    if isinstance(name, unicode):
                        name = name.encode('utf-8')
                    url = 'missing:' + force_unicode(quote(name), 'utf-8')
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
                for link in res_link_xpath(root):
                    ltype = (link.get('type') or 'text/css').lower()
                    rel = (link.get('rel') or 'stylesheet').lower()
                    if ltype != 'text/css' or rel != 'stylesheet':
                        # This link will not be loaded by the browser anyway
                        # and will causes the resource load check to hang
                        link.attrib.clear()
                        changed.add(name)
                rewrite_links(root, partial(link_replacer, name))
                for a in link_xpath(root):
                    href = a.get('href')
                    if href.startswith(link_uid):
                        a.set('href', 'javascript:void(0)')
                        parts = decode_url(href.split('|')[1])
                        a.set('data-' + link_uid, json.dumps({'name':parts[0], 'frag':parts[1]}, ensure_ascii=False))
                    else:
                        a.set('target', '_blank')
                        a.set('rel', 'noopener noreferrer')
                    changed.add(name)
            elif mt == 'image/svg+xml':
                self.virtualized_names.add(name)
                changed.add(name)
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
            return root[0]
        head = heads[0]
        for eh in heads[1:]:
            for child in eh.iterchildren('*'):
                head.append(child)
            extract(eh)
        return head
    return heads[0]


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
    ensure_body(root)
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
        for child in elem.iterchildren('*'):
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
    render(sys.argv[-2], sys.argv[-1])
