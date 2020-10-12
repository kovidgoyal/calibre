#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct


class Unavailable(Exception):
    pass


class NoRaster(Exception):
    pass


class DIBHeader(object):

    '''
    See http://en.wikipedia.org/wiki/BMP_file_format
    '''

    def __init__(self, raw):
        hsize = struct.unpack(b'<I', raw[:4])[0]
        if hsize == 40:
            parts = struct.unpack(b'<IiiHHIIIIII', raw[:hsize])
            for i, attr in enumerate((
                'header_size', 'width', 'height', 'color_planes',
                'bits_per_pixel', 'compression', 'image_size',
                'hres', 'vres', 'ncols', 'nimpcols'
                )):
                setattr(self, attr, parts[i])
        elif hsize == 12:
            parts = struct.unpack(b'<IHHHH', raw[:hsize])
            for i, attr in enumerate((
                'header_size', 'width', 'height', 'color_planes',
                'bits_per_pixel')):
                setattr(self, attr, parts[i])
        else:
            raise ValueError('Unsupported DIB header type of size: %d'%hsize)

        self.bitmasks_size = 12 if getattr(self, 'compression', 0) == 3 else 0
        self.color_table_size = 0
        if self.bits_per_pixel != 24:
            # See http://support.microsoft.com/kb/q81498/
            # for all the gory Micro and soft details
            self.color_table_size = getattr(self, 'ncols', 0) * 4


def create_bmp_from_dib(raw):
    size = len(raw) + 14
    dh = DIBHeader(raw)
    pixel_array_offset = dh.header_size + dh.bitmasks_size + \
                            dh.color_table_size
    parts = [b'BM', struct.pack(b'<I', size), b'\0'*4, struct.pack(b'<I',
        pixel_array_offset)]
    return b''.join(parts) + raw


def to_png(bmp):
    from PyQt5.Qt import QImage, QByteArray, QBuffer
    i = QImage()
    if not i.loadFromData(bmp):
        raise ValueError('Invalid image data')
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    i.save(buf, 'png')
    return ba.data()
