#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct
from collections import OrderedDict

from calibre.ebooks.mobi.utils import decint, count_set_bits

class InvalidFile(ValueError):
    pass

def check_signature(data, signature):
    if data[:len(signature)] != signature:
        raise InvalidFile('Not a valid %r section'%signature)

class NotAnINDXRecord(InvalidFile):
    pass

class NotATAGXSection(InvalidFile):
    pass

def format_bytes(byts):
    byts = bytearray(byts)
    byts = [hex(b)[2:] for b in byts]
    return ' '.join(byts)

def parse_indx_header(data):
    check_signature(data, b'INDX')
    words = (
            'len', 'nul1', 'type', 'gen', 'start', 'count', 'code',
            'lng', 'total', 'ordt', 'ligt', 'nligt', 'ncncx'
    )
    num = len(words)
    values = struct.unpack(b'>%dL' % num, data[4:4*(num+1)])
    header = {words[i]:values[i] for i in xrange(num)}
    return header

class CNCX(object): # {{{

    '''
    Parses the records that contain the compiled NCX (all strings from the
    NCX). Presents a simple offset : string mapping interface to access the
    data.
    '''

    def __init__(self, records, codec):
        self.records = OrderedDict()
        record_offset = 0
        for raw in records:
            pos = 0
            while pos < len(raw):
                length, consumed = decint(raw[pos:])
                if length > 0:
                    try:
                        self.records[pos+record_offset] = raw[
                            pos+consumed:pos+consumed+length].decode(codec)
                    except:
                        byts = raw[pos:]
                        r = format_bytes(byts)
                        print ('CNCX entry at offset %d has unknown format %s'%(
                            pos+record_offset, r))
                        self.records[pos+record_offset] = r
                        pos = len(raw)
                pos += consumed+length
            record_offset += 0x10000

    def __getitem__(self, offset):
        return self.records.get(offset)

    def get(self, offset, default=None):
        return self.records.get(offset, default)
# }}}

def parse_tag_section(data):
    check_signature(data, b'TAGX')

    tags = []
    first_entry_offset, = struct.unpack_from(b'>L', data, 0x04)
    control_byte_count, = struct.unpack_from(b'>L', data, 0x08)

    # Skip the first 12 bytes already read above.
    for i in xrange(12, first_entry_offset, 4):
        pos = i
        tags.append((ord(data[pos]), ord(data[pos+1]), ord(data[pos+2]),
            ord(data[pos+3])))
    return control_byte_count, tags

def get_tag_map(control_byte_count, tags, data, start, end):
    ptags = []
    ans = {}
    control_byte_index = 0
    data_start = start + control_byte_count

    for tag, values_per_entry, mask, end_flag in tags:
        if end_flag == 0x01:
            control_byte_index += 1
            continue
        value = ord(data[start + control_byte_index]) & mask
        if value != 0:
            if value == mask:
                if count_set_bits(mask) > 1:
                    # If all bits of masked value are set and the mask has more
                    # than one bit, a variable width value will follow after
                    # the control bytes which defines the length of bytes (NOT
                    # the value count!) which will contain the corresponding
                    # variable width values.
                    value, consumed = decint(data[data_start:])
                    data_start += consumed
                    ptags.append((tag, None, value, values_per_entry))
                else:
                    ptags.append((tag, 1, None, values_per_entry))
            else:
                # Shift bits to get the masked value.
                while mask & 0x01 == 0:
                    mask = mask >> 1
                    value = value >> 1
                ptags.append((tag, value, None, values_per_entry))
    for tag, value_count, value_bytes, values_per_entry in ptags:
        values = []
        if value_count != None:
            # Read value_count * values_per_entry variable width values.
            for _ in xrange(value_count*values_per_entry):
                byts, consumed = decint(data[data_start:])
                data_start += consumed
                values.append(byts)
        else:
            # Convert value_bytes to variable width values.
            total_consumed = 0
            while total_consumed < value_bytes:
                # Does this work for values_per_entry != 1?
                byts, consumed = decint(data[data_start:])
                data_start += consumed
                total_consumed += consumed
                values.append(byts)
            if total_consumed != value_bytes:
                print ("Error: Should consume %s bytes, but consumed %s" %
                        (value_bytes, total_consumed))
        ans[tag] = values
    # Test that all bytes have been processed if end is given.
    if end is not None and data_start < end:
        # The last entry might have some zero padding bytes, so complain only if non zero bytes are left.
        rest = data[data_start:end]
        if rest.replace(b'\0', b''):
            print ("Warning: There are unprocessed index bytes left: %s" %
                    format_bytes(rest))

    return ans

def read_index(sections, idx, codec):
    table, cncx = OrderedDict(), CNCX([], codec)

    data = sections[idx][0]

    indx_header = parse_indx_header(data)
    indx_count = indx_header['count']

    if indx_header['ncncx'] > 0:
        off = idx + indx_count + 1
        cncx_records = [x[0] for x in sections[off:off+indx_header['ncncx']]]
        cncx = CNCX(cncx_records, codec)

    tag_section_start = indx_header['len']
    control_byte_count, tags = parse_tag_section(data[tag_section_start:])

    for i in xrange(idx + 1, idx + 1 + indx_count):
        data = sections[i][0]
        header = parse_indx_header(data)
        idxt_pos = header['start']
        entry_count = header['count']

        # loop through to build up the IDXT position starts
        idx_positions= []
        for j in xrange(entry_count):
            pos, = struct.unpack_from(b'>H', data, idxt_pos + 4 + (2 * j))
            idx_positions.append(pos)
        # The last entry ends before the IDXT tag (but there might be zero fill
        # bytes we need to ignore!)
        idx_positions.append(idxt_pos)

        # For each entry in the IDXT build up the tag map and any associated
        # text
        for j in xrange(entry_count):
            start, end = idx_positions[j:j+2]
            text_length = ord(data[start])
            text = data[start+1:start+1+text_length]
            tag_map = get_tag_map(control_byte_count, tags, data,
                    start+1+text_length, end)
            table[text] = tag_map

    return table, cncx

