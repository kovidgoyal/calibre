#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.constants import plugins, filesystem_encoding

_magick, _merr = plugins['magick']

if _magick is None:
    raise RuntimeError('Failed to load ImageMagick: '+_merr)

_gravity_map = dict([(getattr(_magick, x), x) for x in dir(_magick) if
    x.endswith('Gravity')])

class DrawingWand(_magick.DrawingWand): # {{{

    @dynamic_property
    def font(self):
        def fget(self):
            return self.font_.decode(filesystem_encoding, 'replace').lower()
        def fset(self, val):
            if isinstance(val, unicode):
                val = val.encode(filesystem_encoding)
            self.font_ = str(val)
        return property(fget=fget, fset=fset, doc=_magick.DrawingWand.font_.__doc__)

    @dynamic_property
    def gravity(self):
        def fget(self):
            val = self.gravity_
            return _gravity_map[val]
        def fset(self, val):
            val = getattr(_magick, str(val))
            self.gravity_ = val
        return property(fget=fget, fset=fset, doc=_magick.DrawingWand.gravity_.__doc__)

# }}}

class Image(_magick.Image): # {{{

    def load(self, data):
        return _magick.Image.load(self, bytes(data))

    def open(self, path_or_file):
        data = path_or_file
        if hasattr(data, 'read'):
            data = data.read()
        else:
            data = open(data, 'rb').read()
        self.load(data)

    @dynamic_property
    def format(self):
        def fget(self):
            return self.format_.decode('utf-8', 'ignore').lower()
        def fset(self, val):
            self.format_ = str(val)
        return property(fget=fget, fset=fset, doc=_magick.Image.format_.__doc__)


    @dynamic_property
    def size(self):
        def fget(self):
            return self.size_
        def fset(self, val):
            filter = 'CatromFilter'
            if len(val) > 2:
                filter = val[2]
            filter = int(getattr(_magick, filter))
            blur = 1.0
            if len(val) > 3:
                blur = float(val[3])
            self.size_ = (int(val[0]), int(val[1]), filter, blur)
        return property(fget=fget, fset=fset, doc=_magick.Image.size_.__doc__)


    def save(self, path, format=None):
        if format is None:
            ext = os.path.splitext(path)[1]
            if len(ext) < 2:
                raise ValueError('No format specified')
            format = ext[1:]
        format = format.upper()

        with open(path, 'wb') as f:
            f.write(self.export(format))

    def compose(self, img, left=0, top=0, operation='OverCompositeOp'):
        op = getattr(_magick, operation)
        bounds = self.size
        if left < 0 or top < 0 or left >= bounds[0] or top >= bounds[1]:
            raise ValueError('left and/or top out of bounds')
        _magick.Image.compose(self, img, int(left), int(top), op)

# }}}

def create_canvas(width, height, bgcolor):
    canvas = Image()
    canvas.create_canvas(int(width), int(height), str(bgcolor))
    return canvas
