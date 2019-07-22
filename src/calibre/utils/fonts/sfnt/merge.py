#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from collections import OrderedDict
from functools import partial


def merge_truetype_fonts_for_pdf(*fonts):
    # only merges the glyf and loca tables, ignoring all other tables
    all_glyphs = {}
    for font in fonts:
        loca = font[b'loca']
        glyf = font[b'glyf']
        loca.load_offsets(font[b'head'], font[b'maxp'])
        for glyph_id in range(len(loca.offset_map) - 1):
            if glyph_id not in all_glyphs:
                offset, sz = loca.glyph_location(glyph_id)
                if sz > 0:
                    all_glyphs[glyph_id] = glyf.glyph_data(offset, sz, as_raw=True)

    ans = fonts[0]
    loca = ans[b'loca']
    glyf = ans[b'glyf']
    gmap = OrderedDict()
    for glyph_id in sorted(all_glyphs):
        gmap[glyph_id] = partial(all_glyphs.__getitem__, glyph_id)
    offset_map = glyf.update(gmap)
    loca.update(offset_map)
    return ans
