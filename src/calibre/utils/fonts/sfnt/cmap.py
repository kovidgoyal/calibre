#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

# Note that the code for creating a BMP table (cmap format 4) is taken with
# thanks from the fonttools project (BSD licensed).

from struct import unpack_from, calcsize, pack
from collections import OrderedDict

from calibre.utils.fonts.utils import get_bmp_glyph_ids, read_bmp_prefix
from calibre.utils.fonts.sfnt import UnknownTable, max_power_of_two
from calibre.utils.fonts.sfnt.errors import UnsupportedFont

def split_range(start_code, end_code, cmap): # {{{
	# Try to split a range of character codes into subranges with consecutive
	# glyph IDs in such a way that the cmap4 subtable can be stored "most"
	# efficiently.
	if start_code == end_code:
		return [], [end_code]

	last_id = cmap[start_code]
	last_code = start_code
	in_order = None
	ordered_begin = None
	sub_ranges = []

	# Gather subranges in which the glyph IDs are consecutive.
	for code in range(start_code + 1, end_code + 1):
		glyph_id = cmap[code]

		if glyph_id - 1 == last_id:
			if in_order is None or not in_order:
				in_order = 1
				ordered_begin = last_code
		else:
			if in_order:
				in_order = 0
				sub_ranges.append((ordered_begin, last_code))
				ordered_begin = None

		last_id = glyph_id
		last_code = code

	if in_order:
		sub_ranges.append((ordered_begin, last_code))
	assert last_code == end_code

	# Now filter out those new subranges that would only make the data bigger.
	# A new segment cost 8 bytes, not using a new segment costs 2 bytes per
	# character.
	new_ranges = []
	for b, e in sub_ranges:
		if b == start_code and e == end_code:
			break  # the whole range, we're fine
		if b == start_code or e == end_code:
			threshold = 4  # split costs one more segment
		else:
			threshold = 8  # split costs two more segments
		if (e - b + 1) > threshold:
			new_ranges.append((b, e))
	sub_ranges = new_ranges

	if not sub_ranges:
		return [], [end_code]

	if sub_ranges[0][0] != start_code:
		sub_ranges.insert(0, (start_code, sub_ranges[0][0] - 1))
	if sub_ranges[-1][1] != end_code:
		sub_ranges.append((sub_ranges[-1][1] + 1, end_code))

	# Fill the "holes" in the segments list -- those are the segments in which
	# the glyph IDs are _not_ consecutive.
	i = 1
	while i < len(sub_ranges):
		if sub_ranges[i-1][1] + 1 != sub_ranges[i][0]:
			sub_ranges.insert(i, (sub_ranges[i-1][1] + 1, sub_ranges[i][0] - 1))
			i = i + 1
		i = i + 1

	# Transform the ranges into start_code/end_code lists.
	start = []
	end = []
	for b, e in sub_ranges:
		start.append(b)
		end.append(e)
	start.pop(0)

	assert len(start) + 1 == len(end)
	return start, end
# }}}

def set_id_delta(id_delta): # {{{
    # The lowest gid in glyphIndexArray, after subtracting id_delta, must be 1.
    # id_delta is a short, and must be between -32K and 32K
    # startCode can be between 0 and 64K-1, and the first glyph index can be between 1 and 64K-1
    # This means that we have a problem because we can need to assign to
    # id_delta values
    # between -(64K-2) and 64K -1.
    # Since the final gi is reconstructed from the glyphArray GID by:
    #    (short)finalGID = (gid +  id_delta) % 0x10000),
    # we can get from a startCode of 0 to a final GID of 64 -1K by subtracting 1, and casting the
    # negative number to an unsigned short.
    # Similarly , we can get from a startCode of 64K-1 to a final GID of 1 by adding 2, because of
    # the modulo arithmetic.

    if id_delta > 0x7FFF:
        id_delta = id_delta - 0x10000
    elif id_delta <  -0x7FFF:
        id_delta = id_delta + 0x10000

    return id_delta
# }}}

