#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from itertools import groupby
from operator import itemgetter
from collections import Counter, OrderedDict
from polyglot.builtins import iteritems, map, zip, unicode_type, codepoint_to_chr

from calibre import as_unicode
from calibre.ebooks.pdf.render.common import (Array, String, Stream,
    Dictionary, Name)
from calibre.utils.fonts.sfnt.subset import pdf_subset, UnsupportedFont, NoGlyphs
from calibre.utils.short_uuid import uuid4

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

import textwrap


class FontStream(Stream):

    def __init__(self, is_otf, compress=False):
        Stream.__init__(self, compress=compress)
        self.is_otf = is_otf

    def add_extra_keys(self, d):
        d['Length1'] = d['DL']
        if self.is_otf:
            d['Subtype'] = Name('CIDFontType0C')


def to_hex_string(c):
    ans = hex(int(c))[2:]
    if isinstance(ans, bytes):
        ans = ans.decode('ascii')
    return ans.rjust(4, '0')


class CMap(Stream):

    skeleton = textwrap.dedent('''\
        /CIDInit /ProcSet findresource begin
        12 dict begin
        begincmap
        /CMapName {name}-cmap def
        /CMapType 2 def
        /CIDSystemInfo <<
        /Registry (Adobe)
        /Ordering (UCS)
        /Supplement 0
        >> def
        1 begincodespacerange
        <0000> <FFFF>
        endcodespacerange
        {mapping}
        endcmap
        CMapName currentdict /CMap defineresource pop
        end
        end
        ''')

    def __init__(self, name, glyph_map, compress=False):
        Stream.__init__(self, compress)
        current_map = OrderedDict()
        maps = []
        for glyph_id in sorted(glyph_map):
            if len(current_map) > 99:
                maps.append(current_map)
                current_map = OrderedDict()
            val = []
            for c in glyph_map[glyph_id]:
                c = ord(c)
                val.append(to_hex_string(c))
            glyph_id = '<%s>'%to_hex_string(glyph_id)
            current_map[glyph_id] = '<%s>'%''.join(val)
        if current_map:
            maps.append(current_map)
        mapping = []
        for m in maps:
            meat = '\n'.join('%s %s'%(k, v) for k, v in iteritems(m))
            mapping.append('%d beginbfchar\n%s\nendbfchar'%(len(m), meat))
        try:
            name = name.encode('ascii').decode('ascii')
        except Exception:
            name = uuid4()
        self.write(self.skeleton.format(name=name, mapping='\n'.join(mapping)))


class Font(object):

    def __init__(self, metrics, num, objects, compress):
        self.metrics, self.compress = metrics, compress
        self.is_otf = self.metrics.is_otf
        self.subset_tag = unicode_type(
            re.sub('.', lambda m: codepoint_to_chr(int(m.group())+ord('A')), oct(num).replace('o', '')
        )).rjust(6, 'A')
        self.font_stream = FontStream(metrics.is_otf, compress=compress)
        try:
            psname = metrics.postscript_name
        except Exception:
            psname = uuid4()
        self.font_descriptor = Dictionary({
            'Type': Name('FontDescriptor'),
            'FontName': Name('%s+%s'%(self.subset_tag, psname)),
            'Flags': 0b100,  # Symbolic font
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
        if not self.is_otf:
            self.descendant_font['CIDToGIDMap'] = Name('Identity')

        self.font_dict = Dictionary({
            'Type':Name('Font'),
            'Subtype':Name('Type0'),
            'Encoding':Name('Identity-H'),
            'BaseFont':self.descendant_font['BaseFont'],
            'DescendantFonts':Array([objects.add(self.descendant_font)]),
        })

        self.used_glyphs = set()

    def embed(self, objects, debug):
        self.font_descriptor['FontFile'+('3' if self.is_otf else '2')
                             ] = objects.add(self.font_stream)
        self.write_widths(objects)
        self.write_to_unicode(objects)
        try:
            pdf_subset(self.metrics.sfnt, self.used_glyphs)
        except UnsupportedFont as e:
            debug('Subsetting of %s not supported, embedding full font. Error: %s'%(
                self.metrics.names.get('full_name', 'Unknown'), as_unicode(e)))
        except NoGlyphs:
            if self.used_glyphs:
                debug(
                    'Subsetting of %s failed, font appears to have no glyphs for the %d characters it is used with, some text may not be rendered in the PDF' %
                    (self.metrics.names.get('full_name', 'Unknown'), len(self.used_glyphs)))
        if self.is_otf:
            self.font_stream.write(self.metrics.sfnt['CFF '].raw)
        else:
            self.metrics.os2.zero_fstype()
            self.metrics.sfnt(self.font_stream)

    def write_to_unicode(self, objects):
        try:
            name = self.metrics.postscript_name
        except KeyError:
            name = uuid4()
        cmap = CMap(name, self.metrics.glyph_map, compress=self.compress)
        self.font_dict['ToUnicode'] = objects.add(cmap)

    def write_widths(self, objects):
        glyphs = sorted(self.used_glyphs|{0})
        widths = {g:self.metrics.pdf_scale(w) for g, w in zip(glyphs,
                                        self.metrics.glyph_widths(glyphs))}
        counter = Counter()
        for g, w in iteritems(widths):
            counter[w] += 1
        most_common = counter.most_common(1)[0][0]
        self.descendant_font['DW'] = most_common
        widths = {g:w for g, w in iteritems(widths) if w != most_common}

        groups = Array()
        for k, g in groupby(enumerate(widths), lambda i_x:i_x[0]-i_x[1]):
            group = list(map(itemgetter(1), g))
            gwidths = [widths[g] for g in group]
            if len(set(gwidths)) == 1 and len(group) > 1:
                w = (min(group), max(group), gwidths[0])
            else:
                w = (min(group), Array(gwidths))
            groups.extend(w)
        self.descendant_font['W'] = objects.add(groups)


class FontManager(object):

    def __init__(self, objects, compress):
        self.objects = objects
        self.compress = compress
        self.std_map = {}
        self.font_map = {}
        self.fonts = []

    def add_font(self, font_metrics, glyph_ids):
        if font_metrics not in self.font_map:
            self.fonts.append(Font(font_metrics, len(self.fonts),
                                   self.objects, self.compress))
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

    def embed_fonts(self, debug):
        for font in self.fonts:
            font.embed(self.objects, debug)
