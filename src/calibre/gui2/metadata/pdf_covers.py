#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, shutil, os
from threading import Thread
from glob import glob

from PyQt5.Qt import (
    QDialog, QApplication, QLabel, QVBoxLayout, QDialogButtonBox, Qt,
    pyqtSignal, QListWidget, QListWidgetItem, QSize, QPixmap, QStyledItemDelegate
)
try:
    from PyQt5 import sip
except ImportError:
    import sip

from calibre import as_unicode
from calibre.ebooks.metadata.pdf import page_images
from calibre.gui2 import error_dialog, file_icon_provider
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.gui2.progress_indicator import WaitLayout
from polyglot.builtins import unicode_type


class CoverDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        style = QApplication.style()
        # Ensure the cover is rendered over any selection rect
        style.drawItemPixmap(painter, option.rect, Qt.AlignTop|Qt.AlignHCenter,
            QPixmap(index.data(Qt.DecorationRole)))


PAGES_PER_RENDER = 10


class PDFCovers(QDialog):
    'Choose a cover from the first few pages of a PDF'

    rendering_done = pyqtSignal()

    def __init__(self, pdfpath, parent=None):
        QDialog.__init__(self, parent)
        self.pdfpath = pdfpath
        self.stack = WaitLayout(_('Rendering PDF pages, please wait...'), parent=self)
        self.container = self.stack.after

        self.container.l = l = QVBoxLayout(self.container)
        self.la = la = QLabel(_('Choose a cover from the list of PDF pages below'))
        l.addWidget(la)
        self.covers = c = QListWidget(self)
        l.addWidget(c)
        self.item_delegate = CoverDelegate(self)
        c.setItemDelegate(self.item_delegate)
        c.setIconSize(QSize(120, 160))
        c.setSelectionMode(c.SingleSelection)
        c.setViewMode(c.IconMode)
        c.setUniformItemSizes(True)
        c.setResizeMode(c.Adjust)
        c.itemDoubleClicked.connect(self.accept, type=Qt.QueuedConnection)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.more_pages = b = bb.addButton(_('&More pages'), QDialogButtonBox.ActionRole)
        b.clicked.connect(self.start_rendering)
        l.addWidget(bb)
        self.rendering_done.connect(self.show_pages, type=Qt.QueuedConnection)
        self.first = 1
        self.setWindowTitle(_('Choose cover from PDF'))
        self.setWindowIcon(file_icon_provider().icon_from_ext('pdf'))
        self.resize(QSize(800, 600))
        self.tdir = PersistentTemporaryDirectory('_pdf_covers')
        self.start_rendering()

    def start_rendering(self):
        self.hide_pages()
        self.thread = Thread(target=self.render)
        self.thread.daemon = True
        self.thread.start()

    @property
    def cover_path(self):
        for item in self.covers.selectedItems():
            return unicode_type(item.data(Qt.UserRole) or '')
        if self.covers.count() > 0:
            return unicode_type(self.covers.item(0).data(Qt.UserRole) or '')

    def cleanup(self):
        try:
            shutil.rmtree(self.tdir)
        except EnvironmentError:
            pass

    def render(self):
        self.current_tdir = os.path.join(self.tdir, unicode_type(self.first))
        self.error = None
        try:
            os.mkdir(self.current_tdir)
            page_images(self.pdfpath, self.current_tdir, first=self.first, last=self.first + PAGES_PER_RENDER - 1)
        except Exception as e:
            if self.covers.count():
                pass
            else:
                self.error = as_unicode(e)
        if not sip.isdeleted(self) and self.isVisible():
            self.rendering_done.emit()

    def hide_pages(self):
        self.stack.start()
        self.more_pages.setVisible(False)

    def show_pages(self):
        if self.error is not None:
            error_dialog(self, _('Failed to render'),
                _('Could not render this PDF file'), show=True, det_msg=self.error)
            self.reject()
            return
        self.stack.stop()
        files = glob(os.path.join(self.current_tdir, '*.jpg')) + glob(os.path.join(self.current_tdir, '*.jpeg'))
        if not files and not self.covers.count():
            error_dialog(self, _('Failed to render'),
                _('This PDF has no pages'), show=True)
            self.reject()
            return

        try:
            dpr = self.devicePixelRatioF()
        except AttributeError:
            dpr = self.devicePixelRatio()

        for i, f in enumerate(sorted(files)):
            p = QPixmap(f).scaled(self.covers.iconSize()*dpr, aspectRatioMode=Qt.IgnoreAspectRatio, transformMode=Qt.SmoothTransformation)
            p.setDevicePixelRatio(dpr)
            i = QListWidgetItem(_('page %d') % (self.first + i))
            i.setData(Qt.DecorationRole, p)
            i.setData(Qt.UserRole, f)
            self.covers.addItem(i)
        self.first += len(files)
        if len(files) == PAGES_PER_RENDER:
            self.more_pages.setVisible(True)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = PDFCovers(sys.argv[-1])
    d.exec_()
    print(d.cover_path)
    del app
