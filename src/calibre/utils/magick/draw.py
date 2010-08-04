#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.utils.magick import Image, DrawingWand, create_canvas

def save_cover_data_to(data, path, bgcolor='white', resize_to=None):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Composes the image onto a blank canvas so as to
    properly convert transparent images.
    '''
    img = Image()
    img.load(data)
    if resize_to is not None:
        img.size = (resize_to[0], resize_to[1])
    canvas = create_canvas(img.size[0], img.size[1], bgcolor)
    canvas.compose(img)
    canvas.save(path)

def identify_data(data):
    '''
    Identify the image in data. Returns a 3-tuple
    (width, height, format)
    or raises an Exception if data is not an image.
    '''
    img = Image()
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

def add_borders_to_image(path_to_image, left=0, top=0, right=0, bottom=0,
        border_color='white'):
    img = Image()
    img.open(path_to_image)
    lwidth, lheight = img.size
    canvas = create_canvas(lwidth+left+right, lheight+top+bottom,
                border_color)
    canvas.compose(img, left, top)
    canvas.save(path_to_image)

def create_text_wand(font_size, font_path=None):
    if font_path is None:
        font_path = P('fonts/liberation/LiberationSerif-Bold.ttf')
    ans = DrawingWand()
    ans.font = font_path
    ans.font_size = font_size
    ans.gravity = 'CenterGravity'
    ans.text_alias = True
    return ans

def create_text_arc(text, font_size, font=None, bgcolor='white'):
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


