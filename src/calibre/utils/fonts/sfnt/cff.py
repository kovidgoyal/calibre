#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack_from, unpack

from calibre.utils.fonts.sfnt import UnknownTable
from calibre.utils.fonts.sfnt.errors import UnsupportedFont

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
        offset = self.top_index.pos

        # Read strings
        self.strings = Strings(raw, offset)
        offset = self.strings.pos
        print (self.strings[len(cff_standard_strings):])

class Index(list):

    def __init__(self, raw, offset):
        list.__init__(self)

        count = unpack_from(b'>H', raw, offset)[0]
        offset += 2
        self.pos = offset

        if count > 0:
            self.offset_size = unpack_from(b'>B', raw, offset)[0]
            offset += 1
            if self.offset_size == 3:
                offsets = [unpack(b'>L', b'\0' + raw[i:i+3])[0]
                            for i in xrange(offset, 3*(count+2), 3)]
            else:
                fmt = {1:'B', 2:'H', 4:'L'}.get(self.offset_size)
                fmt = ('>%d%s'%(count+1, fmt)).encode('ascii')
                offsets = unpack_from(fmt, raw, offset)
            offset += self.offset_size * (count+1) - 1

            for i in xrange(len(offsets)-1):
                off, noff = offsets[i:i+2]
                obj = raw[offset+i:offset+noff]
                self.append(obj)

            self.pos = offset + offsets[-1]

class Strings(Index):

    def __init__(self, raw, offset):
        super(Strings, self).__init__(raw, offset)
        for x in reversed(cff_standard_strings):
            self.insert(0, x)

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

