#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from io import BytesIO
from collections import namedtuple

from calibre.utils.fonts.utils import get_font_names_from_ttlib_names_table, get_font_characteristics


class UnsupportedFont(ValueError):
    pass


FontCharacteristics = namedtuple('FontCharacteristics',
    'weight, is_italic, is_bold, is_regular, fs_type, panose, width, is_oblique, is_wws, os2_version')
FontNames = namedtuple('FontNames',
    'family_name, subfamily_name, full_name, preferred_family_name, preferred_subfamily_name, wws_family_name, wws_subfamily_name')


class FontMetadata:

    def __init__(self, bytes_or_stream):
        from fontTools.subset import load_font, Subsetter
        if not hasattr(bytes_or_stream, 'read'):
            bytes_or_stream = BytesIO(bytes_or_stream)
        f = bytes_or_stream
        f.seek(0)
        s = Subsetter()
        try:
            font = load_font(f, s.options, dontLoadGlyphNames=True)
        except Exception as e:
            raise UnsupportedFont(str(e)) from e
        self.is_otf = font.sfntVersion == 'OTTO'
        self._read_names(font)
        self._read_characteristics(font)

        f.seek(0)
        self.font_family = self.names.family_name
        wt = self.characteristics.weight
        if wt == 400:
            wt = 'normal'
        elif wt == 700:
            wt = 'bold'
        else:
            wt = str(wt)
        self.font_weight = wt

        self.font_stretch = ('ultra-condensed', 'extra-condensed',
                'condensed', 'semi-condensed', 'normal', 'semi-expanded',
                'expanded', 'extra-expanded', 'ultra-expanded')[
                        self.characteristics.width-1]
        if self.characteristics.is_oblique:
            self.font_style = 'oblique'
        elif self.characteristics.is_italic:
            self.font_style = 'italic'
        else:
            self.font_style = 'normal'

    def _read_names(self, font):
        try:
            name_table = font['name']
        except KeyError:
            raise UnsupportedFont('This font has no name table')
        self.names = FontNames(*get_font_names_from_ttlib_names_table(name_table))

    def _read_characteristics(self, font):
        try:
            os2_table = font['OS/2']
        except KeyError:
            raise UnsupportedFont('This font has no OS/2 table')

        vals = get_font_characteristics(os2_table, raw_is_table=True)
        self.characteristics = FontCharacteristics(*vals)

    def to_dict(self):
        ans = {
                'is_otf':self.is_otf,
                'font-family':self.font_family,
                'font-weight':self.font_weight,
                'font-style':self.font_style,
                'font-stretch':self.font_stretch
        }
        for f in self.names._fields:
            ans[f] = getattr(self.names, f)
        for f in self.characteristics._fields:
            ans[f] = getattr(self.characteristics, f)
        return ans


if __name__ == '__main__':
    import sys
    with open(sys.argv[-1], 'rb') as f:
        fm = FontMetadata(f)
        import pprint
        pprint.pprint(fm.to_dict())
