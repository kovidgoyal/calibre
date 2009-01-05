'''
SVG rasterization transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys
import os
from lxml import etree
from PyQt4.QtCore import Qt
from PyQt4.QtCore import QByteArray
from PyQt4.QtCore import QBuffer
from PyQt4.QtCore import QIODevice
from PyQt4.QtGui import QImage
from PyQt4.QtGui import QPainter
from PyQt4.QtSvg import QSvgRenderer
from PyQt4.QtGui import QApplication
from calibre.ebooks.oeb.base import XHTML, SVG, SVG_NS, SVG_MIME
from calibre.ebooks.oeb.base import namespace, barename
from calibre.ebooks.oeb.stylizer import Stylizer

IMAGE_TAGS = set([XHTML('img'), XHTML('object')])

class SVGRasterizer(object):
    def __init__(self):
        if QApplication.instance() is None:
            QApplication([])

    def transform(self, oeb, context):
        self.oeb = oeb
        self.profile = context.dest
        self.images = {}
        self.rasterize_spine()

    def rasterize_spine(self):
        for item in self.oeb.spine:
            html = item.data
            stylizer = Stylizer(html, item.href, self.oeb, self.profile)
            self.rasterize_elem(html.find(XHTML('body')), item, stylizer)

    def rasterize_elem(self, elem, item, stylizer):
        if not isinstance(elem.tag, basestring): return
        style = stylizer.style(elem)
        if namespace(elem.tag) == SVG_NS:
            return self.rasterize_inline(elem, style)
        if elem.tag in IMAGE_TAGS:
            manifest = self.oeb.manifest
            src = elem.get('src', None) or elem.get('data', None)
            image = manifest.hrefs[item.abshref(src)] if src else None
            if image and image.media_type == SVG_MIME:
                return self.rasterize_external(elem, style, item, image)
        for child in elem:
            self.rasterize_elem(child, item, stylizer)

    def rasterize_inline(self, elem, style):
        pass

    def rasterize_external(self, elem, style, item, svgitem):
        data = QByteArray(svgitem.data)
        svg = QSvgRenderer(data)
        size = svg.defaultSize()
        height = style['height']
        if height == 'auto':
            height = self.profile.height
        width = style['width']
        if width == 'auto':
            width = self.profile.width
        width = (width / 72) * self.profile.dpi
        height = (height / 72) * self.profile.dpi
        size.scale(width, height, Qt.KeepAspectRatio)
        key = (svgitem.href, size.width(), size.height())
        if key in self.images:
            href = self.images[key]
        else:
            image = QImage(size, QImage.Format_ARGB32_Premultiplied)
            painter = QPainter(image)
            svg.render(painter)
            painter.end()
            array = QByteArray()
            buffer = QBuffer(array)
            buffer.open(QIODevice.WriteOnly)
            image.save(buffer, 'PNG')
            data = str(array)
            manifest = self.oeb.manifest
            href = os.path.splitext(svgitem.href)[0] + '.png'
            id, href = manifest.generate(svgitem.id, href)
            manifest.add(id, href, 'image/png', data=data)
            self.images[key] = href
        elem.tag = XHTML('img')
        elem.attrib['src'] = item.relhref(href)
        elem.text = None
        for child in elem:
            elem.remove(child)
            
