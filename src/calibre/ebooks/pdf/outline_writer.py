#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from collections import defaultdict

class Outline(object):

    def __init__(self, toc, items):
        self.toc = toc
        self.items = items
        self.anchor_map = {}
        self.pos_map = defaultdict(dict)
        self.toc_map = {}
        for item in items:
            self.anchor_map[item] = anchors = set()
            item_path = os.path.abspath(item).replace('/', os.sep)
            if self.toc is not None:
                for x in self.toc.flat():
                    if x.abspath != item_path: continue
                    x.outline_item_ = item
                    if x.fragment:
                        anchors.add(x.fragment)

    def set_pos(self, item, anchor, pagenum, ypos):
        self.pos_map[item][anchor] = (pagenum, ypos)

    def get_pos(self, toc):
        page, ypos = 0, 0
        item = getattr(toc, 'outline_item_', None)
        if item is not None:
            if toc.fragment:
                amap = self.pos_map.get(item, None)
                if amap is not None:
                    page, ypos = amap.get(toc.fragment, (0, 0))
            else:
                page, ypos = self.pos_map.get(item, {}).get(None, (0, 0))
        return page, ypos

    def add_children(self, toc, parent):
        for child in toc:
            page, ypos = self.get_pos(child)
            text = child.text or _('Page %d')%page
            cn = parent.create(text, page, True)
            self.add_children(child, cn)

    def __call__(self, doc):
        self.pos_map = dict(self.pos_map)
        for child in self.toc:
            page, ypos = self.get_pos(child)
            text = child.text or _('Page %d')%page
            node = doc.create_outline(text, page)
            self.add_children(child, node)



