#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os.path

from PyQt4.Qt import (QDialog, QGridLayout, QIcon, QLabel, QTreeWidget,
                      QTreeWidgetItem, Qt, QFont, QDialogButtonBox)

from calibre.ebooks.metadata import authors_to_string

class DuplicatesQuestion(QDialog):

    def __init__(self, db, duplicates, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QGridLayout()
        self.setLayout(l)
        self.setWindowTitle(_('Duplicates found!'))
        self.i = i = QIcon(I('dialog_question.png'))
        self.setWindowIcon(i)

        self.l1 = l1 = QLabel()
        self.l2 = l2 = QLabel(_(
            'Books with the same titles as the following already '
            'exist in calibre. Select which books you want added anyway.'))
        l2.setWordWrap(True)
        l1.setPixmap(i.pixmap(128, 128))
        l.addWidget(l1, 0, 0)
        l.addWidget(l2, 0, 1)

        self.dup_list = dl = QTreeWidget(self)
        l.addWidget(dl, 1, 0, 1, 2)
        dl.setHeaderHidden(True)
        dl.addTopLevelItems(list(self.process_duplicates(db, duplicates)))
        dl.expandAll()
        dl.setIndentation(30)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 2, 0, 1, 2)
        self.ab = ab = bb.addButton(_('Select &all'), bb.ActionRole)
        ab.clicked.connect(self.select_all)
        self.nb = ab = bb.addButton(_('Select &none'), bb.ActionRole)
        ab.clicked.connect(self.select_none)

        self.resize(self.sizeHint())
        self.exec_()

    def select_all(self):
        for i in xrange(self.dup_list.topLevelItemCount()):
            x = self.dup_list.topLevelItem(i)
            x.setCheckState(0, Qt.Checked)

    def select_none(self):
        for i in xrange(self.dup_list.topLevelItemCount()):
            x = self.dup_list.topLevelItem(i)
            x.setCheckState(0, Qt.Unchecked)

    def reject(self):
        self.select_none()
        QDialog.reject(self)

    def process_duplicates(self, db, duplicates):
        ta = _('%(title)s by %(author)s [%(formats)s]')
        bf = QFont(self.dup_list.font())
        bf.setBold(True)
        itf = QFont(self.dup_list.font())
        itf.setItalic(True)

        for mi, cover, formats in duplicates:
            # formats is a list of file paths
            # Grab just the extension and display to the user
            # Based only off the file name, no file type tests are done.
            incoming_formats = ', '.join(os.path.splitext(path)[-1].replace('.', '').upper() for path in formats)
            item = QTreeWidgetItem([ta%dict(
                title=mi.title, author=mi.format_field('authors')[1],
                formats=incoming_formats)] , 0)
            item.setCheckState(0, Qt.Checked)
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            item.setData(0, Qt.FontRole, bf)
            item.setData(0, Qt.UserRole, (mi, cover, formats))
            matching_books = db.books_with_same_title(mi)

            def add_child(text):
                c = QTreeWidgetItem([text], 1)
                c.setFlags(Qt.ItemIsEnabled)
                item.addChild(c)
                return c

            add_child(_('Already in calibre:')).setData(0, Qt.FontRole, itf)

            for book_id in matching_books:
                aut = [a.replace('|', ',') for a in (db.authors(book_id,
                    index_is_id=True) or '').split(',')]
                add_child(ta%dict(
                    title=db.title(book_id, index_is_id=True),
                    author=authors_to_string(aut),
                    formats=db.formats(book_id, index_is_id=True)))
            add_child('')

            yield item

    @property
    def duplicates(self):
        for i in xrange(self.dup_list.topLevelItemCount()):
            x = self.dup_list.topLevelItem(i)
            if x.checkState(0) == Qt.Checked:
                yield x.data(0, Qt.UserRole).toPyObject()

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    from calibre.ebooks.metadata.book.base import Metadata as M
    from calibre.library import db

    app = QApplication([])
    db = db()
    d = DuplicatesQuestion(db, [(M('Life of Pi', ['Yann Martel']), None, None),
                            (M('Heirs of the blade', ['Adrian Tchaikovsky']), None, None)])
    print (tuple(d.duplicates))

