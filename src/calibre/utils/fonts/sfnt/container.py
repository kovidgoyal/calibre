#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>


from collections import OrderedDict
from io import BytesIO
from struct import calcsize, pack

from calibre.utils.fonts.sfnt import UnknownTable, align_block, max_power_of_two
from calibre.utils.fonts.sfnt.cff.table import CFFTable
from calibre.utils.fonts.sfnt.cmap import CmapTable
from calibre.utils.fonts.sfnt.errors import UnsupportedFont
from calibre.utils.fonts.sfnt.glyf import GlyfTable
from calibre.utils.fonts.sfnt.gsub import GSUBTable
from calibre.utils.fonts.sfnt.head import (
    HeadTable, HorizontalHeader, OS2Table, PostTable, VerticalHeader
)
from calibre.utils.fonts.sfnt.kern import KernTable
from calibre.utils.fonts.sfnt.loca import LocaTable
from calibre.utils.fonts.sfnt.maxp import MaxpTable
from calibre.utils.fonts.utils import checksum_of_block, get_tables, verify_checksums

# OpenType spec: http://www.microsoft.com/typography/otspec/otff.htm


class Sfnt:

    TABLE_MAP = {
        b'head' : HeadTable,
        b'hhea' : HorizontalHeader,
        b'vhea' : VerticalHeader,
        b'maxp' : MaxpTable,
        b'loca' : LocaTable,
        b'glyf' : GlyfTable,
        b'cmap' : CmapTable,
        b'CFF ' : CFFTable,
        b'kern' : KernTable,
        b'GSUB' : GSUBTable,
        b'OS/2' : OS2Table,
        b'post' : PostTable,
    }

    def __init__(self, raw_or_get_table):
        self.tables = {}
        if isinstance(raw_or_get_table, bytes):
            raw = raw_or_get_table
            self.sfnt_version = raw[:4]
            if self.sfnt_version not in {b'\x00\x01\x00\x00', b'OTTO', b'true',
                    b'type1'}:
                raise UnsupportedFont('Font has unknown sfnt version: %r'%self.sfnt_version)
            for table_tag, table, table_index, table_offset, table_checksum in get_tables(raw):
                self.tables[table_tag] = self.TABLE_MAP.get(
                    table_tag, UnknownTable)(table)
        else:
            for table_tag in {
                b'cmap', b'hhea', b'head', b'hmtx', b'maxp', b'name', b'OS/2',
                b'post', b'cvt ', b'fpgm', b'glyf', b'loca', b'prep', b'CFF ',
                b'VORG', b'EBDT', b'EBLC', b'EBSC', b'BASE', b'GSUB', b'GPOS',
                b'GDEF', b'JSTF', b'gasp', b'hdmx', b'kern', b'LTSH', b'PCLT',
                b'VDMX', b'vhea', b'vmtx', b'MATH'}:
                table = bytes(raw_or_get_table(table_tag))
                if table:
                    self.tables[table_tag] = self.TABLE_MAP.get(
                        table_tag, UnknownTable)(table)
            if not self.tables:
                raise UnsupportedFont('This font has no tables')
            self.sfnt_version = (b'\0\x01\0\0' if b'glyf' in self.tables
                                    else b'OTTO')

    def __getitem__(self, key):
        return self.tables[key]

    def __contains__(self, key):
        return key in self.tables

    def __delitem__(self, key):
        del self.tables[key]

    def __iter__(self):
        '''Iterate over the table tags in order.'''
        yield from sorted(self.tables)
        # Although the optimal order is not alphabetical, the OTF spec says
        # they should be alphabetical, so we stick with that. See
        # http://partners.adobe.com/public/developer/opentype/index_recs.html
        # for optimal order.
        # keys = list(self.tables)
        # order = {x:i for i, x in enumerate((b'head', b'hhea', b'maxp', b'OS/2',
        #     b'hmtx', b'LTSH', b'VDMX', b'hdmx', b'cmap', b'fpgm', b'prep',
        #     b'cvt ', b'loca', b'glyf', b'CFF ', b'kern', b'name', b'post',
        #     b'gasp', b'PCLT', b'DSIG'))}
        # keys.sort(key=lambda x:order.get(x, 1000))
        # for x in keys:
        #     yield x

    def pop(self, key, default=None):
        return self.tables.pop(key, default)

    def get(self, key, default=None):
        return self.tables.get(key, default)

    def sizes(self):
        ans = OrderedDict()
        for tag in self:
            ans[tag] = len(self[tag])
        return ans

    def get_all_font_names(self):
        from calibre.utils.fonts.metadata import get_font_names2, FontNames
        name_table = self.get(b'name')
        if name_table is not None:
            return FontNames(*get_font_names2(name_table.raw, raw_is_table=True))

    def __call__(self, stream=None):
        stream = BytesIO() if stream is None else stream

        def spack(*args):
            stream.write(pack(*args))

        stream.seek(0)

        # Write header
        num_tables = len(self.tables)
        ln2 = max_power_of_two(num_tables)
        srange = (2**ln2) * 16
        spack(b'>4s4H',
            self.sfnt_version, num_tables, srange, ln2, num_tables * 16 - srange)

        # Write tables
        head_offset = None
        table_data = []
        offset = stream.tell() + (calcsize(b'>4s3L') * num_tables)
        sizes = OrderedDict()
        for tag in self:
            table = self.tables[tag]
            raw = table()
            table_len = len(raw)
            if tag == b'head':
                head_offset = offset
                raw = raw[:8] + b'\0\0\0\0' + raw[12:]
            raw = align_block(raw)
            checksum = checksum_of_block(raw)
            spack(b'>4s3L', tag, checksum, offset, table_len)
            offset += len(raw)
            table_data.append(raw)
            sizes[tag] = table_len

        for x in table_data:
            stream.write(x)

        checksum = checksum_of_block(stream.getvalue())
        q = (0xB1B0AFBA - checksum) & 0xffffffff
        stream.seek(head_offset + 8)
        spack(b'>L', q)

        return stream.getvalue(), sizes


def test_roundtrip(ff=None):
    if ff is None:
        data = P('fonts/liberation/LiberationSerif-Regular.ttf', data=True)
    else:
        with open(ff, 'rb') as f:
            data = f.read()
    rd = Sfnt(data)()[0]
    verify_checksums(rd)
    if data[:12] != rd[:12]:
        raise ValueError('Roundtripping failed, font header not the same')
    if len(data) != len(rd):
        raise ValueError('Roundtripping failed, size different (%d vs. %d)'%
                         (len(data), len(rd)))


if __name__ == '__main__':
    import sys
    test_roundtrip(sys.argv[-1])
