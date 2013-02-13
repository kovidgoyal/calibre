#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from future_builtins import map
from calibre.utils.fonts.utils import get_all_font_names
from calibre.utils.fonts.sfnt.container import UnsupportedFont

class FontMetrics(object):

    '''
    Get various metrics for the specified sfnt. All the metrics are returned in
    units of pixels. To calculate a metric you have to specify the font size
    (in pixels) and the horizontal stretch factor (between 0.0 and 1.0).
    '''

    def __init__(self, sfnt):
        for table in (b'head', b'hhea', b'hmtx', b'cmap', b'OS/2', b'post',
                      b'name'):
            if table not in sfnt:
                raise UnsupportedFont('This font has no %s table'%table)
        self.sfnt = sfnt

        self.head = self.sfnt[b'head']
        hhea = self.sfnt[b'hhea']
        hhea.read_data(self.sfnt[b'hmtx'])
        self.ascent = hhea.ascender
        self.descent = hhea.descender
        self.bbox = ( self.head.x_min, self.head.y_min, self.head.x_max,
                     self.head.y_max )
        self._advance_widths = hhea.advance_widths
        self.cmap = self.sfnt[b'cmap']
        self.units_per_em = self.head.units_per_em
        self.os2 = self.sfnt[b'OS/2']
        self.os2.read_data()
        self.post = self.sfnt[b'post']
        self.post.read_data()
        self.names = get_all_font_names(self.sfnt[b'name'].raw, raw_is_table=True)
        self.is_otf = 'CFF ' in self.sfnt.tables
        self._sig = hash(self.sfnt[b'name'].raw)

        # Metrics for embedding in PDF
        pdf_scale = self.pdf_scale = lambda x:int(round(x*1000./self.units_per_em))
        self.pdf_ascent, self.pdf_descent = map(pdf_scale,
                        (self.os2.typo_ascender, self.os2.typo_descender))
        self.pdf_bbox = tuple(map(pdf_scale, self.bbox))
        self.pdf_capheight = pdf_scale(getattr(self.os2, 'cap_height',
                                               self.os2.typo_ascender))
        self.pdf_avg_width = pdf_scale(self.os2.average_char_width)
        self.pdf_stemv = 50 + int((self.os2.weight_class / 65.0) ** 2)

    def __hash__(self):
        return self._sig

    @property
    def postscript_name(self):
        if 'postscript_name' in self.names:
            return self.names['postscript_name'].replace(' ', '-')
        return self.names['full_name'].replace(' ', '-')

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
        pixel_size_x = stretch * pixel_size
        xscale = pixel_size_x / self.units_per_em
        return tuple(i*xscale for i in self.glyph_widths(glyph_ids))

    def glyph_widths(self, glyph_ids):
        last = len(self._advance_widths)
        return tuple(self._advance_widths[i if i < last else -1] for i in
                     glyph_ids)

    def width(self, string, pixel_size=12.0, stretch=1.0):
        'The width of the string at the specified pixel size and stretch, in pixels'
        return sum(self.advance_widths(string, pixel_size, stretch))

if __name__ == '__main__':
    import sys
    from calibre.utils.fonts.sfnt.container import Sfnt
    with open(sys.argv[-1], 'rb') as f:
        raw = f.read()
    sfnt = Sfnt(raw)
    m = FontMetrics(sfnt)
    print ('Ascent:', m.pdf_ascent)
    print ('Descent:', m.pdf_descent)
    print ('PDF BBox:', m.pdf_bbox)
    print ('CapHeight:', m.pdf_capheight)
    print ('AvgWidth:', m.pdf_avg_width)
    print ('ItalicAngle', m.post.italic_angle)
    print ('StemV', m.pdf_stemv)

