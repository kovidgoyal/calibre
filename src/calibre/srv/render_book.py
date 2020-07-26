#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from functools import partial
from itertools import count
from math import ceil

from css_parser import replaceUrls
from css_parser.css import CSSRule
from lxml.etree import Comment

from calibre import detect_ncpus, force_unicode, prepare_string_for_xml
from calibre.constants import iswindows, plugins
from calibre.customize.ui import plugin_for_input_format
from calibre.ebooks import parse_css_length
from calibre.ebooks.css_transform_rules import StyleDeclaration
from calibre.ebooks.oeb.base import (
    OEB_DOCS, OEB_STYLES, OPF, XHTML, XHTML_NS, XLINK, XPath as _XPath,
    rewrite_links, urlunquote
)
from calibre.ebooks.oeb.iterator.book import extract_book
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.cover import (
    find_cover_image, find_cover_image_in_page, find_cover_page
)
from calibre.ebooks.oeb.polish.css import transform_inline_styles
from calibre.ebooks.oeb.polish.toc import from_xpaths, get_landmarks, get_toc
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.srv.metadata import encode_datetime
from calibre.srv.opts import grouper
from calibre.utils.date import EPOCH
from calibre.utils.filenames import rmtree
from calibre.utils.ipc.simple_worker import start_pipe_worker
from calibre.utils.logging import default_log
from calibre.utils.serialize import (
    json_dumps, json_loads, msgpack_dumps, msgpack_loads
)
from calibre.utils.short_uuid import uuid4
from polyglot.binary import (
    as_base64_unicode as encode_component, from_base64_bytes,
    from_base64_unicode as decode_component
)
from polyglot.builtins import as_bytes, iteritems, map, unicode_type
from polyglot.urllib import quote, urlparse

RENDER_VERSION = 1

BLANK_JPEG = b'\xff\xd8\xff\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03\x03\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\x08\n\n\t\x08\t\t\n\x0c\x0f\x0c\n\x0b\x0e\x0b\t\t\r\x11\r\x0e\x0f\x10\x10\x11\x10\n\x0c\x12\x13\x12\x10\x13\x0f\x10\x10\x10\xff\xc9\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xcc\x00\x06\x00\x10\x10\x05\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9'  # noqa
speedup = plugins['speedup'][0]


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
        try:
            purl = urlparse(url)
        except Exception:
            return url
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
absolute_font_sizes = {
    'xx-small': '0.5rem', 'x-small': '0.625rem', 'small': '0.8rem',
    'medium': '1rem',
    'large': '1.125rem', 'x-large': '1.5rem', 'xx-large': '2rem', 'xxx-large': '2.55rem'
}


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
            raw = prop.value
            afs = absolute_font_sizes.get(raw)
            if afs is not None:
                changed = True
                decl.change_property(prop, parent_prop, afs)
                continue
            l, unit = parse_css_length(raw)
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
    ans = 0

    fast = getattr(speedup, 'get_element_char_length', None)
    if fast is None:
        ignore_tags = frozenset('script style title noscript'.split())
        img_tags = ('img', 'svg')
        strip_space = re.compile(r'\s+')

        def count(elem):
            tag = getattr(elem, 'tag', count)
            if callable(tag):
                return len(strip_space.sub('', getattr(elem, 'tail', None) or ''))
            num = 0
            tname = tag.rpartition('}')[-1].lower()
            if elem.text and tname not in ignore_tags:
                num += len(strip_space.sub('', elem.text))
            if elem.tail:
                num += len(strip_space.sub('', elem.tail))
            if tname in img_tags:
                num += 1000
            return num
    else:
        def count(elem):
            tag = getattr(elem, 'tag', count)
            if callable(tag):
                return fast('', None, getattr(elem, 'tail', None))
            return fast(tag, elem.text, elem.tail)

    for body in root.iterchildren(XHTML('body')):
        ans += count(body)
        for elem in body.iterdescendants():
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


class SimpleContainer(ContainerBase):

    tweak_mode = True


