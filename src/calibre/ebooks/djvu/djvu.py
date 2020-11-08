#!/usr/bin/env python
# coding: utf-8


__license__   = 'GPL v3'
__copyright__ = '2011, Anthon van der Neut <A.van.der.Neut@ruamel.eu>'

# this code is based on:
# Lizardtech DjVu Reference
# DjVu v3
# November 2005

import sys
import struct

from calibre.ebooks.djvu.djvubzzdec import BZZDecoder


class DjvuChunk(object):

    def __init__(self, buf, start, end, align=True, bigendian=True,
            inclheader=False, verbose=0):
        from calibre_extensions import bzzdec
        self.speedup = bzzdec
        self.subtype = None
        self._subchunks = []
        self.buf = buf
        pos = start + 4
        self.type = buf[start:pos]
        self.align = align      # whether to align to word (2-byte) boundaries
        self.headersize = 0 if inclheader else 8
        if bigendian:
            self.strflag = b'>'
        else:
            self.strflag = b'<'
        oldpos, pos = pos, pos+4
        self.size = struct.unpack(self.strflag+b'L', buf[oldpos:pos])[0]
        self.dataend = pos + self.size - (8 if inclheader else 0)
        if self.type == b'FORM':
            oldpos, pos = pos, pos+4
            # print oldpos, pos
            self.subtype = buf[oldpos:pos]
            # self.headersize += 4
        self.datastart = pos
        if verbose > 0:
            print('found', self.type, self.subtype, pos, self.size)
        if self.type in b'FORM'.split():
            if verbose > 0:
                print('processing substuff %d %d (%x)' % (pos, self.dataend,
                    self.dataend))
            numchunks = 0
            while pos < self.dataend:
                x = DjvuChunk(buf, pos, start+self.size, verbose=verbose)
                numchunks += 1
                self._subchunks.append(x)
                newpos = pos + x.size + x.headersize + (1 if (x.size % 2) else 0)
                if verbose > 0:
                    print('newpos %d %d (%x, %x) %d' % (newpos, self.dataend,
                        newpos, self.dataend, x.headersize))
                pos = newpos
            if verbose > 0:
                print('                  end of chunk %d (%x)' % (pos, pos))

    def dump(self, verbose=0, indent=1, out=None, txtout=None, maxlevel=100):
        if out:
            out.write(b'  ' * indent)
            out.write(b'%s%s [%d]\n' % (self.type,
                b':' + self.subtype if self.subtype else b'', self.size))
        if txtout and self.type == b'TXTz':
            if True:
                # Use the C BZZ decode implementation
                txtout.write(self.speedup.decompress(self.buf[self.datastart:self.dataend]))
            else:
                inbuf = bytearray(self.buf[self.datastart: self.dataend])
                outbuf = bytearray()
                decoder = BZZDecoder(inbuf, outbuf)
                while True:
                    xxres = decoder.convert(1024 * 1024)
                    if not xxres:
                        break
                res = bytes(outbuf)
                if not res.strip(b'\0'):
                    raise ValueError('TXTz block is completely null')
                l = 0
                for x in bytearray(res[:3]):
                    l <<= 8
                    l += x
                if verbose > 0 and out:
                    print(l, file=out)
                txtout.write(res[3:3+l])
            txtout.write(b'\037')
        if txtout and self.type == b'TXTa':
            res = self.buf[self.datastart: self.dataend]
            l = 0
            for x in bytearray(res[:3]):
                l <<= 8
                l += x
            if verbose > 0 and out:
                print(l, file=out)
            txtout.write(res[3:3+l])
            txtout.write(b'\037')
        if indent >= maxlevel:
            return
        for schunk in self._subchunks:
            schunk.dump(verbose=verbose, indent=indent+1, out=out, txtout=txtout)


class DJVUFile(object):

    def __init__(self, instream, verbose=0):
        self.instream = instream
        buf = self.instream.read(4)
        assert(buf == b'AT&T')
        buf = self.instream.read()
        self.dc = DjvuChunk(buf, 0, len(buf), verbose=verbose)

    def get_text(self, outfile=None):
        self.dc.dump(txtout=outfile)

    def dump(self, outfile=None, maxlevel=0):
        self.dc.dump(out=outfile, maxlevel=maxlevel)


def main():
    f = DJVUFile(open(sys.argv[-1], 'rb'))
    print(f.get_text(sys.stdout))


if __name__ == '__main__':
    main()
