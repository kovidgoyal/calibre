#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from itertools import izip, groupby
from operator import itemgetter
from collections import Counter
from future_builtins import map

from calibre.ebooks.pdf.render.common import (Array, String, Stream,
    Dictionary, Name)

STANDARD_FONTS = {
    'Times-Roman', 'Helvetica', 'Courier', 'Symbol', 'Times-Bold',
    'Helvetica-Bold', 'Courier-Bold', 'ZapfDingbats', 'Times-Italic',
    'Helvetica-Oblique', 'Courier-Oblique', 'Times-BoldItalic',
    'Helvetica-BoldOblique', 'Courier-BoldOblique', }

'''
Notes
=======

We must use Type 0 CID keyed fonts to represent unicode text.

For TrueType
--------------

The mapping from the text strings to glyph ids is defined by two things:

    The /Encoding key of the Type-0 font dictionary
    The /CIDToGIDMap key of the descendant font dictionary (for TrueType fonts)

We set /Encoding to /Identity-H and /CIDToGIDMap to /Identity.  This means that
text strings are interpreted as a sequence of two-byte numbers, high order byte
first. Each number gets mapped to a glyph id equal to itself by the
/CIDToGIDMap.

'''

class FontStream(Stream):

    def __init__(self, is_otf):
        Stream.__init__(self)
        self.is_otf = is_otf

    def add_extra_keys(self, d):
        d['Length1'] = d['DL']
        if self.is_otf:
            d['Subtype'] = Name('OpenType')

class Font(object):

    def __init__(self, metrics, num, objects):
        self.metrics = metrics
        self.subset_tag = bytes(re.sub('.', lambda m: chr(int(m.group())+ord('A')),
                                  oct(num))).rjust(6, b'A').decode('ascii')
        self.font_stream = FontStream(metrics.is_otf)
        self.font_descriptor = Dictionary({
            'Type': Name('FontDescriptor'),
            'FontName': Name(metrics.postscript_name),
            'Flags': 0b100, # Symbolic font
            'FontBBox': Array(metrics.pdf_bbox),
            'ItalicAngle': metrics.post.italic_angle,
            'Ascent': metrics.pdf_ascent,
            'Descent': metrics.pdf_descent,
            'CapHeight': metrics.pdf_capheight,
            'AvgWidth': metrics.pdf_avg_width,
            'StemV': metrics.pdf_stemv,
        })
        self.descendant_font = Dictionary({
            'Type':Name('Font'),
            'Subtype':Name('CIDFontType' + ('0' if metrics.is_otf else '2')),
            'BaseFont': self.font_descriptor['FontName'],
            'FontDescriptor':objects.add(self.font_descriptor),
            'CIDSystemInfo':Dictionary({
                'Registry':String('Adobe'),
                'Ordering':String('Identity'),
                'Supplement':0,
            }),
        })
        if not metrics.is_otf:
            self.descendant_font['CIDToGIDMap'] = Name('Identity')

        self.font_dict = Dictionary({
            'Type':Name('Font'),
            'Subtype':Name('Type0'),
            'Encoding':Name('Identity-H'),
            'BaseFont':self.descendant_font['BaseFont'],
            'DescendantFonts':Array([objects.add(self.descendant_font)]),
        })

        self.used_glyphs = set()

    def embed(self, objects):
        # TODO: Subsetting and OpenType
        self.font_descriptor['FontFile2'] = objects.add(self.font_stream)
        self.write_widths(objects)
        self.metrics.os2.zero_fstype()
        self.metrics.sfnt(self.font_stream)

    def write_widths(self, objects):
        glyphs = sorted(self.used_glyphs|{0})
        widths = {g:self.metrics.pdf_scale(w) for g, w in izip(glyphs,
                                        self.metrics.glyph_widths(glyphs))}
        counter = Counter()
        for g, w in widths.iteritems():
            counter[w] += 1
        most_common = counter.most_common(1)[0][0]
        self.descendant_font['DW'] = most_common
        widths = {g:w for g, w in widths.iteritems() if w != most_common}

        groups = Array()
        for k, g in groupby(enumerate(widths.iterkeys()), lambda (i,x):i-x):
            group = list(map(itemgetter(1), g))
            gwidths = [widths[g] for g in group]
            if len(set(gwidths)) == 1 and len(group) > 1:
                w = (min(group), max(group), gwidths[0])
            else:
                w = (min(group), Array(gwidths))
            groups.extend(w)
        self.descendant_font['W'] = objects.add(groups)


class FontManager(object):

    def __init__(self, objects):
        self.objects = objects
        self.std_map = {}
        self.font_map = {}
        self.fonts = []

    def add_font(self, font_metrics, glyph_ids):
        if font_metrics not in self.font_map:
            self.fonts.append(Font(font_metrics, len(self.fonts),
                                   self.objects))
            d = self.objects.add(self.fonts[-1].font_dict)
            self.font_map[font_metrics] = (d, self.fonts[-1])

        fontref, font = self.font_map[font_metrics]
        font.used_glyphs |= glyph_ids
        return fontref

    def add_standard_font(self, name):
        if name not in STANDARD_FONTS:
            raise ValueError('%s is not a standard font'%name)
        if name not in self.std_map:
                self.std_map[name] = self.objects.add(Dictionary({
                'Type':Name('Font'),
                'Subtype':Name('Type1'),
                'BaseFont':Name(name)
            }))
        return self.std_map[name]

    def embed_fonts(self):
        for font in self.fonts:
            font.embed(self.objects)

