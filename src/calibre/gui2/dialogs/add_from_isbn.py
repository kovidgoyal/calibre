#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from qt.core import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QIcon, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, Qt, QVBoxLayout
)

from calibre.constants import iswindows
from calibre.ebooks.metadata import check_isbn
from calibre.gui2 import error_dialog, gprefs, question_dialog


class AddFromISBN(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setup_ui()

        path = 'C:\\Users\\kovid\\e-books\\some_book.epub' if iswindows else \
                '/Users/kovid/e-books/some_book.epub'
        self.label.setText(str(self.label.text())%path)

        self.isbns = []
        self.books = []
        self.set_tags = []

    def setup_ui(self):
        self.resize(678, 430)
        self.setWindowTitle(_("Add books by ISBN"))
        self.setWindowIcon(QIcon.ic('add_book.png'))
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel, self)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(_('&OK'))
        l.addWidget(bb), bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        self.ll = l = QVBoxLayout()
        h.addLayout(l)
        self.isbn_box = i = QPlainTextEdit(self)
        i.setFocus(Qt.FocusReason.OtherFocusReason)
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
            " path to the file after a <code>&gt;&gt;</code>. For example:</p>\n"
            "<p><code>9788842915232 &gt;&gt; %s</code></p>"), self)
        l.addWidget(la), la.setWordWrap(True)
        l.addSpacing(20)
        self.la2 = la = QLabel(_("&Tags to set on created book entries:"), self)
        l.addWidget(la)
        self.add_tags = le = QLineEdit(self)
        le.setText(', '.join(gprefs.get('add from ISBN tags', [])))
        la.setBuddy(le)
        l.addWidget(le)
        self._check_for_existing = ce = QCheckBox(_('Check for books with the same ISBN already in library'), self)
        ce.setChecked(gprefs.get('add from ISBN dup check', False))
        l.addWidget(ce)

        l.addStretch(10)

    def paste(self, *args):
        app = QApplication.instance()
        c = app.clipboard()
        txt = str(c.text()).strip()
        if txt:
            old = str(self.isbn_box.toPlainText()).strip()
            new = old + '\n' + txt
            self.isbn_box.setPlainText(new)

    @property
    def check_for_existing(self):
        return self._check_for_existing.isChecked()

    def accept(self, *args):
        tags = str(self.add_tags.text()).strip().split(',')
        tags = list(filter(None, [x.strip() for x in tags]))
        gprefs['add from ISBN tags'] = tags
        gprefs['add from ISBN dup check'] = self.check_for_existing
        self.set_tags = tags
        bad = set()
        for line in str(self.isbn_box.toPlainText()).strip().splitlines():
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
                        ' be ignored. Click "Show details" to see which ones.'
                        ' Do you want to proceed?'), det_msg='\n'.join(bad),
                    show_copy_button=True):
                    return
            else:
                return error_dialog(self, _('All invalid ISBNs'),
                        _('All the ISBNs you entered were invalid. No books'
                            ' can be added.'), show=True)
        QDialog.accept(self, *args)
