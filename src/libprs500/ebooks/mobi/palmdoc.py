#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

COUNT_BITS = 3

def decompress_doc(data, codec='cp1252'):
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

    return unicode(''.join([chr(i) for i in res]), codec)
    