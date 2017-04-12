#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, textwrap
from threading import Thread
from functools import partial
from future_builtins import map

from PyQt5.Qt import (QPushButton, QFrame, QMenu, QInputDialog,
    QDialog, QVBoxLayout, QDialogButtonBox, QSize, QStackedWidget, QWidget,
    QLabel, Qt, pyqtSignal, QIcon, QTreeWidget, QGridLayout, QTreeWidgetItem,
    QToolButton, QItemSelectionModel, QCursor, QKeySequence, QSizePolicy)

from calibre.ebooks.oeb.polish.container import get_container, AZW3Container
from calibre.ebooks.oeb.polish.toc import (
    get_toc, add_id, TOC, commit_toc, from_xpaths, from_links, from_files)
from calibre.gui2 import Application, error_dialog, gprefs, info_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.toc.location import ItemEdit
from calibre.gui2.convert.xpath_wizard import XPathEdit
from calibre.utils.logging import GUILog

ICON_SIZE = 24


class XPathDialog(QDialog):  # {{{

    def __init__(self, parent, prefs):
        QDialog.__init__(self, parent)
        self.prefs = prefs
        self.setWindowTitle(_('Create ToC from XPath'))
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel(_(
            'Specify a series of XPath expressions for the different levels of'
            ' the Table of Contents. You can use the wizard buttons to help'
            ' you create XPath expressions.'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.widgets = []
        for i in xrange(5):
            la = _('Level %s ToC:')%('&%d'%(i+1))
            xp = XPathEdit(self)
            xp.set_msg(la)
            self.widgets.append(xp)
            l.addWidget(xp)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.ssb = b = bb.addButton(_('&Save settings'), bb.ActionRole)
        b.clicked.connect(self.save_settings)
        self.load_button = b = bb.addButton(_('&Load settings'), bb.ActionRole)
        self.load_menu = QMenu(b)
        b.setMenu(self.load_menu)
        self.setup_load_button()
        l.addStretch()
        l.addWidget(bb)
        self.resize(self.sizeHint() + QSize(50, 75))

    def save_settings(self):
        xpaths = self.xpaths
        if not xpaths:
            return error_dialog(self, _('No XPaths'),
                                _('No XPaths have been entered'), show=True)
        if not self.check():
            return
        name, ok = QInputDialog.getText(self, _('Choose name'),
                _('Choose a name for these settings'))
        if ok:
            name = unicode(name).strip()
            if name:
                saved = self.prefs.get('xpath_toc_settings', {})
                # in JSON all keys have to be strings
                saved[name] = {str(i):x for i, x in enumerate(xpaths)}
                self.prefs.set('xpath_toc_settings', saved)
                self.setup_load_button()

    def setup_load_button(self):
        saved = self.prefs.get('xpath_toc_settings', {})
        m = self.load_menu
        m.clear()
        self.__actions = []
        a = self.__actions.append
        for name in sorted(saved):
            a(m.addAction(name, partial(self.load_settings, name)))
        m.addSeparator()
        a(m.addAction(_('Remove saved settings'), self.clear_settings))
        self.load_button.setEnabled(bool(saved))

    def clear_settings(self):
        self.prefs.set('xpath_toc_settings', {})
        self.setup_load_button()

    def load_settings(self, name):
        saved = self.prefs.get('xpath_toc_settings', {}).get(name, {})
        for i, w in enumerate(self.widgets):
            txt = saved.get(str(i), '')
            w.edit.setText(txt)

    def check(self):
        for w in self.widgets:
            if not w.check():
                error_dialog(self, _('Invalid XPath'),
                    _('The XPath expression %s is not valid.')%w.xpath,
                             show=True)
                return False
        return True

    def accept(self):
        if self.check():
            super(XPathDialog, self).accept()

    @property
    def xpaths(self):
        return [w.xpath for w in self.widgets if w.xpath.strip()]
# }}}


class ItemView(QFrame):  # {{{

    add_new_item = pyqtSignal(object, object)
    delete_item = pyqtSignal()
    flatten_item = pyqtSignal()
    go_to_root = pyqtSignal()
    create_from_xpath = pyqtSignal(object)
    create_from_links = pyqtSignal()
    create_from_files = pyqtSignal()
    flatten_toc = pyqtSignal()

    def __init__(self, parent, prefs):
        QFrame.__init__(self, parent)
        self.prefs = prefs
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(250)
        self.stack = s = QStackedWidget(self)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(s)
        self.root_pane = rp = QWidget(self)
        self.item_pane = ip = QWidget(self)
        self.current_item = None
        s.addWidget(rp)
        s.addWidget(ip)

        self.l1 = la = QLabel('<p>'+_(
            'You can edit existing entries in the Table of Contents by clicking them'
            ' in the panel to the left.')+'<p>'+_(
            'Entries with a green tick next to them point to a location that has '
            'been verified to exist. Entries with a red dot are broken and may need'
            ' to be fixed.'))
        la.setStyleSheet('QLabel { margin-bottom: 20px }')
        la.setWordWrap(True)
        l = rp.l = QVBoxLayout()
        rp.setLayout(l)
        l.addWidget(la)
        self.add_new_to_root_button = b = QPushButton(_('Create a &new entry'))
        b.clicked.connect(self.add_new_to_root)
        l.addWidget(b)
        l.addStretch()

        self.cfmhb = b = QPushButton(_('Generate ToC from &major headings'))
        b.clicked.connect(self.create_from_major_headings)
        b.setToolTip(textwrap.fill(_(
            'Generate a Table of Contents from the major headings in the book.'
            ' This will work if the book identifies its headings using HTML'
            ' heading tags. Uses the <h1>, <h2> and <h3> tags.')))
        l.addWidget(b)
        self.cfmab = b = QPushButton(_('Generate ToC from &all headings'))
        b.clicked.connect(self.create_from_all_headings)
        b.setToolTip(textwrap.fill(_(
            'Generate a Table of Contents from all the headings in the book.'
            ' This will work if the book identifies its headings using HTML'
            ' heading tags. Uses the <h1-6> tags.')))
        l.addWidget(b)

        self.lb = b = QPushButton(_('Generate ToC from &links'))
        b.clicked.connect(self.create_from_links)
        b.setToolTip(textwrap.fill(_(
            'Generate a Table of Contents from all the links in the book.'
            ' Links that point to destinations that do not exist in the book are'
            ' ignored. Also multiple links with the same destination or the same'
            ' text are ignored.'
        )))
        l.addWidget(b)

        self.cfb = b = QPushButton(_('Generate ToC from &files'))
        b.clicked.connect(self.create_from_files)
        b.setToolTip(textwrap.fill(_(
            'Generate a Table of Contents from individual files in the book.'
            ' Each entry in the ToC will point to the start of the file, the'
            ' text of the entry will be the "first line" of text from the file.'
        )))
        l.addWidget(b)

        self.xpb = b = QPushButton(_('Generate ToC from &XPath'))
        b.clicked.connect(self.create_from_user_xpath)
        b.setToolTip(textwrap.fill(_(
            'Generate a Table of Contents from arbitrary XPath expressions.'
        )))
        l.addWidget(b)

        self.fal = b = QPushButton(_('&Flatten the ToC'))
        b.clicked.connect(self.flatten_toc)
        b.setToolTip(textwrap.fill(_(
            'Flatten the Table of Contents, putting all entries at the top level'
        )))
        l.addWidget(b)

        l.addStretch()
        self.w1 = la = QLabel(_('<b>WARNING:</b> calibre only supports the '
                                'creation of linear ToCs in AZW3 files. In a '
                                'linear ToC every entry must point to a '
                                'location after the previous entry. If you '
                                'create a non-linear ToC it will be '
                                'automatically re-arranged inside the AZW3 file.'
                            ))
        la.setWordWrap(True)
        l.addWidget(la)

        l = ip.l = QGridLayout()
        ip.setLayout(l)
        la = ip.heading = QLabel('')
        l.addWidget(la, 0, 0, 1, 2)
        la.setWordWrap(True)
        la = ip.la = QLabel(_(
            'You can move this entry around the Table of Contents by drag '
            'and drop or using the up and down buttons to the left'))
        la.setWordWrap(True)
        l.addWidget(la, 1, 0, 1, 2)

        # Item status
        ip.hl1 = hl =  QFrame()
        hl.setFrameShape(hl.HLine)
        l.addWidget(hl, l.rowCount(), 0, 1, 2)
        self.icon_label = QLabel()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        l.addWidget(self.icon_label, l.rowCount(), 0)
        l.addWidget(self.status_label, l.rowCount()-1, 1)
        ip.hl2 = hl =  QFrame()
        hl.setFrameShape(hl.HLine)
        l.addWidget(hl, l.rowCount(), 0, 1, 2)

        # Edit/remove item
        rs = l.rowCount()
        ip.b1 = b = QPushButton(QIcon(I('edit_input.png')),
            _('Change the &location this entry points to'), self)
        b.clicked.connect(self.edit_item)
        l.addWidget(b, l.rowCount()+1, 0, 1, 2)
        ip.b2 = b = QPushButton(QIcon(I('trash.png')),
            _('&Remove this entry'), self)
        l.addWidget(b, l.rowCount(), 0, 1, 2)
        b.clicked.connect(self.delete_item)
        ip.hl3 = hl =  QFrame()
        hl.setFrameShape(hl.HLine)
        l.addWidget(hl, l.rowCount(), 0, 1, 2)
        l.setRowMinimumHeight(rs, 20)

        # Add new item
        rs = l.rowCount()
        ip.b3 = b = QPushButton(QIcon(I('plus.png')), _('New entry &inside this entry'))
        b.clicked.connect(partial(self.add_new, 'inside'))
        l.addWidget(b, l.rowCount()+1, 0, 1, 2)
        ip.b4 = b = QPushButton(QIcon(I('plus.png')), _('New entry &above this entry'))
        b.clicked.connect(partial(self.add_new, 'before'))
        l.addWidget(b, l.rowCount(), 0, 1, 2)
        ip.b5 = b = QPushButton(QIcon(I('plus.png')), _('New entry &below this entry'))
        b.clicked.connect(partial(self.add_new, 'after'))
        l.addWidget(b, l.rowCount(), 0, 1, 2)
        # Flatten entry
        ip.b3 = b = QPushButton(QIcon(I('heuristics.png')), _('&Flatten this entry'))
        b.clicked.connect(self.flatten_item)
        b.setToolTip(_('All children of this entry are brought to the same '
                       'level as this entry.'))
        l.addWidget(b, l.rowCount()+1, 0, 1, 2)

        ip.hl4 = hl =  QFrame()
        hl.setFrameShape(hl.HLine)
        l.addWidget(hl, l.rowCount(), 0, 1, 2)
        l.setRowMinimumHeight(rs, 20)

        # Return to welcome
        rs = l.rowCount()
        ip.b4 = b = QPushButton(QIcon(I('back.png')), _('&Return to welcome screen'))
        b.clicked.connect(self.go_to_root)
        b.setToolTip(_('Go back to the top level view'))
        l.addWidget(b, l.rowCount()+1, 0, 1, 2)

        l.setRowMinimumHeight(rs, 20)

        l.addWidget(QLabel(), l.rowCount(), 0, 1, 2)
        l.setColumnStretch(1, 10)
        l.setRowStretch(l.rowCount()-1, 10)
        self.w2 = la = QLabel(self.w1.text())
        self.w2.setWordWrap(True)
        l.addWidget(la, l.rowCount(), 0, 1, 2)

    def create_from_major_headings(self):
        self.create_from_xpath.emit(['//h:h%d'%i for i in xrange(1, 4)])

    def create_from_all_headings(self):
        self.create_from_xpath.emit(['//h:h%d'%i for i in xrange(1, 7)])

    def create_from_user_xpath(self):
        d = XPathDialog(self, self.prefs)
        if d.exec_() == d.Accepted and d.xpaths:
            self.create_from_xpath.emit(d.xpaths)

    def hide_azw3_warning(self):
        self.w1.setVisible(False), self.w2.setVisible(False)

    def add_new_to_root(self):
        self.add_new_item.emit(None, None)

    def add_new(self, where):
        self.add_new_item.emit(self.current_item, where)

    def edit_item(self):
        self.add_new_item.emit(self.current_item, None)

    def __call__(self, item):
        if item is None:
            self.current_item = None
            self.stack.setCurrentIndex(0)
        else:
            self.current_item = item
            self.stack.setCurrentIndex(1)
            self.populate_item_pane()

    def populate_item_pane(self):
        item = self.current_item
        name = unicode(item.data(0, Qt.DisplayRole) or '')
        self.item_pane.heading.setText('<h2>%s</h2>'%name)
        self.icon_label.setPixmap(item.data(0, Qt.DecorationRole
                                            ).pixmap(32, 32))
        tt = _('This entry points to an existing destination')
        toc = item.data(0, Qt.UserRole)
        if toc.dest_exists is False:
            tt = _('The location this entry points to does not exist')
        elif toc.dest_exists is None:
            tt = ''
        self.status_label.setText(tt)

    def data_changed(self, item):
        if item is self.current_item:
            self.populate_item_pane()

# }}}


NODE_FLAGS = (Qt.ItemIsDragEnabled|Qt.ItemIsEditable|Qt.ItemIsEnabled|
                        Qt.ItemIsSelectable|Qt.ItemIsDropEnabled)


class TreeWidget(QTreeWidget):  # {{{

    edit_item = pyqtSignal()

    def __init__(self, parent):
        QTreeWidget.__init__(self, parent)
        self.history = []
        self.setHeaderLabel(_('Table of Contents'))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setDragEnabled(True)
        self.setSelectionMode(self.ExtendedSelection)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.InternalMove)
        self.setAutoScroll(True)
        self.setAutoScrollMargin(ICON_SIZE*2)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAutoExpandDelay(1000)
        self.setAnimated(True)
        self.setMouseTracking(True)
        self.in_drop_event = False
        self.root = self.invisibleRootItem()
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def push_history(self):
        self.history.append(self.serialize_tree())

    def pop_history(self):
        if self.history:
            self.unserialize_tree(self.history.pop())

    def iteritems(self, parent=None):
        if parent is None:
            parent = self.invisibleRootItem()
        for i in xrange(parent.childCount()):
            child = parent.child(i)
            yield child
            for gc in self.iteritems(parent=child):
                yield gc

    def update_status_tip(self, item):
        c = item.data(0, Qt.UserRole)
        if c is not None:
            frag = c.frag or ''
            if frag:
                frag = '#'+frag
            item.setStatusTip(0, _('<b>Title</b>: {0} <b>Dest</b>: {1}{2}').format(
                c.title, c.dest, frag))

    def serialize_tree(self):

        def serialize_node(node):
            return {
                'title': node.data(0, Qt.DisplayRole),
                'toc_node': node.data(0, Qt.UserRole),
                'icon': node.data(0, Qt.DecorationRole),
                'tooltip': node.data(0, Qt.ToolTipRole),
                'is_selected': node.isSelected(),
                'is_expanded': node.isExpanded(),
                'children': list(map(serialize_node, (node.child(i) for i in range(node.childCount())))),
            }

        node = self.invisibleRootItem()
        return {'children': list(map(serialize_node, (node.child(i) for i in range(node.childCount()))))}

    def unserialize_tree(self, serialized):

        def unserialize_node(dict_node, parent):
            n = QTreeWidgetItem(parent)
            n.setData(0, Qt.DisplayRole, dict_node['title'])
            n.setData(0, Qt.UserRole, dict_node['toc_node'])
            n.setFlags(NODE_FLAGS)
            n.setData(0, Qt.DecorationRole, dict_node['icon'])
            n.setData(0, Qt.ToolTipRole, dict_node['tooltip'])
            self.update_status_tip(n)
            n.setExpanded(dict_node['is_expanded'])
            n.setSelected(dict_node['is_selected'])
            for c in dict_node['children']:
                unserialize_node(c, n)

        i = self.invisibleRootItem()
        i.takeChildren()
        for child in serialized['children']:
            unserialize_node(child, i)

    def dropEvent(self, event):
        self.in_drop_event = True
        self.push_history()
        try:
            super(TreeWidget, self).dropEvent(event)
        finally:
            self.in_drop_event = False

    def selectedIndexes(self):
        ans = super(TreeWidget, self).selectedIndexes()
        if self.in_drop_event:
            # For order to be be preserved when moving by drag and drop, we
            # have to ensure that selectedIndexes returns an ordered list of
            # indexes.
            sort_map = {self.indexFromItem(item):i for i, item in enumerate(self.iteritems())}
            ans = sorted(ans, key=lambda x:sort_map.get(x, -1), reverse=True)
        return ans

    def highlight_item(self, item):
        self.setCurrentItem(item, 0, QItemSelectionModel.ClearAndSelect)
        self.scrollToItem(item)

    def check_multi_selection(self):
        if len(self.selectedItems()) > 1:
            return info_dialog(self, _('Multiple items selected'), _(
                'You are trying to move multiple items at once, this is not supported. Instead use'
                ' Drag and Drop to move multiple items'), show=True)
        return True

    def move_left(self):
        if not self.check_multi_selection():
            return
        self.push_history()
        item = self.currentItem()
        if item is not None:
            parent = item.parent()
            if parent is not None:
                is_expanded = item.isExpanded() or item.childCount() == 0
                gp = parent.parent() or self.invisibleRootItem()
                idx = gp.indexOfChild(parent)
                for gc in [parent.child(i) for i in xrange(parent.indexOfChild(item)+1, parent.childCount())]:
                    parent.removeChild(gc)
                    item.addChild(gc)
                parent.removeChild(item)
                gp.insertChild(idx+1, item)
                if is_expanded:
                    self.expandItem(item)
                self.highlight_item(item)

    def move_right(self):
        if not self.check_multi_selection():
            return
        self.push_history()
        item = self.currentItem()
        if item is not None:
            parent = item.parent() or self.invisibleRootItem()
            idx = parent.indexOfChild(item)
            if idx > 0:
                is_expanded = item.isExpanded()
                np = parent.child(idx-1)
                parent.removeChild(item)
                np.addChild(item)
                if is_expanded:
                    self.expandItem(item)
                self.highlight_item(item)

    def move_down(self):
        if not self.check_multi_selection():
            return
        self.push_history()
        item = self.currentItem()
        if item is None:
            if self.root.childCount() == 0:
                return
            item = self.root.child(0)
            self.highlight_item(item)
            return
        parent = item.parent() or self.root
        idx = parent.indexOfChild(item)
        if idx == parent.childCount() - 1:
            # At end of parent, need to become sibling of parent
            if parent is self.root:
                return
            gp = parent.parent() or self.root
            parent.removeChild(item)
            gp.insertChild(gp.indexOfChild(parent)+1, item)
        else:
            sibling = parent.child(idx+1)
            parent.removeChild(item)
            sibling.insertChild(0, item)
        self.highlight_item(item)

    def move_up(self):
        if not self.check_multi_selection():
            return
        self.push_history()
        item = self.currentItem()
        if item is None:
            if self.root.childCount() == 0:
                return
            item = self.root.child(self.root.childCount()-1)
            self.highlight_item(item)
            return
        parent = item.parent() or self.root
        idx = parent.indexOfChild(item)
        if idx == 0:
            # At end of parent, need to become sibling of parent
            if parent is self.root:
                return
            gp = parent.parent() or self.root
            parent.removeChild(item)
            gp.insertChild(gp.indexOfChild(parent), item)
        else:
            sibling = parent.child(idx-1)
            parent.removeChild(item)
            sibling.addChild(item)
        self.highlight_item(item)

    def del_items(self):
        self.push_history()
        for item in self.selectedItems():
            p = item.parent() or self.root
            p.removeChild(item)

    def title_case(self):
        self.push_history()
        from calibre.utils.titlecase import titlecase
        for item in self.selectedItems():
            t = unicode(item.data(0, Qt.DisplayRole) or '')
            item.setData(0, Qt.DisplayRole, titlecase(t))

    def upper_case(self):
        self.push_history()
        for item in self.selectedItems():
            t = unicode(item.data(0, Qt.DisplayRole) or '')
            item.setData(0, Qt.DisplayRole, icu_upper(t))

    def bulk_rename(self):
        from calibre.gui2.tweak_book.file_list import get_bulk_rename_settings
        sort_map = {item:i for i, item in enumerate(self.iteritems())}
        items = sorted(self.selectedItems(), key=lambda x:sort_map.get(x, -1))
        fmt, num = get_bulk_rename_settings(self, len(items), prefix=_('Chapter '), msg=_(
            'All selected items will be renamed to the form prefix-number'), sanitize=lambda x:x, leading_zeros=False)
        if fmt is not None and num is not None:
            self.push_history()
            for i, item in enumerate(items):
                item.setData(0, Qt.DisplayRole, fmt % (num + i))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Left and ev.modifiers() & Qt.CTRL:
            self.move_left()
            ev.accept()
        elif ev.key() == Qt.Key_Right and ev.modifiers() & Qt.CTRL:
            self.move_right()
            ev.accept()
        elif ev.key() == Qt.Key_Up and (ev.modifiers() & Qt.CTRL or ev.modifiers() & Qt.ALT):
            self.move_up()
            ev.accept()
        elif ev.key() == Qt.Key_Down and (ev.modifiers() & Qt.CTRL or ev.modifiers() & Qt.ALT):
            self.move_down()
            ev.accept()
        elif ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.del_items()
            ev.accept()
        else:
            return super(TreeWidget, self).keyPressEvent(ev)

    def show_context_menu(self, point):
        item = self.currentItem()

        def key(k):
            sc = unicode(QKeySequence(k | Qt.CTRL).toString(QKeySequence.NativeText))
            return ' [%s]'%sc

        if item is not None:
            m = QMenu()
            ci = unicode(item.data(0, Qt.DisplayRole) or '')
            p = item.parent() or self.invisibleRootItem()
            idx = p.indexOfChild(item)
            if idx > 0:
                m.addAction(QIcon(I('arrow-up.png')), (_('Move "%s" up')%ci)+key(Qt.Key_Up), self.move_up)
            if idx + 1 < p.childCount():
                m.addAction(QIcon(I('arrow-down.png')), (_('Move "%s" down')%ci)+key(Qt.Key_Down), self.move_down)
            m.addAction(QIcon(I('trash.png')), _('Remove all selected items'), self.del_items)
            if item.parent() is not None:
                m.addAction(QIcon(I('back.png')), (_('Unindent "%s"')%ci)+key(Qt.Key_Left), self.move_left)
            if idx > 0:
                m.addAction(QIcon(I('forward.png')), (_('Indent "%s"')%ci)+key(Qt.Key_Right), self.move_right)
            m.addAction(QIcon(I('edit_input.png')), _('Change the location this entry points to'), self.edit_item)
            m.addAction(_('Change all selected items to title case'), self.title_case)
            m.addAction(_('Change all selected items to upper case'), self.upper_case)
            m.addAction(QIcon(I('modified.png')), _('Bulk rename all selected items'), self.bulk_rename)
            m.exec_(QCursor.pos())
# }}}


class TOCView(QWidget):  # {{{

    add_new_item = pyqtSignal(object, object)

    def __init__(self, parent, prefs):
        QWidget.__init__(self, parent)
        self.toc_title = None
        self.prefs = prefs
        l = self.l = QGridLayout()
        self.setLayout(l)
        self.tocw = t = TreeWidget(self)
        self.tocw.edit_item.connect(self.edit_item)
        l.addWidget(t, 0, 0, 7, 3)
        self.up_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 0, 3)
        b.setToolTip(_('Move current entry up [Ctrl+Up]'))
        b.clicked.connect(self.move_up)

        self.left_button = b = QToolButton(self)
        b.setIcon(QIcon(I('back.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 2, 3)
        b.setToolTip(_('Unindent the current entry [Ctrl+Left]'))
        b.clicked.connect(self.tocw.move_left)

        self.del_button = b = QToolButton(self)
        b.setIcon(QIcon(I('trash.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 3, 3)
        b.setToolTip(_('Remove all selected entries'))
        b.clicked.connect(self.del_items)

        self.right_button = b = QToolButton(self)
        b.setIcon(QIcon(I('forward.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 4, 3)
        b.setToolTip(_('Indent the current entry [Ctrl+Right]'))
        b.clicked.connect(self.tocw.move_right)

        self.down_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 6, 3)
        b.setToolTip(_('Move current entry down [Ctrl+Down]'))
        b.clicked.connect(self.move_down)
        self.expand_all_button = b = QPushButton(_('&Expand all'))
        col = 7
        l.addWidget(b, col, 0)
        b.clicked.connect(self.tocw.expandAll)
        self.collapse_all_button = b = QPushButton(_('&Collapse all'))
        b.clicked.connect(self.tocw.collapseAll)
        l.addWidget(b, col, 1)
        self.default_msg = _('Double click on an entry to change the text')
        self.hl = hl = QLabel(self.default_msg)
        hl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        l.addWidget(hl, col, 2, 1, -1)
        self.item_view = i = ItemView(self, self.prefs)
        self.item_view.delete_item.connect(self.delete_current_item)
        i.add_new_item.connect(self.add_new_item)
        i.create_from_xpath.connect(self.create_from_xpath)
        i.create_from_links.connect(self.create_from_links)
        i.create_from_files.connect(self.create_from_files)
        i.flatten_item.connect(self.flatten_item)
        i.flatten_toc.connect(self.flatten_toc)
        i.go_to_root.connect(self.go_to_root)
        l.addWidget(i, 0, 4, col, 1)

        l.setColumnStretch(2, 10)

    def edit_item(self):
        self.item_view.edit_item()

    def event(self, e):
        if e.type() == e.StatusTip:
            txt = unicode(e.tip()) or self.default_msg
            self.hl.setText(txt)
        return super(TOCView, self).event(e)

    def item_title(self, item):
        return unicode(item.data(0, Qt.DisplayRole) or '')

    def del_items(self):
        self.tocw.del_items()

    def delete_current_item(self):
        item = self.tocw.currentItem()
        if item is not None:
            self.tocw.push_history()
            p = item.parent() or self.root
            p.removeChild(item)

    def iteritems(self, parent=None):
        for item in self.tocw.iteritems(parent=parent):
            yield item

    def flatten_toc(self):
        self.tocw.push_history()
        found = True
        while found:
            found = False
            for item in self.iteritems():
                if item.childCount() > 0:
                    self._flatten_item(item)
                    found = True
                    break

    def flatten_item(self):
        self.tocw.push_history()
        self._flatten_item(self.tocw.currentItem())

    def _flatten_item(self, item):
        if item is not None:
            p = item.parent() or self.root
            idx = p.indexOfChild(item)
            children = [item.child(i) for i in xrange(item.childCount())]
            for child in reversed(children):
                item.removeChild(child)
                p.insertChild(idx+1, child)

    def go_to_root(self):
        self.tocw.setCurrentItem(None)

    def highlight_item(self, item):
        self.tocw.highlight_item(item)

    def move_up(self):
        self.tocw.move_up()

    def move_down(self):
        self.tocw.move_down()

    def data_changed(self, top_left, bottom_right):
        for r in xrange(top_left.row(), bottom_right.row()+1):
            idx = self.tocw.model().index(r, 0, top_left.parent())
            new_title = unicode(idx.data(Qt.DisplayRole) or '').strip()
            toc = idx.data(Qt.UserRole)
            if toc is not None:
                toc.title = new_title or _('(Untitled)')
            item = self.tocw.itemFromIndex(idx)
            self.tocw.update_status_tip(item)
            self.item_view.data_changed(item)

    def create_item(self, parent, child, idx=-1):
        if idx == -1:
            c = QTreeWidgetItem(parent)
        else:
            c = QTreeWidgetItem()
            parent.insertChild(idx, c)
        self.populate_item(c, child)
        return c

    def populate_item(self, c, child):
        c.setData(0, Qt.DisplayRole, child.title or _('(Untitled)'))
        c.setData(0, Qt.UserRole, child)
        c.setFlags(NODE_FLAGS)
        c.setData(0, Qt.DecorationRole, self.icon_map[child.dest_exists])
        if child.dest_exists is False:
            c.setData(0, Qt.ToolTipRole, _(
                'The location this entry point to does not exist:\n%s')
                %child.dest_error)
        else:
            c.setData(0, Qt.ToolTipRole, None)

        self.tocw.update_status_tip(c)

    def __call__(self, ebook):
        self.ebook = ebook
        if not isinstance(ebook, AZW3Container):
            self.item_view.hide_azw3_warning()
        self.toc = get_toc(self.ebook)
        self.toc_lang, self.toc_uid = self.toc.lang, self.toc.uid
        self.toc_title = self.toc.toc_title
        self.blank = QIcon(I('blank.png'))
        self.ok = QIcon(I('ok.png'))
        self.err = QIcon(I('dot_red.png'))
        self.icon_map = {None:self.blank, True:self.ok, False:self.err}

        def process_item(toc_node, parent):
            for child in toc_node:
                c = self.create_item(parent, child)
                process_item(child, c)

        root = self.root = self.tocw.invisibleRootItem()
        root.setData(0, Qt.UserRole, self.toc)
        process_item(self.toc, root)
        self.tocw.model().dataChanged.connect(self.data_changed)
        self.tocw.currentItemChanged.connect(self.current_item_changed)
        self.tocw.setCurrentItem(None)

    def current_item_changed(self, current, previous):
        self.item_view(current)

    def update_item(self, item, where, name, frag, title):
        if isinstance(frag, tuple):
            frag = add_id(self.ebook, name, *frag)
        child = TOC(title, name, frag)
        child.dest_exists = True
        self.tocw.push_history()
        if item is None:
            # New entry at root level
            c = self.create_item(self.root, child)
            self.tocw.setCurrentItem(c, 0, QItemSelectionModel.ClearAndSelect)
            self.tocw.scrollToItem(c)
        else:
            if where is None:
                # Editing existing entry
                self.populate_item(item, child)
            else:
                if where == 'inside':
                    parent = item
                    idx = -1
                else:
                    parent = item.parent() or self.root
                    idx = parent.indexOfChild(item)
                    if where == 'after':
                        idx += 1
                c = self.create_item(parent, child, idx=idx)
                self.tocw.setCurrentItem(c, 0, QItemSelectionModel.ClearAndSelect)
                self.tocw.scrollToItem(c)

    def create_toc(self):
        root = TOC()

        def process_node(parent, toc_parent):
            for i in xrange(parent.childCount()):
                item = parent.child(i)
                title = unicode(item.data(0, Qt.DisplayRole) or '').strip()
                toc = item.data(0, Qt.UserRole)
                dest, frag = toc.dest, toc.frag
                toc = toc_parent.add(title, dest, frag)
                process_node(item, toc)

        process_node(self.tocw.invisibleRootItem(), root)
        return root

    def insert_toc_fragment(self, toc):

        def process_node(root, tocparent, added):
            for child in tocparent:
                item = self.create_item(root, child)
                added.append(item)
                process_node(item, child, added)

        self.tocw.push_history()
        nodes = []
        process_node(self.root, toc, nodes)
        self.highlight_item(nodes[0])

    def create_from_xpath(self, xpaths):
        toc = from_xpaths(self.ebook, xpaths)
        if len(toc) == 0:
            return error_dialog(self, _('No items found'),
                _('No items were found that could be added to the Table of Contents.'), show=True)
        self.insert_toc_fragment(toc)

    def create_from_links(self):
        toc = from_links(self.ebook)
        if len(toc) == 0:
            return error_dialog(self, _('No items found'),
                _('No links were found that could be added to the Table of Contents.'), show=True)
        self.insert_toc_fragment(toc)

    def create_from_files(self):
        toc = from_files(self.ebook)
        if len(toc) == 0:
            return error_dialog(self, _('No items found'),
                _('No files were found that could be added to the Table of Contents.'), show=True)
        self.insert_toc_fragment(toc)

    def undo(self):
        self.tocw.pop_history()


# }}}

class TOCEditor(QDialog):  # {{{

    explode_done = pyqtSignal(object)
    writing_done = pyqtSignal(object)

    def __init__(self, pathtobook, title=None, parent=None, prefs=None):
        QDialog.__init__(self, parent)
        self.prefs = prefs or gprefs
        self.pathtobook = pathtobook
        self.working = True

        t = title or os.path.basename(pathtobook)
        self.book_title = t
        self.setWindowTitle(_('Edit the ToC in %s')%t)
        self.setWindowIcon(QIcon(I('highlight_only_on.png')))

        l = self.l = QVBoxLayout()
        self.setLayout(l)

        self.stacks = s = QStackedWidget(self)
        l.addWidget(s)
        self.loading_widget = lw = QWidget(self)
        s.addWidget(lw)
        ll = self.ll = QVBoxLayout()
        lw.setLayout(ll)
        self.pi = pi = ProgressIndicator()
        pi.setDisplaySize(200)
        pi.startAnimation()
        ll.addWidget(pi, alignment=Qt.AlignHCenter|Qt.AlignCenter)
        la = self.wait_label = QLabel(_('Loading %s, please wait...')%t)
        la.setWordWrap(True)
        f = la.font()
        f.setPointSize(20), la.setFont(f)
        ll.addWidget(la, alignment=Qt.AlignHCenter|Qt.AlignTop)
        self.toc_view = TOCView(self, self.prefs)
        self.toc_view.add_new_item.connect(self.add_new_item)
        s.addWidget(self.toc_view)
        self.item_edit = ItemEdit(self)
        s.addWidget(self.item_edit)

        bb = self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.undo_button = b = bb.addButton(_('&Undo'), bb.ActionRole)
        b.setToolTip(_('Undo the last action, if any'))
        b.setIcon(QIcon(I('edit-undo.png')))
        b.clicked.connect(self.toc_view.undo)

        self.explode_done.connect(self.read_toc, type=Qt.QueuedConnection)
        self.writing_done.connect(self.really_accept, type=Qt.QueuedConnection)

        self.resize(950, 630)
        geom = self.prefs.get('toc_editor_window_geom', None)
        if geom is not None:
            self.restoreGeometry(bytes(geom))

    def add_new_item(self, item, where):
        self.item_edit(item, where)
        self.stacks.setCurrentIndex(2)

    def accept(self):
        if self.stacks.currentIndex() == 2:
            self.toc_view.update_item(*self.item_edit.result)
            self.prefs['toc_edit_splitter_state'] = bytearray(self.item_edit.splitter.saveState())
            self.stacks.setCurrentIndex(1)
        elif self.stacks.currentIndex() == 1:
            self.working = False
            Thread(target=self.write_toc).start()
            self.pi.startAnimation()
            self.wait_label.setText(_('Writing %s, please wait...')%
                                    self.book_title)
            self.stacks.setCurrentIndex(0)
            self.bb.setEnabled(False)

    def really_accept(self, tb):
        self.prefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
        if tb:
            error_dialog(self, _('Failed to write book'),
                _('Could not write %s. Click "Show details" for'
                  ' more information.')%self.book_title, det_msg=tb, show=True)
            self.prefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
            super(TOCEditor, self).reject()
            return

        super(TOCEditor, self).accept()

    def reject(self):
        if not self.bb.isEnabled():
            return
        if self.stacks.currentIndex() == 2:
            self.prefs['toc_edit_splitter_state'] = bytearray(self.item_edit.splitter.saveState())
            self.stacks.setCurrentIndex(1)
        else:
            self.working = False
            self.prefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
            super(TOCEditor, self).reject()

    def start(self):
        t = Thread(target=self.explode)
        t.daemon = True
        self.log = GUILog()
        t.start()

    def explode(self):
        tb = None
        try:
            self.ebook = get_container(self.pathtobook, log=self.log)
        except:
            import traceback
            tb = traceback.format_exc()
        if self.working:
            self.working = False
            self.explode_done.emit(tb)

    def read_toc(self, tb):
        if tb:
            error_dialog(self, _('Failed to load book'),
                _('Could not load %s. Click "Show details" for'
                  ' more information.')%self.book_title, det_msg=tb, show=True)
            self.reject()
            return
        self.pi.stopAnimation()
        self.toc_view(self.ebook)
        self.item_edit.load(self.ebook)
        self.stacks.setCurrentIndex(1)

    def write_toc(self):
        tb = None
        try:
            toc = self.toc_view.create_toc()
            toc.toc_title = getattr(self.toc_view, 'toc_title', None)
            commit_toc(self.ebook, toc, lang=self.toc_view.toc_lang,
                    uid=self.toc_view.toc_uid)
            self.ebook.commit()
        except:
            import traceback
            tb = traceback.format_exc()
        self.writing_done.emit(tb)

# }}}


if __name__ == '__main__':
    app = Application([], force_calibre_style=True)
    app
    d = TOCEditor(sys.argv[-1])
    d.start()
    d.exec_()
    del d  # Needed to prevent sigsegv in exit cleanup
