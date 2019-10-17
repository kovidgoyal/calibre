#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from functools import partial
from itertools import count

from css_parser import replaceUrls
from css_parser.css import CSSRule

from calibre import force_unicode, prepare_string_for_xml
from calibre.customize.ui import plugin_for_input_format
from calibre.ebooks import parse_css_length
from calibre.ebooks.css_transform_rules import StyleDeclaration
from calibre.ebooks.oeb.base import (
    EPUB_NS, OEB_DOCS, OEB_STYLES, OPF, XHTML, XHTML_NS, XLINK, XPath as _XPath, rewrite_links,
    urlunquote
)
from calibre.ebooks.oeb.iterator.book import extract_book
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.cover import (
    find_cover_image, has_epub_cover, set_epub_cover
)
from calibre.ebooks.oeb.polish.css import transform_inline_styles
from calibre.ebooks.oeb.polish.toc import from_xpaths, get_landmarks, get_toc
from calibre.ebooks.oeb.polish.utils import extract, guess_type
from calibre.srv.metadata import encode_datetime
from calibre.utils.date import EPOCH
from calibre.utils.iso8601 import parse_iso8601
from calibre.utils.logging import default_log
from calibre.utils.serialize import json_loads
from calibre.utils.short_uuid import uuid4
from polyglot.binary import (
    as_base64_unicode as encode_component, from_base64_bytes,
    from_base64_unicode as decode_component
)
from polyglot.builtins import is_py3, iteritems, map, unicode_type
from polyglot.urllib import quote, urlparse

RENDER_VERSION = 1

BLANK_JPEG = b'\xff\xd8\xff\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03\x03\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\x08\n\n\t\x08\t\t\n\x0c\x0f\x0c\n\x0b\x0e\x0b\t\t\r\x11\r\x0e\x0f\x10\x10\x11\x10\n\x0c\x12\x13\x12\x10\x13\x0f\x10\x10\x10\xff\xc9\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xcc\x00\x06\x00\x10\x10\x05\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9'  # noqa


def XPath(expr):
    ans = XPath.cache.get(expr)
    if ans is None:
        ans = XPath.cache[expr] = _XPath(expr)
    return ans


XPath.cache = {}


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


def create_link_replacer(container, link_uid, changed):
    resource_template = link_uid + '|{}|'

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
        name = container.href_to_name(url, base)
        if name:
            if container.has_name_and_is_not_empty(name):
                frag = urlunquote(frag)
                url = resource_template.format(encode_url(name, frag))
            else:
                if isinstance(name, unicode_type):
                    name = name.encode('utf-8')
                url = 'missing:' + force_unicode(quote(name), 'utf-8')
            changed.add(base)
        return url

    return link_replacer


page_break_properties = ('page-break-before', 'page-break-after', 'page-break-inside')


