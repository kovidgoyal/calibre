#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from, unpack, calcsize
from functools import partial

from calibre.utils.fonts.sfnt import UnknownTable
from calibre.utils.fonts.sfnt.errors import UnsupportedFont
from calibre.utils.fonts.sfnt.cff.dict_data import TopDict, PrivateDict

# Useful links
# http://www.adobe.com/content/dam/Adobe/en/devnet/font/pdfs/5176.CFF.pdf
# http://www.adobe.com/content/dam/Adobe/en/devnet/font/pdfs/5177.Type2.pdf

class CFF(object):

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

        import pprint
        pprint.pprint(self.top_dict)
        pprint.pprint(self.private_dict)

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
                            for i in xrange(offset, offset+3*(count+2), 3)]
            else:
                fmt = {1:'B', 2:'H', 4:'L'}[self.offset_size]
                fmt = ('>%d%s'%(count+1, fmt)).encode('ascii')
                offsets = unpack_from(fmt, raw, offset)
            offset += self.offset_size * (count+1) - 1

            for i in xrange(len(offsets)-1):
                off, noff = offsets[i:i+2]
                obj = raw[offset+off:offset+noff]
                self.append(obj)

            try:
                self.pos = offset + offsets[-1]
            except IndexError:
                self.pos = offset

class Strings(Index):

    def __init__(self, raw, offset):
        super(Strings, self).__init__(raw, offset, prepend=[x.encode('ascii')
            for x in cff_standard_strings])

