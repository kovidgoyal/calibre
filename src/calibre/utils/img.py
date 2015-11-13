#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from PyQt5.Qt import QImage, QByteArray, QBuffer, Qt, QPainter

from calibre import fit_image

def image_from_data(data):
    i = QImage()
    if not i.loadFromData(data):
        raise ValueError('Not a valid image')
    return i

def scale_image(data, width=60, height=80, compression_quality=70, as_png=False, preserve_aspect_ratio=True):
    # We use Qt instead of ImageMagick here because ImageMagick seems to use
    # some kind of memory pool, causing memory consumption to sky rocket. Since
    # we are only using QImage this method is thread safe, and does not require
    # a QApplication/GUI thread
    if isinstance(data, QImage):
        img = data
    else:
        img = QImage()
        if not img.loadFromData(data):
            raise ValueError('Could not load image for thumbnail generation')
    if preserve_aspect_ratio:
        scaled, nwidth, nheight = fit_image(img.width(), img.height(), width, height)
        if scaled:
            img = img.scaled(nwidth, nheight, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    else:
        if img.width() != width or img.height() != height:
            img = img.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    if not as_png and img.hasAlphaChannel():
        nimg = QImage(img.size(), QImage.Format_RGB32)
        nimg.fill(Qt.white)
        p = QPainter(nimg)
        p.drawImage(0, 0, img)
        p.end()
        img = nimg
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    fmt = 'PNG' if as_png else 'JPEG'
    if not img.save(buf, fmt, quality=compression_quality):
        raise ValueError('Failed to export thumbnail image to: ' + fmt)
    return ba.data()


