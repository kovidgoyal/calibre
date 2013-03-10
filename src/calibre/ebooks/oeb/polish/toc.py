#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from urlparse import urlparse

from lxml import etree

from calibre.ebooks.oeb.base import XPath
from calibre.ebooks.oeb.polish.container import guess_type

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

    def iterdescendants(self):
        for child in self:
            yield child
            for gc in child.iterdescendants():
                yield gc

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

def get_toc(container, verify_destinations=True):
    toc = container.opf_xpath('//opf:spine/@toc')
    if toc:
        toc = container.manifest_id_map.get(toc[0], None)
    if not toc:
        ncx = guess_type('a.ncx')
        toc = container.manifest_type_map.get(ncx, [None])[0]
    if not toc:
        return None
    ans = parse_ncx(container, toc)
    if verify_destinations:
        verify_toc_destinations(container, ans)
    return ans


