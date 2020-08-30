#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import QMarginsF, QPageLayout, QPageSize, QSizeF

from calibre.constants import filesystem_encoding
from calibre.ebooks.pdf.render.common import cicero, cm, didot, inch, mm, pica
from calibre.ebooks.pdf.render.serialize import PDFStream
from calibre.utils.img import image_and_format_from_data
from calibre.utils.imghdr import identify
from polyglot.builtins import as_unicode


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


def parse_pdf_page_size(spec, unit='inch', dpi=72.0):
    width, sep, height = spec.lower().partition('x')
    if height:
        try:
            width = float(width.replace(',', '.'))
            height = float(height.replace(',', '.'))
        except Exception:
            pass
        else:
            if unit == 'devicepixel':
                factor = 72.0 / dpi
            else:
                factor = {
                    'point':1.0, 'inch':inch, 'cicero':cicero,
                    'didot':didot, 'pica':pica, 'millimeter':mm,
                    'centimeter':cm
                }.get(unit, 1.0)
            return QPageSize(QSizeF(factor*width, factor*height), QPageSize.Point, matchPolicy=QPageSize.ExactMatch)


def get_page_size(opts, for_comic=False):
    use_profile = opts.use_profile_size and opts.output_profile.short_name != 'default' and opts.output_profile.width <= 9999
    if use_profile:
        w = (opts.output_profile.comic_screen_size[0] if for_comic else
                opts.output_profile.width)
        h = (opts.output_profile.comic_screen_size[1] if for_comic else
                opts.output_profile.height)
        dpi = opts.output_profile.dpi
        factor = 72.0 / dpi
        page_size = QPageSize(QSizeF(factor * w, factor * h), QPageSize.Point, matchPolicy=QPageSize.ExactMatch)
    else:
        page_size = None
        if opts.custom_size is not None:
            page_size = parse_pdf_page_size(opts.custom_size, opts.unit, opts.output_profile.dpi)
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


class Image(object):  # {{{

    def __init__(self, path_or_bytes):
        if not isinstance(path_or_bytes, bytes):
            with open(path_or_bytes, 'rb') as f:
                path_or_bytes = f.read()
        self.img_data = path_or_bytes
        fmt, width, height = identify(path_or_bytes)
        if width > 0 and height > 0 and fmt == 'jpeg':
            self.fmt = fmt
            self.width, self.height = width, height
            self.cache_key = None
        else:
            self.img, self.fmt = image_and_format_from_data(path_or_bytes)
            self.width, self.height = self.img.width(), self.img.height()
            self.cache_key = self.img.cacheKey()
# }}}


def draw_image_page(writer, img, preserve_aspect_ratio=True):
    if img.fmt == 'jpeg':
        ref = writer.add_jpeg_image(img.img_data, img.width, img.height, img.cache_key)
    else:
        ref = writer.add_image(img.img, img.cache_key)
    page_size = tuple(writer.page_size)
    scaling = list(writer.page_size)
    translation = [0, 0]
    img_ar = img.width / img.height
    page_ar = page_size[0]/page_size[1]
    if preserve_aspect_ratio and page_ar != img_ar:
        if page_ar > img_ar:
            scaling[0] = img_ar * page_size[1]
            translation[0] = (page_size[0] - scaling[0]) / 2
        else:
            scaling[1] = page_size[0] / img_ar
            translation[1] = (page_size[1] - scaling[1]) / 2
    writer.draw_image_with_transform(ref, translation=translation, scaling=scaling)


def convert(images, output_path, opts, metadata, report_progress):
    with open(output_path, 'wb') as buf:
        page_layout = get_page_layout(opts, for_comic=True)
        page_size = page_layout.fullRectPoints().size()
        writer = PDFStream(buf, (page_size.width(), page_size.height()), compress=True)
        writer.apply_fill(color=(1, 1, 1))
        pdf_metadata = PDFMetadata(metadata)
        writer.set_metadata(pdf_metadata.title, pdf_metadata.author, pdf_metadata.tags, pdf_metadata.mi)
        for i, path in enumerate(images):
            img = Image(as_unicode(path, filesystem_encoding))
            draw_image_page(writer, img)
            writer.end_page()
            report_progress((i + 1) / len(images), _('Rendered {0} of {1} pages').format(i + 1, len(images)))
        writer.end()
