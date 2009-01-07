'''
SVG rasterization transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys
import os
from urlparse import urldefrag
import base64
from lxml import etree
from PyQt4.QtCore import Qt
from PyQt4.QtCore import QByteArray
from PyQt4.QtCore import QBuffer
from PyQt4.QtCore import QIODevice
from PyQt4.QtGui import QColor
from PyQt4.QtGui import QImage
from PyQt4.QtGui import QPainter
from PyQt4.QtSvg import QSvgRenderer
from PyQt4.QtGui import QApplication
from calibre.ebooks.oeb.base import XHTML_NS, XHTML, SVG_NS, SVG, XLINK
from calibre.ebooks.oeb.base import SVG_MIME, PNG_MIME
from calibre.ebooks.oeb.base import xml2str, xpath, namespace, barename
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
        self.dataize_manifest()
        self.rasterize_spine()
        self.rasterize_cover()

    def rasterize_svg(self, elem, width=0, height=0):
        data = QByteArray(xml2str(elem))
        svg = QSvgRenderer(data)
        size = svg.defaultSize()
        if size.width() == 100 and size.height() == 100 \
           and 'viewBox' in elem.attrib:
            box = [float(x) for x in elem.attrib['viewBox'].split()]
            size.setWidth(box[2] - box[0])
            size.setHeight(box[3] - box[1])
        if width or height:
            size.scale(width, height, Qt.KeepAspectRatio)
        image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        image.fill(QColor("white").rgb())
        painter = QPainter(image)
        svg.render(painter)
        painter.end()
        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, 'PNG')
        return str(array)

    def dataize_manifest(self):
        for item in self.oeb.manifest.values():
            if item.media_type == SVG_MIME:
                self.dataize_svg(item)

    def dataize_svg(self, item, svg=None):
        if svg is None:
            svg = item.data
        hrefs = self.oeb.manifest.hrefs
        for elem in xpath(svg, '//svg:*[@xl:href]'):
            href = elem.attrib[XLINK('href')]
            path, frag = urldefrag(href)
            if not path:
                continue
            abshref = item.abshref(path)
            if abshref not in hrefs:
                continue
            linkee = hrefs[abshref]
            data = base64.encodestring(str(linkee))
            data = "data:%s;base64,%s" % (linkee.media_type, data)
            elem.attrib[XLINK('href')] = data
        return svg
            
    def rasterize_spine(self):
        for item in self.oeb.spine:
            html = item.data
            stylizer = Stylizer(html, item.href, self.oeb, self.profile)
            self.rasterize_elem(html.find(XHTML('body')), item, stylizer)

    def rasterize_elem(self, elem, item, stylizer):
        if not isinstance(elem.tag, basestring): return
        style = stylizer.style(elem)
        if namespace(elem.tag) == SVG_NS:
            return self.rasterize_inline(elem, style, item)
        if elem.tag in IMAGE_TAGS:
            manifest = self.oeb.manifest
            src = elem.get('src', None) or elem.get('data', None)
            image = manifest.hrefs[item.abshref(src)] if src else None
            if image and image.media_type == SVG_MIME:
                return self.rasterize_external(elem, style, item, image)
        for child in elem:
            self.rasterize_elem(child, item, stylizer)

    def rasterize_inline(self, elem, style, item):
        width = style['width']
        if width == 'auto':
            width = self.profile.width
        height = style['height']
        if height == 'auto':
            height = self.profile.height
        width = (width / 72) * self.profile.dpi
        height = (height / 72) * self.profile.dpi
        elem = self.dataize_svg(item, elem)
        data = self.rasterize_svg(elem, width, height)
        manifest = self.oeb.manifest
        href = os.path.splitext(item.href)[0] + '.png'
        id, href = manifest.generate(item.id, href)
        manifest.add(id, href, PNG_MIME, data=data)
        img = etree.Element(XHTML('img'), src=item.relhref(href))
        elem.getparent().replace(elem, img)
        for prop in ('width', 'height'):
            if prop in elem.attrib:
                img.attrib[prop] = elem.attrib[prop]

    def rasterize_external(self, elem, style, item, svgitem):
        width = style['width']
        if width == 'auto':
            width = self.profile.width
        height = style['height']
        if height == 'auto':
            height = self.profile.height
        width = (width / 72) * self.profile.dpi
        height = (height / 72) * self.profile.dpi
        data = QByteArray(str(svgitem))
        svg = QSvgRenderer(data)
        size = svg.defaultSize()
        size.scale(width, height, Qt.KeepAspectRatio)
        key = (svgitem.href, size.width(), size.height())
        if key in self.images:
            href = self.images[key]
        else:
            image = QImage(size, QImage.Format_ARGB32_Premultiplied)
            image.fill(QColor("white").rgb())
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
            manifest.add(id, href, PNG_MIME, data=data)
            self.images[key] = href
        elem.tag = XHTML('img')
        elem.attrib['src'] = item.relhref(href)
        elem.text = None
        for child in elem:
            elem.remove(child)
            
    def rasterize_cover(self):
        covers = self.oeb.metadata.cover
        if not covers:
            return
        cover = self.oeb.manifest.ids[str(covers[0])]
        if not cover.media_type == SVG_MIME:
            return
        data = self.rasterize_svg(cover.data, 500, 800)
        href = os.path.splitext(cover.href)[0] + '.png'
        id, href = self.oeb.manifest.generate(cover.id, href)
        self.oeb.manifest.add(id, href, PNG_MIME, data=data)
        covers[0].value = id
