#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre import fit_image

class RescaleImages(object):
    'Rescale all images to fit inside given screen size'

    def __call__(self, oeb, opts):
        from PyQt4.Qt import QApplication, QImage, Qt
        from calibre.gui2 import pixmap_to_data
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        page_width, page_height = opts.dest.width, opts.dest.height
        for item in oeb.manifest:
            if item.media_type.startswith('image'):
                raw = item.data
                if not raw: continue
                if QApplication.instance() is None:
                    QApplication([])

                img = QImage(10, 10, QImage.Format_ARGB32_Premultiplied)
                if not img.loadFromData(raw): continue
                width, height = img.width(), img.height()
                scaled, new_width, new_height = fit_image(width, height,
                        page_width, page_height)
                if scaled:
                    self.log('Rescaling image', item.href)
                    img = img.scaled(new_width, new_height,
                            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    item.data = pixmap_to_data(img)


