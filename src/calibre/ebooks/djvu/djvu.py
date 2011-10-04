#! /usr/bin/env python
# coding: utf-8

__license__   = 'GPL v3'
__copyright__ = '2011, Anthon van der Neut <A.van.der.Neut@ruamel.eu>'

# this code is based on:
# Lizardtech DjVu Reference
# DjVu v3
# November 2005

from ruamel.util.program import Program, CountAction

import os
import sys
import struct
from cStringIO import StringIO

from .djvubzzdec import BZZDecoder

class DjvuChunk(object):
    def __init__(self, buf, start, end, align=True, bigendian=True, inclheader=False, verbose=0):
        self.subtype = None
        self._subchunks = []
        self.buf = buf
        pos = start + 4
        self.type = buf[start:pos]
        self.align = align      # whether to align to word (2-byte) boundaries
        self.headersize = 0 if inclheader else 8
        if bigendian:
            self.strflag = '>'
        else:
            self.strflag = '<'
        oldpos, pos = pos, pos+4
        self.size = struct.unpack(self.strflag+'L', buf[oldpos:pos])[0]
        self.dataend = pos + self.size - (8 if inclheader else 0)
        if self.type == 'FORM':
            oldpos, pos = pos, pos+4
            #print oldpos, pos
            self.subtype = buf[oldpos:pos]
            #self.headersize += 4
        self.datastart = pos
        if verbose > 0:
            print 'found', self.type, self.subtype, pos, self.size
        if self.type in 'FORM'.split():
            if verbose > 0:
                print 'processing substuff %d %d (%x)' % (pos, self.dataend, self.dataend)
            numchunks = 0
            while pos < self.dataend:
                x = DjvuChunk(buf, pos, start+self.size, verbose=verbose)
                numchunks += 1
                self._subchunks.append(x)
                newpos = pos + x.size + x.headersize + (1 if (x.size % 2) else 0)
                if verbose > 0:
                    print 'newpos %d %d (%x, %x) %d' % (newpos, self.dataend, newpos, self.dataend, x.headersize)
                pos = newpos
            if verbose > 0:
                print '                  end of chunk %d (%x)' % (pos, pos)

    def dump(self, verbose=0, indent=1, out=None):
        if out is None:
            out = sys.stdout
        if verbose > 0:
            out.write('  ' * indent)
            out.write('%s%s [%d]\n' % (self.type, ':' + self.subtype if self.subtype else '', self.size))
        if self.type == 'TXTz':
            inbuf = StringIO(self.buf[self.datastart: self.dataend])
            outbuf = StringIO()
            decoder = BZZDecoder(inbuf, outbuf)
            while True:
                xxres = decoder.convert(1024 * 1024)
                if not xxres:
                    break
            res = outbuf.getvalue()
            l = 0
            for x in res[:3]:
                l <<= 8
                l += ord(x)
            if verbose > 0:
                print >> out, l
            out.write(res[3:3+l])
            out.write('\n\f')
        if self.type == 'TXTa':
            res = self.buf[self.datastart: self.dataend]
            l = 0
            for x in res[:3]:
                l <<= 8
                l += ord(x)
            if verbose > 0:
                print >> out, l
            out.write(res[3:3+l])
            out.write('\n\f')
        for schunk in self._subchunks:
            schunk.dump(verbose=verbose, indent=indent+1, out=out)

class DJVUFile(object):
    def __init__(self, instream):
        self.instream = instream
        buf = self.instream.read(4)
        assert(buf == 'AT&T')
        buf = self.instream.read()
        self.dc = DjvuChunk(buf, 0, len(buf))

    def get_text(self, outfile=None):
        self.dc.dump(out=outfile)

def main():
    from ruamel.util.program import Program, CountAction
    class DJVUDecoder(Program):
        def __init__(self):
            Program.__init__(self)

        def parser_setup(self):
            Program.parser_setup(self)
            #self._argparser.add_argument('--combine', '-c', action=CountAction, const=1, nargs=0)
            #self._argparser.add_argument('--combine', '-c', type=int, default=1)
            #self._argparser.add_argument('--segments', '-s', action='append', nargs='+')
            #self._argparser.add_argument('--force', '-f', action='store_true')
            #self._argparser.add_argument('classname')
            self._argparser.add_argument('file', nargs='+')

        def run(self):
            if self._args.verbose > 1: # can be negative with --quiet
                print self._args.file
            x = DJVUFile(file(self._args.file[0], 'rb'))
            x.get_text()
            return 0

    tt = DJVUDecoder()
    res = tt.result
    if res != 0:
        print res

if __name__ == '__main__':
    main()
