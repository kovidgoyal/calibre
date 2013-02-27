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

_type_map = dict([(getattr(_magick, x), x) for x in dir(_magick) if
    x.endswith('Type')])

# Font metrics {{{
class Rect(object):

    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom

    def __str__(self):
        return '(%s, %s) -- (%s, %s)'%(self.left, self.top, self.right,
                self.bottom)

class FontMetrics(object):

    def __init__(self, ret):
        self._attrs = []
        for i, x in enumerate(('char_width', 'char_height', 'ascender',
            'descender', 'text_width', 'text_height',
            'max_horizontal_advance')):
            setattr(self, x, ret[i])
            self._attrs.append(x)
        self.bounding_box = Rect(ret[7], ret[8], ret[9], ret[10])
        self.x, self.y = ret[11], ret[12]
        self._attrs.extend(['bounding_box', 'x', 'y'])
        self._attrs = tuple(self._attrs)

    def __str__(self):
        return '''FontMetrics:
            char_width: %s
            char_height: %s
            ascender: %s
            descender: %s
            text_width: %s
            text_height: %s
            max_horizontal_advance: %s
            bounding_box: %s
            x: %s
            y: %s
            '''%tuple([getattr(self, x) for x in self._attrs])

# }}}

class PixelWand(_magick.PixelWand): # {{{
    pass

# }}}

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

    @dynamic_property
    def font_size(self):
        def fget(self):
            return self.font_size_
        def fset(self, val):
            self.font_size_ = float(val)
        return property(fget=fget, fset=fset, doc=_magick.DrawingWand.font_size_.__doc__)

    @dynamic_property
    def stroke_color(self):
        def fget(self):
            return self.stroke_color_.color
        def fset(self, val):
            col = PixelWand()
            col.color = unicode(val)
            self.stroke_color_ = col
        return property(fget=fget, fset=fset, doc=_magick.DrawingWand.font_size_.__doc__)

    @dynamic_property
    def fill_color(self):
        def fget(self):
            return self.fill_color_.color
        def fset(self, val):
            col = PixelWand()
            col.color = unicode(val)
            self.fill_color_ = col
        return property(fget=fget, fset=fset, doc=_magick.DrawingWand.font_size_.__doc__)

# }}}

class Image(_magick.Image): # {{{

    @property
    def clone(self):
        ans = Image()
        ans.copy(self)
        return ans

    def load(self, data):
        data = bytes(data)
        if not data:
            raise ValueError('Cannot open image from empty data string')
        return _magick.Image.load(self, data)

    def open(self, path_or_file):
        if not hasattr(path_or_file, 'read') and \
            path_or_file.lower().endswith('.wmf'):
            # Special handling for WMF files as ImageMagick seems
            # to hang while reading them from a blob on linux
            if isinstance(path_or_file, unicode):
                path_or_file = path_or_file.encode(filesystem_encoding)
            return _magick.Image.read(self, path_or_file)
        data = path_or_file
        if hasattr(data, 'read'):
            data = data.read()
        else:
            data = open(data, 'rb').read()
        if not data:
            raise ValueError('%r is an empty file'%path_or_file)
        self.load(data)

    @dynamic_property
    def format(self):
        def fget(self):
            return self.format_.decode('utf-8', 'ignore').lower()
        def fset(self, val):
            self.format_ = str(val)
        return property(fget=fget, fset=fset, doc=_magick.Image.format_.__doc__)

    @dynamic_property
    def type(self):
        def fget(self):
            return _type_map[self.type_]
        def fset(self, val):
            val = getattr(_magick, str(val))
            self.type_ = val
        return property(fget=fget, fset=fset, doc=_magick.Image.type_.__doc__)


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

        with lopen(path, 'wb') as f:
            f.write(self.export(format))

    def compose(self, img, left=0, top=0, operation='OverCompositeOp'):
        op = getattr(_magick, operation)
        bounds = self.size
        if left < 0 or top < 0 or left >= bounds[0] or top >= bounds[1]:
            raise ValueError('left and/or top out of bounds')
        _magick.Image.compose(self, img, int(left), int(top), op)

    def compare(self, img, metric='RootMeanSquaredErrorMetric'):
        return _magick.Image.compare(self, img, getattr(_magick, metric))

    def font_metrics(self, drawing_wand, text):
        if isinstance(text, unicode):
            text = text.encode('UTF-8')
        return FontMetrics(_magick.Image.font_metrics(self, drawing_wand, text))

    def annotate(self, drawing_wand, x, y, angle, text):
        if isinstance(text, unicode):
            text = text.encode('UTF-8')
        return _magick.Image.annotate(self, drawing_wand, x, y, angle, text)

    def distort(self, method, arguments, bestfit):
        method = getattr(_magick, method)
        arguments = [float(x) for x in arguments]
        _magick.Image.distort(self, method, arguments, bestfit)

    def rotate(self, background_pixel_wand, degrees):
        _magick.Image.rotate(self, background_pixel_wand, float(degrees))

    def quantize(self, number_colors, colorspace='RGBColorspace', treedepth=0, dither=True,
            measure_error=False):
        colorspace = getattr(_magick, colorspace)
        _magick.Image.quantize(self, number_colors, colorspace, treedepth, dither,
                measure_error)

# }}}

def create_canvas(width, height, bgcolor='#ffffff'):
    canvas = Image()
    canvas.create_canvas(int(width), int(height), str(bgcolor))
    return canvas
