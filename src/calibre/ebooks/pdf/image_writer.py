#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from io import BytesIO

from PyQt5.Qt import QMarginsF, QPageLayout, QPageSize, QSize

from calibre.ebooks.pdf.render.common import cicero, cm, didot, inch, mm, pica
from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet
from calibre.ebooks.pdf.render.serialize import PDFStream
from calibre.utils.img import image_from_path
from calibre.utils.podofo import get_podofo, set_metadata_implementation


class PDFMetadata(object):  # {{{

    def __init__(self, mi=None):
        from calibre import force_unicode
        from calibre.ebooks.metadata import authors_to_string
        self.title = _('Unknown')
        self.author = _('Unknown')
        self.tags = ''
        self.mi = mi

        if mi is not None:
            if mi.title:
                self.title = mi.title
            if mi.authors:
                self.author = authors_to_string(mi.authors)
            if mi.tags:
                self.tags = ', '.join(mi.tags)

        self.title = force_unicode(self.title)
        self.author = force_unicode(self.author)
# }}}


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
    ans.setMode(QPageLayout.FullPageMode)
    return ans
# }}}


def draw_image_page(writer, img, preserve_aspect_ratio=True):
    ref = writer.add_image(img, img.cacheKey())
    page_size = tuple(writer.page_size)
    scaling = list(writer.page_size)
    translation = [0, 0]
    img_ar = img.width() / img.height()
    page_ar = page_size[0]/page_size[1]
    if preserve_aspect_ratio and page_ar != img_ar:
        if page_ar > img_ar:
            scaling[0] = img_ar * page_size[1]
            translation[0] = (page_size[0] - scaling[0]) / 2
        else:
            scaling[1] = page_size[0] / img_ar
            translation[1] = (page_size[1] - scaling[1]) / 2
    writer.draw_image_with_transform(ref, translation=translation, scaling=scaling)


def update_metadata(pdf_doc, pdf_metadata):
    if pdf_metadata.mi:
        xmp_packet = metadata_to_xmp_packet(pdf_metadata.mi)
        set_metadata_implementation(
            pdf_doc, pdf_metadata.title, pdf_metadata.mi.authors,
            pdf_metadata.mi.book_producer, pdf_metadata.mi.tags, xmp_packet)


def convert(images, output_path, opts, metadata):
    buf = BytesIO()
    page_layout = get_page_layout(opts, for_comic=True)
    page_size = page_layout.fullRectPoints().size()
    writer = PDFStream(buf, (page_size.width(), page_size.height()), compress=True)
    writer.apply_fill(color=(1, 1, 1))
    pdf_metadata = PDFMetadata(metadata)
    for i, path in enumerate(images):
        img = image_from_path(path)
        draw_image_page(writer, img)
        writer.end_page()
    writer.end()

    podofo = get_podofo()
    pdf_doc = podofo.PDFDoc()
    pdf_doc.load(buf.getvalue())
    update_metadata(pdf_doc, pdf_metadata)
    raw = pdf_doc.write()
    with open(output_path, 'wb') as f:
        f.write(raw)
