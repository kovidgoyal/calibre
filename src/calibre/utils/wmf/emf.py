#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import sys
from struct import unpack_from
from typing import NamedTuple

from calibre.utils.wmf import create_bmp_from_dib, to_png

# Record types {{{
# See: http://msdn.microsoft.com/en-us/library/cc231166.aspx
RECORD_TYPES = {
    'EMR_BITBLT': 0x4C,
    'EMR_STRETCHBLT': 0x4D,
    'EMR_MASKBLT': 0x4E,
    'EMR_PLGBLT': 0x4F,
    'EMR_SETDIBITSTODEVICE': 0x50,
    'EMR_STRETCHDIBITS': 0x51,
    'EMR_ALPHABLEND': 0x72,
    'EMR_TRANSPARENTBLT': 0x74,
    'EOF': 0xE,
    'HEADER': 0x1,
}
RECORD_RMAP = {v: k for k, v in RECORD_TYPES.items()}


# See http://msdn.microsoft.com/en-us/library/cc230601.aspx
class StretchDiBits(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int
    x_dest: int
    y_dest: int
    x_src: int
    y_src: int
    cx_src: int
    cy_src: int
    bmp_hdr_offset: int
    bmp_header_size: int
    bmp_bits_offset: int
    bmp_bits_size: int
    usage: int
    op: int
    dest_width: int
    dest_height: int


# }}}


class EMF:
    def __init__(self, raw: bytes, verbose: int = 0) -> None:
        self.pos = 0
        self.found_eof = False
        self.verbose = verbose
        self.func_map = {v: getattr(self, 'handle_{}'.format(k.replace('EMR_', '').lower()), self.handle_unknown) for k, v in RECORD_TYPES.items()}
        self.bitmaps = []
        while self.pos < len(raw) and not self.found_eof:
            self.read_record(raw)
        self.has_raster_image = bool(self.bitmaps)

    def handle_unknown(self, rtype: int, size: int, raw: bytes) -> None:
        if self.verbose:
            print('Ignoring unknown record:', RECORD_RMAP.get(rtype, hex(rtype).upper()))

    def handle_header(self, rtype: int, size: int, raw: bytes) -> None:
        pass

    def handle_stretchdibits(self, rtype: int, size: int, raw: bytes) -> None:
        data = StretchDiBits(*unpack_from(b'<18I', raw, 8))
        hdr = raw[data.bmp_hdr_offset : data.bmp_hdr_offset + data.bmp_header_size]
        bits = raw[data.bmp_bits_offset : data.bmp_bits_offset + data.bmp_bits_size]
        bmp = create_bmp_from_dib(hdr + bits)
        self.bitmaps.append(bmp)

    def handle_eof(self, rtype: int, size: int, raw: bytes) -> None:
        self.found_eof = True

    def read_record(self, raw: bytes) -> None:
        rtype, size = unpack_from(b'<II', raw, self.pos)
        record = raw[self.pos : self.pos + size]
        self.pos += size
        self.func_map.get(rtype, self.handle_unknown)(rtype, size, record)

    def to_png(self) -> bytes:
        bmps = list(sorted(self.bitmaps, key=len))
        bmp = bmps[-1]
        return to_png(bmp)


def emf_unwrap(raw: bytes, verbose: int = 0) -> bytes:
    """
    Return the largest embedded raster image in the EMF.
    The returned data is in PNG format.
    """
    w = EMF(raw, verbose=verbose)
    if not w.has_raster_image:
        raise ValueError('No raster image found in the EMF')
    return w.to_png()


if __name__ == '__main__':
    with open(sys.argv[-1], 'rb') as f:
        raw = f.read()
    emf = EMF(raw, verbose=4)
    with open('/t/test.bmp', 'wb') as f:
        f.write(emf.bitmaps[0])
    with open('/t/test.png', 'wb') as f:
        f.write(emf.to_png())
