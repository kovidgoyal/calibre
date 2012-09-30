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

def is_truetype_font(raw):
    sfnt_version = raw[:4]
    return (sfnt_version in {b'\x00\x01\x00\x00', b'OTTO'}, sfnt_version)

def get_font_characteristics(raw):
    num_tables = struct.unpack_from(b'>H', raw, 4)[0]

    # Find OS/2 table
    offset = 4 + 4*2 # Start of the Table record entries
    os2_table_offset = None
    for i in xrange(num_tables):
        table_tag = raw[offset:offset+4]
        if table_tag == b'OS/2':
            os2_table_offset = struct.unpack_from(b'>I', raw, offset+8)[0]
            break
        offset += 16 # Size of a table record
    if os2_table_offset is None:
        raise UnsupportedFont('Not a supported font, has no OS/2 table')

    common_fields = b'>HhHHHhhhhhhhhhhh'
    (version, char_width, weight, width, fs_type, subscript_x_size,
            subscript_y_size, subscript_x_offset, subscript_y_offset,
            superscript_x_size, superscript_y_size, superscript_x_offset,
            superscript_y_offset, strikeout_size, strikeout_position,
            family_class) = struct.unpack_from(common_fields,
                    raw, os2_table_offset)
    offset = os2_table_offset + struct.calcsize(common_fields)
    panose = struct.unpack_from(b'>'+b'B'*10, raw, offset)
    panose
    offset += 10
    (range1,) = struct.unpack_from(b'>L', raw, offset)
    offset += struct.calcsize(b'>L')
    if version > 0:
        range2, range3, range4 = struct.unpack_from(b'>LLL', raw, offset)
        offset += struct.calcsize(b'>LLL')
    vendor_id = raw[offset:offset+4]
    vendor_id
    offset += 4
    selection, = struct.unpack_from(b'>H', raw, offset)

    is_italic = (selection & 0b1) != 0
    is_bold = (selection & 0b100000) != 0
    is_regular = (selection & 0b1000000) != 0
    return weight, is_italic, is_bold, is_regular

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
        if table_tag == b'OS/2':
            os2_table_offset = struct.unpack_from(b'>I', raw, offset+8)[0]
            break
        offset += 16 # Size of a table record
    if os2_table_offset is None:
        raise UnsupportedFont('Not a supported font, has no OS/2 table')

    version, = struct.unpack_from(b'>H', raw, os2_table_offset)

    fs_type_offset = os2_table_offset + struct.calcsize(b'>HhHH')
    fs_type = struct.unpack_from(b'>H', raw, fs_type_offset)[0]
    if fs_type == 0:
        return raw

    return raw[:fs_type_offset] + struct.pack(b'>H', 0) + raw[fs_type_offset+2:]

if __name__ == '__main__':
    raw = remove_embed_restriction(open(sys.argv[-1], 'rb').read())