def find_epub_cover(container):
    cover_image = find_cover_image(container)
    marked_title_page = find_cover_page(container)
    cover_image_in_first_page = None
    first_page_name = next(container.spine_names)[0]
    if not marked_title_page:
        cover_image_in_first_page = find_cover_image_in_page(container, first_page_name)

    has_epub_cover = cover_image or marked_title_page or cover_image_in_first_page
    if not has_epub_cover:
        return None, None
    if marked_title_page and cover_image:
        return marked_title_page, cover_image

    if marked_title_page:
        if cover_image:
            return marked_title_page, cover_image
        cover_image = find_cover_image_in_page(container, marked_title_page)
        if cover_image:
            return marked_title_page, cover_image
        return None, None

    if cover_image_in_first_page:
        return first_page_name, cover_image_in_first_page

    return None, None


def create_cover_page(container, input_fmt, is_comic, book_metadata=None):
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
        if book_metadata is not None:
            from calibre.ebooks.covers import create_cover
            mi = book_metadata
            return create_cover(mi.title, mi.authors, mi.series, mi.series_index)
        return BLANK_JPEG

    if input_fmt == 'epub':
        titlepage_name, raster_cover_name = find_epub_cover(container)
        if raster_cover_name and titlepage_name:
            raw = templ % prepare_string_for_xml(container.name_to_href(raster_cover_name, titlepage_name), True)
            with container.open(titlepage_name, 'wb') as f:
                f.write(raw.encode('utf-8'))
    else:
        raster_cover_name = find_cover_image(container, strict=True)
        if raster_cover_name is None:
            return None, None
        if is_comic:
            return raster_cover_name, None
        item = container.generate_item(name='titlepage.html', id_prefix='titlepage')
        titlepage_name = container.href_to_name(item.get('href'), container.opf_name)
        raw = templ % prepare_string_for_xml(container.name_to_href(raster_cover_name, titlepage_name), True)
        with container.open(titlepage_name, 'wb') as f:
            f.write(raw.encode('utf-8'))
        spine = container.opf_xpath('//opf:spine')[0]
        ref = spine.makeelement(OPF('itemref'), idref=item.get('id'))
        container.insert_into_xml(spine, ref, index=0)
    return raster_cover_name, titlepage_name


def transform_style_sheet(container, name, link_uid, virtualize_resources, virtualized_names):
    changed = False
    sheet = container.parsed(name)
    if virtualize_resources:
        changed_names = set()
        link_replacer = create_link_replacer(container, link_uid, changed_names)
        replaceUrls(sheet, partial(link_replacer, name))
        if name in changed_names:
            changed = True
            virtualized_names.add(name)
    if transform_sheet(sheet):
        changed = True
    if changed:
        raw = container.serialize_item(name)
    else:
        raw = container.raw_data(name, decode=False)
    raw = raw.lstrip()
    if not raw.startswith(b'@charset'):
        raw = b'@charset "UTF-8";\n' + raw
        changed = True
    if changed:
        with container.open(name, 'wb') as f:
            f.write(raw)


def transform_svg_image(container, name, link_uid, virtualize_resources, virtualized_names):
    if not virtualize_resources:
        return
    link_replacer = create_link_replacer(container, link_uid, set())
    xlink = XLINK('href')
    altered = False
    xlink_xpath = XPath('//*[@xl:href]')
    for elem in xlink_xpath(container.parsed(name)):
        href = elem.get(xlink)
        if not href.startswith('#'):
            elem.set(xlink, link_replacer(name, href))
            altered = True
    if altered:
        virtualized_names.add(name)
        container.dirty(name)
        container.commit_item(name)


