'''
SVG rasterization transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os, re
from urlparse import urldefrag

from PyQt5.Qt import (
    Qt, QByteArray, QBuffer, QIODevice, QColor, QImage, QPainter, QSvgRenderer)
from calibre.ebooks.oeb.base import XHTML, XLINK
from calibre.ebooks.oeb.base import SVG_MIME, PNG_MIME
from calibre.ebooks.oeb.base import xml2str, xpath
from calibre.ebooks.oeb.base import urlnormalize
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.imghdr import what

IMAGE_TAGS = set([XHTML('img'), XHTML('object')])
KEEP_ATTRS = set(['class', 'style', 'width', 'height', 'align'])


class Unavailable(Exception):
    pass


class SVGRasterizer(object):

    def __init__(self, base_css=''):
        self.base_css = base_css
        from calibre.gui2 import must_use_qt
        must_use_qt()

    @classmethod
    def config(cls, cfg):
        return cfg

    @classmethod
    def generate(cls, opts):
        return cls()

    def __call__(self, oeb, context):
        oeb.logger.info('Rasterizing SVG images...')
        self.temp_files = []
        self.stylizer_cache = {}
        self.oeb = oeb
        self.opts = context
        self.profile = context.dest
        self.images = {}
        self.dataize_manifest()
        self.rasterize_spine()
        self.rasterize_cover()
        for pt in self.temp_files:
            try:
                os.remove(pt)
            except:
                pass

    def rasterize_svg(self, elem, width=0, height=0, format='PNG'):
        view_box = elem.get('viewBox', elem.get('viewbox', None))
        sizes = None
        logger = self.oeb.logger

        if view_box is not None:
            try:
                box = [float(x) for x in filter(None, re.split('[, ]', view_box))]
                sizes = [box[2]-box[0], box[3] - box[1]]
            except (TypeError, ValueError, IndexError):
                logger.warn('SVG image has invalid viewBox="%s", ignoring the viewBox' % view_box)
            else:
                for image in elem.xpath('descendant::*[local-name()="image" and '
                        '@height and contains(@height, "%")]'):
                    logger.info('Found SVG image height in %, trying to convert...')
                    try:
                        h = float(image.get('height').replace('%', ''))/100.
                        image.set('height', str(h*sizes[1]))
                    except:
                        logger.exception('Failed to convert percentage height:',
                                image.get('height'))

        data = QByteArray(xml2str(elem, with_tail=False))
        svg = QSvgRenderer(data)
        size = svg.defaultSize()
        if size.width() == 100 and size.height() == 100 and sizes:
            size.setWidth(sizes[0])
            size.setHeight(sizes[1])
        if width or height:
            size.scale(width, height, Qt.KeepAspectRatio)
        logger.info('Rasterizing %r to %dx%d'
                    % (elem, size.width(), size.height()))
        image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        image.fill(QColor("white").rgb())
        painter = QPainter(image)
        svg.render(painter)
        painter.end()
        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, format)
        return str(array)

    def dataize_manifest(self):
        for item in self.oeb.manifest.values():
            if item.media_type == SVG_MIME and item.data is not None:
                self.dataize_svg(item)

    def dataize_svg(self, item, svg=None):
        if svg is None:
            svg = item.data
        hrefs = self.oeb.manifest.hrefs
        for elem in xpath(svg, '//svg:*[@xl:href]'):
            href = urlnormalize(elem.attrib[XLINK('href')])
            path = urldefrag(href)[0]
            if not path:
                continue
            abshref = item.abshref(path)
            if abshref not in hrefs:
                continue
            linkee = hrefs[abshref]
            data = str(linkee)
            ext = what(None, data) or 'jpg'
            with PersistentTemporaryFile(suffix='.'+ext) as pt:
                pt.write(data)
                self.temp_files.append(pt.name)
            elem.attrib[XLINK('href')] = pt.name
        return svg

    def stylizer(self, item):
        ans = self.stylizer_cache.get(item, None)
        if ans is None:
            ans = Stylizer(item.data, item.href, self.oeb, self.opts,
                    self.profile, base_css=self.base_css)
            self.stylizer_cache[item] = ans
        return ans

    def rasterize_spine(self):
        for item in self.oeb.spine:
            self.rasterize_item(item)

    def rasterize_item(self, item):
        html = item.data
        hrefs = self.oeb.manifest.hrefs
        for elem in xpath(html, '//h:img[@src]'):
            src = urlnormalize(elem.attrib['src'])
            image = hrefs.get(item.abshref(src), None)
            if image and image.media_type == SVG_MIME:
                style = self.stylizer(item).style(elem)
                self.rasterize_external(elem, style, item, image)
        for elem in xpath(html, '//h:object[@type="%s" and @data]' % SVG_MIME):
            data = urlnormalize(elem.attrib['data'])
            image = hrefs.get(item.abshref(data), None)
            if image and image.media_type == SVG_MIME:
                style = self.stylizer(item).style(elem)
                self.rasterize_external(elem, style, item, image)
        for elem in xpath(html, '//svg:svg'):
            style = self.stylizer(item).style(elem)
            self.rasterize_inline(elem, style, item)

    def rasterize_inline(self, elem, style, item):
        width = style['width']
        height = style['height']
        width = (width / 72) * self.profile.dpi
        height = (height / 72) * self.profile.dpi
        elem = self.dataize_svg(item, elem)
        data = self.rasterize_svg(elem, width, height)
        manifest = self.oeb.manifest
        href = os.path.splitext(item.href)[0] + '.png'
        id, href = manifest.generate(item.id, href)
        manifest.add(id, href, PNG_MIME, data=data)
        img = elem.makeelement(XHTML('img'), src=item.relhref(href))
        elem.getparent().replace(elem, img)
        for prop in ('width', 'height'):
            if prop in elem.attrib:
                img.attrib[prop] = elem.attrib[prop]

    def rasterize_external(self, elem, style, item, svgitem):
        width = style['width']
        height = style['height']
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
            logger = self.oeb.logger
            logger.info('Rasterizing %r to %dx%d'
                        % (svgitem.href, size.width(), size.height()))
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
        for attr in elem.attrib:
            if attr not in KEEP_ATTRS:
                del elem.attrib[attr]
        elem.attrib['src'] = item.relhref(href)
        if elem.text:
            elem.attrib['alt'] = elem.text
            elem.text = None
        for child in elem:
            elem.remove(child)

    def rasterize_cover(self):
        covers = self.oeb.metadata.cover
        if not covers:
            return
        if unicode(covers[0]) not in self.oeb.manifest.ids:
            self.oeb.logger.warn('Cover not in manifest, skipping.')
            self.oeb.metadata.clear('cover')
            return
        cover = self.oeb.manifest.ids[unicode(covers[0])]
        if not cover.media_type == SVG_MIME:
            return
        width = (self.profile.width / 72) * self.profile.dpi
        height = (self.profile.height / 72) * self.profile.dpi
        data = self.rasterize_svg(cover.data, width, height)
        href = os.path.splitext(cover.href)[0] + '.png'
        id, href = self.oeb.manifest.generate(cover.id, href)
        self.oeb.manifest.add(id, href, PNG_MIME, data=data)
        covers[0].value = id
