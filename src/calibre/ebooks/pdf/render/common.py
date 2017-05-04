#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import codecs, zlib
from io import BytesIO
from datetime import datetime
from binascii import hexlify

from calibre.constants import plugins, ispy3
from calibre.utils.logging import default_log

pdf_float = plugins['speedup'][0].pdf_float

EOL = b'\n'

# Sizes {{{
inch = 72.0
cm = inch / 2.54
mm = cm * 0.1
pica = 12.0
didot = 0.375 * mm
cicero = 12 * didot

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

PAPER_SIZES = {k:globals()[k.upper()] for k in ('a0 a1 a2 a3 a4 a5 a6 b0 b1 b2'
               ' b3 b4 b5 b6 letter legal').split()}

# }}}

# Basic PDF datatypes {{{

ic = str if ispy3 else unicode
icb = (lambda x: str(x).encode('ascii')) if ispy3 else bytes


def fmtnum(o):
    if isinstance(o, float):
        return pdf_float(o)
    return ic(o)


def serialize(o, stream):
    if isinstance(o, float):
        stream.write_raw(pdf_float(o).encode('ascii'))
    elif isinstance(o, bool):
        # Must check bool before int as bools are subclasses of int
        stream.write_raw(b'true' if o else b'false')
    elif isinstance(o, (int, long)):
        stream.write_raw(icb(o))
    elif hasattr(o, 'pdf_serialize'):
        o.pdf_serialize(stream)
    elif o is None:
        stream.write_raw(b'null')
    elif isinstance(o, datetime):
        val = o.strftime("D:%Y%m%d%H%M%%02d%z")%min(59, o.second)
        if datetime.tzinfo is not None:
            val = "(%s'%s')"%(val[:-2], val[-2:])
        stream.write(val.encode('ascii'))
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


def escape_pdf_string(bytestring):
    indices = []
    bad = []
    ba = bytearray(bytestring)
    bad_map = {10:ord('n'), 13:ord('r'), 12:ord('f'), 8:ord('b'), 9:ord('\t'), 92:ord('\\')}
    for i, num in enumerate(ba):
        if num == 40:  # (
            indices.append((i, 40))
        elif num == 41:  # )
            if indices:
                indices.pop()
            else:
                bad.append((i, 41))
        elif num in bad_map:  # '\n\r\f\b\t\\' see Table 3.2 in PDF 1.7 spec
            bad.append((i, bad_map[num]))
    bad = sorted(indices + bad, reverse=True)
    if not bad:
        return bytestring
    for i, repl in bad:
        ba[i:i+1] = (92, repl)  # 92 = ord('\')
    return bytes(ba)


class String(unicode):

    def pdf_serialize(self, stream):
        try:
            raw = self.encode('latin1')
            if raw.startswith(codecs.BOM_UTF16_BE):
                raw = codecs.BOM_UTF16_BE + self.encode('utf-16-be')
        except UnicodeEncodeError:
            raw = codecs.BOM_UTF16_BE + self.encode('utf-16-be')
        stream.write(b'('+escape_pdf_string(raw)+b')')


class UTF16String(unicode):

    def pdf_serialize(self, stream):
        raw = codecs.BOM_UTF16_BE + self.encode('utf-16-be')
        if False:
            # Disabled as the parentheses based strings give easier to debug
            # PDF files
            stream.write(b'<' + hexlify(raw) + b'>')
        else:
            stream.write(b'('+escape_pdf_string(raw)+b')')


class Dictionary(dict):

    def pdf_serialize(self, stream):
        stream.write(b'<<' + EOL)
        sorted_keys = sorted(self.iterkeys(),
                             key=lambda x:({'Type':'1', 'Subtype':'2'}.get(
                                 x, x)+x))
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
        self.filters = Array()

    def add_extra_keys(self, d):
        pass

    def pdf_serialize(self, stream):
        raw = self.getvalue()
        dl = len(raw)
        filters = self.filters
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

    def write_raw(self, raw):
        BytesIO.write(self, raw)


class Reference(object):

    def __init__(self, num, obj):
        self.num, self.obj = num, obj

    def pdf_serialize(self, stream):
        raw = '%d 0 R'%self.num
        stream.write(raw.encode('ascii'))

    def __repr__(self):
        return '%d 0 R'%self.num

    def __str__(self):
        return repr(self)
# }}}


def current_log(newlog=None):
    if newlog:
        current_log.ans = newlog
    return current_log.ans or default_log


current_log.ans = None
