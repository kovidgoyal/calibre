#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from
from collections import OrderedDict

from calibre.utils.fonts.sfnt import UnknownTable
from polyglot.builtins import iteritems

ARG_1_AND_2_ARE_WORDS      = 0x0001  # if set args are words otherwise they are bytes
ARGS_ARE_XY_VALUES         = 0x0002  # if set args are xy values, otherwise they are points
ROUND_XY_TO_GRID           = 0x0004  # for the xy values if above is true
WE_HAVE_A_SCALE            = 0x0008  # Sx = Sy, otherwise scale == 1.0
NON_OVERLAPPING            = 0x0010  # set to same value for all components (obsolete!)
MORE_COMPONENTS            = 0x0020  # indicates at least one more glyph after this one
WE_HAVE_AN_X_AND_Y_SCALE   = 0x0040  # Sx, Sy
WE_HAVE_A_TWO_BY_TWO       = 0x0080  # t00, t01, t10, t11
WE_HAVE_INSTRUCTIONS       = 0x0100  # instructions follow
USE_MY_METRICS             = 0x0200  # apply these metrics to parent glyph
OVERLAP_COMPOUND           = 0x0400  # used by Apple in GX fonts
SCALED_COMPONENT_OFFSET    = 0x0800  # composite designed to have the component offset scaled (designed for Apple)
UNSCALED_COMPONENT_OFFSET  = 0x1000  # composite designed not to have the component offset scaled (designed for MS)


class SimpleGlyph(object):

    def __init__(self, num_of_countours, raw):
        self.num_of_countours = num_of_countours
        self.raw = raw
        # The list of glyph indices referred to by this glyph, will always be
        # empty for a simple glyph and not empty for a composite glyph
        self.glyph_indices = []
        self.is_composite = False

    def __len__(self):
        return len(self.raw)

    def __call__(self):
        return self.raw


class CompositeGlyph(SimpleGlyph):

    def __init__(self, num_of_countours, raw):
        super(CompositeGlyph, self).__init__(num_of_countours, raw)
        self.is_composite = True

        flags = MORE_COMPONENTS
        offset = 10
        while flags & MORE_COMPONENTS:
            flags, glyph_index = unpack_from(b'>HH', raw, offset)
            self.glyph_indices.append(glyph_index)
            offset += 4
            if flags & ARG_1_AND_2_ARE_WORDS:
                offset += 4
            else:
                offset += 2
            if flags & WE_HAVE_A_SCALE:
                offset += 2
            elif flags & WE_HAVE_AN_X_AND_Y_SCALE:
                offset += 4
            elif flags & WE_HAVE_A_TWO_BY_TWO:
                offset += 8


class GlyfTable(UnknownTable):

    def glyph_data(self, offset, length, as_raw=False):
        raw = self.raw[offset:offset+length]
        if as_raw:
            return raw
        num_of_countours = unpack_from(b'>h', raw)[0] if raw else 0
        if num_of_countours >= 0:
            return SimpleGlyph(num_of_countours, raw)
        return CompositeGlyph(num_of_countours, raw)

    def update(self, sorted_glyph_map):
        ans = OrderedDict()
        offset = 0
        block = []
        for glyph_id, glyph in iteritems(sorted_glyph_map):
            raw = glyph()
            pad = 4 - (len(raw) % 4)
            if pad < 4:
                raw += b'\0' * pad
            ans[glyph_id] = offset, len(raw)
            offset += len(raw)
            block.append(raw)
        self.raw = b''.join(block)
        return ans
