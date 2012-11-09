#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import pack
from collections import OrderedDict

from calibre.utils.fonts.sfnt.cff.constants import cff_standard_strings

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
                offsets = pack( ('>%d%s'%(len(offsets), fmt)).encode('ascii'),
                        *offsets)

            self.raw = prefix + offsets + obj_data
        return self.raw

class Strings(Index):

    def __init__(self):
        Index.__init__(self)
        self.added = {x:i for i, x in enumerate(cff_standard_strings)}

    def __call__(self, x):
        ans = self.added.get(x, None)
        if ans is None:
            ans = len(self) + len(cff_standard_strings)
            self.added[x] = ans
            self.append(x)
        return ans

class Dict(Index):

    def __init__(self, src, strings):
        Index.__init__(self)
        self.src, self.strings = src, strings

    def compile(self):
        self[:] = [self.src.compile(self.strings)]
        Index.compile(self)

class PrivateDict(object):

    def __init__(self, src, subrs, strings):
        self.src, self.strings = src, strings
        self.subrs = None
        if subrs is not None:
            self.subrs = Index()
            self.subrs.extend(subrs)
            self.subrs.compile()

    def compile(self):
        raw = self.src.compile(self.strings)
        if self.subrs is not None:
            self.src['Subrs'] = len(raw)
            raw = self.src.compile(self.strings)
        self.raw = raw
        return raw

class Charsets(list):

    def __init__(self, strings):
        list.__init__(self)
        self.strings = strings

    def compile(self):
        ans = pack(b'>B', 0)
        sids = [self.strings(x) for x in self]
        ans += pack(('>%dH'%len(self)).encode('ascii'), *sids)
        self.raw = ans
        return ans

class Subset(object):

    def __init__(self, cff, keep_charnames):
        self.cff = cff
        keep_charnames.add(b'.notdef')

        header = pack(b'>4B', 1, 0, 4, cff.offset_size)

        # Font names Index
        font_names = Index()
        font_names.extend(self.cff.font_names)

        # Strings Index
        strings = Strings()

        # CharStrings Index and charsets
        char_strings = Index()
        self.charname_map = OrderedDict()
        charsets = Charsets(strings)

        for i in xrange(self.cff.num_glyphs):
            cname = self.cff.charset.safe_lookup(i)
            if cname in keep_charnames:
                char_strings.append(self.cff.char_strings[i])
                self.charname_map[cname] = len(self.charname_map)
                if i > 0: # .notdef is not included
                    charsets.append(cname)

        # Add the strings
        char_strings.compile()
        charsets.compile()

        # Global subroutines
        global_subrs = Index()
        global_subrs.extend(cff.global_subrs)
        global_subrs.compile()

        # TOP DICT
        top_dict = Dict(cff.top_dict, strings)
        top_dict.compile() # Add strings

        private_dict = None
        if cff.private_dict is not None:
            private_dict = PrivateDict(cff.private_dict, cff.private_subrs,
                    strings)
            private_dict.compile() # Add strings

        fixed_prefix = header + font_names.compile()

        t = top_dict.src
        # Put in dummy offsets
        t['charset'] = 1
        t['CharStrings'] = 1
        if private_dict is not None:
            t['Private'] = (len(private_dict.raw), 1)
        top_dict.compile()

        strings.compile()

        # Calculate real offsets
        pos = len(fixed_prefix)
        pos += len(top_dict.raw)
        pos += len(strings.raw)
        pos += len(global_subrs.raw)
        t['charset'] = pos
        pos += len(charsets.raw)
        t['CharStrings'] = pos
        pos += len(char_strings.raw)
        if private_dict is not None:
            t['Private'] = (len(private_dict.raw), pos)
        top_dict.compile()

        self.raw = (fixed_prefix + top_dict.raw + strings.raw +
                global_subrs.raw + charsets.raw + char_strings.raw)
        if private_dict is not None:
            self.raw += private_dict.raw
            if private_dict.subrs is not None:
                self.raw += private_dict.subrs.raw


