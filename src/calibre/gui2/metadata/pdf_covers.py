#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import shutil
import sys
from threading import Thread

from qt.core import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPixmap,
    QSize,
    QStyledItemDelegate,
    Qt,
    QTimer,
    QVBoxLayout,
    pyqtSignal,
    sip,
)

from calibre import as_unicode
from calibre.ebooks.metadata.archive import get_comic_images
from calibre.ebooks.metadata.pdf import page_images
from calibre.gui2 import error_dialog, file_icon_provider
from calibre.gui2.progress_indicator import WaitLayout
from calibre.libunzip import comic_exts
from calibre.ptempfile import PersistentTemporaryDirectory


class CoverDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        style = QApplication.style()
        # Ensure the cover is rendered over any selection rect
        style.drawItemPixmap(painter, option.rect, Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter,
            QPixmap(index.data(Qt.ItemDataRole.DecorationRole)))


PAGES_PER_RENDER = 10


class PDFCovers(QDialog):
    'Choose a cover from the first few pages of a PDF'

    rendering_done = pyqtSignal()

    def __init__(self, pdfpath, parent=None):
        QDialog.__init__(self, parent)
        self.pdfpath = pdfpath
        self.ext = os.path.splitext(pdfpath)[1][1:].lower()
        self.is_pdf = self.ext == 'pdf'
        self.stack = WaitLayout(_('Rendering {} pages, please wait...').format('PDF' if self.is_pdf else _('comic book')), parent=self)
        self.container = self.stack.after

        self.container.l = l = QVBoxLayout(self.container)
        self.la = la = QLabel(_('Choose a cover from the list of pages below'))
        l.addWidget(la)
        self.covers = c = QListWidget(self)
        l.addWidget(c)
        self.item_delegate = CoverDelegate(self)
        c.setItemDelegate(self.item_delegate)
        c.setIconSize(QSize(120, 160))
        c.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        c.setViewMode(QListView.ViewMode.IconMode)
        c.setUniformItemSizes(True)
        c.setResizeMode(QListView.ResizeMode.Adjust)
        c.itemDoubleClicked.connect(self.accept, type=Qt.ConnectionType.QueuedConnection)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.more_pages = b = bb.addButton(_('&More pages'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.start_rendering)
        l.addWidget(bb)
        self.rendering_done.connect(self.show_pages, type=Qt.ConnectionType.QueuedConnection)
        self.first = 1
        self.setWindowTitle(_('Choose cover from book'))
        self.setWindowIcon(file_icon_provider().icon_from_ext(self.ext))
        self.resize(QSize(800, 600))
        self.tdir = PersistentTemporaryDirectory('_pdf_covers')
        QTimer.singleShot(0, self.start_rendering)

    def start_rendering(self):
        self.hide_pages()
        self.thread = Thread(target=self.render, daemon=True, name='RenderPages')
        self.thread.start()

    @property
    def cover_path(self):
        for item in self.covers.selectedItems():
            return str(item.data(Qt.ItemDataRole.UserRole) or '')
        if self.covers.count() > 0:
            return str(self.covers.item(0).data(Qt.ItemDataRole.UserRole) or '')

    def cleanup(self):
        try:
            shutil.rmtree(self.tdir)
        except OSError:
            pass

    def render(self):
        self.current_tdir = os.path.join(self.tdir, str(self.first))
        self.error = None
        try:
            os.mkdir(self.current_tdir)
            if self.is_pdf:
                page_images(self.pdfpath, self.current_tdir, first=self.first, last=self.first + PAGES_PER_RENDER - 1)
            else:
                get_comic_images(self.pdfpath, self.current_tdir, first=self.first, last=self.first + PAGES_PER_RENDER - 1)
        except Exception as e:
            import traceback
            traceback.print_exc()
            if not self.covers.count():
                self.error = as_unicode(e)
        if not sip.isdeleted(self) and self.isVisible():
            self.rendering_done.emit()

    def hide_pages(self):
        self.stack.start()
        self.more_pages.setVisible(False)

    def show_pages(self):
        if self.error is not None:
            error_dialog(self, _('Failed to render'),
                _('Could not render this file'), show=True, det_msg=self.error)
            self.reject()
            return
        self.stack.stop()
        files = tuple(x for x in os.listdir(self.current_tdir) if os.path.splitext(x)[1][1:].lower() in comic_exts)
        if not files and not self.covers.count():
            error_dialog(self, _('Failed to render'),
                _('This book has no pages'), show=True)
            self.reject()
            return

        try:
            dpr = self.devicePixelRatioF()
        except AttributeError:
            dpr = self.devicePixelRatio()

        for i, f in enumerate(sorted(files)):
            path = os.path.join(self.current_tdir, f)
            p = QPixmap(path).scaled(
                self.covers.iconSize()*dpr, aspectRatioMode=Qt.AspectRatioMode.IgnoreAspectRatio,
                transformMode=Qt.TransformationMode.SmoothTransformation)
            p.setDevicePixelRatio(dpr)
            i = QListWidgetItem(_('page %d') % (self.first + i))
            i.setData(Qt.ItemDataRole.DecorationRole, p)
            i.setData(Qt.ItemDataRole.UserRole, path)
            self.covers.addItem(i)
        self.first += len(files)
        if len(files) == PAGES_PER_RENDER:
            self.more_pages.setVisible(True)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = PDFCovers(sys.argv[-1])
    d.exec()
    print(d.cover_path)
    del app
