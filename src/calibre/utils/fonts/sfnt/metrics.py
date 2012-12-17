#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from future_builtins import map

class FontMetrics(object):

    '''
    Get various metrics for the specified sfnt. All the metrics are returned in
    units of pixels. To calculate a metric you have to specify the font size
    (in pixels) and the horizontal stretch factor (between 0.0 and 1.0).
    '''

    def __init__(self, sfnt):
        self.sfnt = sfnt

        hhea = self.sfnt[b'hhea']
        hhea.read_data(self.sfnt[b'hmtx'])
        self.ascent = hhea.ascender
        self.descent = hhea.descender
        self._advance_widths = hhea.advance_widths
        self.cmap = self.sfnt[b'cmap']
        self.head = self.sfnt[b'head']
        self.units_per_em = self.head.units_per_em
        self.os2 = self.sfnt[b'OS/2']
        self.os2.read_data()
        self.post = self.sfnt[b'post']
        self.post.read_data()

    def underline_thickness(self, pixel_size=12.0):
        'Thickness for lines (in pixels) at the specified size'
        yscale = pixel_size / self.units_per_em
        return self.post.underline_thickness * yscale

    def underline_position(self, pixel_size=12.0):
        yscale = pixel_size / self.units_per_em
        return self.post.underline_position * yscale

    def overline_position(self, pixel_size=12.0):
        yscale = pixel_size / self.units_per_em
        return (self.ascent + 2) * yscale

    def strikeout_size(self, pixel_size=12.0):
        'The width of the strikeout line, in pixels'
        yscale = pixel_size / self.units_per_em
        return yscale * self.os2.strikeout_size

    def strikeout_position(self, pixel_size=12.0):
        'The displacement from the baseline to top of the strikeout line, in pixels'
        yscale = pixel_size / self.units_per_em
        return yscale * self.os2.strikeout_position

    def advance_widths(self, string, pixel_size=12.0, stretch=1.0):
        '''
        Return the advance widths (in pixels) for all glyphs corresponding to
        the characters in string at the specified pixel_size and stretch factor.
        '''
        if not isinstance(string, type(u'')):
            raise ValueError('Must supply a unicode object')
        chars = tuple(map(ord, string))
        cmap = self.cmap.get_character_map(chars)
        glyph_ids = (cmap[c] for c in chars)
        last = len(self._advance_widths)
        pixel_size_x = stretch * pixel_size
        xscale = pixel_size_x / self.units_per_em
        return tuple(self._advance_widths[i if i < last else -1]*xscale for i in glyph_ids)

    def width(self, string, pixel_size=12.0, stretch=1.0):
        'The width of the string at the specified pixel size and stretch, in pixels'
        return sum(self.advance_widths(string, pixel_size, stretch))

if __name__ == '__main__':
    import sys
    from calibre.utils.fonts.sfnt.container import Sfnt
    with open(sys.argv[-2], 'rb') as f:
        raw = f.read()
    sfnt = Sfnt(raw)
    m = FontMetrics(sfnt)
    print (m.advance_widths(sys.argv[-1]))

