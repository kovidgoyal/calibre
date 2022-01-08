#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Decompress MOBI files compressed with the Huff/cdic algorithm. Code thanks to darkninja
and igorsk.
'''

import struct

from calibre.ebooks.mobi import MobiError


class Reader:

    def __init__(self):
        self.q = struct.Struct(b'>Q').unpack_from

    def load_huff(self, huff):
        if huff[0:8] != b'HUFF\x00\x00\x00\x18':
            raise MobiError('Invalid HUFF header')
        off1, off2 = struct.unpack_from(b'>LL', huff, 8)

        def dict1_unpack(v):
            codelen, term, maxcode = v&0x1f, v&0x80, v>>8
            assert codelen != 0
            if codelen <= 8:
                assert term
            maxcode = ((maxcode + 1) << (32 - codelen)) - 1
            return (codelen, term, maxcode)
        self.dict1 = tuple(map(dict1_unpack, struct.unpack_from(b'>256L', huff, off1)))

        dict2 = struct.unpack_from(b'>64L', huff, off2)
        self.mincode, self.maxcode = (), ()
        for codelen, mincode in enumerate((0,) + dict2[0::2]):
            self.mincode += (mincode << (32 - codelen), )
        for codelen, maxcode in enumerate((0,) + dict2[1::2]):
            self.maxcode += (((maxcode + 1) << (32 - codelen)) - 1, )

        self.dictionary = []

    def load_cdic(self, cdic):
        if cdic[0:8] != b'CDIC\x00\x00\x00\x10':
            raise MobiError('Invalid CDIC header')
        phrases, bits = struct.unpack_from(b'>LL', cdic, 8)
        n = min(1<<bits, phrases-len(self.dictionary))
        h = struct.Struct(b'>H').unpack_from

        def getslice(off):
            blen, = h(cdic, 16+off)
            slice = cdic[18+off:18+off+(blen&0x7fff)]
            return (slice, blen&0x8000)
        self.dictionary += map(getslice, struct.unpack_from(b'>%dH' % n, cdic, 16))

    def unpack(self, data):
        q = self.q

        bitsleft = len(data) * 8
        data += b'\x00\x00\x00\x00\x00\x00\x00\x00'
        pos = 0
        x, = q(data, pos)
        n = 32

        s = []
        while True:
            if n <= 0:
                pos += 4
                x, = q(data, pos)
                n += 32
            code = (x >> n) & ((1 << 32) - 1)

            codelen, term, maxcode = self.dict1[code >> 24]
            if not term:
                while code < self.mincode[codelen]:
                    codelen += 1
                maxcode = self.maxcode[codelen]

            n -= codelen
            bitsleft -= codelen
            if bitsleft < 0:
                break

            r = (maxcode - code) >> (32 - codelen)
            slice_, flag = self.dictionary[r]
            if not flag:
                self.dictionary[r] = None
                slice_ = self.unpack(slice_)
                self.dictionary[r] = (slice_, 1)
            s.append(slice_)
        return b''.join(s)


class HuffReader:

    def __init__(self, huffs):
        self.reader = Reader()
        self.reader.load_huff(huffs[0])
        for cdic in huffs[1:]:
            self.reader.load_cdic(cdic)

    def unpack(self, section):
        return self.reader.unpack(section)
