#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.utils.magick import Image, create_canvas
from calibre.utils.img import save_cover_data_to as _save_cover_data_to, image_to_data, add_borders_to_image as abti
from calibre.utils.imghdr import identify as _identify
from calibre import fit_image


def _data_to_image(data):
    if isinstance(data, Image):
        img = data
    else:
        img = Image()
        img.load(data)
    return img


def minify_image(data, minify_to=(1200, 1600), preserve_aspect_ratio=True):
    '''
    Minify image to specified size if image is bigger than specified
    size and return minified image, otherwise, original image is
    returned.

    :param data: Image data as bytestring or Image object
    :param minify_to: A tuple (width, height) to specify target size
    :param preserve_aspect_ratio: whether preserve original aspect ratio
    '''
    img = _data_to_image(data)
    owidth, oheight = img.size
    nwidth, nheight = minify_to
    if owidth <= nwidth and oheight <= nheight:
        return img
    if preserve_aspect_ratio:
        scaled, nwidth, nheight = fit_image(owidth, oheight, nwidth, nheight)
    img.size = (nwidth, nheight)
    return img


def save_cover_data_to(data, path, bgcolor='#ffffff', resize_to=None,
        return_data=False, compression_quality=90, minify_to=None,
        grayscale=False):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Removes any transparency. If there is no transparency and no
    resize and the input and output image formats are the same, no changes are
    made.

    :param data: Image data as bytestring or Image object
    :param compression_quality: The quality of the image after compression.
        Number between 1 and 100. 1 means highest compression, 100 means no
        compression (lossless).
    :param bgcolor: The color for transparent pixels. Must be specified in hex.
    :param resize_to: A tuple (width, height) or None for no resizing
    :param minify_to: A tuple (width, height) to specify maximum target size.
    :param grayscale: If True, the image is grayscaled
    will be resized to fit into this target size. If None the value from the
    tweak is used.

    '''
    fmt = os.path.splitext(path)[1]
    if return_data:
        path = None
    if isinstance(data, Image):
        data = data.img
    return _save_cover_data_to(
        data, path, bgcolor=bgcolor, resize_to=resize_to, compression_quality=compression_quality, minify_to=minify_to, grayscale=grayscale, data_fmt=fmt)


def thumbnail(data, width=120, height=120, bgcolor='#ffffff', fmt='jpg',
              preserve_aspect_ratio=True, compression_quality=70):
    img = Image()
    img.load(data)
    owidth, oheight = img.size
    if width is None:
        width = owidth
    if height is None:
        height = oheight
    if not preserve_aspect_ratio:
        scaled = owidth > width or oheight > height
        nwidth = width
        nheight = height
    else:
        scaled, nwidth, nheight = fit_image(owidth, oheight, width, height)
    if scaled:
        img.size = (nwidth, nheight)
    canvas = create_canvas(img.size[0], img.size[1], bgcolor)
    canvas.compose(img)
    data = image_to_data(canvas.img, compression_quality=compression_quality)
    return (canvas.size[0], canvas.size[1], data)


def identify_data(data):
    '''
    Identify the image in data. Returns a 3-tuple
    (width, height, format)
    or raises an Exception if data is not an image.
    '''
    fmt, width, height = _identify(data)
    return width, height, fmt


def identify(path):
    '''
    Identify the image at path. Returns a 3-tuple
    (width, height, format)
    or raises an Exception.
    '''
    with lopen(path, 'rb') as f:
        fmt, width, height = _identify(f)
    return width, height, fmt


def add_borders_to_image(img_data, left=0, top=0, right=0, bottom=0,
        border_color='#ffffff', fmt='jpg'):
    img = abti(img_data, left=left, top=top, right=right, bottom=bottom, border_color=border_color)
    return image_to_data(img, fmt=fmt)
