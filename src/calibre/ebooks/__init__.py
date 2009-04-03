__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Code for the conversion of ebook formats and the reading of metadata
from various formats.
'''

import traceback, os
from calibre import CurrentDir

class ConversionError(Exception):

    def __init__(self, msg, only_msg=False):
        Exception.__init__(self, msg)
        self.only_msg = only_msg

class UnknownFormatError(Exception):
    pass

class DRMError(ValueError):
    pass

BOOK_EXTENSIONS = ['lrf', 'rar', 'zip', 'rtf', 'lit', 'txt', 'htm', 'xhtm',
                   'html', 'xhtml', 'pdf', 'prc', 'mobi', 'azw',
                   'epub', 'fb2', 'djvu', 'lrx', 'cbr', 'cbz', 'oebzip',
                   'rb', 'imp', 'odt']

class HTMLRenderer(object):

    def __init__(self, page, loop):
        self.page, self.loop = page, loop
        self.data = ''
        self.exception = self.tb = None

    def __call__(self, ok):
        from PyQt4.Qt import QImage, QPainter, QByteArray, QBuffer
        try:
            if not ok:
                raise RuntimeError('Rendering of HTML failed.')
            image = QImage(self.page.viewportSize(), QImage.Format_ARGB32)
            image.setDotsPerMeterX(96*(100/2.54))
            image.setDotsPerMeterY(96*(100/2.54))
            painter = QPainter(image)
            self.page.mainFrame().render(painter)
            painter.end()
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QBuffer.WriteOnly)
            image.save(buf, 'JPEG')
            self.data = str(ba.data())
        except Exception, e:
            self.exception = e
            self.traceback = traceback.format_exc()
        finally:
            self.loop.exit(0)


def render_html(path_to_html, width=590, height=750):
    from PyQt4.QtWebKit import QWebPage
    from PyQt4.Qt import QEventLoop, QPalette, Qt, SIGNAL, QUrl, QSize
    path_to_html = os.path.abspath(path_to_html)
    with CurrentDir(os.path.dirname(path_to_html)):
        page = QWebPage()
        pal = page.palette()
        pal.setBrush(QPalette.Background, Qt.white)
        page.setPalette(pal)
        page.setViewportSize(QSize(width, height))
        page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        loop = QEventLoop()
        renderer = HTMLRenderer(page, loop)

        page.connect(page, SIGNAL('loadFinished(bool)'), renderer)
        page.mainFrame().load(QUrl.fromLocalFile(path_to_html))
        loop.exec_()
    return renderer

