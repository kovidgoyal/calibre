#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict

from qt.core import (
    QDialog, QGridLayout, QDialogButtonBox, QListWidget, QApplication, Qt,
    pyqtSignal, QSize, QPushButton, QIcon, QStyledItemDelegate, QLabel, QAbstractItemView)

from calibre.utils.config_base import tweaks
from calibre.gui2 import gprefs
from calibre.gui2.complete2 import EditWithComplete
from calibre.ebooks.metadata import string_to_authors


class ItemDelegate(QStyledItemDelegate):

    edited = pyqtSignal(object)

    def __init__(self, all_authors, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.all_authors = all_authors

    def sizeHint(self, *args):
        return QStyledItemDelegate.sizeHint(self, *args) + QSize(0, 15)

    def setEditorData(self, editor, index):
        name = str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        editor.setText(name)
        editor.lineEdit().selectAll()

    def setModelData(self, editor, model, index):
        authors = string_to_authors(str(editor.text()))
        model.setData(index, authors[0])
        self.edited.emit(index.row())

    def createEditor(self, parent, option, index):
        self.ed = EditWithComplete(parent)
        self.ed.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        init_line_edit(self.ed, self.all_authors)
        return self.ed


class List(QListWidget):

    def __init__(self, all_authors, parent):
        QListWidget.__init__(self, parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAlternatingRowColors(True)
        self.d = ItemDelegate(all_authors, self)
        self.d.edited.connect(self.edited, type=Qt.ConnectionType.QueuedConnection)
        self.setItemDelegate(self.d)

    def delete_selected(self):
        for item in self.selectedItems():
            self.takeItem(self.row(item))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Delete:
            self.delete_selected()
            ev.accept()
            return
        return QListWidget.keyPressEvent(self, ev)

    def addItem(self, *args):
        try:
            return QListWidget.addItem(self, *args)
        finally:
            self.mark_as_editable()

    def addItems(self, *args):
        try:
            return QListWidget.addItems(self, *args)
        finally:
            self.mark_as_editable()

    def mark_as_editable(self):
        for i in range(self.count()):
            item = self.item(i)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

    def edited(self, i):
        item = self.item(i)
        q = str(item.text())
        remove = []
        for j in range(self.count()):
            if i != j and str(self.item(j).text()) == q:
                remove.append(j)
        for x in sorted(remove, reverse=True):
            self.takeItem(x)


class Edit(EditWithComplete):

    returnPressed = pyqtSignal()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            ev.accept()
            self.returnPressed.emit()
            return
        return EditWithComplete.keyPressEvent(self, ev)


def init_line_edit(a, all_authors):
    a.set_separator('&')
    a.set_space_before_sep(True)
    a.set_add_separator(tweaks['authors_completer_append_separator'])
    a.update_items_cache(all_authors)


class AuthorsEdit(QDialog):

    def __init__(self, all_authors, current_authors, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QGridLayout()
        self.setLayout(l)
        self.setWindowTitle(_('Edit authors'))

        self.la = QLabel(_(
            'Edit the authors for this book. You can drag and drop to re-arrange authors'))
        self.la.setWordWrap(True)
        l.addWidget(self.la, 0, 0, 1, 3)

        self.al = al = List(all_authors, self)
        al.addItems(current_authors)
        l.addWidget(al, 1, 0, 1, 3)

        self.author = a = Edit(self)
        init_line_edit(a, all_authors)
        a.lineEdit().setPlaceholderText(_('Enter an author to add'))
        a.returnPressed.connect(self.add_author)
        l.addWidget(a, 2, 0)

        self.ab = b = QPushButton(_('&Add'))
        b.setIcon(QIcon.ic('plus.png'))
        l.addWidget(b, 2, 1)
        b.clicked.connect(self.add_author)

        self.db = b = QPushButton(_('&Remove selected'))
        l.addWidget(b, 2, 2)
        b.setIcon(QIcon.ic('minus.png'))
        b.clicked.connect(self.al.delete_selected)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 3, 0, 1, 3)

        l.setColumnStretch(0, 10)
        self.resize(self.sizeHint() + QSize(150, 100))
        geom = gprefs.get('authors-edit-geometry', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)
        self.author.setFocus(Qt.FocusReason.OtherFocusReason)

    def save_geometry(self):
        gprefs.set('authors-edit-geometry', bytearray(self.saveGeometry()))

    def accept(self):
        self.save_geometry()
        return QDialog.accept(self)

    def reject(self):
        self.save_geometry()
        return QDialog.reject(self)

    @property
    def authors(self):
        ans = []
        for i in range(self.al.count()):
            ans.append(str(self.al.item(i).text()))
        return ans or [_('Unknown')]

    def add_author(self):
        text = self.author.text().strip()
        authors = OrderedDict((icu_lower(x), (i, x)) for i, x in enumerate(self.authors))
        if text:
            for author in string_to_authors(text):
                la = icu_lower(author)
                if la in authors and authors[la][1] != author:
                    # Case change
                    i = authors[la][0]
                    authors[la] = (i, author)
                    self.al.item(i).setText(author)
                else:
                    self.al.addItem(author)
                    authors[la] = author
        self.author.setText('')


if __name__ == '__main__':
    app = QApplication([])
    d = AuthorsEdit(['kovid goyal', 'divok layog', 'other author'], ['kovid goyal', 'other author'])
    d.exec()
    print(d.authors)
