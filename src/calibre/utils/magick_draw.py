#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from ctypes import byref, c_double

import calibre.utils.PythonMagickWand as p
from calibre.ptempfile import TemporaryFile
from calibre.constants import filesystem_encoding, __appname__, __version__

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


def get_font_metrics(image, d_wand, text):
    if isinstance(text, unicode):
        text = text.encode('utf-8')
    ret = p.MagickQueryFontMetrics(image, d_wand, text)
    return FontMetrics(ret)

# }}}

class TextLine(object):

    def __init__(self, text, font_size, bottom_margin=30, font_path=None):
        self.text, self.font_size, = text, font_size
        self.bottom_margin = bottom_margin
        self.font_path = font_path

    def __repr__(self):
        return u'TextLine:%r:%f'%(self.text, self.font_size)

def alloc_wand(name):
    ans = getattr(p, name)()
    if ans < 0:
        raise RuntimeError('Cannot create wand')
    return ans

def create_text_wand(font_size, font_path=None):
    if font_path is None:
        font_path = P('fonts/liberation/LiberationSerif-Bold.ttf')
    if isinstance(font_path, unicode):
        font_path = font_path.encode(filesystem_encoding)
    ans = alloc_wand('NewDrawingWand')
    if not p.DrawSetFont(ans, font_path):
        raise ValueError('Failed to set font to: '+font_path)
    p.DrawSetFontSize(ans, font_size)
    p.DrawSetGravity(ans, p.CenterGravity)
    p.DrawSetTextAntialias(ans, p.MagickTrue)
    return ans


def _get_line(img, dw, tokens, line_width):
    line, rest = tokens, []
    while True:
        m = get_font_metrics(img, dw, ' '.join(line))
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
        m = get_font_metrics(img, dw, text)
        img_width = p.MagickGetImageWidth(img)
        img_height = p.MagickGetImageHeight(img)
        left = left - img_width/2. + m.text_width/2.
        top  = top - img_height/2. + m.text_height/2.
    p.MagickAnnotateImage(img, dw, left, top, rotate, text)

def draw_centered_line(img, dw, line, top):
    m = get_font_metrics(img, dw, line)
    width, height = m.text_width, m.text_height
    img_width = p.MagickGetImageWidth(img)
    left = max(int((img_width - width)/2.), 0)
    annotate_img(img, dw, left, top, 0, line)
    return top + height

def draw_centered_text(img, dw, text, top, margin=10):
    img_width = p.MagickGetImageWidth(img)
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

def create_canvas(width, height, bgcolor):
    canvas = alloc_wand('NewMagickWand')
    p_wand = alloc_wand('NewPixelWand')
    p.PixelSetColor(p_wand, bgcolor)
    p.MagickNewImage(canvas, width, height, p_wand)
    p.DestroyPixelWand(p_wand)
    return canvas

def compose_image(canvas, image, left, top):
    p.MagickCompositeImage(canvas, image, p.OverCompositeOp, int(left),
            int(top))

def load_image(path):
    if isinstance(path, unicode):
        path = path.encode(filesystem_encoding)
    img = alloc_wand('NewMagickWand')
    if not p.MagickReadImage(img, path):
        severity = p.ExceptionType(0)
        msg = p.MagickGetException(img, byref(severity))
        raise IOError('Failed to read image from: %s: %s'
                %(path, msg))
    return img

def create_text_arc(text, font_size, font=None, bgcolor='white'):
    if isinstance(text, unicode):
        text = text.encode('utf-8')

    canvas = create_canvas(300, 300, bgcolor)
    tw = create_text_wand(font_size, font_path=font)
    m = get_font_metrics(canvas, tw, text)
    p.DestroyMagickWand(canvas)
    canvas = create_canvas(int(m.text_width)+20, int(m.text_height*3.5), bgcolor)
    p.MagickAnnotateImage(canvas, tw, 0, 0, 0, text)
    angle = c_double(120.)
    p.MagickDistortImage(canvas, 9, 1, byref(angle),
            p.MagickTrue)
    p.MagickTrimImage(canvas, 0)
    return canvas

def add_borders_to_image(path_to_image, left=0, top=0, right=0, bottom=0,
        border_color='white'):
    with p.ImageMagick():
        img = load_image(path_to_image)
        lwidth = p.MagickGetImageWidth(img)
        lheight = p.MagickGetImageHeight(img)
        canvas = create_canvas(lwidth+left+right, lheight+top+bottom,
                border_color)
        compose_image(canvas, img, left, top)
        p.DestroyMagickWand(img)
        p.MagickWriteImage(canvas,path_to_image)
        p.DestroyMagickWand(canvas)

def create_cover_page(top_lines, logo_path, width=590, height=750,
        bgcolor='white', output_format='jpg'):
    ans = None
    with p.ImageMagick():
        canvas = create_canvas(width, height, bgcolor)

        bottom = 10
        for line in top_lines:
            twand = create_text_wand(line.font_size, font_path=line.font_path)
            bottom = draw_centered_text(canvas, twand, line.text, bottom)
            bottom += line.bottom_margin
            p.DestroyDrawingWand(twand)
        bottom -= top_lines[-1].bottom_margin

        vanity = create_text_arc(__appname__ + ' ' + __version__, 24,
                font=P('fonts/liberation/LiberationMono-Regular.ttf'))
        lwidth = p.MagickGetImageWidth(vanity)
        lheight = p.MagickGetImageHeight(vanity)
        left = int(max(0, (width - lwidth)/2.))
        top  = height - lheight - 10
        compose_image(canvas, vanity, left, top)

        logo = load_image(logo_path)
        lwidth = p.MagickGetImageWidth(logo)
        lheight = p.MagickGetImageHeight(logo)
        left = int(max(0, (width - lwidth)/2.))
        top  = max(int((height - lheight)/2.), bottom+20)
        compose_image(canvas, logo, left, top)
        p.DestroyMagickWand(logo)

        with TemporaryFile('.'+output_format) as f:
            p.MagickWriteImage(canvas, f)
            with open(f, 'rb') as f:
                ans = f.read()
        p.DestroyMagickWand(canvas)
    return ans

def save_cover_data_to(data, path, bgcolor='white'):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Composes the image onto a blank cancas so as to
    properly convert transparent images.
    '''
    with open(path, 'wb') as f:
        f.write(data)
    with p.ImageMagick():
        img = load_image(path)
        canvas = create_canvas(p.MagickGetImageWidth(img),
                p.MagickGetImageHeight(img), bgcolor)
        compose_image(canvas, img, 0, 0)
        p.MagickWriteImage(canvas, path)
        p.DestroyMagickWand(img)
        p.DestroyMagickWand(canvas)

def test():
    import subprocess
    with TemporaryFile('.png') as f:
        data = create_cover_page(
                [TextLine('A very long title indeed, don\'t you agree?', 42),
                TextLine('Mad Max & Mixy poo', 32)], I('library.png'))
        with open(f, 'wb') as g:
            g.write(data)
        subprocess.check_call(['gwenview', f])

if __name__ == '__main__':
    test()
