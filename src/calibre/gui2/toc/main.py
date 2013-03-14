#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os
from threading import Thread
from functools import partial

from PyQt4.Qt import (QPushButton, QFrame, QVariant,
    QDialog, QVBoxLayout, QDialogButtonBox, QSize, QStackedWidget, QWidget,
    QLabel, Qt, pyqtSignal, QIcon, QTreeWidget, QGridLayout, QTreeWidgetItem,
    QToolButton, QItemSelectionModel)

from calibre.ebooks.oeb.polish.container import get_container, AZW3Container
from calibre.ebooks.oeb.polish.toc import get_toc, add_id, TOC, commit_toc
from calibre.gui2 import Application, error_dialog, gprefs
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.toc.location import ItemEdit
from calibre.utils.logging import GUILog

ICON_SIZE = 24

class ItemView(QFrame): # {{{

    add_new_item = pyqtSignal(object, object)
    delete_item = pyqtSignal()
    flatten_item = pyqtSignal()

    def __init__(self, parent):
        QFrame.__init__(self, parent)
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
        ip.hl4 = hl =  QFrame()
        hl.setFrameShape(hl.HLine)
        l.addWidget(hl, l.rowCount(), 0, 1, 2)
        l.setRowMinimumHeight(rs, 20)

        # Flatten entry
        rs = l.rowCount()
        ip.b3 = b = QPushButton(QIcon(I('heuristics.png')), _('&Flatten this entry'))
        b.clicked.connect(self.flatten_item)
        b.setToolTip(_('All children of this entry are brought to the same '
                       'level as this entry.'))
        l.addWidget(b, l.rowCount()+1, 0, 1, 2)
        l.setRowMinimumHeight(rs, 20)

        l.addWidget(QLabel(), l.rowCount(), 0, 1, 2)
        l.setColumnStretch(1, 10)
        l.setRowStretch(l.rowCount()-1, 10)
        self.w2 = la = QLabel(self.w1.text())
        self.w2.setWordWrap(True)
        l.addWidget(la, l.rowCount(), 0, 1, 2)

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
        name = unicode(item.data(0, Qt.DisplayRole).toString())
        self.item_pane.heading.setText('<h2>%s</h2>'%name)
        self.icon_label.setPixmap(item.data(0, Qt.DecorationRole
                                            ).toPyObject().pixmap(32, 32))
        tt = _('This entry points to an existing destination')
        toc = item.data(0, Qt.UserRole).toPyObject()
        if toc.dest_exists is False:
            tt = _('The location this entry points to does not exist')
        elif toc.dest_exists is None:
            tt = ''
        self.status_label.setText(tt)

    def data_changed(self, item):
        if item is self.current_item:
            self.populate_item_pane()

# }}}

