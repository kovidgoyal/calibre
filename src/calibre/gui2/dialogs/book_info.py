#!/usr/bin/env  python2
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

from functools import partial

from PyQt5.Qt import (
    QBrush, QCheckBox, QCoreApplication, QDialog, QGridLayout, QHBoxLayout, QIcon,
    QKeySequence, QLabel, QListView, QModelIndex, QPalette, QPixmap, QPushButton,
    QShortcut, QSize, QSplitter, Qt, QTimer, QToolButton, QVBoxLayout, QWidget,
    pyqtSignal
)
from PyQt5.QtWebKitWidgets import QWebView

from calibre import fit_image
from calibre.gui2 import NO_URL_FORMATTING, gprefs
from calibre.gui2.book_details import css, details_context_menu_event, render_html
from calibre.gui2.ui import get_gui
from calibre.gui2.widgets import CoverView
from calibre.gui2.widgets2 import Dialog


class Configure(Dialog):

    def __init__(self, db, parent=None):
        self.db = db
        Dialog.__init__(self, _('Configure the book details window'), 'book-details-popup-conf', parent)

    def setup_ui(self):
        from calibre.gui2.preferences.look_feel import DisplayedFields, move_field_up, move_field_down
        self.l = QVBoxLayout(self)
        self.field_display_order = fdo = QListView(self)
        self.model = DisplayedFields(self.db, fdo, pref_name='popup_book_display_fields')
        self.model.initialize()
        fdo.setModel(self.model)
        fdo.setAlternatingRowColors(True)
        del self.db
        self.l.addWidget(QLabel('Select displayed metadata'))
        h = QHBoxLayout()
        h.addWidget(fdo)
        v = QVBoxLayout()
        self.mub = b = QToolButton(self)
        b.clicked.connect(partial(move_field_up, fdo, self.model))
        b.setIcon(QIcon(I('arrow-up.png')))
        b.setToolTip(_('Move the selected field up'))
        v.addWidget(b), v.addStretch(10)
        self.mud = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        b.setToolTip(_('Move the selected field down'))
        b.clicked.connect(partial(move_field_down, fdo, self.model))
        v.addWidget(b)
        h.addLayout(v)

        self.l.addLayout(h)
        self.l.addWidget(QLabel('<p>' + _(
            'Note that <b>comments</b> will always be displayed at the end, regardless of the order you assign here')))

        b = self.bb.addButton(_('Restore &defaults'), self.bb.ActionRole)
        b.clicked.connect(self.restore_defaults)
        self.l.addWidget(self.bb)
        self.setMinimumHeight(500)

    def restore_defaults(self):
        self.model.initialize(use_defaults=True)

    def accept(self):
        self.model.commit()
        return Dialog.accept(self)


