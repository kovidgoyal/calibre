#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

import os

from PyQt4.Qt import QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QLabel, \
            QPushButton, QDialogButtonBox, QApplication, QTreeWidgetItem, \
            QLineEdit, Qt

from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.library.check_library import CheckLibrary, CHECKS
from calibre.library.database2 import delete_file, delete_tree

class Item(QTreeWidgetItem):
    pass

class CheckLibraryDialog(QDialog):

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        self.db = db

        self.setWindowTitle(_('Check Library'))

        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)

        self.log = QTreeWidget(self)
        self.log.itemChanged.connect(self.item_changed)
        self._layout.addWidget(self.log)

        self.check = QPushButton(_('&Run the check'))
        self.check.setDefault(False)
        self.check.clicked.connect(self.run_the_check)
        self.copy = QPushButton(_('Copy &to clipboard'))
        self.copy.setDefault(False)
        self.copy.clicked.connect(self.copy_to_clipboard)
        self.ok = QPushButton('&Done')
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        self.delete = QPushButton('Delete &marked')
        self.delete.setDefault(False)
        self.delete.clicked.connect(self.delete_marked)
        self.cancel = QPushButton('&Cancel')
        self.cancel.setDefault(False)
        self.cancel.clicked.connect(self.reject)
        self.bbox = QDialogButtonBox(self)
        self.bbox.addButton(self.copy, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.check, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.delete, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.cancel, QDialogButtonBox.RejectRole)
        self.bbox.addButton(self.ok, QDialogButtonBox.AcceptRole)

        h = QHBoxLayout()
        ln = QLabel(_('Names to ignore:'))
        h.addWidget(ln)
        self.name_ignores = QLineEdit()
        self.name_ignores.setText(db.prefs.get('check_library_ignore_names', ''))
        ln.setBuddy(self.name_ignores)
        h.addWidget(self.name_ignores)
        le = QLabel(_('Extensions to ignore'))
        h.addWidget(le)
        self.ext_ignores = QLineEdit()
        self.ext_ignores.setText(db.prefs.get('check_library_ignore_extensions', ''))
        le.setBuddy(self.ext_ignores)
        h.addWidget(self.ext_ignores)
        self._layout.addLayout(h)

        self._layout.addWidget(self.bbox)
        self.resize(750, 500)
        self.bbox.setEnabled(True)

        self.run_the_check()

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
            attr, h, checkable = check
            list = getattr(checker, attr, None)
            if list is None:
                return

            tl = Item([h])
            for problem in list:
                it = Item()
                if checkable:
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    it.setCheckState(1, False)
                else:
                    it.setFlags(Qt.ItemIsEnabled)
                it.setText(0, problem[0])
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
        for check in CHECKS:
            builder(t, checker, check)

        t.setColumnWidth(0, 200)
        t.setColumnWidth(1, 400)
        self.delete.setEnabled(False)
        self.text_results = '\n'.join(plaintext)

    def item_changed(self, item, column):
        print 'item_changed'
        for it in self.all_items:
            if it.checkState(1):
                self.delete.setEnabled(True)
                return

    def delete_marked(self):
        print 'delete marked'
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
                    print 'failed to delete', os.path.join(self.db.library_path ,unicode(it.text(1)))
        self.run_the_check()

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.text_results)


if __name__ == '__main__':
    app = QApplication([])
    d = CheckLibraryDialog()
    d.exec_()
