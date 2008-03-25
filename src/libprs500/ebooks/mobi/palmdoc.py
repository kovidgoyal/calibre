#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

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
    