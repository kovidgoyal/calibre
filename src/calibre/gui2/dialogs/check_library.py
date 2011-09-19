#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

import os, shutil

from PyQt4.Qt import QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QLabel, \
            QPushButton, QDialogButtonBox, QApplication, QTreeWidgetItem, \
            QLineEdit, Qt, QProgressBar, QSize, QTimer, QIcon, QTextEdit

from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.library.check_library import CheckLibrary, CHECKS
from calibre.library.database2 import delete_file, delete_tree
from calibre import prints, as_unicode
from calibre.ptempfile import PersistentTemporaryFile
from calibre.library.sqlite import DBThread, OperationalError

class DBCheck(QDialog): # {{{

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        self.l = QVBoxLayout()
        self.setLayout(self.l)
        self.l1 = QLabel(_('Checking database integrity')+'...')
        self.setWindowTitle(_('Checking database integrity'))
        self.l.addWidget(self.l1)
        self.pb = QProgressBar(self)
        self.l.addWidget(self.pb)
        self.pb.setMaximum(0)
        self.pb.setMinimum(0)
        self.msg = QLabel('')
        self.l.addWidget(self.msg)
        self.msg.setWordWrap(True)
        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.l.addWidget(self.bb)
        self.bb.rejected.connect(self.reject)
        self.resize(self.sizeHint() + QSize(100, 50))
        self.error = None
        self.db = db
        self.closed_orig_conn = False

    def start(self):
        self.user_version = self.db.user_version
        self.rejected = False
        self.db.clean()
        self.db.conn.close()
        self.closed_orig_conn = True
        t = DBThread(self.db.dbpath, False)
        t.connect()
        self.conn = t.conn
        self.dump = self.conn.iterdump()
        self.statements = []
        self.count = 0
        self.msg.setText(_('Dumping database to SQL'))
        # Give the backup thread time to stop
        QTimer.singleShot(2000, self.do_one_dump)
        self.exec_()

    def do_one_dump(self):
        if self.rejected:
            return
        try:
            try:
                self.statements.append(self.dump.next())
                self.count += 1
            except StopIteration:
                self.start_load()
                return
            QTimer.singleShot(0, self.do_one_dump)
        except Exception as e:
            import traceback
            self.error = (as_unicode(e), traceback.format_exc())
            self.reject()

    def start_load(self):
        try:
            self.conn.close()
            self.pb.setMaximum(self.count)
            self.pb.setValue(0)
            self.msg.setText(_('Loading database from SQL'))
            self.db.conn.close()
            self.ndbpath = PersistentTemporaryFile('.db')
            self.ndbpath.close()
            self.ndbpath = self.ndbpath.name
            t = DBThread(self.ndbpath, False)
            t.connect()
            self.conn = t.conn
            self.conn.execute('create temporary table temp_sequence(id INTEGER PRIMARY KEY AUTOINCREMENT)')
            self.conn.commit()

            QTimer.singleShot(0, self.do_one_load)
        except Exception as e:
            import traceback
            self.error = (as_unicode(e), traceback.format_exc())
            self.reject()


    def do_one_load(self):
        if self.rejected:
            return
        if self.count > 0:
            try:
                try:
                    self.conn.execute(self.statements.pop(0))
                except OperationalError:
                    if self.count > 1:
                        # The last statement in the dump could be an extra
                        # commit, so ignore it.
                        raise
                self.pb.setValue(self.pb.value() + 1)
                self.count -= 1
                QTimer.singleShot(0, self.do_one_load)
            except Exception as e:
                import traceback
                self.error = (as_unicode(e), traceback.format_exc())
                self.reject()

        else:
            self.replace_db()

    def replace_db(self):
        self.conn.commit()
        self.conn.execute('pragma user_version=%d'%int(self.user_version))
        self.conn.commit()
        self.conn.close()
        shutil.copyfile(self.ndbpath, self.db.dbpath)
        self.db = None
        self.accept()

    def break_cycles(self):
        self.statements = self.unpickler = self.db = self.conn = None

    def reject(self):
        self.rejected = True
        QDialog.reject(self)
