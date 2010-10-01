#!/usr/bin/env python
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

from PyQt4.Qt import QDialog, QVBoxLayout, QTreeWidget, QPushButton, \
            QDialogButtonBox, QApplication, QTreeWidgetItem

from calibre.library.check_library import CheckLibrary

class Item(QTreeWidgetItem):
    pass

class CheckLibraryDialog(QDialog):

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        self.db = db

        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)
        self.log = QTreeWidget(self)
        self._layout.addWidget(self.log)
        self.setWindowTitle(_('Check Library'))

        self.check = QPushButton(_('Run the check'))
        self.check.setDefault(False)
        self.check.clicked.connect(self.run_the_check)
        self.copy = QPushButton(_('Copy to clipboard'))
        self.copy.setDefault(False)
        self.copy.clicked.connect(self.copy_to_clipboard)
        self.ok = QPushButton('&OK')
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        self.bbox = QDialogButtonBox(self)
        self.bbox.addButton(self.copy, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.check, QDialogButtonBox.ActionRole)
        self.bbox.addButton(self.ok, QDialogButtonBox.AcceptRole)

        self._layout.addWidget(self.bbox)
        self.resize(750, 500)
        self.bbox.setEnabled(True)

        self.run_the_check()

    def run_the_check(self):
        checker = CheckLibrary(self.db.library_path, self.db)
        checker.scan_library()

        plaintext = []

        def builder(tree, checker, check):
            attr = check[0]
            list = getattr(checker, attr, None)
            if list is None:
                return

            h = check[1]
            tl = Item([h])
            for problem in list:
                it = Item()
                it.setText(0, problem[0])
                it.setText(1, problem[1])
                p = ', '.join(problem[2])
                it.setText(2, p)
                tl.addChild(it)
                plaintext.append(','.join([h, problem[0], problem[1], p]))
            tree.addTopLevelItem(tl)

        t = self.log
        t.clear()
        t.setColumnCount(3);
        t.setHeaderLabels([_('Name'), _('Path from library'), _('Additional Information')])
        for check in checker.checks:
            builder(t, checker, check)

        t.setColumnWidth(0, 200)
        t.setColumnWidth(1, 400)

        self.text_results = '\n'.join(plaintext)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.text_results)


if __name__ == '__main__':
    app = QApplication([])
    d = CheckLibraryDialog()
    d.exec_()
