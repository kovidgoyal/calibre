#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os
from io import BytesIO

from calibre.utils.img import (
    image_and_format_from_data, clone_image, null_image, resize_image,
    overlay_image, rotate_image, quantize_image, remove_borders_from_image,
    add_borders_to_image, gaussian_blur_image, create_canvas, despeckle_image,
    image_to_data, flip_image, image_has_transparent_pixels, set_image_opacity,
    gaussian_sharpen_image, texture_image, grayscale_image
)
from calibre.utils.imghdr import identify


class PixelWand(object):

    def __init__(self):
        self.color = '#ffffff'


class Image(object):

    def __init__(self):
        self.read_format = None
        self.write_format = None
        self.img = null_image()

    @property
    def clone(self):
        ans = Image()
        ans.img = clone_image(self.img)
        ans.read_format = self.read_format
        ans.write_format = self.write_format
        return ans

    def open(self, path_or_file):
        if hasattr(path_or_file, 'read'):
            self.load(path_or_file.read())
        else:
            with lopen(path_or_file, 'rb') as f:
                self.load(f.read())

    def load(self, data):
        if not data:
            raise ValueError('No image data present')
        self.img, self.read_format = image_and_format_from_data(data)
    read = load

    def from_qimage(self, img):
        self.img = clone_image(img)

    def to_qimage(self):
        return clone_image(self.img)

    @property
    def type(self):
        if len(self.img.colorTable()) > 0:
            return 'PaletteType'
        return 'TrueColorType'

    @type.setter
    def type(self, t):
        if t == 'GrayscaleType':
            self.img = grayscale_image(self.img)
        elif t == 'PaletteType':
            self.img = quantize_image(self.img)

    @property
    def format(self):
        return self.write_format or self.read_format

    @format.setter
    def format(self, val):
        self.write_format = val

    @property
    def colorspace(self):
        return 'RGBColorspace'

    @colorspace.setter
    def colorspace(self, val):
        raise NotImplementedError('Changing image colorspace is not supported')

    @property
    def size(self):
        return self.img.width(), self.img.height()

    @size.setter
    def size(self, val):
        w, h = val[:2]
        self.img = resize_image(self.img, w, h)

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
        bounds = self.size
        if left < 0 or top < 0 or left >= bounds[0] or top >= bounds[1]:
            raise ValueError('left and/or top out of bounds')
        self.img = overlay_image(img.img, self.img, left=left, top=top)

    def rotate(self, background_pixel_wand, degrees):
        self.img = rotate_image(self.img, degrees)

    def quantize(self, number_colors, colorspace='RGBColorspace', treedepth=0, dither=True, measure_error=False):
        self.img = quantize_image(self.img, max_colors=number_colors, dither=dither)

    def identify(self, data):
        fmt, width, height = identify(data)
        return width, height, fmt

    def remove_border(self, fuzz=None):
        if fuzz is not None and fuzz < 0 or fuzz > 255:
            fuzz = None
        self.img = remove_borders_from_image(self.img, fuzz)
    trim = remove_border

    def add_border(self, pixel_wand, dx, dy):
        self.img = add_borders_to_image(self.img, left=dx, top=dy, right=dx, bottom=dy, border_color=pixel_wand.color)

    def blur(self, radius=-1, sigma=3.0):
        self.img = gaussian_blur_image(self.img, radius, sigma)

    def copy(self, img):
        self.img = clone_image(img.img)

    def create_canvas(self, width, height, background_pixel_wand):
        self.img = create_canvas(width, height, background_pixel_wand)

    def despeckle(self):
        self.img = despeckle_image(self.img)

    def export(self, fmt='JPEG'):
        if fmt.lower() == 'gif':
            data = image_to_data(self.img, fmt='PNG', png_compression_level=0)
            from PIL import Image
            i = Image.open(BytesIO(data))
            buf = BytesIO()
            i.save(buf, 'gif')
            return buf.getvalue()
        return image_to_data(self.img, fmt=fmt)

    def flip(self, vertical=True):
        self.img = flip_image(self.img, horizontal=not vertical, vertical=vertical)

    def has_transparent_pixels(self):
        return image_has_transparent_pixels(self.img)

    def set_border_color(self, *args, **kw):
        pass  # no-op

    def set_compression_quality(self, *args, **kw):
        pass  # no-op

    def set_opacity(self, alpha=0.5):
        self.img = set_image_opacity(self.img, alpha)

    def set_page(self, *args, **kw):
        pass  # no-op

    def sharpen(self, radius=0, sigma=3):
        self.img = gaussian_sharpen_image(self.img, radius, sigma)

    def texture(self, img):
        self.img = texture_image(self.img, img.img)

    def thumbnail(self, width, height):
        self.img = resize_image(self.img, width, height)