def transform_html(container, name, virtualize_resources, link_uid, link_to_map, virtualized_names):
    link_xpath = XPath('//h:a[@href]')
    svg_link_xpath = XPath('//svg:a')
    img_xpath = XPath('//h:img[@src]')
    res_link_xpath = XPath('//h:link[@href]')
    root = container.parsed(name)
    changed_names = set()
    link_replacer = create_link_replacer(container, link_uid, changed_names)

    # Used for viewing images
    for img in img_xpath(root):
        img_name = container.href_to_name(img.get('src'), name)
        if img_name:
            img.set('data-calibre-src', img_name)

    # Disable non-stylesheet link tags. This link will not be loaded by the
    # browser anyway and will causes the resource load check to hang
    for link in res_link_xpath(root):
        ltype = (link.get('type') or 'text/css').lower()
        rel = (link.get('rel') or 'stylesheet').lower()
        if ltype != 'text/css' or rel != 'stylesheet':
            link.attrib.clear()

    def transform_and_virtualize_sheet(sheet):
        changed = transform_sheet(sheet)
        if virtualize_resources:
            replaceUrls(sheet, partial(link_replacer, name))
            if name in changed_names:
                virtualized_names.add(name)
                changed = True
        return changed

    # Transform <style> and style=""
    transform_inline_styles(container, name, transform_sheet=transform_and_virtualize_sheet, transform_style=transform_declaration)

    if virtualize_resources:
        virtualize_html(container, name, link_uid, link_to_map, virtualized_names)
    else:

        def handle_link(a, attr='href'):
            href = a.get(attr)
            if href:
                href = link_replacer(name, href)
            if href and href.startswith(link_uid):
                a.set(attr, 'javascript:void(0)')
                parts = decode_url(href.split('|')[1])
                lname, lfrag = parts[0], parts[1]
                link_to_map.setdefault(lname, {}).setdefault(lfrag or '', set()).add(name)
                a.set('data-' + link_uid, json.dumps({'name':lname, 'frag':lfrag}, ensure_ascii=False))

        for a in link_xpath(root):
            handle_link(a)
        xhref = XLINK('href')
        for a in svg_link_xpath(root):
            handle_link(a, xhref)

    shtml = html_as_json(root)
    with container.open(name, 'wb') as f:
        f.write(shtml)


class RenderManager(object):

    def __init__(self, max_workers):
        self.max_workers = max_workers

    def launch_worker(self):
        with lopen(os.path.join(self.tdir, '{}.json'.format(len(self.workers))), 'wb') as output:
            error = lopen(os.path.join(self.tdir, '{}.error'.format(len(self.workers))), 'wb')
            p = start_pipe_worker('from calibre.srv.render_book import worker_main; worker_main()', stdout=error, stderr=error)
            p.output_path = output.name
            p.error_path = error.name
        self.workers.append(p)

    def __enter__(self):
        self.workers = []
        self.tdir = PersistentTemporaryDirectory()
        return self

    def __exit__(self, *a):
        while self.workers:
            p = self.workers.pop()
            if p.poll() is not None:
                continue
            p.terminate()
            if not iswindows and p.poll() is None:
                time.sleep(0.02)
                if p.poll() is None:
                    p.kill()
        del self.workers
        try:
            rmtree(self.tdir)
        except EnvironmentError:
            time.sleep(0.1)
            try:
                rmtree(self.tdir)
            except EnvironmentError:
                pass
        del self.tdir

    def launch_workers(self, names, in_process_container):
        num_workers = min(detect_ncpus(), len(names))
        if self.max_workers:
            num_workers = min(num_workers, self.max_workers)
        if num_workers > 1:
            if len(names) < 3 or sum(os.path.getsize(in_process_container.name_path_map[n]) for n in names) < 128 * 1024:
                num_workers = 1
        if num_workers > 1:
            num_other_workers = num_workers - 1
            while len(self.workers) < num_other_workers:
                self.launch_worker()
        return num_workers

    def __call__(self, names, args, in_process_container):
        num_workers = len(self.workers) + 1
        if num_workers == 1:
            return [process_book_files(names, *args, container=in_process_container)]

        group_sz = int(ceil(len(names) / num_workers))
        groups = tuple(grouper(group_sz, names))
        for group, worker in zip(groups[:-1], self.workers):
            worker.stdin.write(as_bytes(msgpack_dumps((worker.output_path, group,) + args)))
            worker.stdin.flush(), worker.stdin.close()
            worker.job_sent = True

        for worker in self.workers:
            if not hasattr(worker, 'job_sent'):
                worker.stdin.write(b'_'), worker.stdin.flush(), worker.stdin.close()

        error = None
        results = [process_book_files(groups[-1], *args, container=in_process_container)]
        for worker in self.workers:
            if not hasattr(worker, 'job_sent'):
                worker.wait()
                continue
            if worker.wait() != 0:
                with lopen(worker.error_path, 'rb') as f:
                    error = f.read().decode('utf-8', 'replace')
            else:
                with lopen(worker.output_path, 'rb') as f:
                    results.append(msgpack_loads(f.read()))
        if error is not None:
            raise Exception('Render worker failed with error:\n' + error)
        return results


