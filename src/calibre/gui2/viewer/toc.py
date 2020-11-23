#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import re
from functools import partial

from PyQt5.Qt import (
    QApplication, QFont, QHBoxLayout, QIcon, QMenu, QModelIndex, QStandardItem,
    QStandardItemModel, QStyledItemDelegate, Qt, QToolButton, QToolTip, QTreeView,
    QWidget, pyqtSignal
)

from calibre.gui2 import error_dialog
from calibre.gui2.search_box import SearchBox2
from calibre.utils.icu import primary_contains


class Delegate(QStyledItemDelegate):

    def helpEvent(self, ev, view, option, index):
        # Show a tooltip only if the item is truncated
        if not ev or not view:
            return False
        if ev.type() == ev.ToolTip:
            rect = view.visualRect(index)
            size = self.sizeHint(option, index)
            if rect.width() < size.width():
                tooltip = index.data(Qt.DisplayRole)
                QToolTip.showText(ev.globalPos(), tooltip, view)
                return True
        return QStyledItemDelegate.helpEvent(self, ev, view, option, index)


class TOCView(QTreeView):

    searched = pyqtSignal(object)

    def __init__(self, *args):
        QTreeView.__init__(self, *args)
        self.setFocusPolicy(Qt.NoFocus)
        self.delegate = Delegate(self)
        self.setItemDelegate(self.delegate)
        self.setMinimumWidth(80)
        self.header().close()
        self.setMouseTracking(True)
        self.set_style_sheet()
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)
        QApplication.instance().palette_changed.connect(self.set_style_sheet, type=Qt.QueuedConnection)

    def setModel(self, model):
        QTreeView.setModel(self, model)
        model.auto_expand_nodes.connect(self.auto_expand_indices, type=Qt.QueuedConnection)

    def auto_expand_indices(self, indices):
        for idx in indices:
            self.setExpanded(idx, True)

    def set_style_sheet(self):
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
                color: black;
                border: 1px solid #bfcde4;
                border-radius: 6px;
            }
        ''')

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
        m.addSeparator()
        m.addAction(_('Copy table of contents to clipboard'), self.copy_to_clipboard)
        m.exec_(self.mapToGlobal(pos))

    def copy_to_clipboard(self):
        m = self.model()
        QApplication.clipboard().setText(getattr(m, 'as_plain_text', ''))

    def update_current_toc_nodes(self, current_node_id, toplevel_node_id):
        self.model().update_current_toc_nodes(current_node_id, toplevel_node_id)


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
            self.toc_view.scrollTo(index)
            self.toc_view.searched.emit(index)
        else:
            error_dialog(self.toc_view, _('No matches found'), _(
                'There are no Table of Contents entries matching: %s') % text, show=True)
        self.search.search_done(True)


class TOCItem(QStandardItem):

    def __init__(self, toc, depth, all_items, normal_font, emphasis_font, parent=None):
        text = toc.get('title') or ''
        self.href = (toc.get('dest') or '')
        if toc.get('frag'):
            self.href += '#' + toc['frag']
        if text:
            text = re.sub(r'\s', ' ', text)
        self.title = text
        self.parent = parent
        self.node_id = toc['id']
        QStandardItem.__init__(self, text)
        all_items.append(self)
        self.normal_font, self.emphasis_font = normal_font, emphasis_font
        for t in toc['children']:
            self.appendRow(TOCItem(t, depth+1, all_items, normal_font, emphasis_font, parent=self))
        self.setFlags(Qt.ItemIsEnabled)
        self.is_current_search_result = False
        self.depth = depth
        self.set_being_viewed(False)

    def set_being_viewed(self, is_being_viewed):
        self.is_being_viewed = is_being_viewed
        self.setFont(self.emphasis_font if is_being_viewed else self.normal_font)

    @property
    def ancestors(self):
        parent = self.parent
        while parent is not None:
            yield parent
            parent = parent.parent

    @classmethod
    def type(cls):
        return QStandardItem.UserType+10

    def set_current_search_result(self, yes):
        if yes and not self.is_current_search_result:
            self.setText(self.text() + ' ◄')
            self.is_current_search_result = True
        elif not yes and self.is_current_search_result:
            self.setText(self.text()[:-2])
            self.is_current_search_result = False

    def __repr__(self):
        indent = ' ' * self.depth
        return '{}▶ TOC Item: {} ({})'.format(indent, self.title, self.node_id)

    def __str__(self):
        return repr(self)


class TOC(QStandardItemModel):

    auto_expand_nodes = pyqtSignal(object)

    def __init__(self, toc=None):
        QStandardItemModel.__init__(self)
        self.current_query = {'text':'', 'index':-1, 'items':()}
        self.all_items = depth_first = []
        normal_font = QApplication.instance().font()
        emphasis_font = QFont(normal_font)
        emphasis_font.setBold(True), emphasis_font.setItalic(True)
        if toc:
            for t in toc['children']:
                self.appendRow(TOCItem(t, 0, depth_first, normal_font, emphasis_font))
        self.node_id_map = {x.node_id: x for x in self.all_items}
        self.currently_viewed_entry = None

    def find_items(self, query):
        for item in self.all_items:
            text = item.text()
            if text and primary_contains(query, text):
                yield item

    def node_id_for_text(self, query):
        for item in self.find_items(query):
            return item.node_id

    def node_id_for_href(self, query, exact=False):
        for item in self.all_items:
            href = item.href
            if (exact and query == href) or (not exact and query in href):
                return item.node_id

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

    def update_current_toc_nodes(self, current_node_id, top_level_node_id):
        node = self.node_id_map.get(current_node_id)
        viewed_nodes = set()
        if node is not None:
            viewed_nodes |= {x.node_id for x in node.ancestors}
            viewed_nodes.add(node.node_id)
            self.auto_expand_nodes.emit([n.index() for n in node.ancestors])
        for node in self.all_items:
            is_being_viewed = node.node_id in viewed_nodes
            if is_being_viewed != node.is_being_viewed:
                node.set_being_viewed(is_being_viewed)

    @property
    def as_plain_text(self):
        lines = []
        for item in self.all_items:
            lines.append(' ' * (4 * item.depth) + (item.title or ''))
        return '\n'.join(lines)
