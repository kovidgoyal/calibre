#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from itertools import izip
from struct import unpack_from, pack

from calibre.utils.fonts.sfnt import UnknownTable, DateTimeProperty, FixedProperty
from calibre.utils.fonts.sfnt.errors import UnsupportedFont

class HeadTable(UnknownTable):

    created = DateTimeProperty('_created')
    modified = DateTimeProperty('_modified')
    version_number = FixedProperty('_version_number')
    font_revision = FixedProperty('_font_revision')

    def __init__(self, *args, **kwargs):
        super(HeadTable, self).__init__(*args, **kwargs)

        field_types = (
                '_version_number' , 'l',
                '_font_revision'  , 'l',
                'checksum_adjustment' , 'L',
                'magic_number' , 'L',
                'flags' , 'H',
                'units_per_em' , 'H',
                '_created' , 'q',
                '_modified' , 'q',
                'x_min' , 'H',
                'y_min' , 'H',
                'x_max' , 'H',
                'y_max' , 'H',
                'mac_style' , 'H',
                'lowest_rec_ppem' , 'H',
                'font_direction_hint' , 'h',
                'index_to_loc_format' , 'h',
                'glyph_data_format'   , 'h'
        )

        self._fmt = ('>%s'%(''.join(field_types[1::2]))).encode('ascii')
        self._fields = field_types[0::2]

        for f, val in izip(self._fields, unpack_from(self._fmt, self.raw)):
            setattr(self, f, val)

    def update(self):
        vals = [getattr(self, f) for f in self._fields]
        self.raw = pack(self._fmt, *vals)

class HorizontalHeader(UnknownTable):

    version_number = FixedProperty('_version_number')

    def read_data(self, hmtx):
        if hasattr(self, 'ascender'): return
        field_types = (
            '_version_number' , 'l',
            'ascender', 'h',
            'descender', 'h',
            'line_gap', 'h',
            'advance_width_max', 'H',
            'min_left_size_bearing', 'h',
            'min_right_side_bearing', 'h',
            'x_max_extent', 'h',
            'caret_slope_rise', 'h',
            'caret_slop_run', 'h',
            'caret_offset', 'h',
            'r1', 'h',
            'r2', 'h',
            'r3', 'h',
            'r4', 'h',
            'metric_data_format', 'h',
            'number_of_h_metrics', 'H',
        )

        self._fmt = ('>%s'%(''.join(field_types[1::2]))).encode('ascii')
        self._fields = field_types[0::2]

        for f, val in izip(self._fields, unpack_from(self._fmt, self.raw)):
            setattr(self, f, val)

        raw = hmtx.raw
        num = self.number_of_h_metrics
        if len(raw) < 4*num:
            raise UnsupportedFont('The hmtx table has insufficient data')
        long_hor_metric = raw[:4*num]
        fmt = '>%dH'%(2*num)
        entries = unpack_from(fmt.encode('ascii'), long_hor_metric)
        self.advance_widths = entries[0::2]
        fmt = '>%dh'%(2*num)
        entries = unpack_from(fmt.encode('ascii'), long_hor_metric)
        self.left_side_bearings = entries[1::2]

class OS2Table(UnknownTable):

    version_number = FixedProperty('_version')

    def read_data(self):
        if hasattr(self, 'char_width'): return
        from calibre.utils.fonts.utils import get_font_characteristics
        vals = get_font_characteristics(self.raw, raw_is_table=True,
                                        return_all=True)
        for i, attr in enumerate((
            '_version', 'char_width', 'weight', 'width', 'fs_type',
            'subscript_x_size', 'subscript_y_size', 'subscript_x_offset',
            'subscript_y_offset', 'superscript_x_size', 'superscript_y_size',
            'superscript_x_offset', 'superscript_y_offset', 'strikeout_size',
            'strikeout_position', 'family_class', 'panose', 'selection',
            'is_italic', 'is_bold', 'is_regular')):
            setattr(self, attr, vals[i])

class PostTable(UnknownTable):

    version_number = FixedProperty('_version')
    italic_angle = FixedProperty('_italic_angle')

    def read_data(self):
        if hasattr(self, 'underline_position'): return
        (self._version, self._italic_angle, self.underline_position,
         self.underline_thickness) = unpack_from(b'>llhh', self.raw)

