#!/usr/bin/python

#Read text streams from LRF files. Usage ./stream.py <myfile.lrf> <offset to beginning of stream object in hex>

import array, sys, struct, zlib

def descrambleBuf(buf, l, xorKey):
    i = 0
    a = array.array('B',buf)
    while l>0:
        a[i] ^= xorKey
        i+=1
        l-=1
    return a.tostring()

f = open(sys.argv[1], 'rb')
f.seek(0x0a)
xorkey = struct.unpack('<H', f.read(2))[0]

f.seek(int(sys.argv[2], 16) + 0x10)
flags = struct.unpack('<H', f.read(2))[0]
f.read(2)
l = struct.unpack('<I', f.read(4))[0]
f.read(2)
raw = f.read(l)
key = (l % xorkey) + 0x0f
descrambled = descrambleBuf(raw, l, key) if (flags & 0x200) else  raw
stream = zlib.decompress(descrambled[4:]) if (flags & 0x100)  else  descrambled
print stream
