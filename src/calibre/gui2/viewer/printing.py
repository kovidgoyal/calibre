#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QObject, QEventLoop, Qt, QPrintDialog, QPainter, QSize,
        QPrintPreviewDialog)
from PyQt4.QtWebKit import QWebView

from calibre.gui2 import error_dialog
from calibre.ebooks.oeb.display.webview import load_html
from calibre.utils.resources import compiled_coffeescript

class Printing(QObject):

    def __init__(self, iterator, parent):
        QObject.__init__(self, parent)
        self.current_index = 0
        self.iterator = iterator
        self.view = QWebView(self.parent())
        self.mf = mf = self.view.page().mainFrame()
        for x in (Qt.Horizontal, Qt.Vertical):
            mf.setScrollBarPolicy(x, Qt.ScrollBarAlwaysOff)
        self.view.loadFinished.connect(self.load_finished)
        self.paged_js = compiled_coffeescript('ebooks.oeb.display.utils')
        self.paged_js += compiled_coffeescript('ebooks.oeb.display.paged')

    def load_finished(self, ok):
        self.loaded_ok = ok

    def start_print(self):
        self.pd = QPrintDialog(self.parent())
        self.pd.open(self._start_print)

    def _start_print(self):
        self.do_print(self.pd.printer())

    def start_preview(self):
        self.pd = QPrintPreviewDialog(self.parent())
        self.pd.paintRequested.connect(self.do_print)
        self.pd.exec_()

    def do_print(self, printer):
        painter = QPainter(printer)
        zoomx = printer.logicalDpiX()/self.view.logicalDpiX()
        zoomy = printer.logicalDpiY()/self.view.logicalDpiY()
        painter.scale(zoomx, zoomy)
        pr = printer.pageRect()
        self.view.page().setViewportSize(QSize(pr.width()/zoomx,
            pr.height()/zoomy))
        evaljs = self.mf.evaluateJavaScript
        loop = QEventLoop(self)
        first = True

        for path in self.iterator.spine:
            self.loaded_ok = None
            load_html(path, self.view, codec=getattr(path, 'encoding', 'utf-8'),
                    mime_type=getattr(path, 'mime_type', None))
            while self.loaded_ok is None:
                loop.processEvents(loop.ExcludeUserInputEvents)
            if not self.loaded_ok:
                return error_dialog(self.parent(), _('Failed to render'),
                        _('Failed to render document %s')%path, show=True)
            evaljs(self.paged_js)
            evaljs('''
                document.body.style.backgroundColor = "white";
                paged_display.set_geometry(1, 0, 0, 0);
                paged_display.layout();
                paged_display.fit_images();
                paged_display.check_top_margin();
            ''')

            while True:
                if not first:
                    printer.newPage()
                first = False
                self.mf.render(painter)
                nsl = evaljs('paged_display.next_screen_location()').toInt()
                if not nsl[1] or nsl[0] <= 0: break
                evaljs('window.scrollTo(%d, 0)'%nsl[0])

        painter.end()

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.ebooks.oeb.iterator.book import EbookIterator
    from PyQt4.Qt import QPrinter, QTimer
    import sys
    app = Application([])

    def doit():
        with EbookIterator(sys.argv[-1]) as it:
            p = Printing(it, None)
            printer = QPrinter()
            of = sys.argv[-1]+'.pdf'
            printer.setOutputFileName(of)
            p.do_print(printer)
            print ('Printed to:', of)
            app.exit()
    QTimer.singleShot(0, doit)
    app.exec_()

