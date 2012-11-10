#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import calcsize, unpack_from, pack
from operator import itemgetter

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
        self.fmt = fmt

    def glyph_location(self, glyph_id):
        offset = self.offset_map[glyph_id]
        next_offset = self.offset_map[glyph_id+1]
        return offset, next_offset - offset

    def subset(self, resolved_glyph_map):
        '''
        Update this table to contain pointers only to the glyphs in
        resolved_glyph_map which must be a map of glyph_ids to (offset, sz)
        '''
        self.offset_map = [0 for i in self.offset_map]
        glyphs = [(glyph_id, x[0], x[1]) for glyph_id, x in
                    resolved_glyph_map.iteritems()]
        glyphs.sort(key=itemgetter(1))
        for glyph_id, offset, sz in glyphs:
            self.offset_map[glyph_id] = offset
            self.offset_map[glyph_id+1] = offset + sz
        # Fix all zero entries to be the same as the previous entry, which
        # means that if the ith entry is zero, the i-1 glyph is not present.
        for i in xrange(1, len(self.offset_map)):
            if self.offset_map[i] == 0:
                self.offset_map[i] = self.offset_map[i-1]

        vals = self.offset_map
        if self.fmt == 'H':
            vals = [i//2 for i in self.offset_map]

        self.raw = pack(('>%d%s'%(len(vals), self.fmt)).encode('ascii'), *vals)

    def dump_glyphs(self, sfnt):
        if not hasattr(self, 'offset_map'):
            self.load_offsets(sfnt[b'head'], sfnt[b'maxp'])
        for i in xrange(len(self.offset_map)-1):
            off, noff = self.offset_map[i], self.offset_map[i+1]
            if noff != off:
                print ('Glyph id:', i, 'size:', noff-off)


