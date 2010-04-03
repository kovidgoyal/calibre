#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

def _get_line(draw, font, tokens, line_width):
    line, rest = tokens, []
    while True:
        width, height = draw.textsize(' '.join(line), font=font)
        if width < line_width:
            return line, rest
        rest = line[-1:] + rest
        line = line[:-1]

def draw_centered_line(img, draw, font, line, top):
    width, height = draw.textsize(line, font=font)
    left = max(int((img.size[0] - width)/2.), 0)
    draw.text((left, top), line, fill=(0,0,0), font=font)
    return top + height

def draw_centered_text(img, draw, font, text, top, margin=10, ysep=5):
    img_width, img_height = img.size
    tokens = text.split(' ')
    while tokens:
        line, tokens = _get_line(draw, font, tokens, img_width-2*margin)
        bottom = draw_centered_line(img, draw, font, ' '.join(line), top)
        top = bottom + ysep
    return top - ysep


