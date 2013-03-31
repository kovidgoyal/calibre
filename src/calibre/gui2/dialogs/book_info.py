#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import (QCoreApplication, SIGNAL, QModelIndex, QTimer, Qt,
    QDialog, QPixmap, QIcon, QSize, QPalette, QShortcut, QKeySequence)

from calibre.gui2.dialogs.book_info_ui import Ui_BookInfo
from calibre.gui2 import dynamic
from calibre import fit_image
from calibre.gui2.book_details import render_html

class BookInfo(QDialog, Ui_BookInfo):

    def __init__(self, parent, view, row, link_delegate):
        QDialog.__init__(self, parent)
        Ui_BookInfo.__init__(self)
        self.setupUi(self)
        self.gui = parent
        self.cover_pixmap = None
        self.details.sizeHint = self.details_size_hint
        self.details.page().setLinkDelegationPolicy(self.details.page().DelegateAllLinks)
        self.details.linkClicked.connect(self.link_clicked)
        self.css = P('templates/book_details.css', data=True).decode('utf-8')
        self.link_delegate = link_delegate
        self.details.setAttribute(Qt.WA_OpaquePaintEvent, False)
        palette = self.details.palette()
        self.details.setAcceptDrops(False)
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.details.page().setPalette(palette)


        self.view = view
        self.current_row = None
        self.fit_cover.setChecked(dynamic.get('book_info_dialog_fit_cover',
            True))
        self.refresh(row)
        self.connect(self.view.selectionModel(), SIGNAL('currentChanged(QModelIndex,QModelIndex)'), self.slave)
        self.connect(self.next_button, SIGNAL('clicked()'), self.next)
        self.connect(self.previous_button, SIGNAL('clicked()'), self.previous)
        self.fit_cover.stateChanged.connect(self.toggle_cover_fit)
        self.cover.resizeEvent = self.cover_view_resized
        self.cover.cover_changed.connect(self.cover_changed)
        self.ns = QShortcut(QKeySequence('Alt+Right'), self)
        self.ns.activated.connect(self.next)
        self.ps = QShortcut(QKeySequence('Alt+Left'), self)
        self.ps.activated.connect(self.previous)
        self.next_button.setToolTip(_('Next [%s]')%
                unicode(self.ns.key().toString(QKeySequence.NativeText)))
        self.previous_button.setToolTip(_('Previous [%s]')%
                unicode(self.ps.key().toString(QKeySequence.NativeText)))

        desktop = QCoreApplication.instance().desktop()
        screen_height = desktop.availableGeometry().height() - 100
        self.resize(self.size().width(), screen_height)

    def link_clicked(self, qurl):
        link = unicode(qurl.toString())
        self.link_delegate(link)

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
        dynamic.set('book_info_dialog_fit_cover', self.fit_cover.isChecked())
        self.resize_cover()

    def cover_view_resized(self, event):
        QTimer.singleShot(1, self.resize_cover)

    def slave(self, current, previous):
        row = current.row()
        self.refresh(row)

    def next(self):
        row = self.view.currentIndex().row()
        ni = self.view.model().index(row+1, 0)
        if ni.isValid():
            self.view.setCurrentIndex(ni)

    def previous(self):
        row = self.view.currentIndex().row()
        ni = self.view.model().index(row-1, 0)
        if ni.isValid():
            self.view.setCurrentIndex(ni)

    def resize_cover(self):
        if self.cover_pixmap is None:
            return
        self.setWindowIcon(QIcon(self.cover_pixmap))
        pixmap = self.cover_pixmap
        if self.fit_cover.isChecked():
            scaled, new_width, new_height = fit_image(pixmap.width(),
                    pixmap.height(), self.cover.size().width()-10,
                    self.cover.size().height()-10)
            if scaled:
                pixmap = pixmap.scaled(new_width, new_height,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.cover.set_pixmap(pixmap)
        sz = pixmap.size()
        self.cover.setToolTip(_('Cover size: %(width)d x %(height)d')%dict(
            width=sz.width(), height=sz.height()))

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
        self.title.setText('<b>'+mi.title)
        mi.title = _('Unknown')
        self.cover_pixmap = QPixmap.fromImage(mi.cover_data[1])
        self.resize_cover()
        html = render_html(mi, self.css, True, self, all_fields=True)
        self.details.setHtml(html)

