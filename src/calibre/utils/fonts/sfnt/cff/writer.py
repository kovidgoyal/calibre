#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import pack
from collections import OrderedDict

class Index(list):

    def __init__(self):
        list.__init__(self)
        self.raw = None

    def calcsize(self, largest_offset):
        if largest_offset < 0x100:
            return 1
        elif largest_offset < 0x10000:
            return 2
        elif largest_offset < 0x1000000:
            return 3
        return 4

    def compile(self):
        if len(self) == 0:
            self.raw = pack(b'>H', 0)
        else:
            offsets = [1]
            for i, obj in enumerate(self):
                offsets.append(offsets[-1] + len(obj))
            offsize = self.calcsize(offsets[-1])
            obj_data = b''.join(self)
            prefix = pack(b'>HB', len(self), offsize)

            if offsize == 3:
                offsets = b''.join(pack(b'>L', x)[1:] for x in offsets)
            else:
                fmt = {1:'B', 2:'H', 4:'L'}[offsize]
                offsets = pack( ('>%d%s'%(len(self), fmt)).encode('ascii'),
                        *offsets)

            self.raw = prefix + offsets + obj_data
        return self.raw


class Subset(object):

    def __init__(self, cff, keep_charnames):
        self.cff = cff
        self.keep_charnames = keep_charnames

        # Font names Index
        font_names = Index()
        font_names.extend(self.cff.font_names)

        # CharStrings Index
        char_strings = Index()
        self.charname_map = OrderedDict()

        for i in xrange(self.cff.num_glyphs):
            cname = self.cff.charset.safe_lookup(i)
            if cname in keep_charnames:
                char_strings.append(self.cff.char_strings[i])
                self.charname_map[cname] = i

        char_strings.compile()

