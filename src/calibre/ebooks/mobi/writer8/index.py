#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import namedtuple
from struct import pack
from io import BytesIO

from calibre.ebooks.mobi.utils import CNCX, encint

TagMeta = namedtuple('TagMeta',
        'name number values_per_entry bitmask end_flag')
EndTagTable = TagMeta('eof', 0, 0, 0, 1)

# map of mask to number of shifts needed, works with 1 bit and two-bit wide masks
# could also be extended to 4 bit wide ones as well
mask_to_bit_shifts = { 1:0, 2:1, 3:0, 4:2, 8:3, 12:2, 16:4, 32:5, 48:4, 64:6,
        128:7, 192: 6 }


class Index(object):

    control_byte_count = 1
    cncx = CNCX()
    tag_types = (EndTagTable,)

    @classmethod
    def generate_tagx(cls):
        header = b'TAGX'
        byts = bytearray()
        for tag_meta in cls.tag_types:
            byts.extend(tag_meta[1:])
        # table length, control byte count
        header += pack(b'>II', 12+len(byts), cls.control_byte_count)
        return header + bytes(byts)

    @classmethod
    def calculate_control_bytes_for_each_entry(cls, entries):
        control_bytes = []
        for lead_text, tags in entries:
            cbs = []
            ans = 0
            for (name, number, vpe, mask, endi) in cls.tag_types:
                if endi == 1:
                    cbs.append(ans)
                    ans = 0
                    continue
                nvals = len(tags.get(name, ()))
                nentries = nvals // vpe
                shifts = mask_to_bit_shifts[mask]
                ans |= mask & (nentries << shifts)
            if len(cbs) != cls.control_byte_count:
                raise ValueError('The entry %r is invalid'%[lead_text, tags])
            control_bytes.append(cbs)
        return control_bytes

    def build_records(self):
        self.control_bytes = self.calculate_control_bytes_for_each_entry(
                self.entries)

        self.rendered_entries = []
        offset = 0
        IndexEntry = namedtuple('IndexEntry', 'offset length raw')
        for i, x in enumerate(self.entries):
            control_bytes = self.control_bytes[i]
            leading_text, tags = x
            buf = BytesIO()
            raw = bytearray(leading_text)
            raw.insert(0, len(leading_text))
            buf.write(bytes(raw))
            buf.write(control_bytes)
            for tag in self.tag_types:
                values = tags.get(tag.name, None)
                if values:
                    for val in values:
                        buf.write(encint(val))
            raw = buf.getvalue()
            self.rendered_entries.append(IndexEntry(offset, len(raw), raw))
            offset += len(raw)

class SkelIndex(Index):

    tag_types = tuple(map(TagMeta, (
        ('chunk_count', 1, 1, 3, 0),
        ('geometry',    6, 2, 12, 0),
        EndTagTable
    )))

    def __init__(self, skel_table):
        self.entries = [
                (s.name, {
                    # Dont ask me why these entries have to be repeated twice
                    'chunk_count':(s.chunk_count, s.chunk_count),
                    'geometry':(s.start_pos, s.length, s.start_pos, s.length),
                    }) for s in skel_table
        ]


class ChunkIndex(Index):

    tag_types = tuple(map(TagMeta, (
        ('cncx_offset',     2, 1, 1, 0),
        ('file_number',     3, 1, 2, 0),
        ('sequence_number', 4, 1, 4, 0),
        ('geometry',        6, 2, 8, 0),
        EndTagTable
    )))

    def __init__(self, chunk_table):
        self.cncx = CNCX(c.selector for c in chunk_table)

        self.entries = [
                ('%010d'%c.insert_pos, {

                    'cncx_offset':self.cncx[c.selector],
                    'file_number':c.file_number,
                    'sequence_number':c.sequence_number,
                    'geometry':(c.start_pos, c.length),
                    }) for s in chunk_table
        ]

