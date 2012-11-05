#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from itertools import izip
from struct import unpack_from, pack

from calibre.utils.fonts.sfnt import UnknownTable, DateTimeProperty

class HeadTable(UnknownTable):

    created = DateTimeProperty('_created')
    modified = DateTimeProperty('_modified')

    def __init__(self, *args, **kwargs):
        super(HeadTable, self).__init__(*args, **kwargs)

        field_types = (
                'version_number' , 'L',
                'font_revision'  , 'L',
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


