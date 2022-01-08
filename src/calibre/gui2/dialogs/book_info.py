#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>


import textwrap
from qt.core import (
    QAction, QApplication, QBrush, QCheckBox, QDialog, QGridLayout,
    QHBoxLayout, QIcon, QKeySequence, QLabel, QListView, QModelIndex, QPalette,
    QPixmap, QPushButton, QShortcut, QSize, QSplitter, Qt, QTimer, QToolButton,
    QVBoxLayout, QWidget, pyqtSignal, QDialogButtonBox
)

from calibre import fit_image
from calibre.gui2 import NO_URL_FORMATTING, gprefs
from calibre.gui2.book_details import (
    create_open_cover_with_menu, css, details_context_menu_event, render_html,
    set_html
)
from calibre.gui2.ui import get_gui
from calibre.gui2.widgets import CoverView
from calibre.gui2.widgets2 import Dialog, HTMLDisplay


class Cover(CoverView):

    open_with_requested = pyqtSignal(object)
    choose_open_with_requested = pyqtSignal()

    def __init__(self, parent, show_size=False):
        CoverView.__init__(self, parent, show_size=show_size)

    def build_context_menu(self):
        ans = CoverView.build_context_menu(self)
        create_open_cover_with_menu(self, ans)
        return ans

    def open_with(self, entry):
        self.open_with_requested.emit(entry)

    def choose_open_with(self):
        self.choose_open_with_requested.emit()

    def mouseDoubleClickEvent(self, ev):
        ev.accept()
        self.open_with_requested.emit(None)

    def set_marked(self, marked):
        if marked:
            marked_brush = QBrush(Qt.GlobalColor.darkGray if QApplication.instance().is_dark_theme else Qt.GlobalColor.lightGray)
            self.set_background(marked_brush)
        else:
            self.set_background()