def transform_declaration(decl):
    decl = StyleDeclaration(decl)
    changed = False
    for prop, parent_prop in tuple(decl):
        if prop.name in page_break_properties:
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
                decl.change_property(prop, parent_prop, unicode_type(l) + 'rem')
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
            num += 1000
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

    def __init__(
        self, book_fmt, opfpath, input_fmt, tdir, log=None, book_hash=None, save_bookmark_data=False,
        book_metadata=None, allow_no_cover=True, virtualize_resources=True
    ):
        log = log or default_log
        self.allow_no_cover = allow_no_cover
        ContainerBase.__init__(self, tdir, opfpath, log)
        self.book_metadata = book_metadata
        input_plugin = plugin_for_input_format(input_fmt)
        self.is_comic = bool(getattr(input_plugin, 'is_image_collection', False))
        if save_bookmark_data:
            bm_file = 'META-INF/calibre_bookmarks.txt'
            self.bookmark_data = None
            if self.exists(bm_file):
                with self.open(bm_file, 'rb') as f:
                    self.bookmark_data = f.read()
        # We do not add zero byte sized files as the IndexedDB API in the
        # browser has no good way to distinguish between zero byte files and
        # load failures.
        excluded_names = {
            name for name, mt in iteritems(self.mime_map) if
            name == self.opf_name or mt == guess_type('a.ncx') or name.startswith('META-INF/') or
            name == 'mimetype' or not self.has_name_and_is_not_empty(name)}
        raster_cover_name, titlepage_name = self.create_cover_page(input_fmt.lower())

        toc = get_toc(self).to_dict(count())
        if not toc or not toc.get('children'):
            toc = from_xpaths(self, ['//h:h1', '//h:h2', '//h:h3']).to_dict(count())
        spine = [name for name, is_linear in self.spine_names]
        spineq = frozenset(spine)
        landmarks = [l for l in get_landmarks(self) if l['dest'] in spineq]

        self.book_render_data = data = {
            'version': RENDER_VERSION,
            'toc':toc,
            'book_format': book_fmt,
            'spine':spine,
            'link_uid': uuid4(),
            'book_hash': book_hash,
            'is_comic': self.is_comic,
            'raster_cover_name': raster_cover_name,
            'title_page_name': titlepage_name,
            'has_maths': False,
            'total_length': 0,
            'spine_length': 0,
            'toc_anchor_map': toc_anchor_map(toc),
            'landmarks': landmarks,
            'link_to_map': {},
        }
        # Mark the spine as dirty since we have to ensure it is normalized
        for name in data['spine']:
            self.parsed(name), self.dirty(name)
        self.virtualized_names = set()
        self.transform_all(virtualize_resources)

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
        data = json.dumps(self.book_render_data, ensure_ascii=False)
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        with lopen(os.path.join(self.root, 'calibre-book-manifest.json'), 'wb') as f:
            f.write(data)

    def create_cover_page(self, input_fmt):
        templ = '''
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
        <head><style>
        html, body, img { height: 100vh; display: block; margin: 0; padding: 0; border-width: 0; }
        img {
            width: 100%%; height: 100%%;
            object-fit: contain;
            margin-left: auto; margin-right: auto;
            max-width: 100vw; max-height: 100vh;
            top: 50vh; transform: translateY(-50%%);
            position: relative;
        }
        body.cover-fill img { object-fit: fill; }
        </style></head><body><img src="%s"/></body></html>
        '''

        def generic_cover():
            if self.book_metadata is not None:
                from calibre.ebooks.covers import create_cover
                mi = self.book_metadata
                return create_cover(mi.title, mi.authors, mi.series, mi.series_index)
            return BLANK_JPEG

        if input_fmt == 'epub':

            def image_callback(cover_image, wrapped_image):
                if cover_image:
                    image_callback.cover_data = self.raw_data(cover_image, decode=False)
                if wrapped_image and not getattr(image_callback, 'cover_data', None):
                    image_callback.cover_data = self.raw_data(wrapped_image, decode=False)

            def cover_path(action, data):
                if action == 'write_image':
                    cdata = getattr(image_callback, 'cover_data', None) or generic_cover()
                    data.write(cdata)

            if self.allow_no_cover and not has_epub_cover(self):
                return None, None
            raster_cover_name, titlepage_name = set_epub_cover(
                    self, cover_path, (lambda *a: None), options={'template':templ},
                    image_callback=image_callback)
        else:
            raster_cover_name = find_cover_image(self, strict=True)
            if raster_cover_name is None:
                if self.allow_no_cover:
                    return None, None
                item = self.generate_item(name='cover.jpeg', id_prefix='cover')
                raster_cover_name = self.href_to_name(item.get('href'), self.opf_name)
                with self.open(raster_cover_name, 'wb') as dest:
                    dest.write(generic_cover())
            if self.is_comic:
                return raster_cover_name, None
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

    def transform_html(self, name, virtualize_resources):
        style_xpath = XPath('//h:style')
        link_xpath = XPath('//h:a[@href]')
        img_xpath = XPath('//h:img[@src]')
        res_link_xpath = XPath('//h:link[@href]')
        root = self.parsed(name)
        head = ensure_head(root)
        changed = False
        for style in style_xpath(root):
            # Firefox flakes out sometimes when dynamically creating <style> tags,
            # so convert them to external stylesheets to ensure they never fail
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
                changed = True

        # Used for viewing images
        for img in img_xpath(root):
            img_name = self.href_to_name(img.get('src'), name)
            if img_name:
                img.set('data-calibre-src', img_name)
                changed = True

        # Disable non stylsheet link tags. This link will not be loaded by the
        # browser anyway and will causes the resource load check to hang
        for link in res_link_xpath(root):
            ltype = (link.get('type') or 'text/css').lower()
            rel = (link.get('rel') or 'stylesheet').lower()
            if ltype != 'text/css' or rel != 'stylesheet':
                link.attrib.clear()
                changed = True

        # Transform <style> and style=""
        if transform_inline_styles(self, name, transform_sheet=transform_sheet, transform_style=transform_declaration):
            changed = True

        if not virtualize_resources:
            link_uid = self.book_render_data['link_uid']
            link_replacer = create_link_replacer(self, link_uid, set())
            ltm = self.book_render_data['link_to_map']
            for a in link_xpath(root):
                href = link_replacer(name, a.get('href'))
                if href and href.startswith(link_uid):
                    a.set('href', 'javascript:void(0)')
                    parts = decode_url(href.split('|')[1])
                    lname, lfrag = parts[0], parts[1]
                    ltm.setdefault(lname, {}).setdefault(lfrag or '', set()).add(name)
                    a.set('data-' + link_uid, json.dumps({'name':lname, 'frag':lfrag}, ensure_ascii=False))
                    changed = True

        if changed:
            self.dirty(name)

    def transform_css(self, name):
        sheet = self.parsed(name)
        if transform_sheet(sheet):
            self.dirty(name)

    def transform_all(self, virtualize_resources):
        for name, mt in tuple(iteritems(self.mime_map)):
            mt = mt.lower()
            if mt in OEB_DOCS:
                self.transform_html(name, virtualize_resources)
        for name, mt in tuple(iteritems(self.mime_map)):
            mt = mt.lower()
            if mt in OEB_STYLES:
                self.transform_css(name)
        if virtualize_resources:
            self.virtualize_resources()

        ltm = self.book_render_data['link_to_map']
        for name, amap in iteritems(ltm):
            for k, v in tuple(iteritems(amap)):
                amap[k] = tuple(v)  # needed for JSON serialization

    def virtualize_resources(self):

        changed = set()
        link_uid = self.book_render_data['link_uid']
        xlink_xpath = XPath('//*[@xl:href]')
        link_xpath = XPath('//h:a[@href]')
        link_replacer = create_link_replacer(self, link_uid, changed)

        ltm = self.book_render_data['link_to_map']

        for name, mt in iteritems(self.mime_map):
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
                        lname, lfrag = parts[0], parts[1]
                        ltm.setdefault(lname, {}).setdefault(lfrag or '', set()).add(name)
                        a.set('data-' + link_uid, json.dumps({'name':lname, 'frag':lfrag}, ensure_ascii=False))
                    else:
                        a.set('target', '_blank')
                        a.set('rel', 'noopener noreferrer')
            elif mt == 'image/svg+xml':
                self.virtualized_names.add(name)
                xlink = XLINK('href')
                altered = False
                for elem in xlink_xpath(self.parsed(name)):
                    href = elem.get(xlink)
                    if not href.startswith('#'):
                        elem.set(xlink, link_replacer(name, href))
                        altered = True
                if altered:
                    changed.add(name)

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


