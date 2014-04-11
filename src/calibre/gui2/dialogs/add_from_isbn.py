#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from PyQt5.Qt import QDialog, QApplication

from calibre.gui2.dialogs.add_from_isbn_ui import Ui_Dialog
from calibre.ebooks.metadata import check_isbn
from calibre.constants import iswindows
from calibre.gui2 import gprefs, question_dialog, error_dialog

class AddFromISBN(QDialog, Ui_Dialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        path = r'C:\Users\kovid\e-books\some_book.epub' if iswindows else \
                '/Users/kovid/e-books/some_book.epub'
        self.label.setText(unicode(self.label.text())%path)

        self.isbns = []
        self.books = []
        self.set_tags = []
        self.paste_button.clicked.connect(self.paste)
        self.add_tags.setText(', '.join(gprefs.get('add from ISBN tags', [])))

    def paste(self, *args):
        app = QApplication.instance()
        c = app.clipboard()
        txt = unicode(c.text()).strip()
        if txt:
            old = unicode(self.isbn_box.toPlainText()).strip()
            new = old + '\n' + txt
            self.isbn_box.setPlainText(new)

    def accept(self, *args):
        tags = unicode(self.add_tags.text()).strip().split(',')
        tags = list(filter(None, [x.strip() for x in tags]))
        gprefs['add from ISBN tags'] = tags
        self.set_tags = tags
        bad = set()
        for line in unicode(self.isbn_box.toPlainText()).strip().splitlines():
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

