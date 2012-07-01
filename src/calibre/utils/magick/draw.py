#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.utils.magick import Image, DrawingWand, create_canvas
from calibre.constants import __appname__, __version__
from calibre.utils.config import tweaks
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

def normalize_format_name(fmt):
    fmt = fmt.lower()
    if fmt == 'jpeg':
        fmt = 'jpg'
    return fmt

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
    changed = False
    img = _data_to_image(data)
    orig_fmt = normalize_format_name(img.format)
    fmt = os.path.splitext(path)[1]
    fmt = normalize_format_name(fmt[1:])

    if grayscale:
       img.type = "GrayscaleType"
       changed = True

    if resize_to is not None:
        img.size = (resize_to[0], resize_to[1])
        changed = True
    owidth, oheight = img.size
    nwidth, nheight = tweaks['maximum_cover_size'] if minify_to is None else minify_to
    scaled, nwidth, nheight = fit_image(owidth, oheight, nwidth, nheight)
    if scaled:
        img.size = (nwidth, nheight)
        changed = True
    if img.has_transparent_pixels():
        canvas = create_canvas(img.size[0], img.size[1], bgcolor)
        canvas.compose(img)
        img = canvas
        changed = True

    if not changed:
        changed = fmt != orig_fmt

    ret = None
    if return_data:
        ret = data
        if changed or isinstance(ret, Image):
            if hasattr(img, 'set_compression_quality') and fmt == 'jpg':
                img.set_compression_quality(compression_quality)
            ret = img.export(fmt)
    else:
        if changed or isinstance(ret, Image):
            if hasattr(img, 'set_compression_quality') and fmt == 'jpg':
                img.set_compression_quality(compression_quality)
            img.save(path)
        else:
            with lopen(path, 'wb') as f:
                f.write(data)
    return ret

def thumbnail(data, width=120, height=120, bgcolor='#ffffff', fmt='jpg',
              preserve_aspect_ratio=True, compression_quality=70):
    img = Image()
    img.load(data)
    owidth, oheight = img.size
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
    if fmt == 'jpg':
        canvas.set_compression_quality(compression_quality)
    return (canvas.size[0], canvas.size[1], canvas.export(fmt))

def identify_data(data):
    '''
    Identify the image in data. Returns a 3-tuple
    (width, height, format)
    or raises an Exception if data is not an image.
    '''
    img = Image()
    if hasattr(img, 'identify'):
        img.identify(data)
    else:
        img.load(data)
    width, height = img.size
    fmt = img.format
    return (width, height, fmt)

def identify(path):
    '''
    Identify the image at path. Returns a 3-tuple
    (width, height, format)
    or raises an Exception.
    '''
    data = open(path, 'rb').read()
    return identify_data(data)

def add_borders_to_image(img_data, left=0, top=0, right=0, bottom=0,
        border_color='#ffffff', fmt='jpg'):
    img = Image()
    img.load(img_data)
    lwidth, lheight = img.size
    canvas = create_canvas(lwidth+left+right, lheight+top+bottom,
                border_color)
    canvas.compose(img, left, top)
    return canvas.export(fmt)

def create_text_wand(font_size, font_path=None):
    if font_path is None:
        font_path = tweaks['generate_cover_title_font']
        if font_path is None:
            font_path = P('fonts/liberation/LiberationSerif-Bold.ttf')
    ans = DrawingWand()
    ans.font = font_path
    ans.font_size = font_size
    ans.gravity = 'CenterGravity'
    ans.text_alias = True
    return ans

def create_text_arc(text, font_size, font=None, bgcolor='#ffffff'):
    if isinstance(text, unicode):
        text = text.encode('utf-8')

    canvas = create_canvas(300, 300, bgcolor)

    tw = create_text_wand(font_size, font_path=font)
    m = canvas.font_metrics(tw, text)
    canvas = create_canvas(int(m.text_width)+20, int(m.text_height*3.5), bgcolor)
    canvas.annotate(tw, 0, 0, 0, text)
    canvas.distort("ArcDistortion", [120], True)
    canvas.trim(0)
    return canvas

def _get_line(img, dw, tokens, line_width):
    line, rest = tokens, []
    while True:
        m = img.font_metrics(dw, ' '.join(line))
        width, height = m.text_width, m.text_height
        if width < line_width:
            return line, rest
        rest = line[-1:] + rest
        line = line[:-1]

def annotate_img(img, dw, left, top, rotate, text,
        translate_from_top_left=True):
    if isinstance(text, unicode):
        text = text.encode('utf-8')
    if translate_from_top_left:
        m = img.font_metrics(dw, text)
        img_width, img_height = img.size
        left = left - img_width/2. + m.text_width/2.
        top  = top - img_height/2. + m.text_height/2.
    img.annotate(dw, left, top, rotate, text)

def draw_centered_line(img, dw, line, top):
    m = img.font_metrics(dw, line)
    width, height = m.text_width, m.text_height
    img_width = img.size[0]
    left = max(int((img_width - width)/2.), 0)
    annotate_img(img, dw, left, top, 0, line)
    return top + height

def draw_centered_text(img, dw, text, top, margin=10):
    img_width = img.size[0]
    tokens = text.split(' ')
    while tokens:
        line, tokens = _get_line(img, dw, tokens, img_width-2*margin)
        if not line:
            # Could not fit the first token on the line
            line = tokens[:1]
            tokens = tokens[1:]
        bottom = draw_centered_line(img, dw, ' '.join(line), top)
        top = bottom
    return top

class TextLine(object):

    def __init__(self, text, font_size, bottom_margin=30, font_path=None):
        self.text, self.font_size, = text, font_size
        self.bottom_margin = bottom_margin
        self.font_path = font_path

    def __repr__(self):
        return u'TextLine:%r:%f'%(self.text, self.font_size)


def create_cover_page(top_lines, logo_path, width=590, height=750,
        bgcolor='#ffffff', output_format='jpg', texture_data=None,
        texture_opacity=1.0):
    '''
    Create the standard calibre cover page and return it as a byte string in
    the specified output_format.
    '''
    canvas = create_canvas(width, height, bgcolor)
    if texture_data and hasattr(canvas, 'texture'):
        texture = Image()
        texture.load(texture_data)
        texture.set_opacity(texture_opacity)
        canvas.texture(texture)

    bottom = 10
    for line in top_lines:
        twand = create_text_wand(line.font_size, font_path=line.font_path)
        bottom = draw_centered_text(canvas, twand, line.text, bottom)
        bottom += line.bottom_margin
    bottom -= top_lines[-1].bottom_margin

    foot_font = tweaks['generate_cover_foot_font']
    if not foot_font:
        foot_font = P('fonts/liberation/LiberationMono-Regular.ttf')
    vanity = create_text_arc(__appname__ + ' ' + __version__, 24,
            font=foot_font, bgcolor='#00000000')
    lwidth, lheight = vanity.size
    left = int(max(0, (width - lwidth)/2.))
    top  = height - lheight - 10
    canvas.compose(vanity, left, top)

    available = (width, int(top - bottom)-20)
    if available[1] > 40:
        logo = Image()
        logo.open(logo_path)
        lwidth, lheight = logo.size
        scaled, lwidth, lheight = fit_image(lwidth, lheight, *available)
        if scaled:
            logo.size = (lwidth, lheight)
        left = int(max(0, (width - lwidth)/2.))
        top  = bottom+10
        extra = int((available[1] - lheight)/2.0)
        if extra > 0:
            top += extra
        canvas.compose(logo, left, top)

    return canvas.export(output_format)

