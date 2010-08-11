#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QDialog, QApplication

from calibre.gui2.dialogs.add_from_isbn_ui import Ui_Dialog
from calibre.ebooks.metadata import check_isbn

class AddFromISBN(QDialog, Ui_Dialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.isbns = []
        self.paste_button.clicked.connect(self.paste)

    def paste(self, *args):
        app = QApplication.instance()
        c = app.clipboard()
        txt = unicode(c.text()).strip()
        if txt:
            old = unicode(self.isbn_box.toPlainText()).strip()
            new = old + '\n' + txt
            self.isbn_box.setPlainText(new)

    def accept(self, *args):
        for line in unicode(self.isbn_box.toPlainText()).strip().splitlines():
            if line:
                isbn = check_isbn(line)
                if isbn is not None:
                    isbn = isbn.upper()
                    if isbn not in self.isbns:
                        self.isbns.append(isbn)
        QDialog.accept(self, *args)

