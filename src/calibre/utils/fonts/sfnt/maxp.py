#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from itertools import izip
from struct import unpack_from, pack

from calibre.utils.fonts.sfnt import UnknownTable
from calibre.utils.fonts.sfnt.errors import UnsupportedFont

class MaxpTable(UnknownTable):

    def __init__(self, *args, **kwargs):
        super(MaxpTable, self).__init__(*args, **kwargs)

        self._fmt = b'>LH'
        self._version, self.num_glyphs = unpack_from(self._fmt, self.raw)
        self.fields = ('_version', 'num_glyphs')

        if self._version >= 0x10000:
            self.version = 0x10000
            vals = unpack_from(self._fmt, self.raw)
            for f, val in izip(self.fields, vals):
                setattr(self, f, val)

    @dynamic_property
    def version(self):
        def fget(self):
            return self._version
        def fset(self, val):
            if val == 0x5000:
                self._fmt = b'>LH'
                self._fields = ('_version', 'num_glyphs')
            elif val == 0x10000:
                self.fields = ('_version', 'num_glyphs', 'max_points',
                        'max_contours', 'max_composite_points',
                        'max_composite_contours', 'max_zones',
                        'max_twilight_points', 'max_storage', 'max_function_defs',
                        'max_instruction_defs', 'max_stack_elements',
                        'max_size_of_instructions', 'max_component_elements',
                        'max_component_depth')
                self._fmt = b'>LH' + b'H'*(len(self.fields)-2)
            self._version = val
        return property(fget=fget, fset=fset)

    def update(self):
        if self._version > 0x10000:
            raise UnsupportedFont('maxp table with version > 0x10000 not modifiable')
        vals = [getattr(self, f) for f in self._fields]
        self.raw = pack(self._fmt, *vals)



