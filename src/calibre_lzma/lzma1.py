#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from io import BytesIO
from struct import unpack

from calibre.ptempfile import SpooledTemporaryFile
from .errors import NotLzma, lzma


def read_header(f):
    raw = f.read(13)
    try:
        props, dict_size, uncompressed_size = unpack(b'<BIQ', raw)
    except Exception:
        raise NotLzma('Not a LZMA file')
    if props > (4 * 5 + 4) * 9 + 8:
        raise NotLzma('Not a LZMA file')
    return uncompressed_size, raw


def decompress(raw, outfile=None, bufsize=10 * 1024 * 1024):
    if isinstance(raw, bytes):
        raw = BytesIO(raw)
    uncompressed_size, header = read_header(raw)
    outfile = outfile or SpooledTemporaryFile(50 * 1024 * 1024, '_lzma_decompress')
    lzma.decompress(
        raw.read, raw.seek, outfile.write, uncompressed_size, header, bufsize
    )
    if uncompressed_size < outfile.tell():
        outfile.seek(uncompressed_size)
        outfile.truncate()
    return outfile


if __name__ == '__main__':
    import sys
    decompress(open(sys.argv[-1], 'rb'))