class TOCView(QWidget): # {{{

    add_new_item = pyqtSignal(object, object)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        l = self.l = QGridLayout()
        self.setLayout(l)
        self.tocw = t = QTreeWidget(self)
        t.setHeaderLabel(_('Table of Contents'))
        t.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        t.setDragEnabled(True)
        t.setSelectionMode(t.ExtendedSelection)
        t.viewport().setAcceptDrops(True)
        t.setDropIndicatorShown(True)
        t.setDragDropMode(t.InternalMove)
        t.setAutoScroll(True)
        t.setAutoScrollMargin(ICON_SIZE*2)
        t.setDefaultDropAction(Qt.MoveAction)
        t.setAutoExpandDelay(1000)
        t.setAnimated(True)
        t.setMouseTracking(True)
        l.addWidget(t, 0, 0, 5, 3)
        self.up_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 0, 3)
        b.setToolTip(_('Move current entry up'))
        b.clicked.connect(self.move_up)
        self.del_button = b = QToolButton(self)
        b.setIcon(QIcon(I('trash.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 2, 3)
        b.setToolTip(_('Remove all selected entries'))
        b.clicked.connect(self.del_items)
        self.down_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        b.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        l.addWidget(b, 4, 3)
        b.setToolTip(_('Move current entry down'))
        b.clicked.connect(self.move_down)
        self.expand_all_button = b = QPushButton(_('&Expand all'))
        col = 5
        l.addWidget(b, col, 0)
        b.clicked.connect(self.tocw.expandAll)
        self.collapse_all_button = b = QPushButton(_('&Collapse all'))
        b.clicked.connect(self.tocw.collapseAll)
        l.addWidget(b, col, 1)
        self.default_msg = _('Double click on an entry to change the text')
        self.hl = hl = QLabel(self.default_msg)
        l.addWidget(hl, col, 2, 1, -1)
        self.item_view = i = ItemView(self)
        self.item_view.delete_item.connect(self.delete_current_item)
        i.add_new_item.connect(self.add_new_item)
        i.flatten_item.connect(self.flatten_item)
        l.addWidget(i, 0, 4, col, 1)

        l.setColumnStretch(2, 10)

    def event(self, e):
        if e.type() == e.StatusTip:
            txt = unicode(e.tip()) or self.default_msg
            self.hl.setText(txt)
        return super(TOCView, self).event(e)

    def item_title(self, item):
        return unicode(item.data(0, Qt.DisplayRole).toString())

    def del_items(self):
        for item in self.tocw.selectedItems():
            p = item.parent() or self.root
            p.removeChild(item)

    def delete_current_item(self):
        item = self.tocw.currentItem()
        if item is not None:
            p = item.parent() or self.root
            p.removeChild(item)

    def flatten_item(self):
        item = self.tocw.currentItem()
        if item is not None:
            p = item.parent() or self.root
            idx = p.indexOfChild(item)
            children = [item.child(i) for i in xrange(item.childCount())]
            for child in reversed(children):
                item.removeChild(child)
                p.insertChild(idx+1, child)

    def highlight_item(self, item):
        self.tocw.setCurrentItem(item, 0, QItemSelectionModel.ClearAndSelect)
        self.tocw.scrollToItem(item)

    def move_down(self):
        item = self.tocw.currentItem()
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
        item = self.tocw.currentItem()
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

    def update_status_tip(self, item):
        c = item.data(0, Qt.UserRole).toPyObject()
        if c is not None:
            frag = c.frag or ''
            if frag:
                frag = '#'+frag
            item.setStatusTip(0, _('<b>Title</b>: {0} <b>Dest</b>: {1}{2}').format(
                c.title, c.dest, frag))

    def data_changed(self, top_left, bottom_right):
        for r in xrange(top_left.row(), bottom_right.row()+1):
            idx = self.tocw.model().index(r, 0, top_left.parent())
            new_title = unicode(idx.data(Qt.DisplayRole).toString()).strip()
            toc = idx.data(Qt.UserRole).toPyObject()
            if toc is not None:
                toc.title = new_title or _('(Untitled)')
            item = self.tocw.itemFromIndex(idx)
            self.update_status_tip(item)
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
        c.setFlags(Qt.ItemIsDragEnabled|Qt.ItemIsEditable|Qt.ItemIsEnabled|
                    Qt.ItemIsSelectable|Qt.ItemIsDropEnabled)
        c.setData(0, Qt.DecorationRole, self.icon_map[child.dest_exists])
        if child.dest_exists is False:
            c.setData(0, Qt.ToolTipRole, _(
                'The location this entry point to does not exist:\n%s')
                %child.dest_error)
        else:
            c.setData(0, Qt.ToolTipRole, QVariant())

        self.update_status_tip(c)

    def __call__(self, ebook):
        self.ebook = ebook
        if not isinstance(ebook, AZW3Container):
            self.item_view.hide_azw3_warning()
        self.toc = get_toc(self.ebook)
        self.toc_lang, self.toc_uid = self.toc.lang, self.toc.uid
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
            frag = add_id(self.ebook, name, frag)
        child = TOC(title, name, frag)
        child.dest_exists = True
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
                    if where == 'after': idx += 1
                c = self.create_item(parent, child, idx=idx)
                self.tocw.setCurrentItem(c, 0, QItemSelectionModel.ClearAndSelect)
                self.tocw.scrollToItem(c)


    def create_toc(self):
        root = TOC()

        def process_node(parent, toc_parent):
            for i in xrange(parent.childCount()):
                item = parent.child(i)
                title = unicode(item.data(0, Qt.DisplayRole).toString()).strip()
                toc = item.data(0, Qt.UserRole).toPyObject()
                dest, frag = toc.dest, toc.frag
                toc = toc_parent.add(title, dest, frag)
                process_node(item, toc)

        process_node(self.tocw.invisibleRootItem(), root)
        return root

# }}}

class TOCEditor(QDialog): # {{{

    explode_done = pyqtSignal(object)
    writing_done = pyqtSignal(object)

    def __init__(self, pathtobook, title=None, parent=None):
        QDialog.__init__(self, parent)
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
        la.setStyleSheet('QLabel { font-size: 20pt }')
        ll.addWidget(la, alignment=Qt.AlignHCenter|Qt.AlignTop)
        self.toc_view = TOCView(self)
        self.toc_view.add_new_item.connect(self.add_new_item)
        s.addWidget(self.toc_view)
        self.item_edit = ItemEdit(self)
        s.addWidget(self.item_edit)

        bb = self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self.explode_done.connect(self.read_toc, type=Qt.QueuedConnection)
        self.writing_done.connect(self.really_accept, type=Qt.QueuedConnection)

        self.resize(950, 630)
        geom = gprefs.get('toc_editor_window_geom', None)
        if geom is not None:
            self.restoreGeometry(bytes(geom))

    def add_new_item(self, item, where):
        self.item_edit(item, where)
        self.stacks.setCurrentIndex(2)

    def accept(self):
        if self.stacks.currentIndex() == 2:
            self.toc_view.update_item(*self.item_edit.result)
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
        gprefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
        if tb:
            error_dialog(self, _('Failed to write book'),
                _('Could not write %s. Click "Show details" for'
                  ' more information.')%self.book_title, det_msg=tb, show=True)
            gprefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
            super(TOCEditor, self).reject()
            return

        super(TOCEditor, self).accept()

    def reject(self):
        if not self.bb.isEnabled():
            return
        if self.stacks.currentIndex() == 2:
            self.stacks.setCurrentIndex(1)
        else:
            self.working = False
            gprefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
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
    del d # Needed to prevent sigsegv in exit cleanup

