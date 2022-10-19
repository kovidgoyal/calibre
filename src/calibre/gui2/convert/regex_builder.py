#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import os
from contextlib import suppress
from qt.core import (
    QBrush, QDialog, QDialogButtonBox, Qt, QTextCursor,
    QTextEdit, pyqtSignal
)

from calibre.constants import iswindows
from calibre.ebooks.conversion.search_replace import compile_regular_expression
from calibre.gui2 import choose_files, error_dialog, gprefs
from calibre.gui2.convert.regex_builder_ui import Ui_RegexBuilder
from calibre.gui2.convert.xpath_wizard import XPathEdit
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.ptempfile import TemporaryFile
from calibre.utils.icu import utf16_length
from calibre.utils.ipc.simple_worker import WorkerError, fork_job
from polyglot.builtins import native_string_type


class RegexBuilder(QDialog, Ui_RegexBuilder):

    def __init__(self, db, book_id, regex, doc=None, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.regex.setText(regex)
        self.regex_valid()

        if not db or not book_id:
            button = self.button_box.addButton(QDialogButtonBox.StandardButton.Open)
            button.clicked.connect(self.open_clicked)
        elif not doc and not self.select_format(db, book_id):
            self.cancelled = True
            return

        if doc:
            self.preview.setPlainText(doc)

        self.cancelled = False
        self.button_box.accepted.connect(self.accept)
        self.regex.textChanged[native_string_type].connect(self.regex_valid)
        for src, slot in (('test', 'do'), ('previous', 'goto'), ('next',
            'goto')):
            getattr(self, src).clicked.connect(getattr(self, '%s_%s'%(slot,
                src)))
        self.test.setDefault(True)

        self.match_locs = []
        self.restore_geometry(gprefs, 'regex_builder_geometry')
        self.finished.connect(self.save_state)

    def save_state(self, result):
        self.save_geometry(gprefs, 'regex_builder_geometry')

    def regex_valid(self):
        regex = str(self.regex.text())
        if regex:
            try:
                compile_regular_expression(regex)
                self.regex.setStyleSheet('QLineEdit { color: black; background-color: rgba(0,255,0,20%); }')
                return True
            except:
                self.regex.setStyleSheet('QLineEdit { color: black; background-color: rgba(255,0,0,20%); }')
        else:
            self.regex.setStyleSheet('QLineEdit { color: black; background-color: white; }')
            self.preview.setExtraSelections([])

        self.match_locs = []
        self.next.setEnabled(False)
        self.previous.setEnabled(False)
        self.occurrences.setText('0')

        return False

    def do_test(self):
        selections = []
        self.match_locs = []

        class Pos:
            python: int = 0
            qt: int = 0

        if self.regex_valid():
            text = str(self.preview.toPlainText())
            regex = str(self.regex.text())
            cursor = QTextCursor(self.preview.document())
            extsel = QTextEdit.ExtraSelection()
            extsel.cursor = cursor
            extsel.format.setBackground(QBrush(Qt.GlobalColor.yellow))
            with suppress(Exception):
                prev = Pos()
                for match in compile_regular_expression(regex).finditer(text):
                    es = QTextEdit.ExtraSelection(extsel)
                    qtchars_to_start = utf16_length(text[prev.python:match.start()])
                    qt_pos = prev.qt + qtchars_to_start
                    prev.python = match.end()
                    prev.qt = qt_pos + utf16_length(match.group())
                    es.cursor.setPosition(qt_pos, QTextCursor.MoveMode.MoveAnchor)
                    es.cursor.setPosition(prev.qt, QTextCursor.MoveMode.KeepAnchor)
                    selections.append(es)
                    self.match_locs.append((qt_pos, prev.qt))
        self.preview.setExtraSelections(selections)
        if self.match_locs:
            self.next.setEnabled(True)
            self.previous.setEnabled(True)
        self.occurrences.setText(str(len(self.match_locs)))

    def goto_previous(self):
        pos = self.preview.textCursor().position()
        if self.match_locs:
            match_loc = len(self.match_locs) - 1
            for i in range(len(self.match_locs) - 1, -1, -1):
                loc = self.match_locs[i][1]
                if pos > loc:
                    match_loc = i
                    break
            self.goto_loc(
                self.match_locs[match_loc][1],
                operation=QTextCursor.MoveOperation.Left,
                n=self.match_locs[match_loc][1] - self.match_locs[match_loc][0])

    def goto_next(self):
        pos = self.preview.textCursor().position()
        if self.match_locs:
            match_loc = 0
            for i in range(len(self.match_locs)):
                loc = self.match_locs[i][0]
                if pos < loc:
                    match_loc = i
                    break
            self.goto_loc(self.match_locs[match_loc][0], n=self.match_locs[match_loc][1] - self.match_locs[match_loc][0])

    def goto_loc(self, loc, operation=QTextCursor.MoveOperation.Right, mode=QTextCursor.MoveMode.KeepAnchor, n=0):
        cursor = QTextCursor(self.preview.document())
        cursor.setPosition(loc)
        if n:
            cursor.movePosition(operation, mode, n)
        self.preview.setTextCursor(cursor)

    def select_format(self, db, book_id):
        format = None
        formats = db.formats(book_id, index_is_id=True).upper().split(',')
        if len(formats) == 1:
            format = formats[0]
        elif len(formats) > 1:
            d = ChooseFormatDialog(self, _('Choose the format to view'), formats)
            d.exec()
            if d.result() == QDialog.DialogCode.Accepted:
                format = d.format()
            else:
                return False

        if not format:
            error_dialog(self, _('No formats available'),
                         _('Cannot build regex using the GUI builder without a book.'),
                         show=True)
            return False
        try:
            fpath = db.format(book_id, format, index_is_id=True,
                as_path=True)
        except OSError:
            if iswindows:
                import traceback
                error_dialog(self, _('Could not open file'),
                    _('Could not open the file, do you have it open in'
                        ' another program?'), show=True,
                    det_msg=traceback.format_exc())
                return False
            raise
        try:
            self.open_book(fpath)
        finally:
            try:
                os.remove(fpath)
            except:
                # Fails on windows if the input plugin for this format keeps the file open
                # Happens for LIT files
                pass
        return True

    def open_book(self, pathtoebook):
        with TemporaryFile('_prepprocess_gui') as tf:
            err_msg = _('Failed to generate markup for testing. Click '
                            '"Show details" to learn more.')
            try:
                fork_job('calibre.ebooks.oeb.iterator', 'get_preprocess_html',
                    (pathtoebook, tf))
            except WorkerError as e:
                return error_dialog(self, _('Failed to generate preview'),
                        err_msg, det_msg=e.orig_tb, show=True)
            except:
                import traceback
                return error_dialog(self, _('Failed to generate preview'),
                        err_msg, det_msg=traceback.format_exc(), show=True)
            with open(tf, 'rb') as f:
                self.preview.setPlainText(f.read().decode('utf-8'))

    def open_clicked(self):
        files = choose_files(self, 'regexp tester dialog', _('Open book'),
                select_only_single_file=True)
        if files:
            self.open_book(files[0])

    def doc(self):
        return str(self.preview.toPlainText())


class RegexEdit(XPathEdit):

    doc_update = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.book_id = None
        self.db = None
        self.doc_cache = None

    def wizard(self):
        return self.builder()

    def builder(self):
        if self.db is None:
            self.doc_cache = _('Click the "Open" button below to open a '
                    'e-book to use for testing.')
        bld = RegexBuilder(self.db, self.book_id, self.edit.text(), self.doc_cache, self)
        if bld.cancelled:
            return
        if not self.doc_cache:
            self.doc_cache = bld.doc()
            self.doc_update.emit(self.doc_cache)
        if bld.exec() == QDialog.DialogCode.Accepted:
            self.edit.setText(bld.regex.text())

    def doc(self):
        return self.doc_cache

    def setObjectName(self, *args):
        super().setObjectName(*args)
        if hasattr(self, 'edit'):
            self.edit.initialize('regex_edit_'+str(self.objectName()))

    def set_msg(self, msg):
        self.msg.setText(msg)

    def set_book_id(self, book_id):
        self.book_id = book_id

    def set_db(self, db):
        self.db = db

    def set_doc(self, doc):
        self.doc_cache = doc

    def set_regex(self, regex):
        self.edit.setText(regex)

    def break_cycles(self):
        self.db = self.doc_cache = None

    @property
    def text(self):
        return str(self.edit.text())

    @property
    def regex(self):
        return self.text

    def clear(self):
        self.edit.clear()

    def check(self):
        return True


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = RegexBuilder(None, None, 'a', doc='😉123abc XYZabc')
    d.do_test()
    d.exec()
    del d
    del app
