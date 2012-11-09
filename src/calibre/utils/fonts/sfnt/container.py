#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import pack, calcsize
from io import BytesIO
from collections import OrderedDict

from calibre.utils.fonts.utils import (get_tables, checksum_of_block,
        verify_checksums)
from calibre.utils.fonts.sfnt import align_block, UnknownTable, max_power_of_two
from calibre.utils.fonts.sfnt.errors import UnsupportedFont

from calibre.utils.fonts.sfnt.head import HeadTable
from calibre.utils.fonts.sfnt.maxp import MaxpTable
from calibre.utils.fonts.sfnt.loca import LocaTable
from calibre.utils.fonts.sfnt.glyf import GlyfTable
from calibre.utils.fonts.sfnt.cmap import CmapTable
from calibre.utils.fonts.sfnt.kern import KernTable
from calibre.utils.fonts.sfnt.cff.table import CFFTable

# OpenType spec: http://www.microsoft.com/typography/otspec/otff.htm

class Sfnt(object):

    def __init__(self, raw):
        self.sfnt_version = raw[:4]
        if self.sfnt_version not in {b'\x00\x01\x00\x00', b'OTTO', b'true',
                b'type1'}:
            raise UnsupportedFont('Font has unknown sfnt version: %r'%self.sfnt_version)
        self.read_tables(raw)

    def read_tables(self, raw):
        self.tables = {}
        for table_tag, table, table_index, table_offset, table_checksum in get_tables(raw):
            self.tables[table_tag] = {
                    b'head' : HeadTable,
                    b'maxp' : MaxpTable,
                    b'loca' : LocaTable,
                    b'glyf' : GlyfTable,
                    b'cmap' : CmapTable,
                    b'CFF ' : CFFTable,
                    b'kern' : KernTable,
                    }.get(table_tag, UnknownTable)(table)

    def __getitem__(self, key):
        return self.tables[key]

    def __contains__(self, key):
        return key in self.tables

    def __delitem__(self, key):
        del self.tables[key]

    def __iter__(self):
        '''Iterate over the table tags in optimal order as per
        http://partners.adobe.com/public/developer/opentype/index_recs.html'''
        keys = list(self.tables.keys())
        order = {x:i for i, x in enumerate((b'head', b'hhea', b'maxp', b'OS/2',
            b'hmtx', b'LTSH', b'VDMX', b'hdmx', b'cmap', b'fpgm', b'prep',
            b'cvt ', b'loca', b'glyf', b'CFF ', b'kern', b'name', b'post',
            b'gasp', b'PCLT', b'DSIG'))}
        keys.sort(key=lambda x:order.get(x, 1000))
        for x in keys:
            yield x

    def pop(self, key, default=None):
        return self.tables.pop(key, default)

    def sizes(self):
        ans = OrderedDict()
        for tag in self:
            ans[tag] = len(self[tag])
        return ans

    def __call__(self):
        stream = BytesIO()

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
        offset = stream.tell() + ( calcsize(b'>4s3L') * num_tables )
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
        raise ValueError('Roundtripping failed, size different')

if __name__ == '__main__':
    import sys
    test_roundtrip(sys.argv[-1])

