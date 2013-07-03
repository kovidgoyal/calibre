#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from urlparse import urlparse
from urllib2 import unquote

from calibre.ebooks.pdf.render.common import Array, Name, Dictionary, String

class Destination(Array):

    def __init__(self, start_page, pos, get_pageref):
        pnum = start_page + pos['column']
        try:
            pref = get_pageref(pnum)
        except IndexError:
            pref = get_pageref(pnum-1)
        super(Destination, self).__init__([
            pref, Name('XYZ'), pos['left'], pos['top'], None
        ])

class Links(object):

    def __init__(self, pdf, mark_links, page_size):
        self.anchors = {}
        self.links = []
        self.start = {'top':page_size[1], 'column':0, 'left':0}
        self.pdf = pdf
        self.mark_links = mark_links

    def add(self, base_path, start_page, links, anchors):
        path = os.path.normcase(os.path.abspath(base_path))
        self.anchors[path] = a = {}
        a[None] = Destination(start_page, self.start, self.pdf.get_pageref)
        for anchor, pos in anchors.iteritems():
            a[anchor] = Destination(start_page, pos, self.pdf.get_pageref)
        for link in links:
            href, page, rect = link
            p, frag = href.partition('#')[0::2]
            try:
                pref = self.pdf.get_pageref(page).obj
            except IndexError:
                try:
                    pref = self.pdf.get_pageref(page-1).obj
                except IndexError:
                    self.pdf.debug('Unable to find page for link: %r, ignoring it' % link)
                    continue
                self.pdf.debug('The link %s points to non-existent page, moving it one page back' % href)
            self.links.append(((path, p, frag or None), pref, Array(rect)))

    def add_links(self):
        for link in self.links:
            path, href, frag = link[0]
            page, rect = link[1:]
            combined_path = os.path.normcase(os.path.abspath(os.path.join(os.path.dirname(path), *unquote(href).split('/'))))
            is_local = not href or combined_path in self.anchors
            annot = Dictionary({
                'Type':Name('Annot'), 'Subtype':Name('Link'),
                'Rect':rect, 'Border':Array([0,0,0]),
            })
            if self.mark_links:
                annot.update({'Border':Array([16, 16, 1]), 'C':Array([1.0, 0,
                                                                      0])})
            if is_local:
                path = combined_path if href else path
                try:
                    annot['Dest'] = self.anchors[path][frag]
                except KeyError:
                    try:
                        annot['Dest'] = self.anchors[path][None]
                    except KeyError:
                        pass
            else:
                url = href + (('#'+frag) if frag else '')
                purl = urlparse(url)
                if purl.scheme and purl.scheme != 'file':
                    action = Dictionary({
                        'Type':Name('Action'), 'S':Name('URI'),
                    })
                    # Do not try to normalize/quote/unquote this URL as if it
                    # has a query part, it will get corrupted
                    action['URI'] = String(url)
                    annot['A'] = action
            if 'A' in annot or 'Dest' in annot:
                if 'Annots' not in page:
                    page['Annots'] = Array()
                page['Annots'].append(self.pdf.objects.add(annot))
            else:
                self.pdf.debug('Could not find destination for link: %s in file %s'%
                               (href, path))

    def add_outline(self, toc):
        parent = Dictionary({'Type':Name('Outlines')})
        parentref = self.pdf.objects.add(parent)
        self.process_children(toc, parentref, parent_is_root=True)
        self.pdf.catalog.obj['Outlines'] = parentref

    def process_children(self, toc, parentref, parent_is_root=False):
        childrefs = []
        for child in toc:
            childref = self.process_toc_item(child, parentref)
            if childref is None:
                continue
            if childrefs:
                childrefs[-1].obj['Next'] = childref
                childref.obj['Prev'] = childrefs[-1]
            childrefs.append(childref)

            if len(child) > 0:
                self.process_children(child, childref)
        if childrefs:
            parentref.obj['First'] = childrefs[0]
            parentref.obj['Last'] = childrefs[-1]
            if not parent_is_root:
                parentref.obj['Count'] = -len(childrefs)

    def process_toc_item(self, toc, parentref):
        path = toc.abspath or None
        frag = toc.fragment or None
        if path is None:
            return
        path = os.path.normcase(os.path.abspath(path))
        if path not in self.anchors:
            return None
        a = self.anchors[path]
        dest = a.get(frag, a[None])
        item = Dictionary({'Parent':parentref, 'Dest':dest,
                           'Title':String(toc.text or _('Unknown'))})
        return self.pdf.objects.add(item)


