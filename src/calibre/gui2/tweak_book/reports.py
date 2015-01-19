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
    QAbstractTableModel)

from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import current_container
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.ebooks.oeb.polish.report import gather_data

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
        self.files = ()
        self.total_size = self.text_count = self.style_count = 0
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
        self.text_count = sum(1 for f in self.files if f.category == 'text')
        self.style_count = sum(1 for f in self.files if f.category == 'style')
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            col = index.column()
            if col == 0:
                return entry.dir
            if col == 1:
                return entry.basename
            if col == 2:
                sz = entry.size / 1024.
                return ('%.2f' % sz if int(sz) != sz else type('')(sz))
            if col == 3:
                return self.CATEGORY_NAMES.get(entry.category)

class Reports(Dialog):

    data_gathered = pyqtSignal(object, object)

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Reports'), 'reports-dialog', parent=parent)
        self.data_gathered.connect(self.display_data, type=Qt.QueuedConnection)

    def setup_ui(self):
        self.wait_stack = s = QStackedLayout(self)

        self.pw = pw = QWidget(self)
        s.addWidget(pw)
        pw.l = l = QVBoxLayout(pw)
        self.pi = pi = ProgressIndicator(self, 256)
        l.addStretch(1), l.addWidget(pi, alignment=Qt.AlignHCenter), l.addSpacing(10)
        pw.la = la = QLabel(_('Gathering data, please wait...'))
        la.setStyleSheet('QLabel { font-size: 30pt; font-weight: bold }')
        l.addWidget(la, alignment=Qt.AlignHCenter), l.addStretch(1)

    def sizeHint(self):
        return QSize(950, 600)

    def refresh(self):
        self.wait_stack.setCurrentIndex(0)
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
        if not ok:
            return error_dialog(self, _('Failed to gather data'), _(
                'Failed to gather data for the report. Click "Show details" for more'
                ' information.'), det_msg=data, show=True)


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
