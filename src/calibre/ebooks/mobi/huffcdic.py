#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Decompress MOBI files compressed with the Huff/cdic algorithm. Code thanks to darkninja
and igorsk.
'''

import struct

from calibre.ebooks.mobi import MobiError

class BitReader(object):
    
    def __init__(self, data):
        self.data, self.pos, self.nbits = data + "\x00\x00\x00\x00", 0, len(data) * 8
        
    def peek(self, n):
        r, g = 0, 0
        while g < n:
            r, g = (r << 8) | ord(self.data[(self.pos+g)>>3]), g + 8 - ((self.pos+g) & 7)
        return (r >> (g - n)) & ((1 << n) - 1)
    
    def eat(self, n):
        self.pos += n
        return self.pos <= self.nbits
    
    def left(self):
        return self.nbits - self.pos

class HuffReader(object):
    
    def __init__(self, huffs, extra_flags):
        self.huffs = huffs
        
        if huffs[0][0:4] != 'HUFF' or huffs[0][4:8] != '\x00\x00\x00\x18':
            raise MobiError('Invalid HUFF header')
        
        if huffs[1][0:4] != 'CDIC' or huffs[1][4:8] != '\x00\x00\x00\x10':
            raise ValueError('Invalid CDIC header')
        
        self.entry_bits, = struct.unpack('>L', huffs[1][12:16])
        off1,off2 = struct.unpack('>LL', huffs[0][16:24])
        self.dict1 = struct.unpack('<256L', huffs[0][off1:off1+256*4])
        self.dict2 = struct.unpack('<64L', huffs[0][off2:off2+64*4])
        self.dicts = huffs[1:]
        self.r = ''
        
    def _unpack(self, bits, depth = 0):
        if depth > 32:
            raise MobiError('Corrupt file')
        
        while bits.left():
            dw = bits.peek(32)
            v = self.dict1[dw >> 24]
            codelen = v & 0x1F
            assert codelen != 0
            code = dw >> (32 - codelen)
            r = (v >> 8)
            if not (v & 0x80):
                while code < self.dict2[(codelen-1)*2]:
                    codelen += 1
                    code = dw >> (32 - codelen)
                r = self.dict2[(codelen-1)*2+1]
            r -= code
            assert codelen != 0
            if not bits.eat(codelen):
                return
            dicno = r >> self.entry_bits
            off1 = 16 + (r - (dicno << self.entry_bits)) * 2
            dic = self.dicts[dicno]
            off2 = 16 + ord(dic[off1]) * 256 + ord(dic[off1+1])
            blen = ord(dic[off2]) * 256 + ord(dic[off2+1])
            slice = dic[off2+2:off2+2+(blen&0x7fff)]
            if blen & 0x8000:
                self.r += slice
            else:
                self._unpack(BitReader(slice), depth + 1)

    def unpack(self, data):
        self.r = ''
        self._unpack(BitReader(data))
        return self.r
    
    def decompress(self, sections):
        r = ''
        for data in sections:
            r += self.unpack(data)
        if r.endswith('#'):
            r = r[:-1]
        return r
