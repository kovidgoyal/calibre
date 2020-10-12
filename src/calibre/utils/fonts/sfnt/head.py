#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from, pack, calcsize

from calibre.utils.fonts.sfnt import UnknownTable, DateTimeProperty, FixedProperty
from calibre.utils.fonts.sfnt.errors import UnsupportedFont
from calibre.utils.fonts.sfnt.loca import read_array
from polyglot.builtins import zip


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
                'x_min' , 'h',
                'y_min' , 'h',
                'x_max' , 'h',
                'y_max' , 'h',
                'mac_style' , 'H',
                'lowest_rec_ppem' , 'H',
                'font_direction_hint' , 'h',
                'index_to_loc_format' , 'h',
                'glyph_data_format'   , 'h'
        )

        self._fmt = ('>%s'%(''.join(field_types[1::2]))).encode('ascii')
        self._fields = field_types[0::2]

        for f, val in zip(self._fields, unpack_from(self._fmt, self.raw)):
            setattr(self, f, val)

    def update(self):
        vals = [getattr(self, f) for f in self._fields]
        self.raw = pack(self._fmt, *vals)


class HorizontalHeader(UnknownTable):

    version_number = FixedProperty('_version_number')

    def read_data(self, hmtx):
        if hasattr(self, 'ascender'):
            return
        field_types = (
            '_version_number' , 'l',
            'ascender', 'h',
            'descender', 'h',
            'line_gap', 'h',
            'advance_width_max', 'H',
            'min_left_side_bearing', 'h',
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

        for f, val in zip(self._fields, unpack_from(self._fmt, self.raw)):
            setattr(self, f, val)

        raw = hmtx.raw
        num = self.number_of_h_metrics
        if len(raw) < 4*num:
            raise UnsupportedFont('The hmtx table has insufficient data')
        long_hor_metric = raw[:4*num]
        a = read_array(long_hor_metric)
        self.advance_widths = a[0::2]
        a = read_array(long_hor_metric, 'h')
        self.left_side_bearings = a[1::2]


class VerticalHeader(UnknownTable):

    version_number = FixedProperty('_version_number')

    def read_data(self, vmtx):
        if hasattr(self, 'ascender'):
            return
        field_types = (
            '_version_number' , 'l',
            'ascender', 'h',
            'descender', 'h',
            'line_gap', 'h',
            'advance_height_max', 'H',
            'min_top_side_bearing', 'h',
            'min_bottom_side_bearing', 'h',
            'y_max_extent', 'h',
            'caret_slope_rise', 'h',
            'caret_slop_run', 'h',
            'caret_offset', 'h',
            'r1', 'h',
            'r2', 'h',
            'r3', 'h',
            'r4', 'h',
            'metric_data_format', 'h',
            'number_of_v_metrics', 'H',
        )

        self._fmt = ('>%s'%(''.join(field_types[1::2]))).encode('ascii')
        self._fields = field_types[0::2]

        for f, val in zip(self._fields, unpack_from(self._fmt, self.raw)):
            setattr(self, f, val)

        raw = vmtx.raw
        num = self.number_of_v_metrics
        if len(raw) < 4*num:
            raise UnsupportedFont('The vmtx table has insufficient data')
        long_hor_metric = raw[:4*num]
        long_hor_metric = raw[:4*num]
        a = read_array(long_hor_metric)
        self.advance_heights = a[0::2]
        a = read_array(long_hor_metric, 'h')
        self.top_side_bearings = a[1::2]


class OS2Table(UnknownTable):

    def read_data(self):
        if hasattr(self, 'char_width'):
            return
        ver, = unpack_from(b'>H', self.raw)
        field_types = [
            'version' , 'H',
            'average_char_width', 'h',
            'weight_class', 'H',
            'width_class', 'H',
            'fs_type', 'H',
            'subscript_x_size', 'h',
            'subscript_y_size', 'h',
            'subscript_x_offset', 'h',
            'subscript_y_offset', 'h',
            'superscript_x_size', 'h',
            'superscript_y_size', 'h',
            'superscript_x_offset', 'h',
            'superscript_y_offset', 'h',
            'strikeout_size', 'h',
            'strikeout_position', 'h',
            'family_class', 'h',
            'panose', '10s',
            'ranges', '16s',
            'vendor_id', '4s',
            'selection', 'H',
            'first_char_index', 'H',
            'last_char_index', 'H',
            'typo_ascender', 'h',
            'typo_descender', 'h',
            'typo_line_gap', 'h',
            'win_ascent', 'H',
            'win_descent', 'H',
        ]
        if ver > 1:
            field_types += [
                'code_page_range', '8s',
                'x_height', 'h',
                'cap_height', 'h',
                'default_char', 'H',
                'break_char', 'H',
                'max_context', 'H',
            ]

        self._fmt = ('>%s'%(''.join(field_types[1::2]))).encode('ascii')
        self._fields = field_types[0::2]

        for f, val in zip(self._fields, unpack_from(self._fmt, self.raw)):
            setattr(self, f, val)

    def zero_fstype(self):
        prefix = calcsize(b'>HhHH')
        self.raw = self.raw[:prefix] + b'\0\0' + self.raw[prefix+2:]
        self.fs_type = 0


class PostTable(UnknownTable):

    version_number = FixedProperty('_version')
    italic_angle = FixedProperty('_italic_angle')

    def read_data(self):
        if hasattr(self, 'underline_position'):
            return
        (self._version, self._italic_angle, self.underline_position,
         self.underline_thickness) = unpack_from(b'>llhh', self.raw)