class Configure(Dialog):

    def __init__(self, db, parent=None):
        self.db = db
        Dialog.__init__(self, _('Configure the Book details window'), 'book-details-popup-conf', parent)

    def setup_ui(self):
        from calibre.gui2.preferences.look_feel import (
            DisplayedFields, move_field_down, move_field_up
        )
        self.l = QVBoxLayout(self)
        self.field_display_order = fdo = QListView(self)
        self.model = DisplayedFields(self.db, fdo, pref_name='popup_book_display_fields')
        self.model.initialize()
        fdo.setModel(self.model)
        fdo.setAlternatingRowColors(True)
        del self.db
        self.l.addWidget(QLabel(_('Select displayed metadata')))
        h = QHBoxLayout()
        h.addWidget(fdo)
        v = QVBoxLayout()
        self.mub = b = QToolButton(self)
        connect_lambda(b.clicked, self, lambda self: move_field_up(fdo, self.model))
        b.setIcon(QIcon.ic('arrow-up.png'))
        b.setToolTip(_('Move the selected field up'))
        v.addWidget(b), v.addStretch(10)
        self.mud = b = QToolButton(self)
        b.setIcon(QIcon.ic('arrow-down.png'))
        b.setToolTip(_('Move the selected field down'))
        connect_lambda(b.clicked, self, lambda self: move_field_down(fdo, self.model))
        v.addWidget(b)
        h.addLayout(v)

        self.l.addLayout(h)
        self.l.addWidget(QLabel('<p>' + _(
            'Note that <b>comments</b> will always be displayed at the end, regardless of the order you assign here')))

        b = self.bb.addButton(_('Restore &defaults'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.restore_defaults)
        b = self.bb.addButton(_('Select &all'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.select_all)
        b = self.bb.addButton(_('Select &none'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.select_none)
        self.l.addWidget(self.bb)
        self.setMinimumHeight(500)

    def select_all(self):
        self.model.toggle_all(True)

    def select_none(self):
        self.model.toggle_all(False)

    def restore_defaults(self):
        self.model.initialize(use_defaults=True)

    def accept(self):
        self.model.commit()
        return Dialog.accept(self)


class Details(HTMLDisplay):

    def __init__(self, book_info, parent=None):
        HTMLDisplay.__init__(self, parent)
        self.book_info = book_info
        self.edit_metadata = getattr(parent, 'edit_metadata', None)
        self.setDefaultStyleSheet(css())

    def sizeHint(self):
        return QSize(350, 350)

    def contextMenuEvent(self, ev):
        details_context_menu_event(self, ev, self.book_info, edit_metadata=self.edit_metadata)


class BookInfo(QDialog):

    closed = pyqtSignal(object)
    open_cover_with = pyqtSignal(object, object)

    def __init__(self, parent, view, row, link_delegate):
        QDialog.__init__(self, parent)
        self.marked = None
        self.gui = parent
        self.splitter = QSplitter(self)
        self._l = l = QVBoxLayout(self)
        self.setLayout(l)
        l.addWidget(self.splitter)

        self.cover = Cover(self, show_size=gprefs['bd_overlay_cover_size'])
        self.cover.resizeEvent = self.cover_view_resized
        self.cover.cover_changed.connect(self.cover_changed)
        self.cover.open_with_requested.connect(self.open_with)
        self.cover.choose_open_with_requested.connect(self.choose_open_with)
        self.cover_pixmap = None
        self.cover.sizeHint = self.details_size_hint
        self.splitter.addWidget(self.cover)

        self.details = Details(parent.book_details.book_info, self)
        self.details.anchor_clicked.connect(self.on_link_clicked)
        self.link_delegate = link_delegate
        self.details.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        palette = self.details.palette()
        self.details.setAcceptDrops(False)
        palette.setBrush(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        self.details.setPalette(palette)

        self.c = QWidget(self)
        self.c.l = l2 = QGridLayout(self.c)
        l2.setContentsMargins(0, 0, 0, 0)
        self.c.setLayout(l2)
        l2.addWidget(self.details, 0, 0, 1, -1)
        self.splitter.addWidget(self.c)

        self.fit_cover = QCheckBox(_('Fit &cover within view'), self)
        self.fit_cover.setChecked(gprefs.get('book_info_dialog_fit_cover', True))
        self.hl = hl = QHBoxLayout()
        hl.setContentsMargins(0, 0, 0, 0)
        l2.addLayout(hl, l2.rowCount(), 0, 1, -1)
        hl.addWidget(self.fit_cover), hl.addStretch()
        self.clabel = QLabel('<div style="text-align: right"><a href="calibre:conf" title="{}" style="text-decoration: none">{}</a>'.format(
            _('Configure this view'), _('Configure')))
        self.clabel.linkActivated.connect(self.configure)
        hl.addWidget(self.clabel)
        self.previous_button = QPushButton(QIcon.ic('previous.png'), _('&Previous'), self)
        self.previous_button.clicked.connect(self.previous)
        l2.addWidget(self.previous_button, l2.rowCount(), 0)
        self.next_button = QPushButton(QIcon.ic('next.png'), _('&Next'), self)
        self.next_button.clicked.connect(self.next)
        l2.addWidget(self.next_button, l2.rowCount() - 1, 1)

        self.view = view
        self.path_to_book = None
        self.current_row = None
        self.refresh(row)
        self.view.model().new_bookdisplay_data.connect(self.slave)
        self.fit_cover.stateChanged.connect(self.toggle_cover_fit)
        self.ns = QShortcut(QKeySequence('Alt+Right'), self)
        self.ns.activated.connect(self.next)
        self.ps = QShortcut(QKeySequence('Alt+Left'), self)
        self.ps.activated.connect(self.previous)
        self.next_button.setToolTip(_('Next [%s]')%
                str(self.ns.key().toString(QKeySequence.SequenceFormat.NativeText)))
        self.previous_button.setToolTip(_('Previous [%s]')%
                str(self.ps.key().toString(QKeySequence.SequenceFormat.NativeText)))

        geom = self.screen().availableSize()
        screen_height = geom.height() - 100
        screen_width = geom.width() - 100
        self.resize(max(int(screen_width/2), 700), screen_height)
        saved_layout = gprefs.get('book_info_dialog_layout', None)
        if saved_layout is not None:
            try:
                QApplication.instance().safe_restore_geometry(self, saved_layout[0])
                self.splitter.restoreState(saved_layout[1])
            except Exception:
                pass
        ema = get_gui().iactions['Edit Metadata'].menuless_qaction
        a = self.ema = QAction('edit metadata', self)
        a.setShortcut(ema.shortcut())
        self.addAction(a)
        a.triggered.connect(self.edit_metadata)
        vb = get_gui().iactions['View'].menuless_qaction
        a = self.vba = QAction('view book', self)
        a.setShortcut(vb.shortcut())
        a.triggered.connect(self.view_book)
        self.addAction(a)

    def view_book(self):
        if self.current_row is not None:
            book_id = self.view.model().id(self.current_row)
            get_gui().iactions['View']._view_calibre_books((book_id,))

    def edit_metadata(self):
        if self.current_row is not None:
            book_id = self.view.model().id(self.current_row)
            get_gui().iactions['Edit Metadata'].edit_metadata_for([self.current_row], [book_id], bulk=False)

    def configure(self):
        d = Configure(get_gui().current_db, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            if self.current_row is not None:
                mi = self.view.model().get_book_display_info(self.current_row)
                if mi is not None:
                    self.refresh(self.current_row, mi=mi)

    def on_link_clicked(self, qurl):
        link = str(qurl.toString(NO_URL_FORMATTING))
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
            self.cover.set_marked(self.marked)
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
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                pixmap.setDevicePixelRatio(dpr)
        self.cover.set_pixmap(pixmap)
        self.cover.set_marked(self.marked)
        self.update_cover_tooltip()

    def update_cover_tooltip(self):
        tt = ''
        if self.marked:
            tt += _('This book is marked') if self.marked in {True, 'true'} else _(
                'This book is marked as: %s') % self.marked
            tt += '\n\n'

        if self.path_to_book is not None:
            tt += textwrap.fill(_('Path: {}').format(self.path_to_book))
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
        self.path_to_book = getattr(mi, 'path', None)
        try:
            dpr = self.devicePixelRatioF()
        except AttributeError:
            dpr = self.devicePixelRatio()
        self.cover_pixmap.setDevicePixelRatio(dpr)
        self.marked = mi.marked
        self.resize_cover()
        html = render_html(mi, True, self, pref_name='popup_book_display_fields')
        set_html(mi, html, self.details)
        self.update_cover_tooltip()

    def open_with(self, entry):
        id_ = self.view.model().id(self.current_row)
        self.open_cover_with.emit(id_, entry)

    def choose_open_with(self):
        from calibre.gui2.open_with import choose_program
        entry = choose_program('cover_image', self)
        if entry is not None:
            self.open_with(entry)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    app.current_db = db()
    get_gui.ans = app
    d = Configure(app.current_db)
    d.exec()
    del d
    del app