def worker_main():
    stdin = getattr(sys.stdin, 'buffer', sys.stdin)
    raw = stdin.read()
    if raw == b'_':
        return
    args = msgpack_loads(raw)
    result = process_book_files(*args[1:])
    with open(args[0], 'wb') as f:
        f.write(as_bytes(msgpack_dumps(result)))


def virtualize_html(container, name, link_uid, link_to_map, virtualized_names):

    changed = set()
    link_xpath = XPath('//h:a[@href]')
    svg_link_xpath = XPath('//svg:a')
    link_replacer = create_link_replacer(container, link_uid, changed)

    virtualized_names.add(name)
    root = container.parsed(name)
    rewrite_links(root, partial(link_replacer, name))

    def handle_link(a, attr='href'):
        href = a.get(attr) or ''
        if href.startswith(link_uid):
            a.set(attr, 'javascript:void(0)')
            parts = decode_url(href.split('|')[1])
            lname, lfrag = parts[0], parts[1]
            link_to_map.setdefault(lname, {}).setdefault(lfrag or '', set()).add(name)
            a.set('data-' + link_uid, json.dumps({'name':lname, 'frag':lfrag}, ensure_ascii=False))
        elif href:
            a.set('target', '_blank')
            a.set('rel', 'noopener noreferrer')

    for a in link_xpath(root):
        handle_link(a)
    xhref = XLINK('href')
    for a in svg_link_xpath(root):
        handle_link(a, xhref)

    return name in changed


def process_book_files(names, container_dir, opfpath, virtualize_resources, link_uid, data_for_clone, container=None):
    if container is None:
        container = SimpleContainer(container_dir, opfpath, default_log, clone_data=data_for_clone)
        container.cloned = False
    link_to_map = {}
    html_data = {}
    virtualized_names = set()
    for name in names:
        if name is None:
            continue
        mt = container.mime_map[name].lower()
        if mt in OEB_DOCS:
            root = container.parsed(name)
            html_data[name] = {
                'length': get_length(root),
                'has_maths': check_for_maths(root),
                'anchor_map': anchor_map(root)
            }
            transform_html(container, name, virtualize_resources, link_uid, link_to_map, virtualized_names)
        elif mt in OEB_STYLES:
            transform_style_sheet(container, name, link_uid, virtualize_resources, virtualized_names)
        elif mt == 'image/svg+xml':
            transform_svg_image(container, name, link_uid, virtualize_resources, virtualized_names)
    return link_to_map, html_data, virtualized_names


