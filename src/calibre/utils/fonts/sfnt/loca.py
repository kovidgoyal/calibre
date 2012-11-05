#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import calcsize, unpack_from

from calibre.utils.fonts.sfnt import UnknownTable

class LocaTable(UnknownTable):

    def load_offsets(self, head_table, maxp_table):
        fmt = 'H' if head_table.index_to_loc_format == 0 else 'L'
        num_glyphs = maxp_table.num_glyphs
        sz = calcsize(('>%s'%fmt).encode('ascii'))
        num = len(self.raw)//sz
        self.offset_map = unpack_from(('>%d%s'%(num, fmt)).encode('ascii'),
                self.raw)
        self.offset_map = self.offset_map[:num_glyphs+1]
        if fmt == 'H':
            self.offset_map = [2*i for i in self.offset_map]

    def glyph_location(self, glyph_id):
        offset = self.offset_map[glyph_id]
        next_offset = self.offset_map[glyph_id+1]
        return offset, next_offset - offset

