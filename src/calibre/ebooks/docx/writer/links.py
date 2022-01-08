#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import posixpath, re
from uuid import uuid4

from calibre.ebooks.oeb.base import urlquote
from calibre.utils.filenames import ascii_text
from polyglot.urllib import urlparse


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


class TOCItem:

    def __init__(self, title, bmark, level):
        self.title, self.bmark, self.level = title, bmark, level
        self.is_first = self.is_last = False

    def serialize(self, body, makeelement):
        p = makeelement(body, 'w:p', append=False)
        ppr = makeelement(p, 'w:pPr')
        makeelement(ppr, 'w:pStyle', w_val="Normal")
        makeelement(ppr, 'w:ind', w_left='0', w_firstLineChars='0', w_firstLine='0', w_leftChars=str(200 * self.level))
        if self.is_first:
            makeelement(ppr, 'w:pageBreakBefore', w_val='off')
            r = makeelement(p, 'w:r')
            makeelement(r, 'w:fldChar', w_fldCharType='begin')
            r = makeelement(p, 'w:r')
            makeelement(r, 'w:instrText').text = r' TOC \h '
            r[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            r = makeelement(p, 'w:r')
            makeelement(r, 'w:fldChar', w_fldCharType='separate')
        hl = makeelement(p, 'w:hyperlink', w_anchor=self.bmark)
        r = makeelement(hl, 'w:r')
        rpr = makeelement(r, 'w:rPr')
        makeelement(rpr, 'w:color', w_val='0000FF', w_themeColor='hyperlink')
        makeelement(rpr, 'w:u', w_val='single')
        makeelement(r, 'w:t').text = self.title
        if self.is_last:
            r = makeelement(p, 'w:r')
            makeelement(r, 'w:fldChar', w_fldCharType='end')
        body.insert(0, p)


def sanitize_bookmark_name(base):
    # Max length allowed by Word appears to be 40, we use 32 to leave some
    # space for making the name unique
    return re.sub(r'[^0-9a-zA-Z]', '_', ascii_text(base))[:32].rstrip('_')


class LinksManager:

    def __init__(self, namespace, document_relationships, log):
        self.namespace = namespace
        self.log = log
        self.document_relationships = document_relationships
        self.top_anchor = str(uuid4().hex)
        self.anchor_map = {}
        self.used_bookmark_names = set()
        self.bmark_id = 0
        self.document_hrefs = set()
        self.external_links = {}
        self.toc = []

    def bookmark_for_anchor(self, anchor, current_item, html_tag):
        key = (current_item.href, anchor)
        if key in self.anchor_map:
            return self.anchor_map[key]
        if anchor == self.top_anchor:
            name = ('Top of %s' % posixpath.basename(current_item.href))
            self.document_hrefs.add(current_item.href)
        else:
            name = start_text(html_tag).strip() or anchor
        name = sanitize_bookmark_name(name)
        i, bname = 0, name
        while name in self.used_bookmark_names:
            i += 1
            name  = bname + ('_%d' % i)
        self.anchor_map[key] = name
        self.used_bookmark_names.add(name)
        return name

    @property
    def bookmark_id(self):
        self.bmark_id += 1
        return self.bmark_id

    def serialize_hyperlink(self, parent, link):
        item, url, tooltip = link
        purl = urlparse(url)
        href = purl.path

        def make_link(parent, anchor=None, id=None, tooltip=None):
            kw = {}
            if anchor is not None:
                kw['w_anchor'] = anchor
            elif id is not None:
                kw['r_id'] = id
            if tooltip:
                kw['w_tooltip'] = tooltip
            return self.namespace.makeelement(parent, 'w:hyperlink', **kw)

        if not purl.scheme:
            href = item.abshref(href)
            if href not in self.document_hrefs:
                href = urlquote(href)
            if href in self.document_hrefs:
                key = (href, purl.fragment or self.top_anchor)
                if key in self.anchor_map:
                    bmark = self.anchor_map[key]
                else:
                    bmark = self.anchor_map[(href, self.top_anchor)]
                return make_link(parent, anchor=bmark, tooltip=tooltip)
            else:
                self.log.warn('Ignoring internal hyperlink with href (%s) pointing to unknown destination' % url)
        if purl.scheme in {'http', 'https', 'ftp'}:
            if url not in self.external_links:
                self.external_links[url] = self.document_relationships.add_relationship(url, self.namespace.names['LINKS'], target_mode='External')
            return make_link(parent, id=self.external_links[url], tooltip=tooltip)
        return parent

    def process_toc_node(self, toc, level=0):
        href = toc.href
        if href:
            purl = urlparse(href)
            href = purl.path
            if href in self.document_hrefs:
                key = (href, purl.fragment or self.top_anchor)
                if key in self.anchor_map:
                    bmark = self.anchor_map[key]
                else:
                    bmark = self.anchor_map[(href, self.top_anchor)]
                self.toc.append(TOCItem(toc.title, bmark, level))
        for child in toc:
            self.process_toc_node(child, level+1)

    def process_toc_links(self, oeb):
        self.toc = []
        has_toc = oeb.toc and oeb.toc.count() > 1
        if not has_toc:
            return
        for child in oeb.toc:
            self.process_toc_node(child)
        if self.toc:
            self.toc[0].is_first = True
            self.toc[-1].is_last = True

    def serialize_toc(self, body, primary_heading_style):
        pbb = body[0].xpath('//*[local-name()="pageBreakBefore"]')[0]
        pbb.set('{%s}val' % self.namespace.namespaces['w'], 'on')
        for block in reversed(self.toc):
            block.serialize(body, self.namespace.makeelement)
        title = __('Table of Contents')
        makeelement = self.namespace.makeelement
        p = makeelement(body, 'w:p', append=False)
        ppr = makeelement(p, 'w:pPr')
        if primary_heading_style is not None:
            makeelement(ppr, 'w:pStyle', w_val=primary_heading_style.id)
        makeelement(ppr, 'w:pageBreakBefore', w_val='off')
        makeelement(makeelement(p, 'w:r'), 'w:t').text = title
        body.insert(0, p)
