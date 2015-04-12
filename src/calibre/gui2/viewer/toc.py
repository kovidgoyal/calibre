#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from functools import partial

from PyQt5.Qt import (
    QStandardItem, QStandardItemModel, Qt, QFont, QTreeView, QWidget,
    QHBoxLayout, QToolButton, QIcon, QModelIndex, pyqtSignal, QMenu)

from calibre.ebooks.metadata.toc import TOC as MTOC
from calibre.gui2 import error_dialog
from calibre.gui2.search_box import SearchBox2
from calibre.utils.icu import primary_contains

class TOCView(QTreeView):

    searched = pyqtSignal(object)

    def __init__(self, *args):
        QTreeView.__init__(self, *args)
        self.setMinimumWidth(80)
        self.header().close()
        self.setMouseTracking(True)
        self.setStyleSheet('''
                QTreeView {
                    background-color: palette(window);
                    color: palette(window-text);
                    border: none;
                }

                QTreeView::item {
                    border: 1px solid transparent;
                    padding-top:0.5ex;
                    padding-bottom:0.5ex;
                }

                QTreeView::item:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #e7effd, stop: 1 #cbdaf1);
                    border: 1px solid #bfcde4;
                    border-radius: 6px;
                }
        ''')
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

    def mouseMoveEvent(self, ev):
        if self.indexAt(ev.pos()).isValid():
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
        return QTreeView.mouseMoveEvent(self, ev)

    def expand_tree(self, index):
        self.expand(index)
        i = -1
        while True:
            i += 1
            child = index.child(i, 0)
            if not child.isValid():
                break
            self.expand_tree(child)

    def context_menu(self, pos):
        index = self.indexAt(pos)
        m = QMenu(self)
        if index.isValid():
            m.addAction(_('Expand all items under %s') % index.data(), partial(self.expand_tree, index))
        m.addSeparator()
        m.addAction(_('Expand all items'), self.expandAll)
        m.addAction(_('Collapse all items'), self.collapseAll)
        m.exec_(self.mapToGlobal(pos))

class TOCSearch(QWidget):

    def __init__(self, toc_view, parent=None):
        QWidget.__init__(self, parent)
        self.toc_view = toc_view
        self.l = l = QHBoxLayout(self)
        self.search = s = SearchBox2(self)
        self.search.setMinimumContentsLength(15)
        self.search.initialize('viewer_toc_search_history', help_text=_('Search Table of Contents'))
        self.search.setToolTip(_('Search for text in the Table of Contents'))
        s.search.connect(self.do_search)
        self.go = b = QToolButton(self)
        b.setIcon(QIcon(I('search.png')))
        b.clicked.connect(s.do_search)
        b.setToolTip(_('Find next match'))
        l.addWidget(s), l.addWidget(b)

    def do_search(self, text):
        if not text or not text.strip():
            return
        index = self.toc_view.model().search(text)
        if index.isValid():
            self.toc_view.searched.emit(index)
        else:
            error_dialog(self.toc_view, _('No matches found'), _(
                'There are no Table of Contents entries matching: %s') % text, show=True)
        self.search.search_done(True)