known_tags = ('img', 'script', 'link', 'image', 'style')
discarded_tags = ('meta', 'base')


def serialize_elem(elem, nsmap):
    ns, name = split_name(elem.tag)
    nl = name.lower()
    if ns == EPUB_NS:
        ns, name = None, 'epub-' + name
    if nl in discarded_tags:
        # Filter out <meta> tags as they have unknown side-effects
        # Filter out <base> tags as the viewer uses <base> for URL resolution
        return
    if nl in known_tags:
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
    if is_py3:
        nsmap = defaultdict(count().__next__)
    else:
        nsmap = defaultdict(count().next)
    nsmap[XHTML_NS]
    tags = [serialize_elem(root, nsmap)]
    tree = [0]
    stack = [(root, tree)]
    while stack:
        elem, node = stack.pop()
        prev_child_node = None
        for child in elem.iterchildren():
            tag = getattr(child, 'tag', None)
            if tag is None or callable(tag):
                tail = getattr(child, 'tail', None)
                if tail:
                    if prev_child_node is None:
                        parent_node = node[-1]
                        parent_node = tags[parent_node]
                        parent_node['x'] = parent_node.get('x', '') + tail
                    else:
                        prev_child_node['l'] = prev_child_node.get('l', '') + tail
            else:
                cnode = serialize_elem(child, nsmap)
                if cnode is not None:
                    tags.append(cnode)
                    child_tree_node = [len(tags)-1]
                    node.append(child_tree_node)
                    stack.append((child, child_tree_node))
                    prev_child_node = cnode
    ns_map = [ns for ns, nsnum in sorted(iteritems(nsmap), key=lambda x: x[1])]
    return {'ns_map':ns_map, 'tag_map':tags, 'tree':tree}


