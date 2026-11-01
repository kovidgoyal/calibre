#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import os
import posixpath
from functools import partial
from typing import TYPE_CHECKING, NamedTuple

from lxml import etree

from calibre import fit_image
from calibre.ebooks.docx.images import pt_to_emu
from calibre.ebooks.docx.names import SVG_BLIP_URI, USE_LOCAL_DPI_URI
from calibre.ebooks.oeb.base import Manifest, urlquote, urlunquote
from calibre.utils.filenames import ascii_filename
from calibre.utils.imghdr import identify
from calibre.utils.localization import _
from calibre.utils.resources import get_image_path as I

if TYPE_CHECKING:
    from collections.abc import Callable
    from optparse import Values

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.docx.writer.container import DocumentRelationships
    from calibre.ebooks.docx.writer.from_html import Block
    from calibre.ebooks.docx.writer.links import Link
    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.oeb.stylizer import Style, Stylizer
    from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer


class Image(NamedTuple):
    rid: str
    fname: str
    width: int
    height: int
    fmt: str
    item: Manifest.Item


def as_num(x: str | float) -> float:
    try:
        return float(x)
    except Exception:
        pass
    return 0


def get_image_margins(style: Style) -> dict[str, str]:
    ans: dict[str, str] = {}
    for edge in 'Left Right Top Bottom'.split():
        val = as_num(getattr(style, 'padding' + edge)) + as_num(getattr(style, 'margin' + edge))
        ans['dist' + edge[0]] = str(pt_to_emu(val))
    return ans


