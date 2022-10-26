#!/usr/bin/env python


__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

import os
import weakref
from qt.core import (
    QApplication, QCheckBox, QCursor, QDialog, QDialogButtonBox, QGridLayout,
    QHBoxLayout, QIcon, QLabel, QLineEdit, QProgressBar, QPushButton,
    QStackedLayout, Qt, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget, pyqtSignal, QSplitter
)
from threading import Thread

from calibre import as_unicode, prints
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.library.check_library import CHECKS, CheckLibrary
from calibre.utils.recycle_bin import delete_file, delete_tree


class DBCheck(QDialog):  # {{{

    finished_vacuum = pyqtSignal()

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        self.vacuum_started = False
        self.finished_vacuum.connect(self.accept, type=Qt.ConnectionType.QueuedConnection)
        self.error = None
        self.rejected = False

        s = QStackedLayout(self)
        s.setContentsMargins(0, 0, 0, 0)
        one = QWidget(self)
        s.addWidget(one)
        two = QWidget(self)
        s.addWidget(two)

        l = QVBoxLayout(one)
        la = QLabel(_('Check database integrity and compact it for improved performance.'))
        la.setWordWrap(True)
        l.addWidget(la)

        self.fts = f = QCheckBox(_('Also compact the Full text search database'))
        l.addWidget(f)
        la = QLabel('<p style="margin-left: 20px; font-style: italic">' + _(
            'This can be a very slow and memory intensive operation,'
            ' depending on the size of the Full text database.'))
        la.setWordWrap(True)
        l.addWidget(la)
        l.addStretch(10)
        self.bb1 = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        l.addWidget(bb)
        bb.accepted.connect(self.start)
        bb.rejected.connect(self.reject)
        self.setWindowTitle(_('Check the database file'))

        l = QVBoxLayout(two)
        la = QLabel(_('Vacuuming database to improve performance.') + ' ' +
                         _('This will take a while, please wait...'))
        la.setWordWrap(True)
        l.addWidget(la)
        pb = QProgressBar(self)
        l.addWidget(pb)
        pb.setMinimum(0), pb.setMaximum(0)
        l.addStretch(10)
        self.resize(self.sizeHint())
        self.db = weakref.ref(db.new_api)

    def start(self):
        self.setWindowTitle(_('Vacuuming...'))
        self.layout().setCurrentIndex(1)
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        self.vacuum_started = True
        db = self.db()
        t = self.thread = Thread(target=self.vacuum, args=(db, self.fts.isChecked()), daemon=True, name='VacuumDB')
        t.start()

    def vacuum(self, db, include_fts_db):
        try:
            db.vacuum(include_fts_db)
        except Exception as e:
            import traceback
            self.error = (as_unicode(e), traceback.format_exc())
        self.finished_vacuum.emit()

    def reject(self):
        self.rejected = True
        if self.vacuum_started:
            return
        return QDialog.reject(self)

    def closeEvent(self, ev):
        if self.vacuum_started:
            ev.ignore()
            return
        return super().closeEvent(ev)

    def break_cycles(self):
        if self.vacuum_started:
            QApplication.restoreOverrideCursor()
        self.thread = None

# }}}


class Item(QTreeWidgetItem):
    pass


