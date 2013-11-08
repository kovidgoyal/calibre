#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (QDialog, pyqtSignal, QIcon, QVBoxLayout, QDialogButtonBox, QStackedWidget)

from calibre.ebooks.oeb.polish.toc import commit_toc
from calibre.gui2 import gprefs, error_dialog
from calibre.gui2.toc.main import TOCView, ItemEdit
from calibre.gui2.tweak_book import current_container

class TOCEditor(QDialog):

    explode_done = pyqtSignal(object)
    writing_done = pyqtSignal(object)

    def __init__(self, title=None, parent=None):
        QDialog.__init__(self, parent)

        t = title or current_container().mi.title
        self.book_title = t
        self.setWindowTitle(_('Edit the ToC in %s')%t)
        self.setWindowIcon(QIcon(I('toc.png')))

        l = self.l = QVBoxLayout()
        self.setLayout(l)

        self.stacks = s = QStackedWidget(self)
        l.addWidget(s)
        self.toc_view = TOCView(self)
        self.toc_view.add_new_item.connect(self.add_new_item)
        s.addWidget(self.toc_view)
        self.item_edit = ItemEdit(self)
        s.addWidget(self.item_edit)

        bb = self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self.read_toc()

        self.resize(950, 630)
        geom = gprefs.get('toc_editor_window_geom', None)
        if geom is not None:
            self.restoreGeometry(bytes(geom))

    def add_new_item(self, item, where):
        self.item_edit(item, where)
        self.stacks.setCurrentIndex(1)

    def accept(self):
        if self.stacks.currentIndex() == 1:
            self.toc_view.update_item(*self.item_edit.result)
            gprefs['toc_edit_splitter_state'] = bytearray(self.item_edit.splitter.saveState())
            self.stacks.setCurrentIndex(0)
        elif self.stacks.currentIndex() == 0:
            self.write_toc()
            super(TOCEditor, self).accept()

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
        if self.stacks.currentIndex() == 1:
            gprefs['toc_edit_splitter_state'] = bytearray(self.item_edit.splitter.saveState())
            self.stacks.setCurrentIndex(0)
        else:
            gprefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
            super(TOCEditor, self).reject()

    def read_toc(self):
        self.toc_view(current_container())
        self.item_edit.load(current_container())
        self.stacks.setCurrentIndex(0)

    def write_toc(self):
        toc = self.toc_view.create_toc()
        commit_toc(current_container(), toc, lang=self.toc_view.toc_lang,
                uid=self.toc_view.toc_uid)