# }}}

class Item(QTreeWidgetItem):
    pass

class CheckLibraryDialog(QDialog):

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        self.db = db

        self.setWindowTitle(_('Check Library -- Problems Found'))
        self.setWindowIcon(QIcon(I('debug.png')))

        self._tl = QHBoxLayout()
        self._layout = QVBoxLayout()
        self.setLayout(self._tl)
        self._tl.addLayout(self._layout)
        self.helpw = QTextEdit(self)
        self._tl.addWidget(self.helpw)
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
        entries in the database</li>
        <li><b>Invalid authors</b>: These are files appearing
        in the library where only author folders should be.</li>
        <li><b>Extra authors</b>: These are folders in the
        calibre library that appear to be authors but that do not have entries
        in the database</li>
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
        self.delete_button = QPushButton(_('Delete &marked'))
        self.delete_button.setToolTip(_('Delete marked files (checked subitems)'))
        self.delete_button.setDefault(False)
        self.delete_button.clicked.connect(self.delete_marked)
        self.fix_button = QPushButton(_('&Fix marked'))
        self.fix_button.setDefault(False)
        self.fix_button.setEnabled(False)
        self.fix_button.setToolTip(_('Fix marked sections (checked fixable items)'))
        self.fix_button.clicked.connect(self.fix_items)
        self.bbox = QDialogButtonBox(self)
        self.bbox.addButton(self.check_button, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.delete_button, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.fix_button, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.copy_button, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.ok_button, QDialogButtonBox.AcceptRole)

        h = QHBoxLayout()
        ln = QLabel(_('Names to ignore:'))
        h.addWidget(ln)
        self.name_ignores = QLineEdit()
        self.name_ignores.setText(db.prefs.get('check_library_ignore_names', ''))
        self.name_ignores.setToolTip(
            _('Enter comma-separated standard file name wildcards, such as synctoy*.dat'))
        ln.setBuddy(self.name_ignores)
        h.addWidget(self.name_ignores)
        le = QLabel(_('Extensions to ignore'))
        h.addWidget(le)
        self.ext_ignores = QLineEdit()
        self.ext_ignores.setText(db.prefs.get('check_library_ignore_extensions', ''))
        self.ext_ignores.setToolTip(
            _('Enter comma-separated extensions without a leading dot. Used only in book folders'))
        le.setBuddy(self.ext_ignores)
        h.addWidget(self.ext_ignores)
        self._layout.addLayout(h)

        self._layout.addWidget(self.bbox)
        self.resize(950, 500)
        self.bbox.setEnabled(True)

    def do_exec(self):
        self.run_the_check()

        probs = 0
        for c in self.problem_count:
            probs += self.problem_count[c]
        if probs == 0:
            return False
        self.exec_()
        return True

    def accept(self):
        self.db.prefs['check_library_ignore_extensions'] = \
                                            unicode(self.ext_ignores.text())
        self.db.prefs['check_library_ignore_names'] = \
                                            unicode(self.name_ignores.text())
        QDialog.accept(self)

    def box_to_list(self, txt):
        return [f.strip() for f in txt.split(',') if f.strip()]

    def run_the_check(self):
        checker = CheckLibrary(self.db.library_path, self.db)
        checker.scan_library(self.box_to_list(unicode(self.name_ignores.text())),
                             self.box_to_list(unicode(self.ext_ignores.text())))

        plaintext = []

        def builder(tree, checker, check):
            attr, h, checkable, fixable = check
            list = getattr(checker, attr, None)
            if list is None:
                self.problem_count[attr] = 0
                return
            else:
                self.problem_count[attr] = len(list)

            tl = Item()
            tl.setText(0, h)
            if fixable:
                tl.setText(1, _('(fixable)'))
                tl.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                tl.setCheckState(1, False)
            self.top_level_items[attr] = tl

            for problem in list:
                it = Item()
                if checkable:
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    it.setCheckState(1, False)
                else:
                    it.setFlags(Qt.ItemIsEnabled)
                it.setText(0, problem[0])
                it.setData(0, Qt.UserRole, problem[2])
                it.setText(1, problem[1])
                tl.addChild(it)
                self.all_items.append(it)
                plaintext.append(','.join([h, problem[0], problem[1]]))
            tree.addTopLevelItem(tl)

        t = self.log
        t.clear()
        t.setColumnCount(2);
        t.setHeaderLabels([_('Name'), _('Path from library')])
        self.all_items = []
        self.top_level_items = {}
        self.problem_count = {}
        for check in CHECKS:
            builder(t, checker, check)

        t.resizeColumnToContents(0)
        t.resizeColumnToContents(1)
        self.delete_button.setEnabled(False)
        self.text_results = '\n'.join(plaintext)

    def item_expanded_or_collapsed(self, item):
        self.log.resizeColumnToContents(0)
        self.log.resizeColumnToContents(1)

    def item_changed(self, item, column):
        self.fix_button.setEnabled(False)
        for it in self.top_level_items.values():
            if it.checkState(1):
                self.fix_button.setEnabled(True)

        self.delete_button.setEnabled(False)
        for it in self.all_items:
            if it.checkState(1):
                self.delete_button.setEnabled(True)
                return

    def delete_marked(self):
        if not confirm('<p>'+_('The marked files and folders will be '
               '<b>permanently deleted</b>. Are you sure?')
               +'</p>', 'check_library_editor_delete', self):
            return

        # Sort the paths in reverse length order so that we can be sure that
        # if an item is in another item, the sub-item will be deleted first.
        items = sorted(self.all_items,
                       key=lambda x: len(x.text(1)),
                       reverse=True)
        for it in items:
            if it.checkState(1):
                try:
                    p = os.path.join(self.db.library_path ,unicode(it.text(1)))
                    if os.path.isdir(p):
                        delete_tree(p)
                    else:
                        delete_file(p)
                except:
                    prints('failed to delete',
                            os.path.join(self.db.library_path,
                                unicode(it.text(1))))
        self.run_the_check()

    def fix_missing_formats(self):
        tl = self.top_level_items['missing_formats']
        child_count = tl.childCount()
        for i in range(0, child_count):
            item = tl.child(i);
            id = item.data(0, Qt.UserRole).toInt()[0]
            all = self.db.formats(id, index_is_id=True, verify_formats=False)
            all = set([f.strip() for f in all.split(',')]) if all else set()
            valid = self.db.formats(id, index_is_id=True, verify_formats=True)
            valid = set([f.strip() for f in valid.split(',')]) if valid else set()
            for fmt in all-valid:
                self.db.remove_format(id, fmt, index_is_id=True, db_only=True)

    def fix_missing_covers(self):
        tl = self.top_level_items['missing_covers']
        child_count = tl.childCount()
        for i in range(0, child_count):
            item = tl.child(i);
            id = item.data(0, Qt.UserRole).toInt()[0]
            self.db.set_has_cover(id, False)

    def fix_extra_covers(self):
        tl = self.top_level_items['extra_covers']
        child_count = tl.childCount()
        for i in range(0, child_count):
            item = tl.child(i);
            id = item.data(0, Qt.UserRole).toInt()[0]
            self.db.set_has_cover(id, True)

    def fix_items(self):
        for check in CHECKS:
            attr = check[0]
            fixable = check[3]
            tl = self.top_level_items[attr]
            if fixable and tl.checkState(1):
                func = getattr(self, 'fix_' + attr, None)
                if func is not None and callable(func):
                    func()
        self.run_the_check()

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.text_results)


if __name__ == '__main__':
    app = QApplication([])
    from calibre.library import db
    d = CheckLibraryDialog(None, db())
    d.exec_()
