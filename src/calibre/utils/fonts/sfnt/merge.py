#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from collections import OrderedDict
from functools import partial


class GlyphSizeMismatch(ValueError):
    pass


def merge_truetype_fonts_for_pdf(fonts, log=None):
    all_glyphs = {}
    ans = fonts[0]
    hmetrics_map = {}
    vmetrics_map = {}

    for font in fonts:
        loca = font[b'loca']
        glyf = font[b'glyf']
        num_glyphs = font[b'maxp'].num_glyphs
        loca.load_offsets(font[b'head'], font[b'maxp'])
        try:
            hhea = font[b'hhea']
        except KeyError:
            hhea = None
        else:
            hhea.read_data(font[b'hmtx'], num_glyphs)
        try:
            vhea = font[b'vhea']
        except KeyError:
            vhea = None
        else:
            vhea.read_data(font[b'vmtx'], num_glyphs)

        for glyph_id in range(len(loca.offset_map) - 1):
            offset, sz = loca.glyph_location(glyph_id)
            prev_glyph_data = all_glyphs.get(glyph_id)
            if not prev_glyph_data:
                all_glyphs[glyph_id] = glyf.glyph_data(offset, sz, as_raw=True)
                if hhea is not None:
                    hmetrics_map[glyph_id] = hhea.metrics_for(glyph_id)
                if vhea is not None:
                    vmetrics_map[glyph_id] = vhea.metrics_for(glyph_id)
            elif sz > 0:
                if abs(sz - len(prev_glyph_data)) > 8:
                    # raise Exception('Size mismatch for glyph id: {} prev_sz: {} sz: {}'.format(glyph_id, len(prev_glyph_data), sz))
                    if log is not None:
                        log(f'Size mismatch for glyph id: {glyph_id} prev_sz: {len(prev_glyph_data)} sz: {sz}')
                if hhea is not None:
                    m = hhea.metrics_for(glyph_id)
                    if m != hmetrics_map[glyph_id]:
                        log(f'Metrics mismatch for glyph id: {glyph_id} prev: {hmetrics_map[glyph_id]} cur: {m}')
                if vhea is not None:
                    m = vhea.metrics_for(glyph_id)
                    if m != vmetrics_map[glyph_id]:
                        log(f'Metrics mismatch for glyph id: {glyph_id} prev: {vmetrics_map[glyph_id]} cur: {m}')

    glyf = ans[b'glyf']
    head = ans[b'head']
    loca = ans[b'loca']
    maxp = ans[b'maxp']

    gmap = OrderedDict()
    for glyph_id in sorted(all_glyphs):
        gmap[glyph_id] = partial(all_glyphs.__getitem__, glyph_id)
    offset_map = glyf.update(gmap)
    loca.update(offset_map)
    head.index_to_loc_format = 0 if loca.fmt == 'H' else 1
    head.update()
    maxp.num_glyphs = len(loca.offset_map) - 1
    maxp.update()
    if hmetrics_map:
        ans[b'hhea'].update(hmetrics_map, ans[b'hmtx'])
    if vmetrics_map:
        ans[b'vhea'].update(vmetrics_map, ans[b'vmtx'])

    for name in 'hdmx GPOS GSUB'.split():
        ans.pop(name.encode('ascii'), None)
    return ans
