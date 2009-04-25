#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net> ' \
    'and Marshall T. Vandegrift <llasram@gmail.com>'

from cStringIO import StringIO
from struct import pack

COUNT_BITS = 3

def decompress_doc(data):
    buffer = [ord(i) for i in data]
    res = []
    i = 0
    while i < len(buffer):
        c = buffer[i]
        i += 1
        if c >= 1 and c <= 8:
            res.extend(buffer[i:i+c])
            i += c
        elif c <= 0x7f:
            res.append(c)
        elif c >= 0xc0:
            res.extend( (ord(' '), c^0x80) )
        else:
            c = (c << 8) + buffer[i]
            i += 1
            di = (c & 0x3fff) >> COUNT_BITS
            j = len(res)
            num = (c & ((1 << COUNT_BITS) - 1)) + 3

            for k in range( num ):
                res.append(res[j - di+k])

    return ''.join([chr(i) for i in res])

def compress_doc(data):
    out = StringIO()
    i = 0
    ldata = len(data)
    while i < ldata:
        if i > 10 and (ldata - i) > 10:
            chunk = ''
            match = -1
            for j in xrange(10, 2, -1):
                chunk = data[i:i+j]
                try:
                    match = data.rindex(chunk, 0, i)
                except ValueError:
                    continue
                if (i - match) <= 2047:
                    break
                match = -1
            if match >= 0:
                n = len(chunk)
                m = i - match
                code = 0x8000 + ((m << 3) & 0x3ff8) + (n - 3)
                out.write(pack('>H', code))
                i += n
                continue
        ch = data[i]
        och = ord(ch)
        i += 1
        if ch == ' ' and (i + 1) < ldata:
            onch = ord(data[i])
            if onch >= 0x40 and onch < 0x80:
                out.write(pack('>B', onch ^ 0x80))
                i += 1
                continue
        if och == 0 or (och > 8 and och < 0x80):
            out.write(ch)
        else:
            j = i
            binseq = [ch]
            while j < ldata and len(binseq) < 8:
                ch = data[j]
                och = ord(ch)
                if och == 0 or (och > 8 and och < 0x80):
                    break
                binseq.append(ch)
                j += 1
            out.write(pack('>B', len(binseq)))
            out.write(''.join(binseq))
            i += len(binseq) - 1
    return out.getvalue()

