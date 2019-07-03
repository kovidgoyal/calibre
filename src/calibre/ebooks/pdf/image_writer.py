#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.Qt import QMarginsF, QPageLayout, QPageSize, QPainter, QPdfWriter, QSize

from calibre import fit_image
from calibre.ebooks.docx.writer.container import cicero, cm, didot, inch, mm, pica
from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
from calibre.utils.img import image_from_path
from calibre.utils.podofo import get_podofo, set_metadata_implementation

# Page layout {{{


def get_page_size(opts, for_comic=False):
    use_profile = opts.use_profile_size and opts.output_profile.short_name != 'default' and opts.output_profile.width <= 9999
    if use_profile:
        w = (opts.output_profile.comic_screen_size[0] if for_comic else
                opts.output_profile.width)
        h = (opts.output_profile.comic_screen_size[1] if for_comic else
                opts.output_profile.height)
        dpi = opts.output_profile.dpi
        factor = 72.0 / dpi
        page_size = QPageSize(QSize(factor * w, factor * h), matchPolicy=QPageSize.ExactMatch)
    else:
        page_size = None
        if opts.custom_size is not None:
            width, sep, height = opts.custom_size.partition('x')
            if height:
                try:
                    width = float(width.replace(',', '.'))
                    height = float(height.replace(',', '.'))
                except:
                    pass
                else:
                    if opts.unit == 'devicepixel':
                        factor = 72.0 / opts.output_profile.dpi
                    else:
                        factor = {
                            'point':1.0, 'inch':inch, 'cicero':cicero,
                            'didot':didot, 'pica':pica, 'millimeter':mm,
                            'centimeter':cm
                        }[opts.unit]
                    page_size = QPageSize(QSize(factor*width, factor*height), matchPolicy=QPageSize.ExactMatch)
        if page_size is None:
            page_size = QPageSize(getattr(QPageSize, opts.paper_size.capitalize()))
    return page_size


def get_page_layout(opts, for_comic=False):
    page_size = get_page_size(opts, for_comic)

    def m(which):
        return max(0, getattr(opts, 'pdf_page_margin_' + which) or getattr(opts, 'margin_' + which))

    margins = QMarginsF(m('left'), m('top'), m('right'), m('bottom'))
    ans = QPageLayout(page_size, QPageLayout.Portrait, margins)
    return ans
# }}}


def draw_image_page(painter, img, preserve_aspect_ratio=True):
    page_rect = painter.viewport()
    if preserve_aspect_ratio:
        aspect_ratio = float(img.width())/img.height()
        nw, nh = page_rect.width(), page_rect.height()
        if aspect_ratio > 1:
            nh = int(page_rect.width()/aspect_ratio)
        else:  # Width is smaller than height
            nw = page_rect.height()*aspect_ratio
        __, nnw, nnh = fit_image(nw, nh, page_rect.width(),
                page_rect.height())
        dx = int((page_rect.width() - nnw)/2.)
        dy = int((page_rect.height() - nnh)/2.)
        page_rect.translate(dx, dy)
        page_rect.setHeight(nnh)
        page_rect.setWidth(nnw)
    painter.drawImage(page_rect, img)


def convert(images, output_path, opts, pdf_metadata):
    writer = QPdfWriter(output_path)
    writer.setCreator(pdf_metadata.author)
    writer.setTitle(pdf_metadata.title)
    writer.setPageLayout(get_page_layout(opts, for_comic=True))
    painter = QPainter()
    painter.begin(writer)
    try:
        for i, path in enumerate(images):
            if i > 0:
                writer.newPage()
            img = image_from_path(path)
            draw_image_page(painter, img)
    finally:
        painter.end()
    if pdf_metadata.mi:
        podofo = get_podofo()
        pdf_doc = podofo.PDFDoc()
        with open(output_path, 'r+b') as f:
            raw = f.read()
            pdf_doc.load(raw)
            xmp_packet = metadata_to_xmp_packet(pdf_metadata.mi)
            set_metadata_implementation(
                pdf_doc, pdf_metadata.title, pdf_metadata.mi.authors,
                pdf_metadata.mi.book_producer, pdf_metadata.tags, xmp_packet)
            raw = pdf_doc.write()
            f.seek(0), f.truncate()
            f.write(raw)
