#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import random
from io import BytesIO
from collections import OrderedDict
from struct import pack

from calibre.ebooks.mobi.utils import align_block

NULL = 0xffffffff
zeroes = lambda x: b'\0'*x
nulls = lambda x: b'\xff'*x
short = lambda x: pack(b'>H', x)

class Header(OrderedDict):

    HEADER_NAME = b''

    DEFINITION = '''
    '''

    ALIGN_BLOCK = False
    POSITIONS = {}  # Mapping of position field to field whose position should
                    # be stored in the position field
    SHORT_FIELDS = set()

    def __init__(self):
        OrderedDict.__init__(self)

        for line in self.DEFINITION.splitlines():
            line = line.strip()
            if not line or line.startswith('#'): continue
            name, val = [x.strip() for x in line.partition('=')[0::2]]
            if val:
                val = eval(val, {'zeroes':zeroes, 'NULL':NULL, 'DYN':None,
                    'nulls':nulls, 'short':short, 'random':random})
            else:
                val = 0
            if name in self:
                raise ValueError('Duplicate field in definition: %r'%name)
            self[name] = val

    @property
    def dynamic_fields(self):
        return tuple(k for k, v in self.iteritems() if v is None)

    def __call__(self, **kwargs):
        positions = {}
        for name, val in kwargs.iteritems():
            if name not in self:
                raise KeyError('Not a valid header field: %r'%name)
            self[name] = val

        buf = BytesIO()
        buf.write(bytes(self.HEADER_NAME))
        for name, val in self.iteritems():
            val = self.format_value(name, val)
            positions[name] = buf.tell()
            if val is None:
                raise ValueError('Dynamic field %r not set'%name)
            if isinstance(val, (int, long)):
                fmt = 'H' if name in self.SHORT_FIELDS else 'I'
                val = pack(b'>'+fmt, val)
            buf.write(val)

        for pos_field, field in self.POSITIONS.iteritems():
            buf.seek(positions[pos_field])
            buf.write(pack(b'>I', positions[field]))

        ans = buf.getvalue()
        if self.ALIGN_BLOCK:
            ans = align_block(ans)
        return ans


    def format_value(self, name, val):
        return val