def process_exploded_book(
    book_fmt, opfpath, input_fmt, tdir, render_manager, log=None, book_hash=None, save_bookmark_data=False,
    book_metadata=None, virtualize_resources=True
):
    log = log or default_log
    container = SimpleContainer(tdir, opfpath, log)
    input_plugin = plugin_for_input_format(input_fmt)
    is_comic = bool(getattr(input_plugin, 'is_image_collection', False))

    def needs_work(mt):
        return mt in OEB_STYLES or mt in OEB_DOCS or mt == 'image/svg+xml'

    def work_priority(name):
        # ensure workers with large files or stylesheets
        # have the less names
        size = os.path.getsize(container.name_path_map[name]),
        is_html = container.mime_map.get(name) in OEB_DOCS
        return (0 if is_html else 1), size

    if not is_comic:
        render_manager.launch_workers(tuple(n for n, mt in iteritems(container.mime_map) if needs_work(mt)), container)

    bookmark_data = None
    if save_bookmark_data:
        bm_file = 'META-INF/calibre_bookmarks.txt'
        if container.exists(bm_file):
            with container.open(bm_file, 'rb') as f:
                bookmark_data = f.read()

    # We do not add zero byte sized files as the IndexedDB API in the
    # browser has no good way to distinguish between zero byte files and
    # load failures.
    excluded_names = {
        name for name, mt in iteritems(container.mime_map) if
        name == container.opf_name or mt == guess_type('a.ncx') or name.startswith('META-INF/') or
        name == 'mimetype' or not container.has_name_and_is_not_empty(name)}
    raster_cover_name, titlepage_name = create_cover_page(container, input_fmt.lower(), is_comic, book_metadata)

    toc = get_toc(container, verify_destinations=False).to_dict(count())
    if not toc or not toc.get('children'):
        toc = from_xpaths(container, ['//h:h1', '//h:h2', '//h:h3']).to_dict(count())
    spine = [name for name, is_linear in container.spine_names]
    spineq = frozenset(spine)
    landmarks = [l for l in get_landmarks(container) if l['dest'] in spineq]

    page_progression_direction = None
    try:
        page_progression_direction = container.opf_xpath('//opf:spine/@page-progression-direction')[0]
    except IndexError:
        pass

    book_render_data = {
        'version': RENDER_VERSION,
        'toc':toc,
        'book_format': book_fmt,
        'spine':spine,
        'link_uid': uuid4(),
        'book_hash': book_hash,
        'is_comic': is_comic,
        'raster_cover_name': raster_cover_name,
        'title_page_name': titlepage_name,
        'has_maths': False,
        'total_length': 0,
        'spine_length': 0,
        'toc_anchor_map': toc_anchor_map(toc),
        'landmarks': landmarks,
        'link_to_map': {},
        'page_progression_direction': page_progression_direction,
    }

    names = sorted(
        (n for n, mt in iteritems(container.mime_map) if needs_work(mt)),
        key=work_priority)

    results = render_manager(
        names, (
            tdir, opfpath, virtualize_resources, book_render_data['link_uid'], container.data_for_clone()
        ), container
    )
    ltm = book_render_data['link_to_map']
    html_data = {}
    virtualized_names = set()

    def merge_ltm(dest, src):
        for k, v in iteritems(src):
            if k in dest:
                dest[k] |= v
            else:
                dest[k] = v

    for link_to_map, hdata, vnames in results:
        html_data.update(hdata)
        virtualized_names |= vnames
        for k, v in iteritems(link_to_map):
            if k in ltm:
                merge_ltm(ltm[k], v)
            else:
                ltm[k] = v

    def manifest_data(name):
        mt = (container.mime_map.get(name) or 'application/octet-stream').lower()
        ans = {
            'size':os.path.getsize(container.name_path_map[name]),
            'is_virtualized': name in virtualized_names,
            'mimetype':mt,
            'is_html': mt in OEB_DOCS,
        }
        if ans['is_html']:
            data = html_data[name]
            ans['length'] = l = data['length']
            book_render_data['total_length'] += l
            if name in book_render_data['spine']:
                book_render_data['spine_length'] += l
            ans['has_maths'] = hm = data['has_maths']
            if hm:
                book_render_data['has_maths'] = True
            ans['anchor_map'] = data['anchor_map']
        return ans

    book_render_data['files'] = {name:manifest_data(name) for name in set(container.name_path_map) - excluded_names}
    container.commit()

    for name in excluded_names:
        os.remove(container.name_path_map[name])

    ltm = book_render_data['link_to_map']
    for name, amap in iteritems(ltm):
        for k, v in tuple(iteritems(amap)):
            amap[k] = tuple(v)  # needed for JSON serialization

    data = as_bytes(json.dumps(book_render_data, ensure_ascii=False))
    with lopen(os.path.join(container.root, 'calibre-book-manifest.json'), 'wb') as f:
        f.write(data)

    return container, bookmark_data


def split_name(name):
    l, r = name.partition('}')[::2]
    if r:
        return l[1:], r
    return None, l


known_tags = ('img', 'script', 'link', 'image', 'style')
discarded_tags = ('meta', 'base')


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


