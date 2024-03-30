#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre import fit_image


class RescaleImages:

    'Rescale all images to fit inside given screen size'

    def __init__(self, check_colorspaces=False):
        self.check_colorspaces = check_colorspaces

    def __call__(self, oeb, opts, max_size: str = 'profile'):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        self.rescale(max_size)

    def rescale(self, max_size: str = 'profile'):
        from io import BytesIO

        from PIL import Image

        is_image_collection = getattr(self.opts, 'is_image_collection', False)

        if is_image_collection:
            page_width, page_height = self.opts.dest.comic_screen_size
        else:
            page_width, page_height = self.opts.dest.width, self.opts.dest.height
            page_width -= (self.opts.margin_left + self.opts.margin_right) * self.opts.dest.dpi/72
            page_height -= (self.opts.margin_top + self.opts.margin_bottom) * self.opts.dest.dpi/72

        no_scale_size = 99999999999
        if max_size == 'none':
            page_width = page_height = no_scale_size
        elif max_size != 'profile':
            w, __, h = max_size.strip().lower().partition('x')
            try:
                page_width = int(w.strip())
            except Exception:
                page_width = no_scale_size
            if page_width <= 0:
                page_width = no_scale_size
            try:
                page_height = int(h.strip())
            except Exception:
                page_height = no_scale_size
            if page_height <= 0:
                page_height = no_scale_size
        for item in self.oeb.manifest:
            if item.media_type.startswith('image'):
                ext = item.media_type.split('/')[-1].upper()
                if ext == 'JPG':
                    ext = 'JPEG'
                if ext not in ('PNG', 'JPEG', 'GIF'):
                    ext = 'JPEG'

                raw = item.data
                if hasattr(raw, 'xpath') or not raw:
                    # Probably an svg image
                    continue
                try:
                    img = Image.open(BytesIO(raw))
                except Exception:
                    continue
                width, height = img.size

                try:
                    if self.check_colorspaces and img.mode == 'CMYK':
                        self.log.warn(
                            'The image %s is in the CMYK colorspace, converting it '
                            'to RGB as Adobe Digital Editions cannot display CMYK' % item.href)
                        img = img.convert('RGB')
                except Exception:
                    self.log.exception('Failed to convert image %s from CMYK to RGB' % item.href)

                scaled, new_width, new_height = fit_image(width, height, page_width, page_height)
                if scaled:
                    new_width = max(1, new_width)
                    new_height = max(1, new_height)
                    self.log('Rescaling image from %dx%d to %dx%d'%(
                        width, height, new_width, new_height), item.href)
                    try:
                        img = img.resize((new_width, new_height))
                    except Exception:
                        self.log.exception('Failed to rescale image: %s' % item.href)
                        continue
                    buf = BytesIO()
                    try:
                        img.save(buf, ext)
                    except Exception:
                        self.log.exception('Failed to rescale image: %s' % item.href)
                    else:
                        item.data = buf.getvalue()
                        item.unload_data_from_memory()
