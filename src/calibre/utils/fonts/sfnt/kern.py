#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from, calcsize, pack, error as struct_error

from calibre.utils.fonts.sfnt import (UnknownTable, FixedProperty,
        max_power_of_two)
from calibre.utils.fonts.sfnt.errors import UnsupportedFont


class KernTable(UnknownTable):

    version = FixedProperty('_version')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._version, self.num_tables = unpack_from(b'>HH', self.raw)
        if self._version == 1 and len(self.raw) >= 8:
            self._version, self.num_tables = unpack_from(b'>LL', self.raw)
        self.headerfmt = b'>HH' if self._version == 0 else b'>LL'

    def restrict_to_glyphs(self, glyph_ids):
        if self._version not in {0, 0x10000}:
            raise UnsupportedFont('kern table has version: %x'%self._version)
        offset = 4 if (self._version == 0) else 8
        tables = []
        for i in range(self.num_tables):
            if self._version == 0:
                version, length, coverage = unpack_from(b'>3H', self.raw, offset)
                table_format = version
            else:
                length, coverage = unpack_from(b'>LH', self.raw, offset)
                table_format = coverage & 0xff
            raw = self.raw[offset:offset+length]
            if table_format == 0:
                raw = self.restrict_format_0(raw, glyph_ids)
                if not raw:
                    continue
            tables.append(raw)
            offset += length
        self.raw = pack(self.headerfmt, self._version, len(tables)) + b''.join(tables)

    def restrict_format_0(self, raw, glyph_ids):
        if self._version == 0:
            version, length, coverage, npairs = unpack_from(b'>4H', raw)
            headerfmt = b'>3H'
        else:
            length, coverage, tuple_index, npairs = unpack_from(b'>L3H', raw)
            headerfmt = b'>L2H'

        offset = calcsize(headerfmt + b'4H')
        entries = []
        entrysz = calcsize(b'>2Hh')
        for i in range(npairs):
            try:
                left, right, value = unpack_from(b'>2Hh', raw, offset)
            except struct_error:
                offset = len(raw)
                break  # Buggy kern table
            if left in glyph_ids and right in glyph_ids:
                entries.append(pack(b'>2Hh', left, right, value))
            offset += entrysz

        if offset != len(raw):
            raise UnsupportedFont('This font has extra data at the end of'
                    ' a Format 0 kern subtable')

        npairs = len(entries)
        if npairs == 0:
            return b''

        entry_selector = max_power_of_two(npairs)
        search_range = (2 ** entry_selector) * 6
        range_shift = (npairs - (2 ** entry_selector)) * 6

        entries = b''.join(entries)
        length = calcsize(headerfmt + b'4H') + len(entries)
        if self._version == 0:
            header = pack(headerfmt, version, length, coverage)
        else:
            header = pack(headerfmt, length, coverage, tuple_index)
        return header + pack(b'>4H', npairs, search_range, entry_selector,
                range_shift) + entries