def html_as_json(root):
    ns, name = split_name(root.tag)
    if ns not in (None, XHTML_NS):
        raise ValueError('HTML tag must be in empty or XHTML namespace')
    ensure_body(root)
    pl, err = plugins['html_as_json']
    if err:
        raise SystemExit('Failed to load html_as_json plugin with error: {}'.format(err))
    try:
        serialize = pl.serialize
    except AttributeError:
        raise SystemExit('You are running calibre from source, you need to also update the main calibre installation to version >=4.3')
    for child in tuple(root.iterchildren('*')):
        if child.tag.partition('}')[-1] not in ('head', 'body'):
            root.remove(child)
    root.text = root.tail = None
    return serialize(root, Comment)


def serialize_datetimes(d):
    for k in tuple(d):
        v = d[k]
        if isinstance(v, datetime):
            v = encode_datetime(v)
            d[k] = v


EPUB_FILE_TYPE_MAGIC = b'encoding=json+base64:\n'


def get_stored_annotations(container, bookmark_data):
    raw = bookmark_data or b''
    if not raw:
        return
    if raw.startswith(EPUB_FILE_TYPE_MAGIC):
        raw = raw[len(EPUB_FILE_TYPE_MAGIC):].replace(b'\n', b'')
        for annot in json_loads(from_base64_bytes(raw)):
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


def render(pathtoebook, output_dir, book_hash=None, serialize_metadata=False, extract_annotations=False, virtualize_resources=True, max_workers=1):
    pathtoebook = os.path.abspath(pathtoebook)
    with RenderManager(max_workers) as render_manager:
        mi = None
        if serialize_metadata:
            from calibre.ebooks.metadata.meta import get_metadata
            from calibre.customize.ui import quick_metadata
            with lopen(pathtoebook, 'rb') as f, quick_metadata:
                mi = get_metadata(f, os.path.splitext(pathtoebook)[1][1:].lower())
        book_fmt, opfpath, input_fmt = extract_book(pathtoebook, output_dir, log=default_log)
        container, bookmark_data = process_exploded_book(
            book_fmt, opfpath, input_fmt, output_dir, render_manager,
            book_hash=book_hash, save_bookmark_data=extract_annotations,
            book_metadata=mi, virtualize_resources=virtualize_resources
        )
        if serialize_metadata:
            from calibre.ebooks.metadata.book.serialize import metadata_as_dict
            d = metadata_as_dict(mi)
            d.pop('cover_data', None)
            serialize_datetimes(d), serialize_datetimes(d.get('user_metadata', {}))
            with lopen(os.path.join(output_dir, 'calibre-book-metadata.json'), 'wb') as f:
                f.write(json_dumps(d))
        if extract_annotations:
            annotations = None
            if bookmark_data:
                annotations = json_dumps(tuple(get_stored_annotations(container, bookmark_data)))
            if annotations:
                with lopen(os.path.join(output_dir, 'calibre-book-annotations.json'), 'wb') as f:
                    f.write(annotations)


def render_for_viewer(path, out_dir, book_hash):
    return render(
        path, out_dir, book_hash=book_hash, serialize_metadata=True,
        extract_annotations=True, virtualize_resources=False, max_workers=0
    )


def viewer_main():
    stdin = getattr(sys.stdin, 'buffer', sys.stdin)
    args = msgpack_loads(stdin.read())
    render_for_viewer(*args)


class Profiler(object):

    def __init__(self):
        try:
            import cProfile as profile
        except ImportError:
            import profile
        self.profile = profile.Profile()

    def __enter__(self):
        self.profile.enable()

    def __exit__(self, *a):
        self.profile.disable()
        self.profile.create_stats()
        import pstats
        stats = pstats.Stats(self.profile)
        stats.sort_stats('cumulative')
        stats.print_stats(.05)


def profile():
    from calibre.ptempfile import TemporaryDirectory
    path = sys.argv[-1]
    with TemporaryDirectory() as tdir, Profiler():
        return render(
            path, tdir, serialize_metadata=True,
            extract_annotations=True, virtualize_resources=False, max_workers=1
        )


def develop():
    from calibre.ptempfile import TemporaryDirectory
    path = sys.argv[-1]
    with TemporaryDirectory() as tdir:
        return render(
            path, tdir, serialize_metadata=True,
            extract_annotations=True, virtualize_resources=False, max_workers=1
        )


if __name__ == '__main__':
    develop()