class CmapTable(UnknownTable):

    def __init__(self, *args, **kwargs):
        super(CmapTable, self).__init__(*args, **kwargs)

        self.version, self.num_tables = unpack_from(b'>HH', self.raw)

        self.tables = {}

        offset = 4
        sz = calcsize(b'>HHL')
        recs = []
        for i in xrange(self.num_tables):
            platform, encoding, table_offset = unpack_from(b'>HHL', self.raw,
                    offset)
            offset += sz
            recs.append((platform, encoding, table_offset))

        self.bmp_table = None

        for i in xrange(len(recs)):
            platform, encoding, offset = recs[i]
            try:
                next_offset = recs[i+1][-1]
            except IndexError:
                next_offset = len(self.raw)
            table = self.raw[offset:next_offset]
            if table:
                fmt = unpack_from(b'>H', table)[0]
                if platform == 3 and encoding == 1 and fmt == 4:
                    self.bmp_table = table

    def get_character_map(self, chars):
        '''
        Get a mapping of character codes to glyph ids in the font.
        '''
        if self.bmp_table is None:
            raise UnsupportedFont('This font has no Windows BMP cmap subtable.'
                    ' Most likely a special purpose font.')
        chars = list(set(chars))
        chars.sort()
        ans = OrderedDict()
        for i, glyph_id in enumerate(get_bmp_glyph_ids(self.bmp_table, 0,
            chars)):
            if glyph_id > 0:
                ans[chars[i]] = glyph_id
        return ans

    def get_char_codes(self, glyph_ids):
        if self.bmp_table is None:
            raise UnsupportedFont('This font has no Windows BMP cmap subtable.'
                    ' Most likely a special purpose font.')
        ans = {}
        (start_count, end_count, range_offset, id_delta, glyph_id_len,
        glyph_id_map, array_len) = read_bmp_prefix(self.bmp_table, 0)

        glyph_ids = frozenset(glyph_ids)

        for i, ec in enumerate(end_count):
            sc = start_count[i]
            ro = range_offset[i]
            for code in xrange(sc, ec+1):
                if ro == 0:
                    glyph_id = id_delta[i] + code
                else:
                    idx = ro//2 + (code - sc) + i - array_len
                    glyph_id = glyph_id_map[idx]
                    if glyph_id != 0:
                        glyph_id += id_delta[i]
                glyph_id %= 0x1000
                if glyph_id in glyph_ids:
                    ans[glyph_id] = code

        return ans

    def set_character_map(self, cmap):
        self.version, self.num_tables = 0, 1
        fmt = b'>7H'
        codes = list(cmap.iterkeys())
        codes.sort()

        if not codes:
            start_code = [0xffff]
            end_code = [0xffff]
        else:
            last_code = codes[0]
            end_code = []
            start_code = [last_code]

            for code in codes[1:]:
				if code == last_code + 1:
					last_code = code
					continue
				start, end = split_range(start_code[-1], last_code, cmap)
				start_code.extend(start)
				end_code.extend(end)
				start_code.append(code)
				last_code = code
			end_code.append(last_code)
			start_code.append(0xffff)
			end_code.append(0xffff)

		id_delta = []
		id_range_offset = []
		glyph_index_array = []
		for i in xrange(len(end_code)-1):  # skip the closing codes (0xffff)
			indices = []
			for char_code in xrange(start_code[i], end_code[i] + 1):
				indices.append(cmap[char_code])
			if  (indices == xrange(indices[0], indices[0] + len(indices))):
				id_delta_temp = set_id_delta(indices[0] - start_code[i])
				id_delta.append(id_delta_temp)
				id_range_offset.append(0)
			else:
				id_delta.append(0)
				id_range_offset.append(2 * (len(end_code) +
                    len(glyph_index_array) - i))
				glyph_index_array.extend(indices)
		id_delta.append(1)  # 0xffff + 1 == 0. So this end code maps to .notdef
		id_range_offset.append(0)

		seg_count = len(end_code)
		max_exponent = max_power_of_two(seg_count)
		search_range = 2 * (2 ** max_exponent)
		entry_selector = max_exponent
		range_shift = 2 * seg_count - search_range

        char_code_array = end_code + [0] + start_code
		char_code_array = pack(b'>%dH'%len(char_code_array), *char_code_array)
		id_delta_array = pack(b'>%dh'%len(id_delta), *id_delta)
        rest_array = id_range_offset + glyph_index_array
        rest_array = pack(b'>%dH'%len(rest_array), *rest_array)
		data = char_code_array + id_delta_array + rest_array

		length = calcsize(fmt) + len(data)
		header = pack(fmt, 4, length, 0,
				2*seg_count, search_range, entry_selector, range_shift)
		self.bmp_table = header + data

        fmt = b'>4HL'
        offset = calcsize(fmt)
        self.raw = pack(fmt, self.version, self.num_tables, 3, 1, offset) + \
                self.bmp_table

