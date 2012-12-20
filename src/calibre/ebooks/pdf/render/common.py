#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import codecs, zlib
from io import BytesIO
from struct import pack

EOL = b'\n'

# Sizes {{{
inch = 72.0
cm = inch / 2.54
mm = cm * 0.1
pica = 12.0

_W, _H = (21*cm, 29.7*cm)

A6 = (_W*.5, _H*.5)
A5 = (_H*.5, _W)
A4 = (_W, _H)
A3 = (_H, _W*2)
A2 = (_W*2, _H*2)
A1 = (_H*2, _W*4)
A0 = (_W*4, _H*4)

LETTER = (8.5*inch, 11*inch)
LEGAL = (8.5*inch, 14*inch)
ELEVENSEVENTEEN = (11*inch, 17*inch)

_BW, _BH = (25*cm, 35.3*cm)
B6 = (_BW*.5, _BH*.5)
B5 = (_BH*.5, _BW)
B4 = (_BW, _BH)
B3 = (_BH*2, _BW)
B2 = (_BW*2, _BH*2)
B1 = (_BH*4, _BW*2)
B0 = (_BW*4, _BH*4)
# }}}

# Basic PDF datatypes {{{

def serialize(o, stream):
    if hasattr(o, 'pdf_serialize'):
        o.pdf_serialize(stream)
    elif isinstance(o, bool):
        stream.write(b'true' if o else b'false')
    elif isinstance(o, (int, long, float)):
        stream.write(type(u'')(o).encode('ascii'))
    elif o is None:
        stream.write(b'null')
    else:
        raise ValueError('Unknown object: %r'%o)

class Name(unicode):

    def pdf_serialize(self, stream):
        raw = self.encode('ascii')
        if len(raw) > 126:
            raise ValueError('Name too long: %r'%self)
        buf = [x if 33 < ord(x) < 126 and x != b'#' else b'#'+hex(ord(x)) for x
               in raw]
        stream.write(b'/'+b''.join(buf))

class String(unicode):

    def pdf_serialize(self, stream):
        s = self.replace('\\', '\\\\').replace('(', r'\(').replace(')', r'\)')
        try:
            raw = s.encode('latin1')
            if raw.startswith(codecs.BOM_UTF16_BE):
                raise UnicodeEncodeError('')
        except UnicodeEncodeError:
            raw = codecs.BOM_UTF16_BE + s.encode('utf-16-be')
        stream.write(b'('+raw+b')')

class GlyphIndex(object):

    def __init__(self, code, compress):
        self.code = code
        self.compress = compress

    def pdf_serialize(self, stream):
        if self.compress:
            stream.write(pack(b'>sHs', b'(', self.code, b')'))
        else:
            byts = bytearray(pack(b'>H', self.code))
            stream.write('<%s>'%''.join(map(
                lambda x: bytes(hex(x)[2:]).rjust(2, b'0'), byts)))

class Dictionary(dict):

    def pdf_serialize(self, stream):
        stream.write(b'<<' + EOL)
        sorted_keys = sorted(self.iterkeys(),
                    key=lambda x:((' ' if x == 'Type' else '')+x))
        for k in sorted_keys:
            serialize(Name(k), stream)
            stream.write(b' ')
            serialize(self[k], stream)
            stream.write(EOL)
        stream.write(b'>>' + EOL)

class InlineDictionary(Dictionary):

    def pdf_serialize(self, stream):
        stream.write(b'<< ')
        for k, v in self.iteritems():
            serialize(Name(k), stream)
            stream.write(b' ')
            serialize(v, stream)
            stream.write(b' ')
        stream.write(b'>>')

class Array(list):

    def pdf_serialize(self, stream):
        stream.write(b'[')
        for i, o in enumerate(self):
            if i != 0:
                stream.write(b' ')
            serialize(o, stream)
        stream.write(b']')

class Stream(BytesIO):

    def __init__(self, compress=False):
        BytesIO.__init__(self)
        self.compress = compress

    def add_extra_keys(self, d):
        pass

    def pdf_serialize(self, stream):
        raw = self.getvalue()
        dl = len(raw)
        filters = Array()
        if self.compress:
            filters.append(Name('FlateDecode'))
            raw = zlib.compress(raw)

        d = InlineDictionary({'Length':len(raw), 'DL':dl})
        self.add_extra_keys(d)
        if filters:
            d['Filter'] = filters
        serialize(d, stream)
        stream.write(EOL+b'stream'+EOL)
        stream.write(raw)
        stream.write(EOL+b'endstream'+EOL)

    def write_line(self, raw=b''):
        self.write(raw if isinstance(raw, bytes) else raw.encode('ascii'))
        self.write(EOL)

    def write(self, raw):
        super(Stream, self).write(raw if isinstance(raw, bytes) else
                                  raw.encode('ascii'))

class Reference(object):

    def __init__(self, num, obj):
        self.num, self.obj = num, obj

    def pdf_serialize(self, stream):
        raw = '%d 0 R'%self.num
        stream.write(raw.encode('ascii'))
# }}}

