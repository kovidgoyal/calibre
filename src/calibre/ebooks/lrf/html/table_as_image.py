#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Render HTML tables as images.
'''
import os, tempfile, atexit, shutil
from PyQt5.Qt import QUrl, QApplication, QSize, QEventLoop, \
                     QPainter, QImage, QObject, Qt
from PyQt5.QtWebKit import QWebPage

class HTMLTableRenderer(QObject):

    def __init__(self, html, base_dir, width, height, dpi, factor):
        '''
        `width, height`: page width and height in pixels
        `base_dir`: The directory in which the HTML file that contains the table resides
        '''
        QObject.__init__(self)

        self.app = None
        self.width, self.height, self.dpi = width, height, dpi
        self.base_dir = base_dir
        self.images = []
        self.tdir = tempfile.mkdtemp(prefix='calibre_render_table')
        self.loop = QEventLoop()
        self.page = QWebPage()
        self.page.loadFinished.connect(self.render_html)
        self.page.mainFrame().setTextSizeMultiplier(factor)
        self.page.mainFrame().setHtml(html,
                                QUrl('file:'+os.path.abspath(self.base_dir)))

    def render_html(self, ok):
        try:
            if not ok:
                return
            cwidth, cheight = self.page.mainFrame().contentsSize().width(), self.page.mainFrame().contentsSize().height()
            self.page.setViewportSize(QSize(cwidth, cheight))
            factor = float(self.width)/cwidth if cwidth > self.width else 1
            cutoff_height = int(self.height/factor)-3
            image = QImage(self.page.viewportSize(), QImage.Format_ARGB32)
            image.setDotsPerMeterX(self.dpi*(100/2.54))
            image.setDotsPerMeterY(self.dpi*(100/2.54))
            painter = QPainter(image)
            self.page.mainFrame().render(painter)
            painter.end()
            cheight = image.height()
            cwidth = image.width()
            pos = 0
            while pos < cheight:
                img = image.copy(0, pos, cwidth, min(cheight-pos, cutoff_height))
                pos += cutoff_height-20
                if cwidth > self.width:
                    img = img.scaledToWidth(self.width, Qt.SmoothTransform)
                f = os.path.join(self.tdir, '%d.png'%pos)
                img.save(f)
                self.images.append((f, img.width(), img.height()))
        finally:
            QApplication.quit()

def render_table(soup, table, css, base_dir, width, height, dpi, factor=1.0):
    head = ''
    for e in soup.findAll(['link', 'style']):
        head += unicode(e)+'\n\n'
    style = ''
    for key, val in css.items():
        style += key + ':%s;'%val
    html = u'''\
<html>
    <head>
        %s
    </head>
    <body style="width: %dpx; background: white">
        <style type="text/css">
            table {%s}
        </style>
        %s
    </body>
</html>
    '''%(head, width-10, style, unicode(table))
    images, tdir = do_render(html, base_dir, width, height, dpi, factor)
    atexit.register(shutil.rmtree, tdir)
    return images

def do_render(html, base_dir, width, height, dpi, factor):
    from calibre.gui2 import is_ok_to_use_qt
    if not is_ok_to_use_qt():
        raise Exception('Not OK to use Qt')
    tr = HTMLTableRenderer(html, base_dir, width, height, dpi, factor)
    tr.loop.exec_()
    return tr.images, tr.tdir
