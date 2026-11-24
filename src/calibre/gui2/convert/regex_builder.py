#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import os
from contextlib import suppress
from typing import TYPE_CHECKING, cast

from qt.core import QBrush, QDialog, QDialogButtonBox, Qt, QTextCursor, QTextEdit, pyqtSignal

from calibre.constants import iswindows
from calibre.ebooks.conversion.search_replace import compile_regular_expression
from calibre.gui2 import choose_files, error_dialog, gprefs
from calibre.gui2.convert.regex_builder_ui import Ui_RegexBuilder
from calibre.gui2.convert.xpath_wizard import XPathEdit
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2.widgets2 import to_plain_text
from calibre.ptempfile import TemporaryFile
from calibre.utils.icu import utf16_length
from calibre.utils.ipc.simple_worker import WorkerError, fork_job
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QByteArray, QWidget

    from calibre.db.legacy import LibraryDatabase


class RegexBuilder(QDialog, Ui_RegexBuilder):
    def __init__(self, db: LibraryDatabase | None, book_id: int | None, regex: str, doc: str | None = None, parent: QWidget | None = None) -> None:
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.regex.setText(regex)
        self.regex_valid()

        if not db or not book_id:
            button = self.button_box.addButton(QDialogButtonBox.StandardButton.Open)
            assert button is not None
            button.clicked.connect(self.open_clicked)
        elif not doc and not self.select_format(db, book_id):
            self.cancelled = True
            return

        if doc:
            self.preview.setPlainText(doc)

        self.cancelled = False
        self.button_box.accepted.connect(self.accept)
        self.regex.textChanged[str].connect(self.regex_valid)
        for src, slot in (('test', 'do'), ('previous', 'goto'), ('next', 'goto')):
            getattr(self, src).clicked.connect(getattr(self, f'{slot}_{src}'))
        self.test.setDefault(True)

        self.match_locs: list[tuple[int, int]] = []
        self.restore_geometry(gprefs, 'regex_builder_geometry')
        self.finished.connect(self.save_state)

    def save_state(self, result: int) -> None:
        self.save_geometry(gprefs, 'regex_builder_geometry')

    def regex_valid(self) -> bool:
        regex = str(self.regex.text())
        if regex:
            try:
                compile_regular_expression(regex)
                self.regex.setStyleSheet('QLineEdit { background-color: rgba(0,255,0,20%); }')
                return True
            except Exception:
                self.regex.setStyleSheet('QLineEdit { background-color: rgba(255,0,0,20%); }')
        else:
            self.regex.setStyleSheet('')
            self.preview.setExtraSelections([])

        self.match_locs = []
        self.next.setEnabled(False)
        self.previous.setEnabled(False)
        self.occurrences.setText('0')

        return False

    def do_test(self) -> None:
        selections = []
        self.match_locs = []

        class Pos:
            python: int = 0
            qt: int = 0

        if self.regex_valid():
            text = to_plain_text(self.preview)
            regex = str(self.regex.text())
            cursor = QTextCursor(self.preview.document())
            extsel = QTextEdit.ExtraSelection()
            extsel.cursor = cursor
            extsel.format.setBackground(QBrush(Qt.GlobalColor.yellow))
            with suppress(Exception):
                prev = Pos()
                for match in compile_regular_expression(regex).finditer(text):
                    es = QTextEdit.ExtraSelection(extsel)
                    qtchars_to_start = utf16_length(text[prev.python : match.start()])
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

    def goto_previous(self) -> None:
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
                n=self.match_locs[match_loc][1] - self.match_locs[match_loc][0],
            )

    def goto_next(self) -> None:
        pos = self.preview.textCursor().position()
        if self.match_locs:
            match_loc = 0
            for i in range(len(self.match_locs)):
                loc = self.match_locs[i][0]
                if pos < loc:
                    match_loc = i
                    break
            self.goto_loc(self.match_locs[match_loc][0], n=self.match_locs[match_loc][1] - self.match_locs[match_loc][0])

    def goto_loc(
        self,
        loc: int,
        operation: QTextCursor.MoveOperation = QTextCursor.MoveOperation.Right,
        mode: QTextCursor.MoveMode = QTextCursor.MoveMode.KeepAnchor,
        n: int = 0,
    ) -> None:
        cursor = QTextCursor(self.preview.document())
        cursor.setPosition(loc)
        if n:
            cursor.movePosition(operation, mode, n)
        self.preview.setTextCursor(cursor)

    def select_format(self, db: LibraryDatabase, book_id: int) -> bool:
        format = None
        formats = (db.formats(book_id, index_is_id=True) or '').upper().split(',')
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
            error_dialog(
                self,
                _('No formats available'),
                _('Cannot build regex using the GUI builder without a book.'),
                show=True,
            )
            return False
        try:
            fpath = cast('str', db.format(book_id, format, index_is_id=True, as_path=True))
        except OSError:
            if iswindows:
                import traceback

                error_dialog(
                    self,
                    _('Could not open file'),
                    _('Could not open the file, do you have it open in another program?'),
                    show=True,
                    det_msg=traceback.format_exc(),
                )
                return False
            raise
        try:
            self.open_book(fpath)
        finally:
            try:
                os.remove(fpath)
            except Exception:
                # Fails on windows if the input plugin for this format keeps the file open
                # Happens for LIT files
                pass
        return True

    def open_book(self, pathtoebook: str) -> int | None:
        with TemporaryFile('_prepprocess_gui') as tf:
            err_msg = _('Failed to generate markup for testing. Click "Show details" to learn more.')
            try:
                fork_job('calibre.ebooks.oeb.iterator', 'get_preprocess_html', (pathtoebook, tf))
            except WorkerError as e:
                return error_dialog(self, _('Failed to generate preview'), err_msg, det_msg=str(e) + '\n\n' + e.orig_tb, show=True)
            except Exception:
                import traceback

                return error_dialog(self, _('Failed to generate preview'), err_msg, det_msg=traceback.format_exc(), show=True)
            with open(tf, 'rb') as f:
                self.preview.setPlainText(f.read().decode('utf-8'))

    def open_clicked(self) -> None:
        files = choose_files(self, 'regexp tester dialog', _('Open book'), select_only_single_file=True)
        if files:
            self.open_book(files[0])

    def doc(self) -> str:
        return to_plain_text(self.preview)


