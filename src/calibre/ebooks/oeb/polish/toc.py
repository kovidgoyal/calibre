#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from urlparse import urlparse
from collections import deque
from functools import partial

from lxml import etree

from calibre import __version__
from calibre.ebooks.oeb.base import XPath, uuid_id, xml2text, NCX, NCX_NS, XML, XHTML
from calibre.ebooks.oeb.polish.container import guess_type
from calibre.utils.localization import get_lang, canonicalize_lang, lang_as_iso639_1

ns = etree.FunctionNamespace('calibre_xpath_extensions')
ns.prefix = 'calibre'
ns['lower-case'] = lambda c, x: x.lower() if hasattr(x, 'lower') else x


class TOC(object):

    def __init__(self, title=None, dest=None, frag=None):
        self.title, self.dest, self.frag = title, dest, frag
        self.dest_exists = self.dest_error = None
        if self.title: self.title = self.title.strip()
        self.parent = None
        self.children = []

    def add(self, title, dest, frag=None):
        c = TOC(title, dest, frag)
        self.children.append(c)
        c.parent = self
        return c

    def __iter__(self):
        for c in self.children:
            yield c

    def __len__(self):
        return len(self.children)

    def iterdescendants(self):
        for child in self:
            yield child
            for gc in child.iterdescendants():
                yield gc

    @property
    def depth(self):
        """The maximum depth of the navigation tree rooted at this node."""
        try:
            return max(node.depth for node in self) + 1
        except ValueError:
            return 1

    def get_lines(self, lvl=0):
        frag = ('#'+self.frag) if self.frag else ''
        ans = [(u'\t'*lvl) + u'TOC: %s --> %s%s'%(self.title, self.dest, frag)]
        for child in self:
            ans.extend(child.get_lines(lvl+1))
        return ans

    def __str__(self):
        return b'\n'.join([x.encode('utf-8') for x in self.get_lines()])

def child_xpath(tag, name):
    return tag.xpath('./*[calibre:lower-case(local-name()) = "%s"]'%name)


def add_from_navpoint(container, navpoint, parent, ncx_name):
    dest = frag = text = None
    nl = child_xpath(navpoint, 'navlabel')
    if nl:
        nl = nl[0]
        text = ''
        for txt in child_xpath(nl, 'text'):
            text += etree.tostring(txt, method='text',
                    encoding=unicode, with_tail=False)
    content = child_xpath(navpoint, 'content')
    if content:
        content = content[0]
        href = content.get('src', None)
        if href:
            dest = container.href_to_name(href, base=ncx_name)
            frag = urlparse(href).fragment or None
    return parent.add(text or None, dest or None, frag or None)


def process_ncx_node(container, node, toc_parent, ncx_name):
    for navpoint in node.xpath('./*[calibre:lower-case(local-name()) = "navpoint"]'):
        child = add_from_navpoint(container, navpoint, toc_parent, ncx_name)
        if child is not None:
            process_ncx_node(container, navpoint, child, ncx_name)


def parse_ncx(container, ncx_name):
    root = container.parsed(ncx_name)
    toc_root = TOC()
    navmaps = root.xpath('//*[calibre:lower-case(local-name()) = "navmap"]')
    if navmaps:
        process_ncx_node(container, navmaps[0], toc_root, ncx_name)
    toc_root.lang = toc_root.uid = None
    for attr, val in root.attrib.iteritems():
        if attr.endswith('lang'):
            toc_root.lang = unicode(val)
            break
    for uid in root.xpath('//*[calibre:lower-case(local-name()) = "meta" and @name="dtb:uid"]/@content'):
        if uid:
            toc_root.uid = unicode(uid)
            break
    return toc_root


def verify_toc_destinations(container, toc):
    anchor_map = {}
    anchor_xpath = XPath('//*/@id|//h:a/@name')
    for item in toc.iterdescendants():
        name = item.dest
        if not name:
            item.dest_exists = False
            item.dest_error = _('No file named %s exists')%name
            continue
        try:
            root = container.parsed(name)
        except KeyError:
            item.dest_exists = False
            item.dest_error = _('No file named %s exists')%name
            continue
        if not hasattr(root, 'xpath'):
            item.dest_exists = False
            item.dest_error = _('No HTML file named %s exists')%name
            continue
        if not item.frag:
            item.dest_exists = True
            continue
        if name not in anchor_map:
            anchor_map[name] = frozenset(anchor_xpath(root))
        item.dest_exists = item.frag in anchor_map[name]
        if not item.dest_exists:
            item.dest_error = _(
                'The anchor %(a)s does not exist in file %(f)s')%dict(
                a=item.frag, f=name)


def find_existing_toc(container):
    toc = container.opf_xpath('//opf:spine/@toc')
    if toc:
        toc = container.manifest_id_map.get(toc[0], None)
    if not toc:
        ncx = guess_type('a.ncx')
        toc = container.manifest_type_map.get(ncx, [None])[0]
    if not toc:
        return None
    return toc


def get_toc(container, verify_destinations=True):
    toc = find_existing_toc(container)
    if toc is None:
        ans = TOC()
        ans.lang = ans.uid = None
        return ans
    ans = parse_ncx(container, toc)
    if verify_destinations:
        verify_toc_destinations(container, ans)
    return ans

