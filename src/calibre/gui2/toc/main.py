#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os
from threading import Thread

from PyQt4.Qt import (QDialog, QVBoxLayout, QDialogButtonBox, QSize,
                      QStackedWidget, QWidget, QLabel, Qt, pyqtSignal, QIcon,
                      QTreeWidget, QHBoxLayout, QTreeWidgetItem)

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.gui2 import Application
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils.logging import GUILog

class TOCView(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        l = self.l = QHBoxLayout()
        self.setLayout(l)
        self.tocw = t = QTreeWidget(self)
        t.setHeaderLabel(_('Table of Contents'))
        icon_size = 16
        t.setIconSize(QSize(icon_size, icon_size))
        t.setDragEnabled(True)
        t.setSelectionMode(t.SingleSelection)
        t.viewport().setAcceptDrops(True)
        t.setDropIndicatorShown(True)
        t.setDragDropMode(t.InternalMove)
        t.setAutoScroll(True)
        t.setAutoScrollMargin(icon_size*2)
        t.setDefaultDropAction(Qt.MoveAction)
        l.addWidget(t)

    def data_changed(self, top_left, bottom_right):
        for r in xrange(top_left.row(), bottom_right.row()+1):
            idx = self.tocw.model().index(r, 0, top_left.parent())
            new_title = unicode(idx.data(Qt.DisplayRole).toString()).strip()
            toc = idx.data(Qt.UserRole).toPyObject()
            toc.title = new_title or _('(Untitled)')

    def __call__(self, ebook):
        self.ebook = ebook
        self.toc = get_toc(self.ebook)
        blank = QIcon(I('blank.png'))

        def process_item(node, parent):
            for child in node:
                c = QTreeWidgetItem(parent)
                c.setData(0, Qt.DisplayRole, child.title or _('(Untitled)'))
                c.setData(0, Qt.UserRole, child)
                c.setFlags(Qt.ItemIsDragEnabled|Qt.ItemIsEditable|Qt.ItemIsEnabled|
                           Qt.ItemIsSelectable|Qt.ItemIsDropEnabled)
                c.setData(0, Qt.DecorationRole, blank)
                process_item(child, c)

        root = self.tocw.invisibleRootItem()
        root.setData(0, Qt.UserRole, self.toc)
        process_item(self.toc, root)
        self.tocw.model().dataChanged.connect(self.data_changed)

class TOCEditor(QDialog):

    explode_done = pyqtSignal()

    def __init__(self, pathtobook, title=None, parent=None):
        QDialog.__init__(self, parent)
        self.pathtobook = pathtobook

        t = title or os.path.basename(pathtobook)
        self.setWindowTitle(_('Edit the ToC in %s')%t)
        self.setWindowIcon(QIcon(I('highlight_only_on.png')))

        l = self.l = QVBoxLayout()
        self.setLayout(l)

        self.stacks = s = QStackedWidget(self)
        l.addWidget(s)
        self.loading_widget = lw = QWidget(self)
        s.addWidget(lw)
        ll = QVBoxLayout()
        lw.setLayout(ll)
        self.pi = pi = ProgressIndicator()
        pi.setDisplaySize(200)
        pi.startAnimation()
        ll.addWidget(pi, alignment=Qt.AlignHCenter|Qt.AlignCenter)
        la = QLabel(_('Loading %s, please wait...')%t)
        la.setStyleSheet('QLabel { font-size: 20pt }')
        ll.addWidget(la, alignment=Qt.AlignHCenter|Qt.AlignTop)
        self.toc_view = TOCView(self)
        s.addWidget(self.toc_view)

        bb = self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self.explode_done.connect(self.read_toc, type=Qt.QueuedConnection)

        self.resize(950, 630)

    def start(self):
        t = Thread(target=self.explode)
        t.daemon = True
        self.log = GUILog()
        t.start()

    def explode(self):
        self.ebook = get_container(self.pathtobook, log=self.log)
        if not self.isVisible():
            return
        self.explode_done.emit()

    def read_toc(self):
        self.toc_view(self.ebook)
        self.stacks.setCurrentIndex(1)

if __name__ == '__main__':
    app = Application([], force_calibre_style=True)
    app
    d = TOCEditor(sys.argv[-1])
    d.start()
    d.exec_()

