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

    def __init__(self, spine, toc, depth, all_items, parent=None):
        text = toc.text
        if text:
            text = re.sub(r'\s', ' ', text)
        self.title = text
        self.parent = parent
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
            self.appendRow(TOCItem(spine, t, depth+1, all_items, parent=self))
        self.setFlags(Qt.ItemIsEnabled)
        spos = 0
        for i, si in enumerate(spine):
            if si == self.abspath:
                spos = i
                break
        am = getattr(spine[i], 'anchor_map', {})
        frag = self.fragment if (self.fragment and self.fragment in am) else None
        self.starts_at = spos
        self.start_anchor = frag
        self.start_src_offset = am.get(frag, 0)
        self.depth = depth
        self.is_being_viewed = False

    @property
    def ancestors(self):
        parent = self.parent
        while parent is not None:
            yield parent
            parent = parent.parent

    @classmethod
    def type(cls):
        return QStandardItem.UserType+10

    def update_indexing_state(self, spine_index, scroll_pos, anchor_map):
        is_being_viewed = False
        top, bottom = scroll_pos
        # We use bottom-25 in the checks below to account for the case where
        # the next entry has some invisible margin that just overlaps with the
        # bottom of the screen. In this case it will appear to the user that
        # the entry is not visible on the screen. Of course, the margin could
        # be larger than 25, but that's a decent compromise. Also we dont want
        # to count a partial line as being visible.

        if spine_index >= self.starts_at and spine_index <= self.ends_at:
            start_pos = anchor_map.get(self.start_anchor, 0)
            psp = [anchor_map.get(x, 0) for x in self.possible_end_anchors]
            if self.ends_at == spine_index:
                psp = [x for x in psp if x >= start_pos]
            end_pos = min(psp) if psp else (bottom+1 if self.ends_at >=
                    spine_index else 0)
            if spine_index > self.starts_at and spine_index < self.ends_at:
                is_being_viewed = True
            elif spine_index == self.starts_at and bottom-25 >= start_pos:
                if spine_index != self.ends_at or top < end_pos:
                    is_being_viewed = True
            elif spine_index == self.ends_at and top < end_pos:
                if spine_index != self.starts_at or bottom-25 >= start_pos:
                    is_being_viewed = True
        changed = is_being_viewed != self.is_being_viewed
        self.is_being_viewed = is_being_viewed
        if changed:
            self.setFont(self.bold_font if is_being_viewed else self.normal_font)
            self.setBackground(self.alternate_base if is_being_viewed else
                    self.base)

    def __repr__(self):
        return 'TOC Item: %s %s#%s'%(self.title, self.abspath, self.fragment)

    def __str__(self):
        return repr(self)

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
                    and t.starts_at >= x.starts_at and t is not x and t not in
                    x.ancestors]
            if possible_enders:
                min_spine = min(t.starts_at for t in possible_enders)
                possible_enders = { t.fragment for t in possible_enders if
                        t.starts_at == min_spine }
            else:
                min_spine = len(spine) - 1
                possible_enders = set()
            x.ends_at = min_spine
            x.possible_end_anchors = possible_enders

        self.currently_viewed_entry = None

    def update_indexing_state(self, *args):
        items_being_viewed = []
        for t in self.all_items:
            t.update_indexing_state(*args)
            if t.is_being_viewed:
                items_being_viewed.append(t)
                self.currently_viewed_entry = t
        return items_being_viewed

    def next_entry(self, spine_pos, anchor_map, scroll_pos, backwards=False,
            current_entry=None):
        current_entry = (self.currently_viewed_entry if current_entry is None
                else current_entry)
        if current_entry is None: return
        items = reversed(self.all_items) if backwards else self.all_items
        found = False
        top = scroll_pos[0]
        for item in items:
            if found:
                start_pos = anchor_map.get(item.start_anchor, 0)
                if backwards and item.is_being_viewed and start_pos >= top:
                    # Going to this item will either not move the scroll
                    # position or cause to to *increase* instead of descresing
                    continue
                if item.starts_at != spine_pos or item.start_anchor:
                    return item
            if item is current_entry:
                found = True



