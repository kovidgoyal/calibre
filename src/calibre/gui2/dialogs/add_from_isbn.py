#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from PyQt5.Qt import (
    QDialog, QApplication, QIcon, QVBoxLayout, QHBoxLayout, QDialogButtonBox,
    QPlainTextEdit, QPushButton, QLabel, QLineEdit, Qt
)

from calibre.ebooks.metadata import check_isbn
from calibre.constants import iswindows
from calibre.gui2 import gprefs, question_dialog, error_dialog
from polyglot.builtins import unicode_type, filter


class AddFromISBN(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setup_ui()

        path = 'C:\\Users\\kovid\\e-books\\some_book.epub' if iswindows else \
                '/Users/kovid/e-books/some_book.epub'
        self.label.setText(unicode_type(self.label.text())%path)

        self.isbns = []
        self.books = []
        self.set_tags = []

    def setup_ui(self):
        self.resize(678, 430)
        self.setWindowTitle(_("Add books by ISBN"))
        self.setWindowIcon(QIcon(I('add_book.png')))
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel, self)
        bb.button(bb.Ok).setText(_('&OK'))
        l.addWidget(bb), bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        self.ll = l = QVBoxLayout()
        h.addLayout(l)
        self.isbn_box = i = QPlainTextEdit(self)
        i.setFocus(Qt.OtherFocusReason)
        l.addWidget(i)
        self.paste_button = b = QPushButton(_("&Paste from clipboard"), self)
        l.addWidget(b), b.clicked.connect(self.paste)
        self.lll = l  = QVBoxLayout()
        h.addLayout(l)
        self.label = la = QLabel(_(
            "<p>Enter a list of ISBNs in the box to the left, one per line. calibre will automatically"
            " create entries for books based on the ISBN and download metadata and covers for them.</p>\n"
            "<p>Any invalid ISBNs in the list will be ignored.</p>\n"
            "<p>You can also specify a file that will be added with each ISBN. To do this enter the full"
            " path to the file after a <code>>></code>.  For example:</p>\n"
            "<p><code>9788842915232 >> %s</code></p>"), self)
        l.addWidget(la), la.setWordWrap(True)
        l.addSpacing(20)
        self.la2 = la = QLabel(_("&Tags to set on created book entries:"), self)
        l.addWidget(la)
        self.add_tags = le = QLineEdit(self)
        le.setText(', '.join(gprefs.get('add from ISBN tags', [])))
        la.setBuddy(le)
        l.addWidget(le)
        l.addStretch(10)

    def paste(self, *args):
        app = QApplication.instance()
        c = app.clipboard()
        txt = unicode_type(c.text()).strip()
        if txt:
            old = unicode_type(self.isbn_box.toPlainText()).strip()
            new = old + '\n' + txt
            self.isbn_box.setPlainText(new)

    def accept(self, *args):
        tags = unicode_type(self.add_tags.text()).strip().split(',')
        tags = list(filter(None, [x.strip() for x in tags]))
        gprefs['add from ISBN tags'] = tags
        self.set_tags = tags
        bad = set()
        for line in unicode_type(self.isbn_box.toPlainText()).strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split('>>')
            if len(parts) > 2:
                parts = [parts[0] + '>>'.join(parts[1:])]
            parts = [x.strip() for x in parts]
            if not parts[0]:
                continue
            isbn = check_isbn(parts[0])
            if isbn is not None:
                isbn = isbn.upper()
                if isbn not in self.isbns:
                    self.isbns.append(isbn)
                    book = {'isbn': isbn, 'path': None}
                    if len(parts) > 1 and parts[1] and \
                        os.access(parts[1], os.R_OK) and os.path.isfile(parts[1]):
                        book['path'] = parts[1]
                    self.books.append(book)
            else:
                bad.add(parts[0])
        if bad:
            if self.books:
                if not question_dialog(self, _('Some invalid ISBNs'),
                    _('Some of the ISBNs you entered were invalid. They will'
                        ' be ignored. Click Show Details to see which ones.'
                        ' Do you want to proceed?'), det_msg='\n'.join(bad),
                    show_copy_button=True):
                    return
            else:
                return error_dialog(self, _('All invalid ISBNs'),
                        _('All the ISBNs you entered were invalid. No books'
                            ' can be added.'), show=True)
        QDialog.accept(self, *args)