class RegexEdit(XPathEdit):
    doc_update = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _completer = self.edit.completer()
        assert _completer is not None
        _completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.book_id: int | None = None
        self.db: LibraryDatabase | None = None
        self.doc_cache: str | None = None

    def wizard(self) -> None:
        return self.builder()

    def builder(self) -> None:
        if self.db is None:
            self.doc_cache = _('Click the "Open" button below to open a e-book to use for testing.')
        bld = RegexBuilder(self.db, self.book_id, self.edit.text(), self.doc_cache, self)
        if bld.cancelled:
            return
        if not self.doc_cache:
            self.doc_cache = bld.doc()
            self.doc_update.emit(self.doc_cache)
        if bld.exec() == QDialog.DialogCode.Accepted:
            self.edit.setText(bld.regex.text())

    def doc(self) -> str | None:
        return self.doc_cache

    def setObjectName(self, name: QByteArray | bytes | bytearray | memoryview | str | None = None) -> None:
        args = (name,)
        super().setObjectName(*args)
        if hasattr(self, 'edit'):
            self.edit.initialize('regex_edit_' + str(self.objectName()))

    def set_msg(self, msg: str | None) -> None:
        self.msg.setText(msg)

    def set_book_id(self, book_id: int | None) -> None:
        self.book_id = book_id

    def set_db(self, db: LibraryDatabase | None) -> None:
        self.db = db

    def set_doc(self, doc: str | None) -> None:
        self.doc_cache = doc

    def set_regex(self, regex: str) -> None:
        self.edit.setText(regex)

    def break_cycles(self) -> None:
        self.db = self.doc_cache = None

    @property
    def text(self) -> str:  # ty: ignore[incompatible-property-override]
        return str(self.edit.text())

    @property
    def regex(self) -> str:
        return self.text

    def clear(self) -> None:
        self.edit.clear()

    def check(self) -> bool:
        return True


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    d = RegexBuilder(None, None, 'a', doc='😉123abc XYZabc')
    d.do_test()
    d.exec()
    del d
    del app
