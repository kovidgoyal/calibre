#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'


import os, sys, urlparse

from BeautifulSoup import BeautifulSoup, Tag


from PyQt4 import QtCore
from PyQt4.Qt import QUrl, QEventLoop, SIGNAL,  QObject, Qt, \
    QPrinter, QPrintPreviewDialog, QPrintDialog, QDialog, QMetaObject, Q_ARG
from PyQt4.QtWebKit import QWebView

PRINTCSS = 'body{width:100%;margin:0;padding:0;font-family:Arial;color:#000;background:none;font-size:12pt;text-align:left;}h1,h2,h3,h4,h5,h6{font-family:Helvetica;}h1{font-size:19pt;}h2{font-size:17pt;}h3{font-size:15pt;}h4,h5,h6{font-size:12pt;}pre,code,samp{font:10ptCourier,monospace;white-space:pre-wrap;page-break-inside:avoid;}blockquote{margin:1.3em;padding:1em;font-size:10pt;}hr{background-color:#ccc;}aimg{border:none;}a:link,a:visited{background:transparent;font-weight:700;text-decoration:underline;color:#333;}a:link:after,a{color:#000;}table{margin:1px;text-align:left;}th{border-bottom:1pxsolid#333;font-weight:bold;}td{border-bottom:1pxsolid#333;}th,td{padding:4px10px4px0;}tfoot{font-style:italic;}caption{background:#fff;margin-bottom:2em;text-align:left;}thead{display:table-header-group;}tr{page-break-inside:avoid;}#header,.header,#footer,.footer,#navbar,.navbar,#navigation,.navigation,#rightSideBar,.rightSideBar,#leftSideBar,.leftSideBar{display:none;}'

class Printing(QObject):
    def __init__(self, spine, preview):
        from calibre.gui2 import is_ok_to_use_qt
        if not is_ok_to_use_qt():
            raise Exception('Not OK to use Qt')
        QObject.__init__(self)
        self.loop = QEventLoop()

        self.view = QWebView()
        if preview:
            self.connect(self.view, SIGNAL('loadFinished(bool)'), self.print_preview)
        else:
            self.connect(self.view, SIGNAL('loadFinished(bool)'), self.print_book)

        self.process_content(spine)

    def process_content(self, spine):
        content = ''

        for path in spine:
            raw = self.raw_content(path)
            content += self.parsed_content(raw, path)

        refined_content = self.refine_content(content)

        base = os.path.splitdrive(spine[0])[0]
        base = base if base != '' else '/'

        QMetaObject.invokeMethod(self, "load_content", Qt.QueuedConnection, Q_ARG('QString', refined_content), Q_ARG('QString', base))
        self.loop.exec_()

    @QtCore.pyqtSignature('load_content(QString, QString)')
    def load_content(self, content, base):
        self.view.setHtml(content, QUrl(base))

    def raw_content(self, path):
        return open(path, 'rb').read().decode(path.encoding)

    def parsed_content(self, raw_content, path):
        dom_tree = BeautifulSoup(raw_content).body

        # Remove sytle information that is applied to the entire document.
        # This does not remove styles applied within a tag.
        styles = dom_tree.findAll('style')
        for s in styles:
            s.extract()

        scripts = dom_tree.findAll('script')
        for s in scripts:
            s.extract()

        # Convert all relative links to absolute paths.
        links = dom_tree.findAll(src=True)
        for s in links:
            if QUrl(s['src']).isRelative():
                s['src'] = urlparse.urljoin(path, s['src'])
        links = dom_tree.findAll(href=True)
        for s in links:
            if QUrl(s['href']).isRelative():
                s['href'] = urlparse.urljoin(path, s['href'])

        return unicode(dom_tree)

    # Adds the begenning and endings tags to the document.
    # Adds the print css.
    def refine_content(self, content):
        dom_tree = BeautifulSoup('<html><head></head><body>%s</body></html>' % content)

        css = dom_tree.findAll('link')
        for c in css:
            c.extract()

        print_css = Tag(BeautifulSoup(), 'style', [('type', 'text/css'), ('title', 'override_css')])
        print_css.insert(0, PRINTCSS)
        dom_tree.findAll('head')[0].insert(0, print_css)

        return unicode(dom_tree)

    def print_preview(self, ok):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageMargins(1, 1, 1, 1, QPrinter.Inch)

        previewDialog = QPrintPreviewDialog(printer)

        self.connect(previewDialog, SIGNAL('paintRequested(QPrinter *)'), self.view.print_)
        previewDialog.exec_()
        self.disconnect(previewDialog, SIGNAL('paintRequested(QPrinter *)'), self.view.print_)

        self.loop.quit()

    def print_book(self, ok):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageMargins(1, 1, 1, 1, QPrinter.Inch)

        printDialog = QPrintDialog(printer)
        printDialog.setWindowTitle(_("Print eBook"))

        printDialog.exec_()
        if printDialog.result() == QDialog.Accepted:
            self.view.print_(printer)

        self.loop.quit()

def main():
    return 0

if __name__ == '__main__':
    sys.exit(main())

