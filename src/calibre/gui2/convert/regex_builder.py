# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog, QWidget, QDialogButtonBox, QFileDialog, \
                        QBrush, QTextCursor, QTextEdit

from calibre.gui2.convert.regex_builder_ui import Ui_RegexBuilder
from calibre.gui2.convert.xexp_edit_ui import Ui_Form as Ui_Edit
from calibre.gui2 import qstring_to_unicode
from calibre.gui2 import error_dialog
from calibre.ebooks.oeb.iterator import EbookIterator
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog

class RegexBuilder(QDialog, Ui_RegexBuilder):

    def __init__(self, db, book_id, regex, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

        self.regex.setText(regex)
        self.regex_valid()

        if not db or not book_id:
            self.button_box.addButton(QDialogButtonBox.Open)
        else:
            self.select_format(db, book_id)

        self.connect(self.button_box, SIGNAL('clicked(QAbstractButton*)'), self.button_clicked)
        self.connect(self.regex, SIGNAL('textChanged(QString)'), self.regex_valid)
        self.connect(self.test, SIGNAL('clicked()'), self.do_test)

    def regex_valid(self):
        regex = qstring_to_unicode(self.regex.text())
        if regex:
            try:
                re.compile(regex)
                self.regex.setStyleSheet('QLineEdit { color: black; background-color: rgba(0,255,0,20%); }')
            except:
                self.regex.setStyleSheet('QLineEdit { color: black; background-color: rgb(255,0,0,20%); }')
                return False
        else:
            self.regex.setStyleSheet('QLineEdit { color: black; background-color: white; }')
        return True

    def do_test(self):
        selections = []
        if self.regex_valid():
            text = qstring_to_unicode(self.preview.toPlainText())
            regex = qstring_to_unicode(self.regex.text())
            cursor = QTextCursor(self.preview.document())
            extsel = QTextEdit.ExtraSelection()
            extsel.cursor = cursor
            extsel.format.setBackground(QBrush(Qt.yellow))
            try:
                for match in re.finditer(regex, text):
                    es = QTextEdit.ExtraSelection(extsel)
                    es.cursor.setPosition(match.start(), QTextCursor.MoveAnchor)
                    es.cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                    selections.append(es)
            except:
                pass
        self.preview.setExtraSelections(selections)

    def select_format(self, db, book_id):
        format = None
        formats = db.formats(book_id, index_is_id=True).upper().split(',')
        if len(formats) == 1:
            format = formats[0]
        elif len(formats) > 1:
            d = ChooseFormatDialog(self, _('Choose the format to view'), formats)
            d.exec_()
            if d.result() == QDialog.Accepted:
                format = d.format()

        if not format:
            error_dialog(self, _('No formats available'), _('Cannot build regex using the GUI builder without a book.'))
            QDialog.reject()
        else:
            self.open_book(db.format_abspath(book_id, format, index_is_id=True))

    def open_book(self, pathtoebook):
        self.iterator = EbookIterator(pathtoebook)
        self.iterator.__enter__(processed=True)
        text = [u'']
        for path in self.iterator.spine:
            html = open(path, 'rb').read().decode('utf-8', 'replace')
            text.append(html)
        self.preview.setPlainText('\n---\n'.join(text))

    def button_clicked(self, button):
        if button == self.button_box.button(QDialogButtonBox.Open):
            name = QFileDialog.getOpenFileName(self, _('Open book'), _('~'))
            if name:
                self.open_book(qstring_to_unicode(name))
        if button == self.button_box.button(QDialogButtonBox.Ok):
            self.accept()

class RegexEdit(QWidget, Ui_Edit):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self.book_id = None
        self.db = None

        self.connect(self.button, SIGNAL('clicked()'), self.builder)

    def builder(self):
        bld = RegexBuilder(self.db, self.book_id, self.edit.text(), self)
        if bld.exec_() == bld.Accepted:
            self.edit.setText(bld.regex.text())

    def set_msg(self, msg):
        self.msg.setText(msg)

    def set_book_id(self, book_id):
        self.book_id = book_id

    def set_db(self, db):
        self.db = db

    def break_cycles(self):
        self.db = None

    @property
    def text(self):
        return unicode(self.edit.text())

    @property
    def regex(self):
        return self.text

    def check(self):
        return True
