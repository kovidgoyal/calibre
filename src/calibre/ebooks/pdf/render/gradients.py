#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from future_builtins import map

from PyQt4.Qt import (QPointF)

from calibre.ebooks.pdf.render.common import Stream

def generate_linear_gradient_shader(gradient, page_rect, is_transparent=False):
    pass

class LinearGradient(Stream):

    def __init__(self, brush, matrix, pixel_page_width, pixel_page_height):
        is_opaque = brush.isOpaque()
        gradient = brush.gradient()
        inv = matrix.inverted()[0]

        page_rect = tuple(map(inv.map, (
            QPointF(0, 0), QPointF(pixel_page_width, 0), QPointF(0, pixel_page_height),
            QPointF(pixel_page_width, pixel_page_height))))

        shader = generate_linear_gradient_shader(gradient, page_rect)
        alpha_shader = None
        if not is_opaque:
            alpha_shader = generate_linear_gradient_shader(gradient, page_rect, True)

        shader, alpha_shader