class Charset(list):

    STANDARD_CHARSETS = [ # {{{
    # ISOAdobe
    (".notdef", "space", "exclam", "quotedbl", "numbersign", "dollar",
        "percent", "ampersand", "quoteright", "parenleft", "parenright",
        "asterisk", "plus", "comma", "hyphen", "period", "slash", "zero",
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "colon", "semicolon", "less", "equal", "greater", "question", "at",
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N",
        "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
        "bracketleft", "backslash", "bracketright", "asciicircum",
        "underscore", "quoteleft", "a", "b", "c", "d", "e", "f", "g", "h", "i",
        "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w",
        "x", "y", "z", "braceleft", "bar", "braceright", "asciitilde",
        "exclamdown", "cent", "sterling", "fraction", "yen", "florin",
        "section", "currency", "quotesingle", "quotedblleft", "guillemotleft",
        "guilsinglleft", "guilsinglright", "fi", "fl", "endash", "dagger",
        "daggerdbl", "periodcentered", "paragraph", "bullet", "quotesinglbase",
        "quotedblbase", "quotedblright", "guillemotright", "ellipsis",
        "perthousand", "questiondown", "grave", "acute", "circumflex", "tilde",
        "macron", "breve", "dotaccent", "dieresis", "ring", "cedilla",
        "hungarumlaut", "ogonek", "caron", "emdash", "AE", "ordfeminine",
        "Lslash", "Oslash", "OE", "ordmasculine", "ae", "dotlessi", "lslash",
        "oslash", "oe", "germandbls", "onesuperior", "logicalnot", "mu",
        "trademark", "Eth", "onehalf", "plusminus", "Thorn", "onequarter",
        "divide", "brokenbar", "degree", "thorn", "threequarters",
        "twosuperior", "registered", "minus", "eth", "multiply",
        "threesuperior", "copyright", "Aacute", "Acircumflex", "Adieresis",
        "Agrave", "Aring", "Atilde", "Ccedilla", "Eacute", "Ecircumflex",
        "Edieresis", "Egrave", "Iacute", "Icircumflex", "Idieresis", "Igrave",
        "Ntilde", "Oacute", "Ocircumflex", "Odieresis", "Ograve", "Otilde",
        "Scaron", "Uacute", "Ucircumflex", "Udieresis", "Ugrave", "Yacute",
        "Ydieresis", "Zcaron", "aacute", "acircumflex", "adieresis", "agrave",
        "aring", "atilde", "ccedilla", "eacute", "ecircumflex", "edieresis",
        "egrave", "iacute", "icircumflex", "idieresis", "igrave", "ntilde",
        "oacute", "ocircumflex", "odieresis", "ograve", "otilde", "scaron",
        "uacute", "ucircumflex", "udieresis", "ugrave", "yacute", "ydieresis",
        "zcaron"),

    # Expert
    ("notdef", "space", "exclamsmall", "Hungarumlautsmall", "dollaroldstyle",
        "dollarsuperior", "ampersandsmall", "Acutesmall", "parenleftsuperior",
        "parenrightsuperior", "twodotenleader", "onedotenleader", "comma",
        "hyphen", "period", "fraction", "zerooldstyle", "oneoldstyle",
        "twooldstyle", "threeoldstyle", "fouroldstyle", "fiveoldstyle",
        "sixoldstyle", "sevenoldstyle", "eightoldstyle", "nineoldstyle",
        "colon", "semicolon", "commasuperior", "threequartersemdash",
        "periodsuperior", "questionsmall", "asuperior", "bsuperior",
        "centsuperior", "dsuperior", "esuperior", "isuperior", "lsuperior",
        "msuperior", "nsuperior", "osuperior", "rsuperior", "ssuperior",
        "tsuperior", "ff", "fi", "fl", "ffi", "ffl", "parenleftinferior",
        "parenrightinferior", "Circumflexsmall", "hyphensuperior",
        "Gravesmall", "Asmall", "Bsmall", "Csmall", "Dsmall", "Esmall",
        "Fsmall", "Gsmall", "Hsmall", "Ismall", "Jsmall", "Ksmall", "Lsmall",
        "Msmall", "Nsmall", "Osmall", "Psmall", "Qsmall", "Rsmall", "Ssmall",
        "Tsmall", "Usmall", "Vsmall", "Wsmall", "Xsmall", "Ysmall", "Zsmall",
        "colonmonetary", "onefitted", "rupiah", "Tildesmall",
        "exclamdownsmall", "centoldstyle", "Lslashsmall", "Scaronsmall",
        "Zcaronsmall", "Dieresissmall", "Brevesmall", "Caronsmall",
        "Dotaccentsmall", "Macronsmall", "figuredash", "hypheninferior",
        "Ogoneksmall", "Ringsmall", "Cedillasmall", "onequarter", "onehalf",
        "threequarters", "questiondownsmall", "oneeighth", "threeeighths",
        "fiveeighths", "seveneighths", "onethird", "twothirds", "zerosuperior",
        "onesuperior", "twosuperior", "threesuperior", "foursuperior",
        "fivesuperior", "sixsuperior", "sevensuperior", "eightsuperior",
        "ninesuperior", "zeroinferior", "oneinferior", "twoinferior",
        "threeinferior", "fourinferior", "fiveinferior", "sixinferior",
        "seveninferior", "eightinferior", "nineinferior", "centinferior",
        "dollarinferior", "periodinferior", "commainferior", "Agravesmall",
        "Aacutesmall", "Acircumflexsmall", "Atildesmall", "Adieresissmall",
        "Aringsmall", "AEsmall", "Ccedillasmall", "Egravesmall", "Eacutesmall",
        "Ecircumflexsmall", "Edieresissmall", "Igravesmall", "Iacutesmall",
        "Icircumflexsmall", "Idieresissmall", "Ethsmall", "Ntildesmall",
        "Ogravesmall", "Oacutesmall", "Ocircumflexsmall", "Otildesmall",
        "Odieresissmall", "OEsmall", "Oslashsmall", "Ugravesmall",
        "Uacutesmall", "Ucircumflexsmall", "Udieresissmall", "Yacutesmall",
        "Thornsmall", "Ydieresissmall"),

    # Expert Subset
    (".notdef", "space", "dollaroldstyle", "dollarsuperior",
            "parenleftsuperior", "parenrightsuperior", "twodotenleader",
            "onedotenleader", "comma", "hyphen", "period", "fraction",
            "zerooldstyle", "oneoldstyle", "twooldstyle", "threeoldstyle",
            "fouroldstyle", "fiveoldstyle", "sixoldstyle", "sevenoldstyle",
            "eightoldstyle", "nineoldstyle", "colon", "semicolon",
            "commasuperior", "threequartersemdash", "periodsuperior",
            "asuperior", "bsuperior", "centsuperior", "dsuperior", "esuperior",
            "isuperior", "lsuperior", "msuperior", "nsuperior", "osuperior",
            "rsuperior", "ssuperior", "tsuperior", "ff", "fi", "fl", "ffi",
            "ffl", "parenleftinferior", "parenrightinferior", "hyphensuperior",
            "colonmonetary", "onefitted", "rupiah", "centoldstyle",
            "figuredash", "hypheninferior", "onequarter", "onehalf",
            "threequarters", "oneeighth", "threeeighths", "fiveeighths",
            "seveneighths", "onethird", "twothirds", "zerosuperior",
            "onesuperior", "twosuperior", "threesuperior", "foursuperior",
            "fivesuperior", "sixsuperior", "sevensuperior", "eightsuperior",
            "ninesuperior", "zeroinferior", "oneinferior", "twoinferior",
            "threeinferior", "fourinferior", "fiveinferior", "sixinferior",
            "seveninferior", "eightinferior", "nineinferior", "centinferior",
            "dollarinferior", "periodinferior", "commainferior"),
    ] # }}}

    def __init__(self, raw, offset, strings, num_glyphs, is_CID):
        super(Charset, self).__init__()
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
        count = 0
        while count < num_glyphs - 1:
            first, nleft = unpack_from(fmt, raw, offset)
            offset += sz
            count += nleft + 1
            self.extend('cid%05d'%x if is_CID else strings[x] for x in
                    xrange(first, first + nleft+1))

    def lookup(self, glyph_id):
        if self.standard_charset is None:
            return self[glyph_id]
        return self.STANDARD_CHARSETS[self.standard_charset][glyph_id].encode('ascii')

