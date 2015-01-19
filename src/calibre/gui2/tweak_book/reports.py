#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Thread
from future_builtins import map
from operator import itemgetter

from PyQt5.Qt import (
    QSize, QStackedLayout, QLabel, QVBoxLayout, Qt, QWidget, pyqtSignal,
    QAbstractTableModel, QTableView, QSortFilterProxyModel, QIcon, QListWidget,
    QListWidgetItem, QLineEdit, QStackedWidget, QSplitter, QByteArray)

from calibre import human_readable
from calibre.ebooks.oeb.polish.report import gather_data
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import current_container, tprefs
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils.icu import primary_contains, primary_sort_key

def read_state(name, default=None):
    data = tprefs.get('reports-ui-state')
    if data is None:
        tprefs['reports-ui-state'] = data = {}
    return data.get(name, default)

def save_state(name, val):
    data = tprefs.get('reports-ui-state')
    if isinstance(val, QByteArray):
        val = bytearray(val)
    if data is None:
        tprefs['reports-ui-state'] = data = {}
    data[name] = val

class ProxyModel(QSortFilterProxyModel):  # {{{

    def __init__(self, parent=None):
        QSortFilterProxyModel.__init__(self, parent)
        self._filter_text = None

    def filter_text(self, text):
        self._filter_text = text
        self.setFilterFixedString(text)

    def filterAcceptsRow(self, row, parent):
        if not self._filter_text:
            return True
        sm = self.sourceModel()
        for item in (sm.data(sm.index(row, c, parent)) or '' for c in xrange(sm.columnCount())):
            if item and primary_contains(self._filter_text, item):
                return True
        return False

    def lessThan(self, left, right):
        sm = self.sourceModel()
        return sm.sort_key(left.row(), left.column()) < sm.sort_key(right.row(), right.column())

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return section + 1
        return QSortFilterProxyModel.headerData(self, section, orientation, role)
# }}}

# Files {{{
class FilesModel(QAbstractTableModel):

    COLUMN_HEADERS = [_('Folder'), _('Name'), _('Size (KB)'), _('Type')]
    CATEGORY_NAMES = {
        'image':_('Image'),
        'text': _('Text'),
        'font': _('Font'),
        'style': _('Style'),
        'opf': _('Metadata'),
        'toc': _('Table of Contents'),
    }

    def __init__(self, parent=None):
        self.files = self.sort_keys = ()
        self.total_size = self.images_size = self.fonts_size = 0
        QAbstractTableModel.__init__(self, parent)

    def columnCount(self, parent=None):
        return len(self.COLUMN_HEADERS)

    def rowCount(self, parent=None):
        return len(self.files)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            try:
                return self.COLUMN_HEADERS[section]
            except IndexError:
                pass
        return QAbstractTableModel.headerData(self, section, orientation, role)

    def __call__(self, data):
        self.beginResetModel()
        self.files = data['files']
        self.total_size = sum(map(itemgetter(3), self.files))
        self.images_size = sum(map(itemgetter(3), (f for f in self.files if f.category == 'image')))
        self.fonts_size = sum(map(itemgetter(3), (f for f in self.files if f.category == 'font')))
        psk = primary_sort_key
        self.sort_keys = tuple((psk(entry.dir), psk(entry.basename), entry.size, psk(self.CATEGORY_NAMES.get(entry.category, '')))
                               for entry in self.files)
        self.endResetModel()

    def sort_key(self, row, col):
        try:
            return self.sort_keys[row][col]
        except IndexError:
            pass

    def name(self, index):
        try:
            return self.files[index.row()].name
        except IndexError:
            pass

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            col = index.column()
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            if col == 0:
                return entry.dir
            if col == 1:
                return entry.basename
            if col == 2:
                sz = entry.size / 1024.
                return ('%.2f' % sz if int(sz) != sz else type('')(sz))
            if col == 3:
                return self.CATEGORY_NAMES.get(entry.category)

