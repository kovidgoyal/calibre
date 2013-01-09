#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from PyQt4.Qt import (QBrush, QColor, QPoint, QPixmap, QPainterPath, QRectF,
                      QApplication, QPainter, Qt, QImage, QLinearGradient,
                      QPointF, QPen)
QBrush, QColor, QPoint, QPixmap, QPainterPath, QRectF, Qt, QPointF

from calibre.ebooks.pdf.render.engine import PdfDevice

def full(p, xmax, ymax):
    p.drawRect(0, 0, xmax, ymax)
    p.drawPolyline(QPoint(0, 0), QPoint(xmax, 0), QPoint(xmax, ymax),
                    QPoint(0, ymax), QPoint(0, 0))
    pp = QPainterPath()
    pp.addRect(0, 0, xmax, ymax)
    p.drawPath(pp)
    p.save()
    for i in xrange(3):
        col = [0, 0, 0, 200]
        col[i] = 255
        p.setOpacity(0.3)
        p.fillRect(0, 0, xmax/10, xmax/10, QBrush(QColor(*col)))
        p.setOpacity(1)
        p.drawRect(0, 0, xmax/10, xmax/10)
        p.translate(xmax/10, xmax/10)
        p.scale(1, 1.5)
    p.restore()

    # p.scale(2, 2)
    # p.rotate(45)
    p.drawPixmap(0, 0, xmax/4, xmax/4, QPixmap(I('library.png')))
    p.drawRect(0, 0, xmax/4, xmax/4)

    f = p.font()
    f.setPointSize(20)
    # f.setLetterSpacing(f.PercentageSpacing, 200)
    f.setUnderline(True)
    # f.setOverline(True)
    # f.setStrikeOut(True)
    f.setFamily('Calibri')
    p.setFont(f)
    # p.setPen(QColor(0, 0, 255))
    # p.scale(2, 2)
    # p.rotate(45)
    p.drawText(QPoint(xmax/3.9, 30), 'Some—text not By’s ū --- Д AV ﬀ ff')

    b = QBrush(Qt.HorPattern)
    b.setColor(QColor(Qt.blue))
    pix = QPixmap(I('console.png'))
    w = xmax/4
    p.fillRect(0, ymax/3, w, w, b)
    p.fillRect(xmax/3, ymax/3, w, w, QBrush(pix))
    x, y = 2*xmax/3, ymax/3
    p.drawTiledPixmap(QRectF(x, y, w, w), pix, QPointF(10, 10))

    x, y = 1, ymax/1.9
    g = QLinearGradient(QPointF(x, y), QPointF(x+w, y+w))
    g.setColorAt(0, QColor('#00f'))
    g.setColorAt(1, QColor('#fff'))
    p.fillRect(x, y, w, w, QBrush(g))


def run(dev, func):
    p = QPainter(dev)
    if isinstance(dev, PdfDevice):
        dev.init_page()
    xmax, ymax = p.viewport().width(), p.viewport().height()
    try:
        func(p, xmax, ymax)
    finally:
        p.end()
    if isinstance(dev, PdfDevice):
        if dev.engine.errors_occurred:
            raise SystemExit(1)

def brush(p, xmax, ymax):
    x = xmax/3
    y = 0
    w = xmax/2
    g = QLinearGradient(QPointF(x, y), QPointF(x+w, y+w))
    g.setColorAt(0, QColor('#00f'))
    g.setColorAt(1, QColor('#fff'))
    p.fillRect(x, y, w, w, QBrush(g))

def pen(p, xmax, ymax):
    pix = QPixmap(I('console.png'))
    pen = QPen(QBrush(pix), 60)
    p.setPen(pen)
    p.drawRect(0, xmax/3, xmax/3, xmax/2)

def text(p, xmax, ymax):
    f = p.font()
    f.setPixelSize(24)
    f.setFamily('Candara')
    p.setFont(f)
    p.drawText(QPoint(0, 100),
        'Test intra glyph spacing ffagain imceo')

def main():
    app = QApplication([])
    app
    tdir = os.path.abspath('.')
    pdf = os.path.join(tdir, 'painter.pdf')
    func = brush
    dpi = 100
    with open(pdf, 'wb') as f:
        dev = PdfDevice(f, xdpi=dpi, ydpi=dpi, compress=False)
        img = QImage(dev.width(), dev.height(),
                     QImage.Format_ARGB32_Premultiplied)
        img.setDotsPerMeterX(dpi*39.37)
        img.setDotsPerMeterY(dpi*39.37)
        img.fill(Qt.white)
        run(dev, func)
    run(img, func)
    path = os.path.join(tdir, 'painter.png')
    img.save(path)
    print ('PDF written to:', pdf)
    print ('Image written to:', path)

if __name__ == '__main__':
    main()


