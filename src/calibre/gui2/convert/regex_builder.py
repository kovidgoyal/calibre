# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from PyQt5.Qt import (QDialog, QWidget, QDialogButtonBox,
        QBrush, QTextCursor, QTextEdit, QByteArray, Qt, pyqtSignal)

from calibre.gui2.convert.regex_builder_ui import Ui_RegexBuilder
from calibre.gui2.convert.xexp_edit_ui import Ui_Form as Ui_Edit
from calibre.gui2 import error_dialog, choose_files, gprefs
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.constants import iswindows
from calibre.utils.ipc.simple_worker import fork_job, WorkerError
from calibre.ebooks.conversion.search_replace import compile_regular_expression
from calibre.ptempfile import TemporaryFile


class RegexBuilder(QDialog, Ui_RegexBuilder):

    def __init__(self, db, book_id, regex, doc=None, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.regex.setText(regex)
        self.regex_valid()

        if not db or not book_id:
            button = self.button_box.addButton(QDialogButtonBox.Open)
            button.clicked.connect(self.open_clicked)
        elif not doc and not self.select_format(db, book_id):
            self.cancelled = True
            return

        if doc:
            self.preview.setPlainText(doc)

        self.cancelled = False
        self.button_box.accepted.connect(self.accept)
        self.regex.textChanged[str].connect(self.regex_valid)
        for src, slot in (('test', 'do'), ('previous', 'goto'), ('next',
            'goto')):
            getattr(self, src).clicked.connect(getattr(self, '%s_%s'%(slot,
                src)))
        self.test.setDefault(True)

        self.match_locs = []
        geom = gprefs.get('regex_builder_geometry', None)
        if geom is not None:
            self.restoreGeometry(QByteArray(geom))
        self.finished.connect(self.save_state)

    def save_state(self, result):
        geom = bytearray(self.saveGeometry())
        gprefs['regex_builder_geometry'] = geom

    def regex_valid(self):
        regex = unicode(self.regex.text())
        if regex:
            try:
                compile_regular_expression(regex)
                self.regex.setStyleSheet('QLineEdit { color: black; background-color: rgba(0,255,0,20%); }')
                return True
            except:
                self.regex.setStyleSheet('QLineEdit { color: black; background-color: rgb(255,0,0,20%); }')
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
        if self.regex_valid():
            text = unicode(self.preview.toPlainText())
            regex = unicode(self.regex.text())
            cursor = QTextCursor(self.preview.document())
            extsel = QTextEdit.ExtraSelection()
            extsel.cursor = cursor
            extsel.format.setBackground(QBrush(Qt.yellow))
            try:
                for match in compile_regular_expression(regex).finditer(text):
                    es = QTextEdit.ExtraSelection(extsel)
                    es.cursor.setPosition(match.start(), QTextCursor.MoveAnchor)
                    es.cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                    selections.append(es)
                    self.match_locs.append((match.start(), match.end()))
            except:
                pass
        self.preview.setExtraSelections(selections)
        if self.match_locs:
            self.next.setEnabled(True)
            self.previous.setEnabled(True)
        self.occurrences.setText(str(len(self.match_locs)))

    def goto_previous(self):
        pos = self.preview.textCursor().position()
        if self.match_locs:
            match_loc = len(self.match_locs) - 1
            for i in xrange(len(self.match_locs) - 1, -1, -1):
                loc = self.match_locs[i][1]
                if pos > loc:
                    match_loc = i
                    break
            self.goto_loc(self.match_locs[match_loc][1], operation=QTextCursor.Left, n=self.match_locs[match_loc][1] - self.match_locs[match_loc][0])

    def goto_next(self):
        pos = self.preview.textCursor().position()
        if self.match_locs:
            match_loc = 0
            for i in xrange(len(self.match_locs)):
                loc = self.match_locs[i][0]
                if pos < loc:
                    match_loc = i
                    break
            self.goto_loc(self.match_locs[match_loc][0], n=self.match_locs[match_loc][1] - self.match_locs[match_loc][0])

    def goto_loc(self, loc, operation=QTextCursor.Right, mode=QTextCursor.KeepAnchor, n=0):
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
            d.exec_()
            if d.result() == QDialog.Accepted:
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
                            '"Show Details" to learn more.')
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
        return unicode(self.preview.toPlainText())


class RegexEdit(QWidget, Ui_Edit):

    doc_update = pyqtSignal(unicode)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self.book_id = None
        self.db = None
        self.doc_cache = None

        self.button.clicked.connect(self.builder)

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
        if bld.exec_() == bld.Accepted:
            self.edit.setText(bld.regex.text())

    def doc(self):
        return self.doc_cache

    def setObjectName(self, *args):
        QWidget.setObjectName(self, *args)
        if hasattr(self, 'edit'):
            self.edit.initialize('regex_edit_'+unicode(self.objectName()))

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
        return unicode(self.edit.text())

    @property
    def regex(self):
        return self.text

    def clear(self):
        self.edit.clear()

    def check(self):
        return True