class CheckLibraryDialog(QDialog):

    is_deletable = 1
    is_fixable = 2

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        self.db = db

        self.setWindowTitle(_('Check library -- Problems found'))
        self.setWindowIcon(QIcon.ic('debug.png'))

        self._tl = QHBoxLayout()
        self.setLayout(self._tl)
        self.splitter = QSplitter(self)
        self.left = QWidget(self)
        self.splitter.addWidget(self.left)
        self.helpw = QTextEdit(self)
        self.splitter.addWidget(self.helpw)
        self._tl.addWidget(self.splitter)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.left.setLayout(self._layout)
        self.helpw.setReadOnly(True)
        self.helpw.setText(_('''\
        <h1>Help</h1>

        <p>calibre stores the list of your books and their metadata in a
        database. The actual book files and covers are stored as normal
        files in the calibre library folder. The database contains a list of the files
        and covers belonging to each book entry. This tool checks that the
        actual files in the library folder on your computer match the
        information in the database.</p>

        <p>The result of each type of check is shown to the left. The various
        checks are:
        </p>
        <ul>
        <li><b>Invalid titles</b>: These are files and folders appearing
        in the library where books titles should, but that do not have the
        correct form to be a book title.</li>
        <li><b>Extra titles</b>: These are extra files in your calibre
        library that appear to be correctly-formed titles, but have no corresponding
        entries in the database.</li>
        <li><b>Invalid authors</b>: These are files appearing
        in the library where only author folders should be.</li>
        <li><b>Extra authors</b>: These are folders in the
        calibre library that appear to be authors but that do not have entries
        in the database.</li>
        <li><b>Missing book formats</b>: These are book formats that are in
        the database but have no corresponding format file in the book's folder.
        <li><b>Extra book formats</b>: These are book format files found in
        the book's folder but not in the database.
        <li><b>Unknown files in books</b>: These are extra files in the
        folder of each book that do not correspond to a known format or cover
        file.</li>
        <li><b>Missing cover files</b>: These represent books that are marked
        in the database as having covers but the actual cover files are
        missing.</li>
        <li><b>Cover files not in database</b>: These are books that have
        cover files but are marked as not having covers in the database.</li>
        <li><b>Folder raising exception</b>: These represent folders in the
        calibre library that could not be processed/understood by this
        tool.</li>
        </ul>

        <p>There are two kinds of automatic fixes possible: <i>Delete
        marked</i> and <i>Fix marked</i>.</p>
        <p><i>Delete marked</i> is used to remove extra files/folders/covers that
        have no entries in the database. Check the box next to the item you want
        to delete. Use with caution.</p>

        <p><i>Fix marked</i> is applicable only to covers and missing formats
        (the three lines marked 'fixable'). In the case of missing cover files,
        checking the fixable box and pushing this button will tell calibre that
        there is no cover for all of the books listed. Use this option if you
        are not going to restore the covers from a backup. In the case of extra
        cover files, checking the fixable box and pushing this button will tell
        calibre that the cover files it found are correct for all the books
        listed. Use this when you are not going to delete the file(s). In the
        case of missing formats, checking the fixable box and pushing this
        button will tell calibre that the formats are really gone. Use this if
        you are not going to restore the formats from a backup.</p>

        '''))

        self.log = QTreeWidget(self)
        self.log.itemChanged.connect(self.item_changed)
        self.log.itemExpanded.connect(self.item_expanded_or_collapsed)
        self.log.itemCollapsed.connect(self.item_expanded_or_collapsed)
        self._layout.addWidget(self.log)

        self.check_button = QPushButton(_('&Run the check again'))
        self.check_button.setDefault(False)
        self.check_button.clicked.connect(self.run_the_check)
        self.copy_button = QPushButton(_('Copy &to clipboard'))
        self.copy_button.setDefault(False)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.ok_button = QPushButton(_('&Done'))
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept)
        self.mark_delete_button = QPushButton(_('Mark &all for delete'))
        self.mark_delete_button.setToolTip(_('Mark all deletable subitems'))
        self.mark_delete_button.setDefault(False)
        self.mark_delete_button.clicked.connect(self.mark_for_delete)
        self.delete_button = QPushButton(_('Delete &marked'))
        self.delete_button.setToolTip(_('Delete marked files (checked subitems)'))
        self.delete_button.setDefault(False)
        self.delete_button.clicked.connect(self.delete_marked)
        self.mark_fix_button = QPushButton(_('Mar&k all for fix'))
        self.mark_fix_button.setToolTip(_('Mark all fixable items'))
        self.mark_fix_button.setDefault(False)
        self.mark_fix_button.clicked.connect(self.mark_for_fix)
        self.fix_button = QPushButton(_('&Fix marked'))
        self.fix_button.setDefault(False)
        self.fix_button.setEnabled(False)
        self.fix_button.setToolTip(_('Fix marked sections (checked fixable items)'))
        self.fix_button.clicked.connect(self.fix_items)
        self.bbox = QGridLayout()
        self.bbox.addWidget(self.check_button, 0, 0)
        self.bbox.addWidget(self.copy_button, 0, 1)
        self.bbox.addWidget(self.ok_button, 0, 2)
        self.bbox.addWidget(self.mark_delete_button, 1, 0)
        self.bbox.addWidget(self.delete_button, 1, 1)
        self.bbox.addWidget(self.mark_fix_button, 2, 0)
        self.bbox.addWidget(self.fix_button, 2, 1)

        h = QHBoxLayout()
        ln = QLabel(_('Names to ignore:'))
        h.addWidget(ln)
        self.name_ignores = QLineEdit()
        self.name_ignores.setText(db.new_api.pref('check_library_ignore_names', ''))
        self.name_ignores.setToolTip(
            _('Enter comma-separated standard file name wildcards, such as synctoy*.dat'))
        ln.setBuddy(self.name_ignores)
        h.addWidget(self.name_ignores)
        le = QLabel(_('Extensions to ignore:'))
        h.addWidget(le)
        self.ext_ignores = QLineEdit()
        self.ext_ignores.setText(db.new_api.pref('check_library_ignore_extensions', ''))
        self.ext_ignores.setToolTip(
            _('Enter comma-separated extensions without a leading dot. Used only in book folders'))
        le.setBuddy(self.ext_ignores)
        h.addWidget(self.ext_ignores)
        self._layout.addLayout(h)

        self._layout.addLayout(self.bbox)
        self.resize(950, 500)

    def do_exec(self):
        self.run_the_check()

        probs = 0
        for c in self.problem_count:
            probs += self.problem_count[c]
        if probs == 0:
            return False
        self.exec()
        return True

    def accept(self):
        self.db.new_api.set_pref('check_library_ignore_extensions', str(self.ext_ignores.text()))
        self.db.new_api.set_pref('check_library_ignore_names', str(self.name_ignores.text()))
        QDialog.accept(self)

    def box_to_list(self, txt):
        return [f.strip() for f in txt.split(',') if f.strip()]

    def run_the_check(self):
        checker = CheckLibrary(self.db.library_path, self.db)
        checker.scan_library(self.box_to_list(str(self.name_ignores.text())),
                             self.box_to_list(str(self.ext_ignores.text())))

        plaintext = []

        def builder(tree, checker, check):
            attr, h, checkable, fixable = check
            list_ = getattr(checker, attr, None)
            if list_ is None:
                self.problem_count[attr] = 0
                return
            else:
                self.problem_count[attr] = len(list_)

            tl = Item()
            tl.setText(0, h)
            if fixable and list:
                tl.setData(1, Qt.ItemDataRole.UserRole, self.is_fixable)
                tl.setText(1, _('(fixable)'))
                tl.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                tl.setCheckState(1, Qt.CheckState.Unchecked)
            else:
                tl.setData(1, Qt.ItemDataRole.UserRole, self.is_deletable)
                tl.setData(2, Qt.ItemDataRole.UserRole, self.is_deletable)
                tl.setText(1, _('(deletable)'))
                tl.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                tl.setCheckState(1, Qt.CheckState.Unchecked)
            if attr == 'extra_covers':
                tl.setData(2, Qt.ItemDataRole.UserRole, self.is_deletable)
                tl.setText(2, _('(deletable)'))
                tl.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                tl.setCheckState(2, Qt.CheckState.Unchecked)
            self.top_level_items[attr] = tl

            for problem in list_:
                it = Item()
                if checkable:
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    it.setCheckState(2, Qt.CheckState.Unchecked)
                    it.setData(2, Qt.ItemDataRole.UserRole, self.is_deletable)
                else:
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it.setText(0, problem[0])
                it.setData(0, Qt.ItemDataRole.UserRole, problem[2])
                it.setText(2, problem[1])
                tl.addChild(it)
                self.all_items.append(it)
                plaintext.append(','.join([h, problem[0], problem[1]]))
            tree.addTopLevelItem(tl)

        t = self.log
        t.clear()
        t.setColumnCount(3)
        t.setHeaderLabels([_('Name'), '', _('Path from library')])
        self.all_items = []
        self.top_level_items = {}
        self.problem_count = {}
        for check in CHECKS:
            builder(t, checker, check)

        t.resizeColumnToContents(0)
        t.resizeColumnToContents(1)
        self.delete_button.setEnabled(False)
        self.fix_button.setEnabled(False)
        self.text_results = '\n'.join(plaintext)

    def item_expanded_or_collapsed(self, item):
        self.log.resizeColumnToContents(0)
        self.log.resizeColumnToContents(1)

    def item_changed(self, item, column):
        def set_delete_boxes(node, col, to_what):
            if isinstance(to_what, bool):
                to_what = Qt.CheckState.Checked if to_what else Qt.CheckState.Unchecked
            self.log.blockSignals(True)
            if col:
                node.setCheckState(col, to_what)
            for i in range(0, node.childCount()):
                node.child(i).setCheckState(2, to_what)
            self.log.blockSignals(False)

        def is_child_delete_checked(node):
            checked = False
            all_checked = True
            for i in range(0, node.childCount()):
                c = node.child(i).checkState(2)
                checked = checked or c == Qt.CheckState.Checked
                all_checked = all_checked and c == Qt.CheckState.Checked
            return (checked, all_checked)

        def any_child_delete_checked():
            for parent in self.top_level_items.values():
                (c, _) = is_child_delete_checked(parent)
                if c:
                    return True
            return False

        def any_fix_checked():
            for parent in self.top_level_items.values():
                if (parent.data(1, Qt.ItemDataRole.UserRole) == self.is_fixable and
                        parent.checkState(1) == Qt.CheckState.Checked):
                    return True
            return False

        if item in self.top_level_items.values():
            if item.childCount() > 0:
                if item.data(1, Qt.ItemDataRole.UserRole) == self.is_fixable and column == 1:
                    if item.data(2, Qt.ItemDataRole.UserRole) == self.is_deletable:
                        set_delete_boxes(item, 2, False)
                else:
                    set_delete_boxes(item, column, item.checkState(column))
                    if column == 2:
                        self.log.blockSignals(True)
                        item.setCheckState(1, Qt.CheckState.Unchecked)
                        self.log.blockSignals(False)
            else:
                item.setCheckState(column, Qt.CheckState.Unchecked)
        else:
            for parent in self.top_level_items.values():
                if parent.data(2, Qt.ItemDataRole.UserRole) == self.is_deletable:
                    (child_chkd, all_chkd) = is_child_delete_checked(parent)
                    if all_chkd and child_chkd:
                        check_state = Qt.CheckState.Checked
                    elif child_chkd:
                        check_state = Qt.CheckState.PartiallyChecked
                    else:
                        check_state = Qt.CheckState.Unchecked
                    self.log.blockSignals(True)
                    if parent.data(1, Qt.ItemDataRole.UserRole) == self.is_fixable:
                        parent.setCheckState(2, check_state)
                    else:
                        parent.setCheckState(1, check_state)
                    if child_chkd and parent.data(1, Qt.ItemDataRole.UserRole) == self.is_fixable:
                        parent.setCheckState(1, Qt.CheckState.Unchecked)
                    self.log.blockSignals(False)
        self.delete_button.setEnabled(any_child_delete_checked())
        self.fix_button.setEnabled(any_fix_checked())

    def mark_for_fix(self):
        for it in self.top_level_items.values():
            if (it.flags() & Qt.ItemFlag.ItemIsUserCheckable and
                    it.data(1, Qt.ItemDataRole.UserRole) == self.is_fixable and
                    it.childCount() > 0):
                it.setCheckState(1, Qt.CheckState.Checked)

    def mark_for_delete(self):
        for it in self.all_items:
            if (it.flags() & Qt.ItemFlag.ItemIsUserCheckable and
                    it.data(2, Qt.ItemDataRole.UserRole) == self.is_deletable):
                it.setCheckState(2, Qt.CheckState.Checked)

    def delete_marked(self):
        if not confirm('<p>'+_('The marked files and folders will be '
               '<b>permanently deleted</b>. Are you sure?') + '</p>', 'check_library_editor_delete', self):
            return

        # Sort the paths in reverse length order so that we can be sure that
        # if an item is in another item, the sub-item will be deleted first.
        items = sorted(self.all_items,
                       key=lambda x: len(x.text(1)),
                       reverse=True)
        for it in items:
            if it.checkState(2) == Qt.CheckState.Checked:
                try:
                    p = os.path.join(self.db.library_path, str(it.text(2)))
                    if os.path.isdir(p):
                        delete_tree(p)
                    else:
                        delete_file(p)
                except:
                    prints('failed to delete',
                            os.path.join(self.db.library_path,
                                str(it.text(2))))
        self.run_the_check()

    def fix_missing_formats(self):
        tl = self.top_level_items['missing_formats']
        child_count = tl.childCount()
        for i in range(0, child_count):
            item = tl.child(i)
            id = int(item.data(0, Qt.ItemDataRole.UserRole))
            all = self.db.formats(id, index_is_id=True, verify_formats=False)
            all = {f.strip() for f in all.split(',')} if all else set()
            valid = self.db.formats(id, index_is_id=True, verify_formats=True)
            valid = {f.strip() for f in valid.split(',')} if valid else set()
            for fmt in all-valid:
                self.db.remove_format(id, fmt, index_is_id=True, db_only=True)

    def fix_missing_covers(self):
        tl = self.top_level_items['missing_covers']
        child_count = tl.childCount()
        for i in range(0, child_count):
            item = tl.child(i)
            id = int(item.data(0, Qt.ItemDataRole.UserRole))
            self.db.set_has_cover(id, False)

    def fix_extra_covers(self):
        tl = self.top_level_items['extra_covers']
        child_count = tl.childCount()
        for i in range(0, child_count):
            item = tl.child(i)
            id = int(item.data(0, Qt.ItemDataRole.UserRole))
            self.db.set_has_cover(id, True)

    def fix_items(self):
        for check in CHECKS:
            attr = check[0]
            fixable = check[3]
            tl = self.top_level_items[attr]
            if fixable and tl.checkState(1) == Qt.CheckState.Checked:
                func = getattr(self, 'fix_' + attr, None)
                if func is not None and callable(func):
                    func()
        self.run_the_check()

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.text_results)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    from calibre.library import db as dbconn
    d = DBCheck(None, dbconn())
    d.exec()
