#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from io import BytesIO
from struct import calcsize, unpack, unpack_from
from collections import namedtuple

from calibre.utils.fonts.utils import get_font_names2, get_font_characteristics


class UnsupportedFont(ValueError):
    pass


FontCharacteristics = namedtuple('FontCharacteristics',
    'weight, is_italic, is_bold, is_regular, fs_type, panose, width, is_oblique, is_wws, os2_version')
FontNames = namedtuple('FontNames',
    'family_name, subfamily_name, full_name, preferred_family_name, preferred_subfamily_name, wws_family_name, wws_subfamily_name')


class FontMetadata:

    def __init__(self, bytes_or_stream):
        if not hasattr(bytes_or_stream, 'read'):
            bytes_or_stream = BytesIO(bytes_or_stream)
        f = bytes_or_stream
        f.seek(0)
        header = f.read(4)
        if header not in {b'\x00\x01\x00\x00', b'OTTO'}:
            raise UnsupportedFont('Not a supported sfnt variant')

        self.is_otf = header == b'OTTO'
        self.read_table_metadata(f)
        self.read_names(f)
        self.read_characteristics(f)

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

    def read_table_metadata(self, f):
        f.seek(4)
        num_tables = unpack(b'>H', f.read(2))[0]
        # Start of table record entries
        f.seek(4 + 4*2)
        table_record = b'>4s3L'
        sz = calcsize(table_record)
        self.tables = {}
        block = f.read(sz * num_tables)
        for i in range(num_tables):
            table_tag, table_checksum, table_offset, table_length = \
                    unpack_from(table_record, block, i*sz)
            self.tables[table_tag.lower()] = (table_offset, table_length,
                    table_checksum)

    def read_names(self, f):
        if b'name' not in self.tables:
            raise UnsupportedFont('This font has no name table')
        toff, tlen = self.tables[b'name'][:2]
        f.seek(toff)
        table = f.read(tlen)
        if len(table) != tlen:
            raise UnsupportedFont('This font has a name table of incorrect length')
        vals = get_font_names2(table, raw_is_table=True)
        self.names = FontNames(*vals)

    def read_characteristics(self, f):
        if b'os/2' not in self.tables:
            raise UnsupportedFont('This font has no OS/2 table')
        toff, tlen = self.tables[b'os/2'][:2]
        f.seek(toff)
        table = f.read(tlen)
        if len(table) != tlen:
            raise UnsupportedFont('This font has an OS/2 table of incorrect length')
        vals = get_font_characteristics(table, raw_is_table=True)
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