def serialize_datetimes(d):
    for k in tuple(d):
        v = d[k]
        if isinstance(v, datetime):
            v = encode_datetime(v)
            d[k] = v


EPUB_FILE_TYPE_MAGIC = b'encoding=json+base64:\n'


def parse_annotation(annot):
    ts = annot['timestamp']
    if hasattr(ts, 'rstrip'):
        annot['timestamp'] = parse_iso8601(ts, assume_utc=True)
    return annot


def parse_annotations(raw):
    for annot in json_loads(raw):
        yield parse_annotation(annot)


def get_stored_annotations(container):
    raw = container.bookmark_data or b''
    if not raw:
        return
    if raw.startswith(EPUB_FILE_TYPE_MAGIC):
        raw = raw[len(EPUB_FILE_TYPE_MAGIC):].replace(b'\n', b'')
        for annot in parse_annotations(from_base64_bytes(raw)):
            yield annot
        return

    from calibre.ebooks.oeb.iterator.bookmarks import parse_bookmarks
    for bm in parse_bookmarks(raw):
        if bm['type'] == 'cfi' and isinstance(bm['pos'], unicode_type):
            spine_index = (1 + bm['spine']) * 2
            epubcfi = 'epubcfi(/{}/{})'.format(spine_index, bm['pos'].lstrip('/'))
            title = bm.get('title')
            if title and title != 'calibre_current_page_bookmark':
                yield {'type': 'bookmark', 'title': title, 'pos': epubcfi, 'pos_type': 'epubcfi', 'timestamp': EPOCH}
            else:
                yield {'type': 'last-read', 'pos': epubcfi, 'pos_type': 'epubcfi', 'timestamp': EPOCH}


def render(pathtoebook, output_dir, book_hash=None, serialize_metadata=False, extract_annotations=False, virtualize_resources=True):
    mi = None
    if serialize_metadata:
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.customize.ui import quick_metadata
        with lopen(pathtoebook, 'rb') as f, quick_metadata:
            mi = get_metadata(f, os.path.splitext(pathtoebook)[1][1:].lower())
    book_fmt, opfpath, input_fmt = extract_book(pathtoebook, output_dir, log=default_log)
    container = Container(
        book_fmt, opfpath, input_fmt, output_dir, book_hash=book_hash,
        save_bookmark_data=extract_annotations,
        book_metadata=mi, virtualize_resources=virtualize_resources
    )
    if serialize_metadata:
        from calibre.utils.serialize import json_dumps
        from calibre.ebooks.metadata.book.serialize import metadata_as_dict
        d = metadata_as_dict(mi)
        d.pop('cover_data', None)
        serialize_datetimes(d), serialize_datetimes(d.get('user_metadata', {}))
        with lopen(os.path.join(output_dir, 'calibre-book-metadata.json'), 'wb') as f:
            f.write(json_dumps(d))
    if extract_annotations:
        annotations = None
        if container.bookmark_data:
            annotations = json_dumps(tuple(get_stored_annotations(container)))
        if annotations:
            with lopen(os.path.join(output_dir, 'calibre-book-annotations.json'), 'wb') as f:
                f.write(annotations)


if __name__ == '__main__':
    render(sys.argv[-2], sys.argv[-1], serialize_metadata=True)
