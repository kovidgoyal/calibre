#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from struct import unpack, error
import os
from calibre.utils.speedups import ReadOnlyFileBuffer

""" Recognize image file formats and sizes based on their first few bytes."""

HSIZE = 120

def what(file, h=None):
    ' Recognize image headers '
    if h is None:
        if isinstance(file, basestring):
            with lopen(file, 'rb') as f:
                h = f.read(HSIZE)
        else:
            location = file.tell()
            h = file.read(HSIZE)
            file.seek(location)
    if isinstance(h, bytes):
        h = memoryview(h)
    for tf in tests:
        res = tf(h)
        if res:
            return res
    # There exist some jpeg files with no headers, only the starting two bits
    # If we cannot identify as anything else, identify as jpeg.
    if h[:2] == b'\xff\xd8':
        return 'jpeg'
    return None

def identify(src):
    ''' Recognize file format and sizes. Returns format, width, height. width
    and height will be -1 if not found and fmt will be None if the image is not
    recognized. '''
    width = height = -1

    if isinstance(src, type('')):
        stream = lopen(src, 'rb')
    elif isinstance(src, bytes):
        stream = ReadOnlyFileBuffer(src)
    else:
        stream = src

    pos = stream.tell()
    head = stream.read(HSIZE)
    stream.seek(pos)
    fmt = what(None, head)

    if fmt in {'jpeg', 'gif', 'png', 'jpeg2000'}:
        size = len(head)
        if fmt == 'png':
            # PNG
            s = head[16:24] if size >= 24 and head[12:16] == b'IHDR' else head[8:16]
            try:
                width, height = unpack(b">LL", s)
            except error:
                return fmt, width, height
        elif fmt == 'jpeg':
            # JPEG
            pos = stream.tell()
            try:
                height, width = jpeg_dimensions(stream)
            except Exception:
                return fmt, width, height
            finally:
                stream.seek(pos)
        elif fmt == 'gif':
            # GIF
            try:
                width, height = unpack(b"<HH", head[6:10])
            except error:
                return fmt, width, height
        elif size >= 56 and fmt == 'jpeg2000':
            # JPEG2000
            try:
                height, width = unpack(b'>LL', head[48:56])
            except error:
                return fmt, width, height
    return fmt, width, height

# ---------------------------------#
# Subroutines per image file type #
# ---------------------------------#

tests = []

def test_jpeg(h):
    """JPEG data in JFIF format (Changed by Kovid to mimic the file utility,
    the original code was failing with some jpegs that included ICC_PROFILE
    data, for example: http://nationalpostnews.files.wordpress.com/2013/03/budget.jpeg?w=300&h=1571)"""
    if h[6:10] in (b'JFIF', b'Exif'):
        return 'jpeg'
    if h[:2] == b'\xff\xd8':
        q = h[:32].tobytes()
        if b'JFIF' in q or b'8BIM' in q:
            return 'jpeg'

def jpeg_dimensions(stream):
    # A JPEG marker is two bytes of the form 0xff x where 0 < x < 0xff
    # See section B.1.1.2 of https://www.w3.org/Graphics/JPEG/itu-t81.pdf
    # We read the dimensions from the first SOFn section we come across
    stream.seek(2, os.SEEK_CUR)

    def read(n):
        ans = stream.read(n)
        if len(ans) != n:
            raise ValueError('Truncated JPEG data')
        return ans

    x = b''
    while True:
        # Find next marker
        while x != b'\xff':
            x = read(1)
        # Soak up padding
        marker = b'\xff'
        while marker == b'\xff':
            marker = read(1)
        q = ord(marker[0])  # [0] needed for memoryview
        if 0xc0 <= q <= 0xcf and q != 0xc4 and q != 0xcc:
            # SOFn marker
            stream.seek(3, os.SEEK_CUR)
            return unpack(b'>HH', read(4))
        elif 0xd8 <= q <= 0xda:
            break  # start of image, end of image, start of scan, no point
        elif q == 0:
            return -1, -1  # Corrupted JPEG
        elif q == 0x01 or 0xd0 <= q <= 0xd7:
            # Standalone marker
            continue
        else:
            # skip this section
            size = unpack(b'>H', read(2))[0]
            stream.seek(size - 2, os.SEEK_CUR)
        # standalone marker, keep going

    return -1, -1

tests.append(test_jpeg)

def test_png(h):
    if h[:8] == b"\211PNG\r\n\032\n":
        return 'png'

tests.append(test_png)

def test_gif(h):
    """GIF ('87 and '89 variants)"""
    if h[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'

tests.append(test_gif)

def test_tiff(h):
    """TIFF (can be in Motorola or Intel byte order)"""
    if h[:2] in (b'MM', b'II'):
        return 'tiff'

tests.append(test_tiff)

def test_webp(h):
    if h[:4] == b'RIFF' and h[8:12] == b'WEBP':
        return 'webp'

tests.append(test_webp)

def test_rgb(h):
    """SGI image library"""
    if h[:2] == b'\001\332':
        return 'rgb'

tests.append(test_rgb)

def test_pbm(h):
    """PBM (portable bitmap)"""
    if len(h) >= 3 and \
        h[0] == b'P' and h[1] in b'14' and h[2] in b' \t\n\r':
        return 'pbm'

tests.append(test_pbm)

def test_pgm(h):
    """PGM (portable graymap)"""
    if len(h) >= 3 and \
        h[0] == b'P' and h[1] in b'25' and h[2] in b' \t\n\r':
        return 'pgm'

tests.append(test_pgm)

def test_ppm(h):
    """PPM (portable pixmap)"""
    if len(h) >= 3 and \
        h[0] == b'P' and h[1] in b'36' and h[2] in b' \t\n\r':
        return 'ppm'

tests.append(test_ppm)

def test_rast(h):
    """Sun raster file"""
    if h[:4] == b'\x59\xA6\x6A\x95':
        return 'rast'

tests.append(test_rast)

def test_xbm(h):
    """X bitmap (X10 or X11)"""
    s = b'#define '
    if h[:len(s)] == s:
        return 'xbm'

tests.append(test_xbm)

def test_bmp(h):
    if h[:2] == b'BM':
        return 'bmp'

tests.append(test_bmp)

def test_emf(h):
    if h[:4] == b'\x01\0\0\0' and h[40:44] == b' EMF':
        return 'emf'

tests.append(test_emf)

def test_jpeg2000(h):
    if h[:12] == b'\x00\x00\x00\x0cjP  \r\n\x87\n':
        return 'jpeg2000'

tests.append(test_jpeg2000)

def test_svg(h):
    if h[:4] == b'<svg' or (h[:2] == b'<?' and h[2:5].tobytes().lower() == b'xml' and b'<svg' in h.tobytes()):
        return 'svg'

tests.append(test_svg)

