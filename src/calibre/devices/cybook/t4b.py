# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
__license__   = 'GPL v3'
__copyright__ = '2013, Jellby <jellby at yahoo.com>'
'''
Write a t4b file to disk.
'''

from io import BytesIO

DEFAULT_T4B_DATA = b''

def reduce_color(c):
    return max(0, min(255, c))//16

def write_t4b(t4bfile, coverdata=None):
    '''
    t4bfile is a file handle ready to write binary data to disk.
    coverdata is a string representation of a JPEG file.
    '''
    from PIL import Image
    if coverdata is not None:
        coverdata = BytesIO(coverdata)
        cover = Image.open(coverdata).convert("L")
        cover.thumbnail((96, 144), Image.ANTIALIAS)
        t4bcover = Image.new('L', (96, 144), 'white')

        x, y = cover.size
        t4bcover.paste(cover, ((96-x)//2, (144-y)//2))

        pxs = t4bcover.getdata()
        t4bfile.write(b't4bp')
        data = (16 * reduce_color(pxs[i]) + reduce_color(pxs[i+1])
                          for i in xrange(0, len(pxs), 2))
        t4bfile.write(bytes(bytearray(data)))
    else:
        t4bfile.write(DEFAULT_T4B_DATA)

