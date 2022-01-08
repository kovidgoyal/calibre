#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from, pack

from calibre.utils.fonts.sfnt import UnknownTable, FixedProperty
from calibre.utils.fonts.sfnt.errors import UnsupportedFont


class MaxpTable(UnknownTable):

    version = FixedProperty('_version')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._fmt = b'>lH'
        self._version, self.num_glyphs = unpack_from(self._fmt, self.raw)
        self.fields = ('_version', 'num_glyphs')

        if self.version > 1.0:
            raise UnsupportedFont('This font has a maxp table with version: %s'
                    %self.version)
        if self.version == 1.0:
            self.fields = ('_version', 'num_glyphs', 'max_points',
                    'max_contours', 'max_composite_points',
                    'max_composite_contours', 'max_zones',
                    'max_twilight_points', 'max_storage', 'max_function_defs',
                    'max_instruction_defs', 'max_stack_elements',
                    'max_size_of_instructions', 'max_component_elements',
                    'max_component_depth')
            self._fmt = b'>lH' + b'H'*(len(self.fields)-2)

            vals = unpack_from(self._fmt, self.raw)
            for f, val in zip(self.fields, vals):
                setattr(self, f, val)

    def update(self):
        vals = [getattr(self, f) for f in self.fields]
        self.raw = pack(self._fmt, *vals)
