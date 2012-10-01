#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct
from io import BytesIO
from collections import defaultdict

class UnsupportedFont(ValueError):
    pass

def is_truetype_font(raw):
    sfnt_version = raw[:4]
    return (sfnt_version in {b'\x00\x01\x00\x00', b'OTTO'}, sfnt_version)

def get_table(raw, name):
    ''' Get the raw table bytes for the specified table in the font '''
    num_tables = struct.unpack_from(b'>H', raw, 4)[0]
    offset = 4*3 # start of the table record entries
    table_offset = table_checksum = table_length = table_index = table = None
    name = bytes(name.lower())
    for i in xrange(num_tables):
        table_tag = raw[offset:offset+4]
        if table_tag.lower() == name:
            table_checksum, table_offset, table_length = struct.unpack_from(
                    b'>3L', raw, offset+4)
            table_index = offset
            break
        offset += 4*4
    if table_offset is not None:
        table = raw[table_offset:table_offset+table_length]
    return table, table_index, table_offset, table_checksum

def get_font_characteristics(raw):
    '''
    Return (weight, is_italic, is_bold, is_regular, fs_type). These values are taken
    from the OS/2 table of the font. See
    http://www.microsoft.com/typography/otspec/os2.htm for details
    '''
    os2_table = get_table(raw, 'os/2')[0]
    if os2_table is None:
        raise UnsupportedFont('Not a supported font, has no OS/2 table')

    common_fields = b'>Hh3H11h'
    (version, char_width, weight, width, fs_type, subscript_x_size,
            subscript_y_size, subscript_x_offset, subscript_y_offset,
            superscript_x_size, superscript_y_size, superscript_x_offset,
            superscript_y_offset, strikeout_size, strikeout_position,
            family_class) = struct.unpack_from(common_fields, os2_table)
    offset = struct.calcsize(common_fields)
    panose = struct.unpack_from(b'>10B', os2_table, offset)
    panose
    offset += 10
    (range1,) = struct.unpack_from(b'>L', os2_table, offset)
    offset += struct.calcsize(b'>L')
    if version > 0:
        range2, range3, range4 = struct.unpack_from(b'>3L', os2_table, offset)
        offset += struct.calcsize(b'>3L')
    vendor_id = os2_table[offset:offset+4]
    vendor_id
    offset += 4
    selection, = struct.unpack_from(b'>H', os2_table, offset)

    is_italic = (selection & 0b1) != 0
    is_bold = (selection & 0b100000) != 0
    is_regular = (selection & 0b1000000) != 0
    return weight, is_italic, is_bold, is_regular, fs_type

def decode_name_record(recs):
    '''
    Get the English names of this font. See
    http://www.microsoft.com/typography/otspec/name.htm for details.
    '''
    if not recs: return None
    unicode_names = {}
    windows_names = {}
    mac_names = {}
    for platform_id, encoding_id, language_id, src in recs:
        if language_id > 0x8000: continue
        if platform_id == 0:
            if encoding_id < 4:
                try:
                    unicode_names[language_id] = src.decode('utf-16-be')
                except ValueError:
                    continue
        elif platform_id == 1:
            try:
                mac_names[language_id] = src.decode('utf-8')
            except ValueError:
                continue
        elif platform_id == 2:
            codec = {0:'ascii', 1:'utf-16-be', 2:'iso-8859-1'}.get(encoding_id,
                    None)
            if codec is None: continue
            try:
                unicode_names[language_id] = src.decode(codec)
            except ValueError:
                continue
        elif platform_id == 3:
            codec = {1:16, 10:32}.get(encoding_id, None)
            if codec is None: continue
            try:
                windows_names[language_id] = src.decode('utf-%d-be'%codec)
            except ValueError:
                continue

    # First try the windows names
    # First look for the US English name
    if 1033 in windows_names:
        return windows_names[1033]
    # Look for some other english name variant
    for lang in (3081, 10249, 4105, 9225, 16393, 6153, 8201, 17417, 5129,
            13321, 18441, 7177, 11273, 2057, 12297):
        if lang in windows_names:
            return windows_names[lang]

    # Look for Mac name
    if 0 in mac_names:
        return mac_names[0]

    # Use unicode names
    for val in unicode_names.itervalues():
        return val

    return None

def get_font_names(raw):
    table = get_table(raw, 'name')[0]
    if table is None:
        raise UnsupportedFont('Not a supported font, has no name table')
    table_type, count, string_offset = struct.unpack_from(b'>3H', table)

    records = defaultdict(list)

    for i in xrange(count):
        try:
            platform_id, encoding_id, language_id, name_id, length, offset = \
                    struct.unpack_from(b'>6H', table, 6+i*12)
        except struct.error:
            break
        offset += string_offset
        src = table[offset:offset+length]
        records[name_id].append((platform_id, encoding_id, language_id,
            src))

    family_name = decode_name_record(records[1])
    subfamily_name = decode_name_record(records[2])
    full_name = decode_name_record(records[4])

    return family_name, subfamily_name, full_name


def remove_embed_restriction(raw):
    ok, sig = is_truetype_font(raw)
    if not ok:
        raise UnsupportedFont('Not a supported font, sfnt_version: %r'%sig)

    table, table_index, table_offset = get_table(raw, 'os/2')
    if table is None:
        raise UnsupportedFont('Not a supported font, has no OS/2 table')

    fs_type_offset = struct.calcsize(b'>HhHH')
    fs_type = struct.unpack_from(b'>H', table, fs_type_offset)[0]
    if fs_type == 0:
        return raw

    f = BytesIO(raw)
    f.seek(fs_type_offset + table_offset)
    f.write(struct.pack(b'>H', 0))
    return f.getvalue()

def test():
    import sys, os
    for f in sys.argv[1:]:
        print (os.path.basename(f))
        raw = open(f, 'rb').read()
        print (get_font_names(raw))
        print (get_font_characteristics(raw))

if __name__ == '__main__':
    test()

