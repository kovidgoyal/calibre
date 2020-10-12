#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QVBoxLayout, QDialog, QLabel, QDialogButtonBox, Qt, \
        QAbstractListModel, QListView, QSize, QApplication

from calibre.gui2 import file_icon_provider


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
            return ('%s [%d]'%(fmt.upper(), count))
        if role == Qt.DecorationRole:
            return (self.fi.icon_from_ext(self.fmts[row].lower()))
        if role == Qt.ToolTipRole:
            fmt = self.fmts[row]
            count = self.counts[fmt]
            return _('There is one book with the {} format').format(fmt.upper()) if count == 1 else _(
                'There are {count} books with the {fmt} format').format(
                                count=count, fmt=fmt.upper())
        return None

    def flags(self, index):
        return Qt.ItemIsSelectable|Qt.ItemIsEnabled

    def fmt(self, idx):
        return self.fmts[idx.row()]


class SelectFormats(QDialog):

    def __init__(self, fmt_count, msg, single=False, parent=None, exclude=False):
        QDialog.__init__(self, parent)
        self._l = QVBoxLayout(self)
        self.single_fmt = single
        self.setLayout(self._l)
        self.setWindowTitle(_('Choose formats'))
        self._m = QLabel(msg)
        self._m.setWordWrap(True)
        self._l.addWidget(self._m)
        self.formats = Formats(fmt_count)
        self.fview = QListView(self)
        self.fview.doubleClicked.connect(self.double_clicked,
                type=Qt.QueuedConnection)
        if exclude:
            if QApplication.instance().is_dark_theme:
                sheet = 'background-color: #DAA520; color: black'
            else:
                sheet = 'background-color: #fae7b5'
            self.fview.setStyleSheet('QListView { %s }' % sheet)
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
        self.selected_formats = set()

    def accept(self, *args):
        for idx in self.fview.selectedIndexes():
            self.selected_formats.add(self.formats.fmt(idx))
        QDialog.accept(self, *args)

    def double_clicked(self, index):
        if self.single_fmt:
            self.accept()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = SelectFormats(['epub', 'lrf', 'lit', 'mobi'], 'Choose a format')
    d.exec_()
    print(d.selected_formats)
