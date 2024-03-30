'''
SVG rasterization transform.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os
import re
from base64 import standard_b64encode
from functools import lru_cache

from lxml import etree
from qt.core import QBuffer, QByteArray, QColor, QImage, QIODevice, QPainter, QSvgRenderer, Qt

from calibre import guess_type
from calibre.ebooks.oeb.base import PNG_MIME, SVG_MIME, XHTML, XLINK, urlnormalize, xml2str, xpath
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.utils.imghdr import what
from polyglot.urllib import urldefrag

IMAGE_TAGS = {XHTML('img'), XHTML('object')}
KEEP_ATTRS = {'class', 'style', 'width', 'height', 'align'}

def test_svg():  # {{{
    TEST_PNG_DATA_URI='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAWJQTFRFAAAAAAAAAAAAAAAAAAAAAQEAAgIBAwIBBgQCBwUCCAYDCggECwkEDgsFDwwFEA0GHRcKHxkLIBkLIxwMJR0NJx8OKCAOKCAPKSAPMScSPTAWQTQXQzUYSjsaSjsbSzsbUD8dUUAdVEMeWkggW0ggW0ghW0khXUohYk4ja1Umb1gocVoocVopclspc1spdV0qd18reF8riW0xjXEzl3g2mns3nn04nn45n345oIA6ooE7o4I7pII7pIM7pYQ7p4U8qYY8rYo+s45Bxp1Hx55Hy6FJy6JJzaRJz6RKz6RLz6VL0qdL1KpM1apM1qtN16xN2KxN2K1O2a1O2q1O265P3K9P3bBQ3rBP37FP37FQ37JQ4rNR47VR5LVR7LxV7bxV7r1V7r5W8L9W8MBW8b9V8b9W8cBW8cBX8sBW8sBX8sFW8sFX88BX88FW88FX88FY88JX88JY9MFX9MJX9MJY9MNYSw0rOAAAAAR0Uk5T2+rr8giKtGMAAAFDSURBVDjLhdNFUwNBEIbhJWkkuLu7u5PgHtwWl0CGnW34aJLl/3OgUlRlGfKepqafmstUW1Yw8E9By6IMWVn/z7OsQOpYNrE0H4lEwuFwZHmyLnUb+AUzIiLMItDgrWIfKH3mnz4RA6PX/8Im8xuEgVfxxG33g+rVi9OT46OdPQ0kDgv8gCg3FMrLphkNyCD9BYiIqEErraP5ZrDGDrw2MoIhsPACGUH5g2gVqzWDKQ/gETKCZmHwbo4ZbHhJ1q1kBMMJCKbJCCof35V+qjCDOUCrMTKCFkc8vU5GENpW8NwmMxhVccYsGUHVvWKOFhlBySJicV6u7+7s6Ozq6anxgT44Lwy4jlKK4br96WDl09GA/gA4zp7gLh2MM3MS+EgCGl+iD9JB4cDZzbV9ZV/atn1+frvfaPhuX4HMq0cZsjKt/zfXXmDab9zjGwAAAABJRU5ErkJggg=='
    return f'''
    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
    <path d="M4.5 11H3v4h4v-1.5H4.5V11zM3 7h1.5V4.5H7V3H3v4zm10.5 6.5H11V15h4v-4h-1.5v2.5zM11 3v1.5h2.5V7H15V3h-4z"/>
    <image width="32" height="32" x="32" y="32" xlink:href="{TEST_PNG_DATA_URI}"/>
    </svg>'''.encode()
# }}}


class Unavailable(Exception):
    pass


def rasterize_svg(data=None, sizes=(), width=0, height=0, print=None, fmt='PNG', as_qimage=False):
    if data is None:
        data = test_svg()
    svg = QSvgRenderer(QByteArray(data))
    size = svg.defaultSize()
    if size.width() == 100 and size.height() == 100 and sizes:
        size.setWidth(int(sizes[0]))
        size.setHeight(int(sizes[1]))
    if width or height:
        size.scale(int(width), int(height), Qt.AspectRatioMode.KeepAspectRatio)
    if print is not None:
        print(f'Rasterizing SVG to {size.width()} x {size.height()}')
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("white").rgb())
    painter = QPainter(image)
    svg.render(painter)
    painter.end()
    if as_qimage:
        return image
    array = QByteArray()
    buffer = QBuffer(array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, fmt)
    return array.data()


@lru_cache(maxsize=128)
def data_url(mime_type: str, data: bytes) -> str:
    return f'data:{mime_type};base64,' + standard_b64encode(data).decode('ascii')


class SVGRasterizer:

    def __init__(self, base_css='', save_svg_originals=False):
        self.base_css = base_css
        self.save_svg_originals = save_svg_originals
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
        self.stylizer_cache = {}
        self.oeb = oeb
        self.opts = context
        self.profile = context.dest
        self.images = {}
        self.svg_originals = {}
        self.scan_for_linked_resources_in_manifest()
        self.rasterize_spine()
        self.rasterize_cover()

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

        return rasterize_svg(xml2str(elem, with_tail=False), sizes=sizes, width=width, height=height, print=logger.info, fmt=format)

    def scan_for_linked_resources_in_manifest(self):
        for item in self.oeb.manifest.values():
            if item.media_type == SVG_MIME and item.data is not None:
                self.scan_for_linked_resources_in_svg(item)

    def scan_for_linked_resources_in_svg(self, item, svg=None):
        if svg is None:
            svg = item.data
        hrefs = self.oeb.manifest.hrefs
        ha = XLINK('href')
        for elem in xpath(svg, '//svg:*[@xl:href]'):
            href = urlnormalize(elem.get(ha))
            path = urldefrag(href)[0]
            if not path:
                continue
            abshref = item.abshref(path)
            linkee = hrefs.get(abshref)
            if linkee is None:
                continue
            data = linkee.bytes_representation
            ext = what(None, data)
            if not ext:
                continue
            mt = guess_type('file.'+ext)[0]
            if not mt or not mt.startswith('image/'):
                continue
            elem.set(ha, data_url(mt, data))

        return svg

    def stylizer(self, item):
        ans = self.stylizer_cache.get(item, None)
        if ans is None:
            ans = self.stylizer_cache[item] = Stylizer(item.data, item.href, self.oeb, self.opts,
                    self.profile, base_css=self.base_css)
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
        self.scan_for_linked_resources_in_svg(item, elem)
        data = self.rasterize_svg(elem, width, height)
        manifest = self.oeb.manifest
        href = os.path.splitext(item.href)[0] + '.png'
        id, href = manifest.generate(item.id, href)
        manifest.add(id, href, PNG_MIME, data=data)
        img = elem.makeelement(XHTML('img'), src=item.relhref(href))
        if self.save_svg_originals:
            svg_bytes = etree.tostring(elem, encoding='utf-8', xml_declaration=True, pretty_print=True, with_tail=False)
            svg_id, svg_href = manifest.generate(item.id, 'inline.svg')
            manifest.add(svg_id, svg_href, SVG_MIME, data=svg_bytes)
            self.svg_originals[href] = svg_href
        img.tail = elem.tail
        elem.getparent().replace(elem, img)
        for prop in ('width', 'height'):
            if prop in elem.attrib:
                img.attrib[prop] = elem.attrib[prop]

    def rasterize_external(self, elem, style, item, svgitem):
        width = style['width']
        height = style['height']
        width = (width / 72) * self.profile.dpi
        height = (height / 72) * self.profile.dpi
        data = QByteArray(svgitem.bytes_representation)
        svg = QSvgRenderer(data)
        size = svg.defaultSize()
        size.scale(int(width), int(height), Qt.AspectRatioMode.KeepAspectRatio)
        key = (svgitem.href, size.width(), size.height())
        if key in self.images:
            href = self.images[key]
        else:
            logger = self.oeb.logger
            logger.info('Rasterizing %r to %dx%d'
                        % (svgitem.href, size.width(), size.height()))
            image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor("white").rgb())
            painter = QPainter(image)
            svg.render(painter)
            painter.end()
            array = QByteArray()
            buffer = QBuffer(array)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, 'PNG')
            data = array.data()
            manifest = self.oeb.manifest
            href = os.path.splitext(svgitem.href)[0] + '.png'
            id, href = manifest.generate(svgitem.id, href)
            manifest.add(id, href, PNG_MIME, data=data)
            self.images[key] = href
        self.svg_originals[href] = svgitem.href
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
        if str(covers[0]) not in self.oeb.manifest.ids:
            self.oeb.logger.warn('Cover not in manifest, skipping.')
            self.oeb.metadata.clear('cover')
            return
        cover = self.oeb.manifest.ids[str(covers[0])]
        if not cover.media_type == SVG_MIME:
            return
        width = (self.profile.width / 72) * self.profile.dpi
        height = (self.profile.height / 72) * self.profile.dpi
        data = self.rasterize_svg(cover.data, width, height)
        href = os.path.splitext(cover.href)[0] + '.png'
        id, href = self.oeb.manifest.generate(cover.id, href)
        self.oeb.manifest.add(id, href, PNG_MIME, data=data)
        covers[0].value = id


if __name__ == '__main__':
    open('/t/test-svg-rasterization.png', 'wb').write(rasterize_svg())