class ImagesManager:
    def __init__(self, oeb: OEBBook, document_relationships: DocumentRelationships, opts: Values | OptionValues, svg_rasterizer: SVGRasterizer) -> None:
        self.oeb, self.log = oeb, oeb.log
        self.svg_rasterizer = svg_rasterizer
        self.page_width, self.page_height = opts.output_profile.width_pts, opts.output_profile.height_pts
        self.images: dict[str, Image] = {}
        self.seen_filenames: set[str] = set()
        self.document_relationships = document_relationships
        self.count = 0
        self.svg_images: dict[str, Image] = {}

    def read_svg(self, href: str) -> Image | None:
        if href not in self.svg_images:
            item = self.oeb.manifest.hrefs.get(href) or self.oeb.manifest.hrefs.get(urlquote(href))
            if item is None:
                self.log.warning('Failed to find image:', href)
                return None
            image_fname = 'media/' + self.create_filename(href, 'svg')
            image_rid = self.document_relationships.add_image(image_fname)
            self.svg_images[href] = Image(image_rid, image_fname, -1, -1, 'svg', item)
        return self.svg_images[href]

    def read_image(self, href: str) -> Image | None:
        if href not in self.images:
            item = self.oeb.manifest.hrefs.get(href) or self.oeb.manifest.hrefs.get(urlquote(href))
            try:
                if item is None or not isinstance(item.data, bytes):
                    self.log.warning('Failed to find image:', href)
                    return None
            except FileNotFoundError:
                self.log.warning('Failed to find image:', href)
                return None
            try:
                fmt, width, height = identify(item.data)
                if fmt is None:
                    raise ValueError('Unknown image format')
            except Exception:
                self.log.warning(f'Replacing corrupted image with blank: {href}')
                item.data = blank = I('blank.png', data=True, allow_user_override=False)
                fmt, width, height = identify(blank)
                fmt = fmt or 'png'
            image_fname = 'media/' + self.create_filename(href, fmt)
            image_rid = self.document_relationships.add_image(image_fname)
            self.images[href] = Image(image_rid, image_fname, width, height, fmt, item)
            item.unload_data_from_memory()
        return self.images[href]

    def abshref(self, x: str) -> str:
        return x

    def add_image(
        self, img: etree._Element, block: Block, stylizer: Stylizer, bookmark: str | None = None, as_block: bool = False, link: Link | None = None
    ) -> str | None:
        src = img.get('src')
        if not src:
            return None
        href = self.abshref(src)
        try:
            rid = self.read_image(href).rid  # ty: ignore[unresolved-attribute]  # AttributeError for None is handled below
        except AttributeError:
            return None
        drawing, floating = self.create_image_markup(img, stylizer, href, as_block=as_block)
        block.add_image(drawing, bookmark=bookmark, link=link, floating=floating)
        return rid

    def create_image_markup(self, html_img: etree._Element, stylizer: Stylizer, href: str, as_block: bool = False) -> tuple[etree._Element, bool]:
        """Return the <w:drawing> for the image and whether it is floating"""
        svg_rid = ''
        svghref = self.svg_rasterizer.svg_originals.get(href)
        if svghref:
            si = self.read_svg(svghref)
            if si:
                svg_rid = si.rid
        style = stylizer.style(html_img)
        float_val = style['float']
        floating = float_val if isinstance(float_val, str) and float_val in {'left', 'right'} else None
        if as_block:
            ml, mr = style._get('margin-left'), style._get('margin-right')
            if ml == 'auto':
                floating = 'center' if mr == 'auto' else 'right'
            if mr == 'auto':
                floating = 'center' if ml == 'auto' else 'right'
        else:
            parent = html_img.getparent()
            assert parent is not None  # images are always inside the body
            if len(parent) == 1 and not (parent.text or '').strip() and not (html_img.tail or '').strip():
                pstyle = stylizer.style(parent)
                display = pstyle['display']
                assert isinstance(display, str)  # display values are keywords, a number would fail the in test
                if 'block' in display:
                    # We have an inline image alone inside a block
                    as_block = True
                    float_val = pstyle['float']
                    floating = float_val if isinstance(float_val, str) and float_val in {'left', 'right'} else None
                    if floating is None:
                        text_align = pstyle['text-align']
                        if isinstance(text_align, str) and text_align in ('center', 'right'):
                            floating = text_align
                    floating = floating or 'left'
        fake_margins = floating is None
        self.count += 1
        img = self.images[href]
        name = urlunquote(posixpath.basename(href))
        width, height = style.img_size(img.width, img.height)
        scaled, width, height = fit_image(width, height, self.page_width, self.page_height)
        width, height = map(pt_to_emu, (width, height))

        makeelement, namespaces = (
            self.document_relationships.namespace.makeelement,
            self.document_relationships.namespace.namespaces,
        )

        root = etree.Element('root', nsmap=namespaces)
        ans = makeelement(root, 'w:drawing', append=False)
        if floating is None:
            parent = makeelement(ans, 'wp:inline')
        else:
            parent = makeelement(ans, 'wp:anchor', append=True, **get_image_margins(style))
            # The next three lines are boilerplate that Word requires, even
            # though the DOCX specs define defaults for all of them
            (
                parent.set('simplePos', '0'),
                parent.set('relativeHeight', '1'),
                parent.set('behindDoc', '0'),
                parent.set('locked', '0'),
            )
            parent.set('layoutInCell', '1'), parent.set('allowOverlap', '1')
            makeelement(parent, 'wp:simplePos', x='0', y='0')
            makeelement(makeelement(parent, 'wp:positionH', relativeFrom='margin'), 'wp:align').text = floating
            makeelement(makeelement(parent, 'wp:positionV', relativeFrom='line'), 'wp:align').text = 'top'
        makeelement(parent, 'wp:extent', cx=str(width), cy=str(height))
        if fake_margins:
            # DOCX does not support setting margins for inline images, so we
            # fake it by using effect extents to simulate margins
            makeelement(parent, 'wp:effectExtent', append=True, **{k[-1].lower(): v for k, v in get_image_margins(style).items()})
        else:
            makeelement(parent, 'wp:effectExtent', l='0', r='0', t='0', b='0')
        if floating is not None:
            # The idiotic Word requires this to be after the extent settings
            if as_block:
                makeelement(parent, 'wp:wrapTopAndBottom')
            else:
                makeelement(parent, 'wp:wrapSquare', wrapText='bothSides')
        self.create_docx_image_markup(parent, name, html_img.get('alt') or name, img.rid, width, height, svg_rid=svg_rid)
        return ans, floating is not None

    def create_docx_image_markup(self, parent: etree._Element, name: str, alt: str, img_rid: str, width: int, height: int, svg_rid: str = '') -> None:
        makeelement, namespaces = (
            self.document_relationships.namespace.makeelement,
            self.document_relationships.namespace.namespaces,
        )
        makeelement(parent, 'wp:docPr', id=str(self.count), name=name, descr=alt)
        makeelement(makeelement(parent, 'wp:cNvGraphicFramePr'), 'a:graphicFrameLocks', noChangeAspect='1')
        g = makeelement(parent, 'a:graphic')
        gd = makeelement(g, 'a:graphicData', uri=namespaces['pic'])
        pic = makeelement(gd, 'pic:pic')
        nvPicPr = makeelement(pic, 'pic:nvPicPr')
        makeelement(nvPicPr, 'pic:cNvPr', id='0', name=name, descr=alt)
        makeelement(nvPicPr, 'pic:cNvPicPr')
        bf = makeelement(pic, 'pic:blipFill')
        blip = makeelement(bf, 'a:blip', r_embed=img_rid)
        if svg_rid:
            ext_list = makeelement(blip, 'a:extLst')
            makeelement(makeelement(ext_list, 'a:ext', uri=USE_LOCAL_DPI_URI), 'a14:useLocalDpi', val='0')
            makeelement(makeelement(ext_list, 'a:ext', uri=SVG_BLIP_URI), 'asvg:svgBlip', r_embed=svg_rid)
        makeelement(makeelement(bf, 'a:stretch'), 'a:fillRect')
        spPr = makeelement(pic, 'pic:spPr')
        xfrm = makeelement(spPr, 'a:xfrm')
        makeelement(xfrm, 'a:off', x='0', y='0'), makeelement(xfrm, 'a:ext', cx=str(width), cy=str(height))
        makeelement(makeelement(spPr, 'a:prstGeom', prst='rect'), 'a:avLst')

    def create_filename(self, href: str, fmt: str) -> str:
        fname = ascii_filename(urlunquote(posixpath.basename(href)))
        fname = posixpath.splitext(fname)[0]
        fname = fname[:75].rstrip('.') or 'image'
        num = 0
        base = fname
        while fname.lower() in self.seen_filenames:
            num += 1
            fname = base + str(num)
        self.seen_filenames.add(fname.lower())
        fname += os.extsep + fmt.lower()
        return fname

    def serialize(self, images_map: dict[str, Callable[[], bytes | str]]) -> None:
        for img in self.images.values():
            images_map['word/' + img.fname] = partial(self.get_data, img.item)

        def get_svg_data(img: Image) -> bytes | str:
            ans = img.item.data_as_bytes_or_none
            # SVG items created in memory have no loader, serialize them
            return img.item.bytes_representation if ans is None else ans

        for img in self.svg_images.values():
            images_map['word/' + img.fname] = partial(get_svg_data, img)

    def get_data(self, item: Manifest.Item) -> bytes:
        try:
            data = item.data
            assert isinstance(data, bytes)  # read_image() replaces anything identify() cannot handle with a PNG
            return data
        finally:
            item.unload_data_from_memory()

    def create_cover_markup(self, img: Image, preserve_aspect_ratio: bool, width: float, height: float) -> etree._Element:
        self.count += 1
        makeelement, namespaces = (
            self.document_relationships.namespace.makeelement,
            self.document_relationships.namespace.namespaces,
        )
        if preserve_aspect_ratio:
            if img.width >= img.height:
                ar = img.height / img.width
                height = ar * width
            else:
                ar = img.width / img.height
                width = ar * height

        root = etree.Element('root', nsmap=namespaces)
        ans = makeelement(root, 'w:drawing', append=False)
        parent = makeelement(ans, 'wp:anchor', append=True, **{'dist' + edge: '0' for edge in 'LRTB'})
        (
            parent.set('simplePos', '0'),
            parent.set('relativeHeight', '1'),
            parent.set('behindDoc', '0'),
            parent.set('locked', '0'),
        )
        parent.set('layoutInCell', '1'), parent.set('allowOverlap', '1')
        makeelement(parent, 'wp:simplePos', x='0', y='0')
        makeelement(makeelement(parent, 'wp:positionH', relativeFrom='page'), 'wp:align').text = 'center'
        makeelement(makeelement(parent, 'wp:positionV', relativeFrom='page'), 'wp:align').text = 'center'
        width, height = map(pt_to_emu, (width, height))
        makeelement(parent, 'wp:extent', cx=str(width), cy=str(height))
        makeelement(parent, 'wp:effectExtent', l='0', r='0', t='0', b='0')
        makeelement(parent, 'wp:wrapTopAndBottom')
        self.create_docx_image_markup(parent, 'cover.jpg', _('Cover'), img.rid, width, height)
        return ans

    def write_cover_block(self, body: etree._Element, cover_image: etree._Element) -> None:
        makeelement, namespaces = (
            self.document_relationships.namespace.makeelement,
            self.document_relationships.namespace.namespaces,
        )
        pbb = body[0].xpath('//*[local-name()="pageBreakBefore"]')[0]
        pbb.set('{{{}}}val'.format(namespaces['w']), 'on')
        p = makeelement(body, 'w:p', append=False)
        body.insert(0, p)
        r = makeelement(p, 'w:r')
        r.append(cover_image)
