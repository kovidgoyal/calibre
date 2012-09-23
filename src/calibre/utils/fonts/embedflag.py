#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, struct

class UnsupportedFont(ValueError):
    pass

def remove_embed_restriction(raw):
    sfnt_version = raw[:4]
    if sfnt_version not in {b'\x00\x01\x00\x00', b'OTTO'}:
        raise UnsupportedFont('Not a supported font, sfnt_version: %r'%sfnt_version)

    num_tables = struct.unpack_from(b'>H', raw, 4)[0]

    # Find OS/2 table
    offset = 4 + 4*2 # Start of the Table record entries
    os2_table_offset = None
    for i in xrange(num_tables):
        table_tag = raw[offset:offset+4]
        offset += 16 # Size of a table record
        if table_tag == b'OS/2':
            os2_table_offset = struct.unpack_from(b'>I', raw, offset+8)[0]
            break
    if os2_table_offset is None:
        raise UnsupportedFont('Not a supported font, has no OS/2 table')

    version, = struct.unpack_from(b'>H', raw, os2_table_offset)

    fs_type_offset = os2_table_offset + struct.calcsize(b'>HhHH')
    fs_type = struct.unpack_from(b'>H', raw, fs_type_offset)[0]
    if fs_type == 0:
        return raw

    return raw[:fs_type_offset] + struct.pack(b'>H', 0) + raw[fs_type_offset+2:]

if __name__ == '__main__':
    remove_embed_restriction(open(sys.argv[-1], 'rb').read())

