#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os.path

from qt.core import (
    QDialog, QGridLayout, QIcon, QLabel, QTreeWidget, QTreeWidgetItem, Qt,
    QFont, QDialogButtonBox, QApplication)

from calibre.gui2 import gprefs
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.icu import primary_sort_key


class DuplicatesQuestion(QDialog):

    def __init__(self, db, duplicates, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QGridLayout()
        self.setLayout(l)
        t = ngettext('Duplicate found', 'duplicates found', len(duplicates))
        if len(duplicates) > 1:
            t = '%d %s' % (len(duplicates), t)
        self.setWindowTitle(t)
        self.i = i = QIcon.ic('dialog_question.png')
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

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 2, 0, 1, 2)
        l.setColumnStretch(1, 10)
        self.ab = ab = bb.addButton(_('Select &all'), QDialogButtonBox.ButtonRole.ActionRole)
        ab.clicked.connect(self.select_all), ab.setIcon(QIcon.ic('plus.png'))
        self.nb = ab = bb.addButton(_('Select &none'), QDialogButtonBox.ButtonRole.ActionRole)
        ab.clicked.connect(self.select_none), ab.setIcon(QIcon.ic('minus.png'))
        self.cb = cb = bb.addButton(_('&Copy to clipboard'), QDialogButtonBox.ButtonRole.ActionRole)
        cb.setIcon(QIcon.ic('edit-copy.png'))
        cb.clicked.connect(self.copy_to_clipboard)

        self.resize(self.sizeHint())
        geom = gprefs.get('duplicates-question-dialog-geometry', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)
        self.exec()

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.as_text)

    def select_all(self):
        for i in range(self.dup_list.topLevelItemCount()):
            x = self.dup_list.topLevelItem(i)
            x.setCheckState(0, Qt.CheckState.Checked)

    def select_none(self):
        for i in range(self.dup_list.topLevelItemCount()):
            x = self.dup_list.topLevelItem(i)
            x.setCheckState(0, Qt.CheckState.Unchecked)

    def reject(self):
        self.save_geometry()
        self.select_none()
        QDialog.reject(self)

    def accept(self):
        self.save_geometry()
        QDialog.accept(self)

    def save_geometry(self):
        gprefs.set('duplicates-question-dialog-geometry', bytearray(self.saveGeometry()))

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
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(0, Qt.ItemDataRole.FontRole, bf)
            item.setData(0, Qt.ItemDataRole.UserRole, (mi, cover, formats))
            matching_books = db.books_with_same_title(mi)

            def add_child(text):
                c = QTreeWidgetItem([text], 1)
                c.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.addChild(c)
                return c

            add_child(_('Already in calibre:')).setData(0, Qt.ItemDataRole.FontRole, itf)

            author_text = {}
            for book_id in matching_books:
                author_text[book_id] = authors_to_string([a.replace('|', ',') for a in (db.authors(book_id,
                    index_is_id=True) or '').split(',')])

            def key(x):
                return primary_sort_key(str(author_text[x]))

            for book_id in sorted(matching_books, key=key):
                add_child(ta%dict(
                    title=db.title(book_id, index_is_id=True),
                    author=author_text[book_id],
                    formats=db.formats(book_id, index_is_id=True,
                                       verify_formats=False)))
            add_child('')

            yield item

    @property
    def duplicates(self):
        for i in range(self.dup_list.topLevelItemCount()):
            x = self.dup_list.topLevelItem(i)
            if x.checkState(0) == Qt.CheckState.Checked:
                yield x.data(0, Qt.ItemDataRole.UserRole)

    @property
    def as_text(self):
        entries = []
        for i in range(self.dup_list.topLevelItemCount()):
            x = self.dup_list.topLevelItem(i)
            check = '✓' if x.checkState(0) == Qt.CheckState.Checked else '✗'
            title = f'{check} {str(x.text(0))}'
            dups = []
            for child in (x.child(j) for j in range(x.childCount())):
                dups.append('\t' + str(child.text(0)))
            entries.append(title + '\n' + '\n'.join(dups))
        return '\n\n'.join(entries)


if __name__ == '__main__':
    from calibre.ebooks.metadata.book.base import Metadata as M
    from calibre.library import db

    app = QApplication([])
    db = db()
    d = DuplicatesQuestion(db, [(M('Life of Pi', ['Yann Martel']), None, None),
                            (M('Heirs of the blade', ['Adrian Tchaikovsky']), None, None)])
    print(tuple(d.duplicates))