class Details(QWebView):

    def __init__(self, book_info, parent=None):
        QWebView.__init__(self, parent)
        self.book_info = book_info

    def sizeHint(self):
        return QSize(350, 350)

    def contextMenuEvent(self, ev):
        details_context_menu_event(self, ev, self.book_info)


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

        self.cover = CoverView(self, show_size=gprefs['bd_overlay_cover_size'])
        self.cover.resizeEvent = self.cover_view_resized
        self.cover.cover_changed.connect(self.cover_changed)
        self.cover_pixmap = None
        self.cover.sizeHint = self.details_size_hint
        self.splitter.addWidget(self.cover)

        self.details = Details(parent.book_details.book_info, self)
        self.details.page().setLinkDelegationPolicy(self.details.page().DelegateAllLinks)
        self.details.linkClicked.connect(self.link_clicked)
        s = self.details.page().settings()
        s.setAttribute(s.JavascriptEnabled, False)
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
        l2.addWidget(self.fit_cover, l2.rowCount(), 0, 1, 1)
        self.clabel = QLabel('<div style="text-align: right"><a href="calibre:conf" title="{}" style="text-decoration: none">{}</a>'.format(
            _('Configure this view'), _('Configure')))
        self.clabel.linkActivated.connect(self.configure)
        l2.addWidget(self.clabel, l2.rowCount() - 1, 1, 1, 1)
        self.previous_button = QPushButton(QIcon(I('previous.png')), _('&Previous'), self)
        self.previous_button.clicked.connect(self.previous)
        l2.addWidget(self.previous_button, l2.rowCount(), 0)
        self.next_button = QPushButton(QIcon(I('next.png')), _('&Next'), self)
        self.next_button.clicked.connect(self.next)
        l2.addWidget(self.next_button, l2.rowCount() - 1, 1)

        self.view = view
        self.current_row = None
        self.refresh(row)
        self.view.model().new_bookdisplay_data.connect(self.slave)
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

    def configure(self):
        d = Configure(get_gui().current_db, self)
        if d.exec_() == d.Accepted:
            if self.current_row is not None:
                mi = self.view.model().get_book_display_info(self.current_row)
                if mi is not None:
                    self.refresh(self.current_row, mi=mi)

    def link_clicked(self, qurl):
        link = unicode(qurl.toString(NO_URL_FORMATTING))
        self.link_delegate(link)

    def done(self, r):
        saved_layout = (bytearray(self.saveGeometry()), bytearray(self.splitter.saveState()))
        gprefs.set('book_info_dialog_layout', saved_layout)
        ret = QDialog.done(self, r)
        self.view.model().new_bookdisplay_data.disconnect(self.slave)
        self.view = self.link_delegate = self.gui = None
        self.closed.emit(self)
        return ret

    def cover_changed(self, data):
        if self.current_row is not None:
            id_ = self.view.model().id(self.current_row)
            self.view.model().db.set_cover(id_, data)
        self.gui.refresh_cover_browser()
        ci = self.view.currentIndex()
        if ci.isValid():
            self.view.model().current_changed(ci, ci)

    def details_size_hint(self):
        return QSize(350, 550)

    def toggle_cover_fit(self, state):
        gprefs.set('book_info_dialog_fit_cover', self.fit_cover.isChecked())
        self.resize_cover()

    def cover_view_resized(self, event):
        QTimer.singleShot(1, self.resize_cover)

    def slave(self, mi):
        self.refresh(mi.row_number, mi)

    def move(self, delta=1):
        idx = self.view.currentIndex()
        if idx.isValid():
            m = self.view.model()
            ni = m.index(idx.row() + delta, idx.column())
            if ni.isValid():
                if self.view.isVisible():
                    self.view.scrollTo(ni)
                self.view.setCurrentIndex(ni)

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
                try:
                    dpr = self.devicePixelRatioF()
                except AttributeError:
                    dpr = self.devicePixelRatio()
                pixmap = pixmap.scaled(int(dpr * new_width), int(dpr * new_height),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pixmap.setDevicePixelRatio(dpr)
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
            tt += _('Cover size: %(width)d x %(height)d pixels')%dict(width=sz.width(), height=sz.height())
        self.cover.setToolTip(tt)
        self.cover.pixmap_size = sz.width(), sz.height()

    def refresh(self, row, mi=None):
        if isinstance(row, QModelIndex):
            row = row.row()
        if row == self.current_row and mi is None:
            return
        mi = self.view.model().get_book_display_info(row) if mi is None else mi
        if mi is None:
            # Indicates books was deleted from library, or row numbers have
            # changed
            return

        self.previous_button.setEnabled(False if row == 0 else True)
        self.next_button.setEnabled(False if row == self.view.model().rowCount(QModelIndex())-1 else True)
        self.current_row = row
        self.setWindowTitle(mi.title)
        self.cover_pixmap = QPixmap.fromImage(mi.cover_data[1])
        try:
            dpr = self.devicePixelRatioF()
        except AttributeError:
            dpr = self.devicePixelRatio()
        self.cover_pixmap.setDevicePixelRatio(dpr)
        self.resize_cover()
        html = render_html(mi, self.css, True, self, pref_name='popup_book_display_fields')
        self.details.setHtml(html)
        self.marked = mi.marked
        self.cover.setBackgroundBrush(self.marked_brush if mi.marked else self.normal_brush)
        self.update_cover_tooltip()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    app.current_db = db()
    get_gui.ans = app
    d = Configure(app.current_db)
    d.exec_()
    del d
    del app
