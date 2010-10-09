#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import cStringIO

from calibre import fit_image

class RescaleImages(object):
    'Rescale all images to fit inside given screen size'

    def __call__(self, oeb, opts):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        from calibre.gui2 import is_ok_to_use_qt
        self.rescale(qt=is_ok_to_use_qt())

    def rescale(self, qt=True):
        from PyQt4.Qt import QImage, Qt
        from calibre.gui2 import pixmap_to_data
        try:
            from PIL import Image as PILImage
            PILImage
        except ImportError:
            import Image as PILImage

        is_image_collection = getattr(self.opts, 'is_image_collection', False)

        if is_image_collection:
            page_width, page_height = self.opts.dest.comic_screen_size
        else:
            page_width, page_height = self.opts.dest.width, self.opts.dest.height
            page_width -= (self.opts.margin_left + self.opts.margin_right) * self.opts.dest.dpi/72.
            page_height -= (self.opts.margin_top + self.opts.margin_bottom) * self.opts.dest.dpi/72.
        for item in self.oeb.manifest:
            if item.media_type.startswith('image'):
                ext = item.media_type.split('/')[-1].upper()
                if ext == 'JPG': ext = 'JPEG'
                if ext not in ('PNG', 'JPEG', 'GIF'):
                    ext = 'JPEG'

                raw = item.data
                if not raw: continue
                if qt:
                    img = QImage(10, 10, QImage.Format_ARGB32_Premultiplied)
                    try:
                        if not img.loadFromData(raw): continue
                    except:
                        continue
                    width, height = img.width(), img.height()
                else:
                    f = cStringIO.StringIO(raw)
                    try:
                        im = PILImage.open(f)
                    except IOError:
                        continue
                    width, height = im.size



                scaled, new_width, new_height = fit_image(width, height,
                        page_width, page_height)
                if scaled:
                    data = None
                    self.log('Rescaling image from %dx%d to %dx%d'%(
                        width, height, new_width, new_height), item.href)
                    if qt:
                        img = img.scaled(new_width, new_height,
                                Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        data = pixmap_to_data(img, format=ext)
                    else:
                        try:
                            im = im.resize((int(new_width), int(new_height)), PILImage.ANTIALIAS)
                            of = cStringIO.StringIO()
                            im.convert('RGB').save(of, ext)
                            data = of.getvalue()
                        except:
                            self.log.exception('Failed to rescale image')
                    if data is not None:
                        item.data = data
                        item.unload_data_from_memory()



