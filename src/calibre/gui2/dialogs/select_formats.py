#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import QVBoxLayout, QDialog, QLabel, QDialogButtonBox, Qt, \
        QAbstractListModel, QVariant, QListView, QSize

from calibre.gui2 import NONE, file_icon_provider

class Formats(QAbstractListModel):

    def __init__(self, fmt_count):
        QAbstractListModel.__init__(self)
        self.fmts = sorted(set(fmt_count))
        self.counts = fmt_count
        self.fi = file_icon_provider()

    def rowCount(self, parent):
        return len(self.fmts)

    def data(self, index, role):
        row = index.row()
        if role == Qt.DisplayRole:
            fmt = self.fmts[row]
            count = self.counts[fmt]
            return QVariant('%s [%d]'%(fmt.upper(), count))
        if role == Qt.DecorationRole:
            return QVariant(self.fi.icon_from_ext(self.fmts[row].lower()))
        if role == Qt.ToolTipRole:
            fmt = self.fmts[row]
            count = self.counts[fmt]
            return QVariant(
                _('There are %(count)d book(s) with the %(fmt)s format')%dict(
                    count=count, fmt=fmt.upper()))
        return NONE

    def flags(self, index):
        return Qt.ItemIsSelectable|Qt.ItemIsEnabled

    def fmt(self, idx):
        return self.fmts[idx.row()]

class SelectFormats(QDialog):

    def __init__(self, fmt_count, msg, single=False, parent=None, exclude=False):
        QDialog.__init__(self, parent)
        self._l = QVBoxLayout(self)
        self.setLayout(self._l)
        self.setWindowTitle(_('Choose formats'))
        self._m = QLabel(msg)
        self._m.setWordWrap(True)
        self._l.addWidget(self._m)
        self.formats = Formats(fmt_count)
        self.fview = QListView(self)
        if exclude:
            self.fview.setStyleSheet('''
                    QListView { background-color: #FAE7B5}
                    ''')
        self._l.addWidget(self.fview)
        self.fview.setModel(self.formats)
        self.fview.setSelectionMode(self.fview.SingleSelection if single else
                self.fview.MultiSelection)
        self.bbox = \
        QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel,
                Qt.Horizontal, self)
        self._l.addWidget(self.bbox)
        self.bbox.accepted.connect(self.accept)
        self.bbox.rejected.connect(self.reject)
        self.fview.setIconSize(QSize(48, 48))
        self.fview.setSpacing(2)

        self.resize(350, 500)
        self.selected_formats = set([])

    def accept(self, *args):
        for idx in self.fview.selectedIndexes():
            self.selected_formats.add(self.formats.fmt(idx))
        QDialog.accept(self, *args)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    d = SelectFormats(['epub', 'lrf', 'lit', 'mobi'], 'Choose a format')
    d.exec_()
    print d.selected_formats