class TOCItem(QStandardItem):

    def __init__(self, spine, toc, depth, all_items, parent=None):
        text = toc.text
        if text:
            text = re.sub(r'\s', ' ', text)
        self.title = text
        self.parent = parent
        QStandardItem.__init__(self, text if text else '')
        self.abspath = toc.abspath if toc.href else None
        self.fragment = toc.fragment
        all_items.append(self)
        self.emphasis_font = QFont(self.font())
        self.emphasis_font.setBold(True), self.emphasis_font.setItalic(True)
        self.normal_font = self.font()
        for t in toc:
            self.appendRow(TOCItem(spine, t, depth+1, all_items, parent=self))
        self.setFlags(Qt.ItemIsEnabled)
        self.is_current_search_result = False
        spos = 0
        for i, si in enumerate(spine):
            if si == self.abspath:
                spos = i
                break
        am = {}
        if self.abspath is not None:
            try:
                am = getattr(spine[i], 'anchor_map', {})
            except UnboundLocalError:
                # Spine was empty?
                pass
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

    def update_indexing_state(self, spine_index, viewport_rect, anchor_map,
            in_paged_mode):
        if in_paged_mode:
            self.update_indexing_state_paged(spine_index, viewport_rect,
                    anchor_map)
        else:
            self.update_indexing_state_unpaged(spine_index, viewport_rect,
                    anchor_map)

    def update_indexing_state_unpaged(self, spine_index, viewport_rect,
            anchor_map):
        is_being_viewed = False
        top, bottom = viewport_rect[1], viewport_rect[3]
        # We use bottom-25 in the checks below to account for the case where
        # the next entry has some invisible margin that just overlaps with the
        # bottom of the screen. In this case it will appear to the user that
        # the entry is not visible on the screen. Of course, the margin could
        # be larger than 25, but that's a decent compromise. Also we dont want
        # to count a partial line as being visible.

        # We only care about y position
        anchor_map = {k:v[1] for k, v in anchor_map.iteritems()}

        if spine_index >= self.starts_at and spine_index <= self.ends_at:
            # The position at which this anchor is present in the document
            start_pos = anchor_map.get(self.start_anchor, 0)
            psp = []
            if self.ends_at == spine_index:
                # Anchors that could possibly indicate the start of the next
                # section and therefore the end of this section.
                # self.possible_end_anchors is a set of anchors belonging to
                # toc entries with depth <= self.depth that are also not
                # ancestors of this entry.
                psp = [anchor_map.get(x, 0) for x in self.possible_end_anchors]
                psp = [x for x in psp if x >= start_pos]
            # The end position. The first anchor whose pos is >= start_pos
            # or if the end is not in this spine item, we set it to the bottom
            # of the window +1
            end_pos = min(psp) if psp else (bottom+1 if self.ends_at >=
                    spine_index else 0)
            if spine_index > self.starts_at and spine_index < self.ends_at:
                # The entire spine item is contained in this entry
                is_being_viewed = True
            elif (spine_index == self.starts_at and bottom-25 >= start_pos and
                # This spine item contains the start
                # The start position is before the end of the viewport
                (spine_index != self.ends_at or top < end_pos)):
                # The end position is after the start of the viewport
                is_being_viewed = True
            elif (spine_index == self.ends_at and top < end_pos and
                # This spine item contains the end
                # The end position is after the start of the viewport
                (spine_index != self.starts_at or bottom-25 >= start_pos)):
                # The start position is before the end of the viewport
                is_being_viewed = True

        changed = is_being_viewed != self.is_being_viewed
        self.is_being_viewed = is_being_viewed
        if changed:
            self.setFont(self.emphasis_font if is_being_viewed else self.normal_font)

    def update_indexing_state_paged(self, spine_index, viewport_rect,
            anchor_map):
        is_being_viewed = False

        left, right = viewport_rect[0], viewport_rect[2]
        left, right = (left, 0), (right, -1)

        if spine_index >= self.starts_at and spine_index <= self.ends_at:
            # The position at which this anchor is present in the document
            start_pos = anchor_map.get(self.start_anchor, (0, 0))
            psp = []
            if self.ends_at == spine_index:
                # Anchors that could possibly indicate the start of the next
                # section and therefore the end of this section.
                # self.possible_end_anchors is a set of anchors belonging to
                # toc entries with depth <= self.depth that are also not
                # ancestors of this entry.
                psp = [anchor_map.get(x, (0, 0)) for x in self.possible_end_anchors]
                psp = [x for x in psp if x >= start_pos]
            # The end position. The first anchor whose pos is >= start_pos
            # or if the end is not in this spine item, we set it to the column
            # after the right edge of the viewport
            end_pos = min(psp) if psp else (right if self.ends_at >=
                    spine_index else (0, 0))
            if spine_index > self.starts_at and spine_index < self.ends_at:
                # The entire spine item is contained in this entry
                is_being_viewed = True
            elif (spine_index == self.starts_at and right > start_pos and
                # This spine item contains the start
                # The start position is before the end of the viewport
                (spine_index != self.ends_at or left < end_pos)):
                # The end position is after the start of the viewport
                is_being_viewed = True
            elif (spine_index == self.ends_at and left < end_pos and
                # This spine item contains the end
                # The end position is after the start of the viewport
                (spine_index != self.starts_at or right > start_pos)):
                # The start position is before the end of the viewport
                is_being_viewed = True

        changed = is_being_viewed != self.is_being_viewed
        self.is_being_viewed = is_being_viewed
        if changed:
            self.setFont(self.emphasis_font if is_being_viewed else self.normal_font)

    def set_current_search_result(self, yes):
        if yes and not self.is_current_search_result:
            self.setText(self.text() + ' ◄')
            self.is_current_search_result = True
        elif not yes and self.is_current_search_result:
            self.setText(self.text()[:-2])
            self.is_current_search_result = False

    def __repr__(self):
        return 'TOC Item: %s %s#%s'%(self.title, self.abspath, self.fragment)

    def __str__(self):
        return repr(self)

class TOC(QStandardItemModel):

    def __init__(self, spine, toc=None):
        QStandardItemModel.__init__(self)
        self.current_query = {'text':'', 'index':-1, 'items':()}
        if toc is None:
            toc = MTOC()
        self.all_items = depth_first = []
        for t in toc:
            self.appendRow(TOCItem(spine, t, 0, depth_first))

        for x in depth_first:
            possible_enders = [t for t in depth_first if t.depth <= x.depth and
                               t.starts_at >= x.starts_at and t is not x and t not in
                    x.ancestors]
            if possible_enders:
                min_spine = min(t.starts_at for t in possible_enders)
                possible_enders = {t.fragment for t in possible_enders if
                        t.starts_at == min_spine}
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

    def next_entry(self, spine_pos, anchor_map, viewport_rect, in_paged_mode,
            backwards=False, current_entry=None):
        current_entry = (self.currently_viewed_entry if current_entry is None
                else current_entry)
        if current_entry is None:
            return
        items = reversed(self.all_items) if backwards else self.all_items
        found = False

        if in_paged_mode:
            start = viewport_rect[0]
            anchor_map = {k:v[0] for k, v in anchor_map.iteritems()}
        else:
            start = viewport_rect[1]
            anchor_map = {k:v[1] for k, v in anchor_map.iteritems()}

        for item in items:
            if found:
                start_pos = anchor_map.get(item.start_anchor, 0)
                if backwards and item.is_being_viewed and start_pos >= start:
                    # This item will not cause any scrolling
                    continue
                if item.starts_at != spine_pos or item.start_anchor:
                    return item
            if item is current_entry:
                found = True

    def find_items(self, query):
        for item in self.all_items:
            if primary_contains(query, item.text()):
                yield item

    def search(self, query):
        cq = self.current_query
        if cq['items'] and -1 < cq['index'] < len(cq['items']):
            cq['items'][cq['index']].set_current_search_result(False)
        if cq['text'] != query:
            items = tuple(self.find_items(query))
            cq.update({'text':query, 'items':items, 'index':-1})
        if len(cq['items']) > 0:
            cq['index'] = (cq['index'] + 1) % len(cq['items'])
            item = cq['items'][cq['index']]
            item.set_current_search_result(True)
            index = self.indexFromItem(item)
            return index
        return QModelIndex()
