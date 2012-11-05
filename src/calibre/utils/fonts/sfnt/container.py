#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from math import log
from struct import pack, calcsize
from io import BytesIO

from calibre.utils.fonts.utils import (get_tables, checksum_of_block,
        verify_checksums)
from calibre.utils.fonts.sfnt import align_block
from calibre.utils.fonts.sfnt.errors import UnsupportedFont

class UnknownTable(object):

    def __init__(self, raw):
        self.raw = raw

    def __call__(self):
        return self.raw

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
                    }.get(table_tag, UnknownTable)(table)

    def __call__(self):
        stream = BytesIO()

        def spack(*args):
            stream.write(pack(*args))

        stream.seek(0)

        # Write header
        num_tables = len(self.tables)
        ln2 = int(log(num_tables, 2))
        srange = (2**ln2) * 16
        spack(b'>4s4H',
            self.sfnt_version, num_tables, srange, ln2, num_tables * 16 - srange)

        # Write tables
        head_offset = None
        table_data = []
        offset = stream.tell() + ( calcsize(b'>4s3L') * num_tables )
        for tag in sorted(self.tables):
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

        for x in table_data:
            stream.write(x)

        checksum = checksum_of_block(stream.getvalue())
        q = (0xB1B0AFBA - checksum) & 0xffffffff
        stream.seek(head_offset + 8)
        spack(b'>L', q)

        return stream.getvalue()

def test_roundtrip(ff=None):
    if ff is None:
        data = P('fonts/liberation/LiberationSerif-Regular.ttf', data=True)
    else:
        with open(ff, 'rb') as f:
            data = f.read()
    rd = Sfnt(data)()
    verify_checksums(rd)
    if data[:12] != rd[:12]:
        raise ValueError('Roundtripping failed, font header not the same')
    if len(data) != len(rd):
        raise ValueError('Roundtripping failed, size different')

if __name__ == '__main__':
    import sys
    test_roundtrip(sys.argv[-1])