class FilesWidget(QWidget):

    edit_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        self.files = f = QTableView(self)
        f.setSelectionBehavior(f.SelectRows), f.setSelectionMode(f.SingleSelection)
        f.doubleClicked.connect(self.double_clicked)
        self.model = m = FilesModel(self)
        self.proxy = p = ProxyModel(self)
        e.textChanged.connect(p.filter_text)
        p.setSourceModel(m)
        f.setModel(p)
        l.addWidget(f)
        f.setSortingEnabled(True)

        self.summary = s = QLabel(self)
        l.addWidget(s)
        s.setText('\xa0')
        try:
            self.files.horizontalHeader().restoreState(read_state('all-files-table'))
        except TypeError:
            self.files.sortByColumn(1, Qt.AscendingOrder)

    def __call__(self, data):
        self.model(data)
        m = self.model
        self.summary.setText(_('Total uncompressed size of all files: {0} :: Images: {1} :: Fonts: {2}').format(*map(
            human_readable, (m.total_size, m.images_size, m.fonts_size))))

    def double_clicked(self, index):
        name = self.model.name(self.proxy.mapToSource(index))
        if name is not None:
            self.edit_requested.emit(name, None)

    def save(self):
        save_state('all-files-table', bytearray(self.files.horizontalHeader().saveState()))

# }}}

# Wrapper UI {{{
class ReportsWidget(QWidget):

    edit_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = QVBoxLayout(self)
        self.splitter = l = QSplitter(self)
        l.setChildrenCollapsible(False)
        self.layout().addWidget(l)
        self.reports = r = QListWidget(self)
        l.addWidget(r)
        self.stack = s = QStackedWidget(self)
        l.addWidget(s)
        r.currentRowChanged.connect(s.setCurrentIndex)

        self.files = f = FilesWidget(self)
        f.edit_requested.connect(self.edit_requested)
        s.addWidget(f)
        QListWidgetItem(_('Files'), r)

        self.splitter.setStretchFactor(1, 500)
        try:
            self.splitter.restoreState(read_state('splitter-state'))
        except TypeError:
            pass
        current_page = read_state('report-page')
        if current_page is not None:
            self.reports.setCurrentRow(current_page)

    def __call__(self, data):
        self.files(data)

    def save(self):
        save_state('splitter-state', bytearray(self.splitter.saveState()))
        save_state('report-page', self.reports.currentRow())
        self.files.save()

class Reports(Dialog):

    data_gathered = pyqtSignal(object, object)
    edit_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Reports'), 'reports-dialog', parent=parent)
        self.data_gathered.connect(self.display_data, type=Qt.QueuedConnection)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.wait_stack = s = QStackedLayout()
        l.addLayout(s)
        l.addWidget(self.bb)
        self.reports = r = ReportsWidget(self)
        r.edit_requested.connect(self.edit_requested)

        self.pw = pw = QWidget(self)
        s.addWidget(pw), s.addWidget(r)
        pw.l = l = QVBoxLayout(pw)
        self.pi = pi = ProgressIndicator(self, 256)
        l.addStretch(1), l.addWidget(pi, alignment=Qt.AlignHCenter), l.addSpacing(10)
        pw.la = la = QLabel(_('Gathering data, please wait...'))
        la.setStyleSheet('QLabel { font-size: 30pt; font-weight: bold }')
        l.addWidget(la, alignment=Qt.AlignHCenter), l.addStretch(1)

        self.bb.setStandardButtons(self.bb.Close)
        self.refresh_button = b = self.bb.addButton(_('&Refresh'), self.bb.ActionRole)
        b.clicked.connect(self.refresh)
        b.setIcon(QIcon(I('view-refresh')))

    def sizeHint(self):
        return QSize(950, 600)

    def refresh(self):
        self.wait_stack.setCurrentIndex(0)
        self.setCursor(Qt.BusyCursor)
        self.pi.startAnimation()
        t = Thread(name='GatherReportData', target=self.gather_data)
        t.daemon = True
        t.start()

    def gather_data(self):
        try:
            ok, data = True, gather_data(current_container())
        except Exception:
            import traceback
            ok, data = False, traceback.format_exc()
        self.data_gathered.emit(ok, data)

    def display_data(self, ok, data):
        self.wait_stack.setCurrentIndex(1)
        self.unsetCursor()
        self.pi.stopAnimation()
        if not ok:
            return error_dialog(self, _('Failed to gather data'), _(
                'Failed to gather data for the report. Click "Show details" for more'
                ' information.'), det_msg=data, show=True)
        self.reports(data)

    def accept(self):
        with tprefs:
            self.reports.save()
        Dialog.accept(self)

    def reject(self):
        self.reports.save()
        Dialog.reject(self)
# }}}

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    from calibre.gui2.tweak_book import set_current_container
    from calibre.gui2.tweak_book.boss import get_container
    set_current_container(get_container('/t/demo.epub'))
    d = Reports()
    d.refresh()
    d.exec_()
    del d, app
