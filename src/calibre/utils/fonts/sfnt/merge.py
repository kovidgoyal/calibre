#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from collections import OrderedDict
from functools import partial


class GlyphSizeMismatch(ValueError):
    pass


def merge_truetype_fonts_for_pdf(fonts, log=None):
    # only merges the glyf and loca tables, ignoring all other tables
    all_glyphs = {}
    ans = fonts[0]
    for font in fonts:
        loca = font[b'loca']
        glyf = font[b'glyf']
        loca.load_offsets(font[b'head'], font[b'maxp'])
        for glyph_id in range(len(loca.offset_map) - 1):
            offset, sz = loca.glyph_location(glyph_id)
            if sz > 0:
                prev_glyph_data = all_glyphs.get(glyph_id)
                if prev_glyph_data is None:
                    all_glyphs[glyph_id] = glyf.glyph_data(offset, sz, as_raw=True)
                else:
                    if abs(sz - len(prev_glyph_data)) > 8:
                        # raise Exception('Size mismatch for glyph id: {} prev_sz: {} sz: {}'.format(glyph_id, len(prev_glyph_data), sz))
                        if log is not None:
                            log('Size mismatch for glyph id: {} prev_sz: {} sz: {}'.format(glyph_id, len(prev_glyph_data), sz))

    glyf = ans[b'glyf']
    head = ans[b'head']
    loca = ans[b'loca']
    maxp = ans[b'maxp']
    advance_widths = advance_heights = (0,)
    hhea = ans.get(b'hhea')
    if hhea is not None:
        hhea.read_data(ans[b'hmtx'])
        advance_widths = tuple(x/head.units_per_em for x in hhea.advance_widths)
    vhea = ans.get(b'vhea')
    if vhea is not None:
        vhea.read_data(ans[b'vmtx'])
        advance_heights = tuple(x/head.units_per_em for x in vhea.advance_heights)

    def width_for_glyph_id(gid):
        if gid >= len(advance_widths):
            gid = -1
        return advance_widths[gid]

    def height_for_glyph_id(gid):
        if gid >= len(advance_heights):
            gid = -1
        return advance_heights[gid]

    gmap = OrderedDict()
    for glyph_id in sorted(all_glyphs):
        gmap[glyph_id] = partial(all_glyphs.__getitem__, glyph_id)
    offset_map = glyf.update(gmap)
    loca.update(offset_map)
    head.index_to_loc_format = 0 if loca.fmt == 'H' else 1
    head.update()
    maxp.num_glyphs = len(loca.offset_map) - 1
    maxp.update()
    return ans, width_for_glyph_id, height_for_glyph_id
