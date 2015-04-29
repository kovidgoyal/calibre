#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import posixpath
from uuid import uuid4
from urlparse import urlparse


def start_text(tag, prefix_len=0, top_level=True):
    ans = tag.text or ''
    limit = 50 - prefix_len
    if len(ans) < limit:
        for child in tag.iterchildren('*'):
            ans += start_text(child, len(ans), top_level=False) + (child.tail or '')
            if len(ans) >= limit:
                break
    if top_level and len(ans) > limit:
        ans = ans[:limit] + '...'
    return ans

class LinksManager(object):

    def __init__(self, namespace, document_relationships):
        self.namespace = namespace
        self.docment_relationships = document_relationships
        self.top_anchor = type('')(uuid4().hex)
        self.anchor_map = {}
        self.used_bookmark_names = set()
        self.bmark_id = 0
        self.document_hrefs = set()
        self.external_links = {}

    def bookmark_for_anchor(self, anchor, current_item, html_tag):
        key = (current_item.href, anchor)
        if key in self.anchor_map:
            return self.anchor_map[key]
        if anchor == self.top_anchor:
            name = ('Top of %s' % posixpath.basename(current_item.href))
            self.document_hrefs.add(current_item.href)
        else:
            name = start_text(html_tag).strip() or anchor
        i, bname = 0, name
        while name in self.used_bookmark_names:
            i += 1
            name  = bname + (' %d' % i)
        self.anchor_map[key] = name
        return name

    @property
    def bookmark_id(self):
        self.bmark_id += 1
        return self.bmark_id

    def serialize_hyperlink(self, parent, link):
        item, url, tooltip = link
        purl = urlparse(url)
        href = purl.path
        if not purl.scheme:
            href = item.abshref(href)
            if href in self.document_hrefs:
                key = (href, purl.fragment or self.top_anchor)
                if key in self.anchor_map:
                    bmark = self.anchor_map[key]
                else:
                    bmark = self.anchor_map[(href, self.top_anchor)]
                return self.namespace.makeelement(parent, 'w:hyperlink', w_anchor=bmark, w_tooltip=tooltip or '')
        if purl.scheme in {'http', 'https', 'ftp'}:
            if url not in self.external_links:
                self.external_links[url] = self.docment_relationships.add_relationship(url, self.namespace.names['LINKS'], target_mode='External')
            return self.namespace.makeelement(parent, 'w:hyperlink', r_id=self.external_links[url], w_tooltip=tooltip or '')
        return parent
