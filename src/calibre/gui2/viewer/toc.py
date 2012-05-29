#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from PyQt4.Qt import (QStandardItem, QStandardItemModel, Qt, QFont,
        QApplication)

from calibre.ebooks.metadata.toc import TOC as MTOC

class TOCItem(QStandardItem):

    def __init__(self, spine, toc, depth, all_items):
        text = toc.text
        if text:
            text = re.sub(r'\s', ' ', text)
        self.title = text
        QStandardItem.__init__(self, text if text else '')
        self.abspath = toc.abspath
        self.fragment = toc.fragment
        all_items.append(self)
        p = QApplication.palette()
        self.base = p.base()
        self.alternate_base = p.alternateBase()
        self.bold_font = QFont(self.font())
        self.bold_font.setBold(True)
        self.normal_font = self.font()
        for t in toc:
            self.appendRow(TOCItem(spine, t, depth+1, all_items))
        self.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
        spos = 0
        for i, si in enumerate(spine):
            if si == self.abspath:
                spos = i
                break
        am = getattr(spine[i], 'anchor_map', {})
        frag = self.fragment if (self.fragment and self.fragment in am) else None
        self.starts_at = spos
        self.start_anchor = frag
        self.depth = depth
        self.is_being_viewed = False

    @classmethod
    def type(cls):
        return QStandardItem.UserType+10

    def update_indexing_state(self, spine_index, scroll_pos, anchor_map):
        is_being_viewed = False
        if spine_index >= self.starts_at and spine_index <= self.ends_at:
            start_pos = anchor_map.get(self.start_anchor, 0)
            psp = [anchor_map.get(x, 0) for x in self.possible_end_anchors]
            if self.ends_at == spine_index:
                psp = [x for x in psp if x >= start_pos]
            end_pos = min(psp) if psp else (scroll_pos+1 if self.ends_at ==
                    spine_index else 0)
            if spine_index > self.starts_at and spine_index < self.ends_at:
                is_being_viewed = True
            elif spine_index == self.starts_at and scroll_pos >= start_pos:
                if spine_index != self.ends_at or scroll_pos < end_pos:
                    is_being_viewed = True
            elif spine_index == self.ends_at and scroll_pos < end_pos:
                if spine_index != self.starts_at or scroll_pos >= start_pos:
                    is_being_viewed = True
        changed = is_being_viewed != self.is_being_viewed
        self.is_being_viewed = is_being_viewed
        if changed:
            self.setFont(self.bold_font if is_being_viewed else self.normal_font)
            self.setBackground(self.alternate_base if is_being_viewed else
                    self.base)

class TOC(QStandardItemModel):

    def __init__(self, spine, toc=None):
        QStandardItemModel.__init__(self)
        if toc is None:
            toc = MTOC()
        self.all_items = depth_first = []
        for t in toc:
            self.appendRow(TOCItem(spine, t, 0, depth_first))
        self.setHorizontalHeaderItem(0, QStandardItem(_('Table of Contents')))

        for x in depth_first:
            possible_enders = [ t for t in depth_first if t.depth <= x.depth
                    and t.starts_at >= x.starts_at and t is not x]
            if possible_enders:
                min_spine = min(t.starts_at for t in possible_enders)
                possible_enders = { t.fragment for t in possible_enders if
                        t.starts_at == min_spine }
            else:
                min_spine = len(spine) - 1
                possible_enders = set()
            x.ends_at = min_spine
            x.possible_end_anchors = possible_enders

    def update_indexing_state(self, *args):
        items_being_viewed = []
        for t in self.all_items:
            t.update_indexing_state(*args)
            if t.is_being_viewed:
                items_being_viewed.append(t)
        return items_being_viewed

