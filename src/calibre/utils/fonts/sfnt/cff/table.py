#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from, unpack, calcsize
from functools import partial

from calibre.utils.fonts.sfnt import UnknownTable
from calibre.utils.fonts.sfnt.errors import UnsupportedFont, NoGlyphs
from calibre.utils.fonts.sfnt.cff.dict_data import TopDict, PrivateDict
from calibre.utils.fonts.sfnt.cff.constants import (cff_standard_strings,
        STANDARD_CHARSETS)
from polyglot.builtins import iteritems, itervalues

# Useful links
# http://www.adobe.com/content/dam/Adobe/en/devnet/font/pdfs/5176.CFF.pdf
# http://www.adobe.com/content/dam/Adobe/en/devnet/font/pdfs/5177.Type2.pdf


class CFF:

    def __init__(self, raw):
        (self.major_version, self.minor_version, self.header_size,
                self.offset_size) = unpack_from(b'>4B', raw)
        if (self.major_version, self.minor_version) != (1, 0):
            raise UnsupportedFont('The CFF table has unknown version: '
                    '(%d, %d)'%(self.major_version, self.minor_version))
        offset = self.header_size

        # Read Names Index
        self.font_names = Index(raw, offset)
        offset = self.font_names.pos
        if len(self.font_names) > 1:
            raise UnsupportedFont('CFF table has more than one font.')

        # Read Top Dict
        self.top_index = Index(raw, offset)
        self.top_dict = TopDict()
        offset = self.top_index.pos

        # Read strings
        self.strings = Strings(raw, offset)
        offset = self.strings.pos

        # Read global subroutines
        self.global_subrs = Subrs(raw, offset)
        offset = self.global_subrs.pos

        # Decompile Top Dict
        self.top_dict.decompile(self.strings, self.global_subrs, self.top_index[0])
        self.is_CID = 'ROS' in self.top_dict
        if self.is_CID:
            raise UnsupportedFont('Subsetting of CID keyed fonts is not supported')

        # Read CharStrings (Glyph definitions)
        try:
            offset = self.top_dict['CharStrings']
        except KeyError:
            raise ValueError('This font has no CharStrings')
        cs_type = self.top_dict.safe_get('CharstringType')
        if cs_type != 2:
            raise UnsupportedFont('This font has unsupported CharstringType: '
                    '%s'%cs_type)
        self.char_strings = CharStringsIndex(raw, offset)
        self.num_glyphs = len(self.char_strings)

        # Read Private Dict
        self.private_dict = self.private_subrs = None
        pd = self.top_dict.safe_get('Private')
        if pd:
            size, offset = pd
            self.private_dict = PrivateDict()
            self.private_dict.decompile(self.strings, self.global_subrs,
                    raw[offset:offset+size])
            if 'Subrs' in self.private_dict:
                self.private_subrs = Subrs(raw, offset +
                        self.private_dict['Subrs'])

        # Read charset (Glyph names)
        self.charset = Charset(raw, self.top_dict.safe_get('charset'),
                self.strings, self.num_glyphs, self.is_CID)

        # import pprint
        # pprint.pprint(self.top_dict)
        # pprint.pprint(self.private_dict)


class Index(list):

    def __init__(self, raw, offset, prepend=()):
        list.__init__(self)
        self.extend(prepend)

        count = unpack_from(b'>H', raw, offset)[0]
        offset += 2
        self.pos = offset

        if count > 0:
            self.offset_size = unpack_from(b'>B', raw, offset)[0]
            offset += 1
            if self.offset_size == 3:
                offsets = [unpack(b'>L', b'\0' + raw[i:i+3])[0]
                            for i in range(offset, offset+3*(count+1), 3)]
            else:
                fmt = {1:'B', 2:'H', 4:'L'}[self.offset_size]
                fmt = ('>%d%s'%(count+1, fmt)).encode('ascii')
                offsets = unpack_from(fmt, raw, offset)
            offset += self.offset_size * (count+1) - 1

            for i in range(len(offsets)-1):
                off, noff = offsets[i:i+2]
                obj = raw[offset+off:offset+noff]
                self.append(obj)

            try:
                self.pos = offset + offsets[-1]
            except IndexError:
                self.pos = offset


class Strings(Index):

    def __init__(self, raw, offset):
        super().__init__(raw, offset, prepend=[x.encode('ascii')
            for x in cff_standard_strings])


class Charset(list):

    def __init__(self, raw, offset, strings, num_glyphs, is_CID):
        super().__init__()
        self.standard_charset = offset if offset in {0, 1, 2} else None
        if is_CID and self.standard_charset is not None:
            raise ValueError("CID font must not use a standard charset")
        if self.standard_charset is None:
            self.append(b'.notdef')
            fmt = unpack_from(b'>B', raw, offset)[0]
            offset += 1
            f = {0:self.parse_fmt0, 1:self.parse_fmt1,
                2:partial(self.parse_fmt1, is_two_byte=True)}.get(fmt, None)
            if f is None:
                raise UnsupportedFont('This font uses unsupported charset '
                        'table format: %d'%fmt)
            f(raw, offset, strings, num_glyphs, is_CID)

    def parse_fmt0(self, raw, offset, strings, num_glyphs, is_CID):
        fmt = ('>%dH'%(num_glyphs-1)).encode('ascii')
        ids = unpack_from(fmt, raw, offset)
        if is_CID:
            ids = ('cid%05d'%x for x in ids)
        else:
            ids = (strings[x] for x in ids)
        self.extend(ids)

    def parse_fmt1(self, raw, offset, strings, num_glyphs, is_CID,
            is_two_byte=False):
        fmt = b'>2H' if is_two_byte else b'>HB'
        sz = calcsize(fmt)
        count = 1
        while count < num_glyphs:
            first, nleft = unpack_from(fmt, raw, offset)
            offset += sz
            count += nleft + 1
            self.extend('cid%05d'%x if is_CID else strings[x] for x in
                    range(first, first + nleft+1))

    def lookup(self, glyph_id):
        if self.standard_charset is None:
            return self[glyph_id]
        return STANDARD_CHARSETS[self.standard_charset][glyph_id].encode('ascii')

    def safe_lookup(self, glyph_id):
        try:
            return self.lookup(glyph_id)
        except (KeyError, IndexError, ValueError):
            return None


class Subrs(Index):
    pass


class CharStringsIndex(Index):
    pass


class CFFTable(UnknownTable):

    def decompile(self):
        self.cff = CFF(self.raw)

    def subset(self, character_map, extra_glyphs):
        from calibre.utils.fonts.sfnt.cff.writer import Subset
        # Map codes from the cmap table to glyph names, this will be used to
        # reconstruct character_map for the subset font
        charset_map = {code:self.cff.charset.safe_lookup(glyph_id) for code,
                glyph_id in iteritems(character_map)}
        charset = set(itervalues(charset_map))
        charset.discard(None)
        if not charset and character_map:
            raise NoGlyphs('This font has no glyphs for the specified characters')
        charset |= {
            self.cff.charset.safe_lookup(glyph_id) for glyph_id in extra_glyphs}
        charset.discard(None)
        s = Subset(self.cff, charset)

        # Rebuild character_map with the glyph ids from the subset font
        character_map.clear()
        for code, charname in iteritems(charset_map):
            glyph_id = s.charname_map.get(charname, None)
            if glyph_id:
                character_map[code] = glyph_id

        # Check that raw is parseable
        CFF(s.raw)

        self.raw = s.raw