class Subrs(Index):
    pass

class CharStringsIndex(Index):
    pass

class CFFTable(UnknownTable):

    def decompile(self):
        self.cff = CFF(self.raw)

# cff_standard_strings {{{
# The 391 Standard Strings as used in the CFF format.
# from Adobe Technical None #5176, version 1.0, 18 March 1998

cff_standard_strings = [
'.notdef', 'space', 'exclam', 'quotedbl', 'numbersign', 'dollar', 'percent',
'ampersand', 'quoteright', 'parenleft', 'parenright', 'asterisk', 'plus',
'comma', 'hyphen', 'period', 'slash', 'zero', 'one', 'two', 'three', 'four',
'five', 'six', 'seven', 'eight', 'nine', 'colon', 'semicolon', 'less', 'equal',
'greater', 'question', 'at', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
'bracketleft', 'backslash', 'bracketright', 'asciicircum', 'underscore',
'quoteleft', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'braceleft',
'bar', 'braceright', 'asciitilde', 'exclamdown', 'cent', 'sterling',
'fraction', 'yen', 'florin', 'section', 'currency', 'quotesingle',
'quotedblleft', 'guillemotleft', 'guilsinglleft', 'guilsinglright', 'fi', 'fl',
'endash', 'dagger', 'daggerdbl', 'periodcentered', 'paragraph', 'bullet',
'quotesinglbase', 'quotedblbase', 'quotedblright', 'guillemotright',
'ellipsis', 'perthousand', 'questiondown', 'grave', 'acute', 'circumflex',
'tilde', 'macron', 'breve', 'dotaccent', 'dieresis', 'ring', 'cedilla',
'hungarumlaut', 'ogonek', 'caron', 'emdash', 'AE', 'ordfeminine', 'Lslash',
'Oslash', 'OE', 'ordmasculine', 'ae', 'dotlessi', 'lslash', 'oslash', 'oe',
'germandbls', 'onesuperior', 'logicalnot', 'mu', 'trademark', 'Eth', 'onehalf',
'plusminus', 'Thorn', 'onequarter', 'divide', 'brokenbar', 'degree', 'thorn',
'threequarters', 'twosuperior', 'registered', 'minus', 'eth', 'multiply',
'threesuperior', 'copyright', 'Aacute', 'Acircumflex', 'Adieresis', 'Agrave',
'Aring', 'Atilde', 'Ccedilla', 'Eacute', 'Ecircumflex', 'Edieresis', 'Egrave',
'Iacute', 'Icircumflex', 'Idieresis', 'Igrave', 'Ntilde', 'Oacute',
'Ocircumflex', 'Odieresis', 'Ograve', 'Otilde', 'Scaron', 'Uacute',
'Ucircumflex', 'Udieresis', 'Ugrave', 'Yacute', 'Ydieresis', 'Zcaron',
'aacute', 'acircumflex', 'adieresis', 'agrave', 'aring', 'atilde', 'ccedilla',
'eacute', 'ecircumflex', 'edieresis', 'egrave', 'iacute', 'icircumflex',
'idieresis', 'igrave', 'ntilde', 'oacute', 'ocircumflex', 'odieresis',
'ograve', 'otilde', 'scaron', 'uacute', 'ucircumflex', 'udieresis', 'ugrave',
'yacute', 'ydieresis', 'zcaron', 'exclamsmall', 'Hungarumlautsmall',
'dollaroldstyle', 'dollarsuperior', 'ampersandsmall', 'Acutesmall',
'parenleftsuperior', 'parenrightsuperior', 'twodotenleader', 'onedotenleader',
'zerooldstyle', 'oneoldstyle', 'twooldstyle', 'threeoldstyle', 'fouroldstyle',
'fiveoldstyle', 'sixoldstyle', 'sevenoldstyle', 'eightoldstyle',
'nineoldstyle', 'commasuperior', 'threequartersemdash', 'periodsuperior',
'questionsmall', 'asuperior', 'bsuperior', 'centsuperior', 'dsuperior',
'esuperior', 'isuperior', 'lsuperior', 'msuperior', 'nsuperior', 'osuperior',
'rsuperior', 'ssuperior', 'tsuperior', 'ff', 'ffi', 'ffl', 'parenleftinferior',
'parenrightinferior', 'Circumflexsmall', 'hyphensuperior', 'Gravesmall',
'Asmall', 'Bsmall', 'Csmall', 'Dsmall', 'Esmall', 'Fsmall', 'Gsmall', 'Hsmall',
'Ismall', 'Jsmall', 'Ksmall', 'Lsmall', 'Msmall', 'Nsmall', 'Osmall', 'Psmall',
'Qsmall', 'Rsmall', 'Ssmall', 'Tsmall', 'Usmall', 'Vsmall', 'Wsmall', 'Xsmall',
'Ysmall', 'Zsmall', 'colonmonetary', 'onefitted', 'rupiah', 'Tildesmall',
'exclamdownsmall', 'centoldstyle', 'Lslashsmall', 'Scaronsmall', 'Zcaronsmall',
'Dieresissmall', 'Brevesmall', 'Caronsmall', 'Dotaccentsmall', 'Macronsmall',
'figuredash', 'hypheninferior', 'Ogoneksmall', 'Ringsmall', 'Cedillasmall',
'questiondownsmall', 'oneeighth', 'threeeighths', 'fiveeighths',
'seveneighths', 'onethird', 'twothirds', 'zerosuperior', 'foursuperior',
'fivesuperior', 'sixsuperior', 'sevensuperior', 'eightsuperior',
'ninesuperior', 'zeroinferior', 'oneinferior', 'twoinferior', 'threeinferior',
'fourinferior', 'fiveinferior', 'sixinferior', 'seveninferior',
'eightinferior', 'nineinferior', 'centinferior', 'dollarinferior',
'periodinferior', 'commainferior', 'Agravesmall', 'Aacutesmall',
'Acircumflexsmall', 'Atildesmall', 'Adieresissmall', 'Aringsmall', 'AEsmall',
'Ccedillasmall', 'Egravesmall', 'Eacutesmall', 'Ecircumflexsmall',
'Edieresissmall', 'Igravesmall', 'Iacutesmall', 'Icircumflexsmall',
'Idieresissmall', 'Ethsmall', 'Ntildesmall', 'Ogravesmall', 'Oacutesmall',
'Ocircumflexsmall', 'Otildesmall', 'Odieresissmall', 'OEsmall', 'Oslashsmall',
'Ugravesmall', 'Uacutesmall', 'Ucircumflexsmall', 'Udieresissmall',
'Yacutesmall', 'Thornsmall', 'Ydieresissmall', '001.000', '001.001', '001.002',
'001.003', 'Black', 'Bold', 'Book', 'Light', 'Medium', 'Regular', 'Roman',
'Semibold'
]
# }}}