def ensure_id(elem):
    if elem.tag == XHTML('a'):
        anchor = elem.get('name', None)
        if anchor:
            return False, anchor
    elem_id = elem.get('id', None)
    if elem_id:
        return False, elem_id
    elem.set('id', uuid_id())
    return True, elem.get('id')

def elem_to_toc_text(elem):
    text = xml2text(elem).strip()
    if not text:
        text = elem.get('title', '')
    if not text:
        text = elem.get('alt', '')
    text = re.sub(r'\s+', ' ', text.strip())
    text = text[:1000].strip()
    return text

def from_xpaths(container, xpaths):
    tocroot = TOC()
    xpaths = [XPath(xp) for xp in xpaths]
    level_prev = {i+1:None for i in xrange(len(xpaths))}
    level_prev[0] = tocroot

    for spinepath in container.spine_items:
        name = container.abspath_to_name(spinepath)
        root = container.parsed(name)
        level_item_map = {i+1:frozenset(xp(root)) for i, xp in enumerate(xpaths)}
        item_level_map = {e:i for i, elems in level_item_map.iteritems() for e in elems}
        item_dirtied = False

        for item in root.iterdescendants(etree.Element):
            lvl = plvl = item_level_map.get(item, None)
            if lvl is None:
                continue
            parent = None
            while parent is None:
                plvl -= 1
                parent = level_prev[plvl]
            lvl = plvl + 1
            dirtied, elem_id = ensure_id(item)
            text = elem_to_toc_text(item)
            item_dirtied = dirtied or item_dirtied
            toc = parent.add(text, name, elem_id)
            toc.dest_exists = True
            level_prev[lvl] = toc
            for i in xrange(lvl+1, len(xpaths)+1):
                level_prev[i] = None

        if item_dirtied:
            container.commit_item(name, keep_parsed=True)

    return tocroot

def add_id(container, name, loc):
    root = container.parsed(name)
    body = root.xpath('//*[local-name()="body"]')[0]
    locs = deque(loc)
    node = body
    while locs:
        children = tuple(node.iterchildren(etree.Element))
        node = children[locs[0]]
        locs.popleft()
    node.set('id', node.get('id', uuid_id()))
    container.commit_item(name, keep_parsed=True)
    return node.get('id')


def create_ncx(toc, to_href, btitle, lang, uid):
    lang = lang.replace('_', '-')
    ncx = etree.Element(NCX('ncx'),
        attrib={'version': '2005-1', XML('lang'): lang},
        nsmap={None: NCX_NS})
    head = etree.SubElement(ncx, NCX('head'))
    etree.SubElement(head, NCX('meta'),
        name='dtb:uid', content=unicode(uid))
    etree.SubElement(head, NCX('meta'),
        name='dtb:depth', content=str(toc.depth))
    generator = ''.join(['calibre (', __version__, ')'])
    etree.SubElement(head, NCX('meta'),
        name='dtb:generator', content=generator)
    etree.SubElement(head, NCX('meta'), name='dtb:totalPageCount', content='0')
    etree.SubElement(head, NCX('meta'), name='dtb:maxPageNumber', content='0')
    title = etree.SubElement(ncx, NCX('docTitle'))
    text = etree.SubElement(title, NCX('text'))
    text.text = btitle
    navmap = etree.SubElement(ncx, NCX('navMap'))
    spat = re.compile(r'\s+')

    def process_node(xml_parent, toc_parent, play_order=0):
        for child in toc_parent:
            play_order += 1
            point = etree.SubElement(xml_parent, NCX('navPoint'), id=uuid_id(),
                            playOrder=str(play_order))
            label = etree.SubElement(point, NCX('navLabel'))
            title = child.title
            if title:
                title = spat.sub(' ', title)
            etree.SubElement(label, NCX('text')).text = title
            if child.dest:
                href = to_href(child.dest)
                if child.frag:
                    href += '#'+child.frag
                etree.SubElement(point, NCX('content'), src=href)
            process_node(point, child, play_order)

    process_node(navmap, toc)
    return ncx


def commit_toc(container, toc, lang=None, uid=None):
    tocname = find_existing_toc(container)
    if tocname is None:
        item = container.generate_item('toc.ncx', id_prefix='toc')
        tocname = container.href_to_name(item.get('href'),
                                         base=container.opf_name)
    if not lang:
        lang = get_lang()
        for l in container.opf_xpath('//dc:language'):
            l = canonicalize_lang(xml2text(l).strip())
            if l:
                lang = l
                lang = lang_as_iso639_1(l) or l
                break
    lang = lang_as_iso639_1(lang) or lang
    if not uid:
        uid = uuid_id()
        eid = container.opf.get('unique-identifier', None)
        if eid:
            m = container.opf_xpath('//*[@id="%s"]'%eid)
            if m:
                uid = xml2text(m[0])

    title = _('Table of Contents')
    m = container.opf_xpath('//dc:title')
    if m:
        x = xml2text(m[0]).strip()
        title = x or title

    to_href = partial(container.name_to_href, base=tocname)
    root = create_ncx(toc, to_href, title, lang, uid)
    container.replace(tocname, root)
    container.pretty_print.add(tocname)

