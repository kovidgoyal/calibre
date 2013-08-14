#!/usr/bin/env  python
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import (
    QCoreApplication, QModelIndex, QTimer, Qt, pyqtSignal, QWidget,
    QGridLayout, QDialog, QPixmap, QSize, QPalette, QShortcut, QKeySequence,
    QSplitter, QVBoxLayout, QCheckBox, QPushButton, QIcon, QBrush)
from PyQt4.QtWebKit import QWebView

from calibre.gui2 import gprefs
from calibre import fit_image
from calibre.gui2.book_details import render_html
from calibre.gui2.widgets import CoverView

_css = None
def css():
    global _css
    if _css is None:
        _css = P('templates/book_details.css', data=True).decode('utf-8')
    return _css

class BookInfo(QDialog):

    closed = pyqtSignal(object)

    def __init__(self, parent, view, row, link_delegate):
        QDialog.__init__(self, parent)
        self.normal_brush = QBrush(Qt.white)
        self.marked_brush = QBrush(Qt.lightGray)
        self.marked = None
        self.gui = parent
        self.splitter = QSplitter(self)
        self._l = l = QVBoxLayout(self)
        self.setLayout(l)
        l.addWidget(self.splitter)

        self.cover = CoverView(self)
        self.cover.resizeEvent = self.cover_view_resized
        self.cover.cover_changed.connect(self.cover_changed)
        self.cover_pixmap = None
        self.cover.sizeHint = self.details_size_hint
        self.splitter.addWidget(self.cover)

        self.details = QWebView(self)
        self.details.sizeHint = self.details_size_hint
        self.details.page().setLinkDelegationPolicy(self.details.page().DelegateAllLinks)
        self.details.linkClicked.connect(self.link_clicked)
        self.css = css()
        self.link_delegate = link_delegate
        self.details.setAttribute(Qt.WA_OpaquePaintEvent, False)
        palette = self.details.palette()
        self.details.setAcceptDrops(False)
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.details.page().setPalette(palette)

        self.c = QWidget(self)
        self.c.l = l2 = QGridLayout(self.c)
        self.c.setLayout(l2)
        l2.addWidget(self.details, 0, 0, 1, -1)
        self.splitter.addWidget(self.c)

        self.fit_cover = QCheckBox(_('Fit &cover within view'), self)
        self.fit_cover.setChecked(gprefs.get('book_info_dialog_fit_cover', True))
        l2.addWidget(self.fit_cover, l2.rowCount(), 0, 1, -1)
        self.previous_button = QPushButton(QIcon(I('previous.png')), _('&Previous'), self)
        self.previous_button.clicked.connect(self.previous)
        l2.addWidget(self.previous_button, l2.rowCount(), 0)
        self.next_button = QPushButton(QIcon(I('next.png')), _('&Next'), self)
        self.next_button.clicked.connect(self.next)
        l2.addWidget(self.next_button, l2.rowCount() - 1, 1)

        self.view = view
        self.current_row = None
        self.refresh(row)
        self.view.selectionModel().currentChanged.connect(self.slave)
        self.fit_cover.stateChanged.connect(self.toggle_cover_fit)
        self.ns = QShortcut(QKeySequence('Alt+Right'), self)
        self.ns.activated.connect(self.next)
        self.ps = QShortcut(QKeySequence('Alt+Left'), self)
        self.ps.activated.connect(self.previous)
        self.next_button.setToolTip(_('Next [%s]')%
                unicode(self.ns.key().toString(QKeySequence.NativeText)))
        self.previous_button.setToolTip(_('Previous [%s]')%
                unicode(self.ps.key().toString(QKeySequence.NativeText)))

        geom = QCoreApplication.instance().desktop().availableGeometry(self)
        screen_height = geom.height() - 100
        screen_width = geom.width() - 100
        self.resize(max(int(screen_width/2), 700), screen_height)
        saved_layout = gprefs.get('book_info_dialog_layout', None)
        if saved_layout is not None:
            try:
                self.restoreGeometry(saved_layout[0])
                self.splitter.restoreState(saved_layout[1])
            except Exception:
                pass

    def link_clicked(self, qurl):
        link = unicode(qurl.toString())
        self.link_delegate(link)

    def done(self, r):
        saved_layout = (bytearray(self.saveGeometry()), bytearray(self.splitter.saveState()))
        gprefs.set('book_info_dialog_layout', saved_layout)
        ret = QDialog.done(self, r)
        self.view.selectionModel().currentChanged.disconnect(self.slave)
        self.view = self.link_delegate = self.gui = None
        self.closed.emit(self)
        return ret

    def cover_changed(self, data):
        if self.current_row is not None:
            id_ = self.view.model().id(self.current_row)
            self.view.model().db.set_cover(id_, data)
        if self.gui.cover_flow:
            self.gui.cover_flow.dataChanged()
        ci = self.view.currentIndex()
        if ci.isValid():
            self.view.model().current_changed(ci, ci)
        self.cover_pixmap = QPixmap()
        self.cover_pixmap.loadFromData(data)
        if self.fit_cover.isChecked():
            self.resize_cover()

    def details_size_hint(self):
        return QSize(350, 550)

    def toggle_cover_fit(self, state):
        gprefs.set('book_info_dialog_fit_cover', self.fit_cover.isChecked())
        self.resize_cover()

    def cover_view_resized(self, event):
        QTimer.singleShot(1, self.resize_cover)

    def slave(self, current, previous):
        if current.row() != previous.row():
            row = current.row()
            self.refresh(row)

    def move(self, delta=1):
        self.view.selectionModel().currentChanged.disconnect(self.slave)
        try:
            idx = self.view.currentIndex()
            if idx.isValid():
                m = self.view.model()
                ni = m.index(idx.row() + delta, idx.column())
                if ni.isValid():
                    self.view.setCurrentIndex(ni)
                    self.refresh(ni.row())
                    if self.view.isVisible():
                        self.view.scrollTo(ni)
        finally:
            self.view.selectionModel().currentChanged.connect(self.slave)

    def next(self):
        self.move()

    def previous(self):
        self.move(-1)

    def resize_cover(self):
        if self.cover_pixmap is None:
            return
        pixmap = self.cover_pixmap
        if self.fit_cover.isChecked():
            scaled, new_width, new_height = fit_image(pixmap.width(),
                    pixmap.height(), self.cover.size().width()-10,
                    self.cover.size().height()-10)
            if scaled:
                pixmap = pixmap.scaled(new_width, new_height,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.cover.set_pixmap(pixmap)
        self.update_cover_tooltip()

    def update_cover_tooltip(self):
        tt = ''
        if self.marked:
            tt = _('This book is marked') if self.marked in {True, 'true'} else _(
                'This book is marked as: %s') % self.marked
            tt += '\n\n'
        if self.cover_pixmap is not None:
            sz = self.cover_pixmap.size()
            tt += _('Cover size: %(width)d x %(height)d')%dict(width=sz.width(), height=sz.height())
        self.cover.setToolTip(tt)

    def refresh(self, row):
        if isinstance(row, QModelIndex):
            row = row.row()
        if row == self.current_row:
            return
        mi = self.view.model().get_book_display_info(row)
        if mi is None:
            # Indicates books was deleted from library, or row numbers have
            # changed
            return

        self.previous_button.setEnabled(False if row == 0 else True)
        self.next_button.setEnabled(False if row == self.view.model().rowCount(QModelIndex())-1 else True)
        self.current_row = row
        self.setWindowTitle(mi.title)
        self.cover_pixmap = QPixmap.fromImage(mi.cover_data[1])
        self.resize_cover()
        html = render_html(mi, self.css, True, self, all_fields=True)
        self.details.setHtml(html)
        self.marked = mi.marked
        self.cover.setBackgroundBrush(self.marked_brush if mi.marked else self.normal_brush)
        self.update_cover_tooltip()
