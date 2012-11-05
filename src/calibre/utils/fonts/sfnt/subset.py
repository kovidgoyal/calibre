#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.utils.fonts.sfnt.container import Sfnt
from calibre.utils.fonts.sfnt.errors import UnsupportedFont

def subset_truetype(sfnt, character_map):
    loca = sfnt[b'loca']
    try:
        head, maxp = sfnt[b'head'], sfnt[b'maxp']
    except KeyError:
        raise UnsupportedFont('This font does not contain head and/or maxp tables')
    loca.load_offsets(head, maxp)

def subset(raw, individual_chars, ranges=()):
    chars = list(map(ord, individual_chars))
    for r in ranges:
        chars += list(xrange(ord(r[0]), ord(r[1])+1))

    sfnt = Sfnt(raw)
    # Remove the Digital Signature table since it is useless in a subset
    # font anyway
    sfnt.pop(b'DSIG', None)

    try:
        cmap = sfnt[b'cmap']
    except KeyError:
        raise UnsupportedFont('This font has no cmap table')

    # Get mapping of chars to glyph ids for all specified chars
    character_map = cmap.get_character_map(chars)
    # Restrict the cmap table to only contain entries for the specified chars
    cmap.set_character_map(character_map)

    if b'loca' in sfnt and b'glyf' in sfnt:
        subset_truetype(sfnt, character_map)
    elif b'CFF ' in sfnt:
        raise UnsupportedFont('This font contains PostScript outlines, '
                'subsetting not supported')
    else:
        raise UnsupportedFont('This font does not contain TrueType '
                'or PostScript outlines')


