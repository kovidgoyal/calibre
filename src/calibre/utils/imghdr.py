#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
from collections.abc import Iterator
from struct import error, unpack, unpack_from
from typing import IO

from calibre.utils.speedups import ReadOnlyFileBuffer

''' Recognize image file formats and sizes based on their first few bytes.'''

HSIZE = 120


def what(file, h=None):
    "Recognize image headers"
    if h is None:
        if isinstance(file, (str, bytes)):
            with open(file, 'rb') as f:
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
    """Recognize file format and sizes. Returns format, width, height. width
    and height will be -1 if not found and fmt will be None if the image is not
    recognized."""
    needs_close = False

    if isinstance(src, str):
        stream = open(src, 'rb')
        needs_close = True
    elif isinstance(src, bytes):
        stream = ReadOnlyFileBuffer(src)
    else:
        stream = src
    try:
        return _identify(stream)
    finally:
        if needs_close:
            stream.close()


def _identify(stream):
    width = height = -1

    pos = stream.tell()
    head = stream.read(HSIZE)
    stream.seek(pos)
    fmt = what(None, head)

    if fmt in {'jpeg', 'gif', 'png', 'jpeg2000', 'webp', 'avif', 'jxl'}:
        size = len(head)
        if fmt == 'png':
            # PNG
            s = head[16:24] if size >= 24 and head[12:16] == b'IHDR' else head[8:16]
            try:
                width, height = unpack(b'>LL', s)
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
                width, height = unpack(b'<HH', head[6:10])
            except error:
                return fmt, width, height
        elif size >= 56 and fmt == 'jpeg2000':
            # JPEG2000
            try:
                height, width = unpack(b'>LL', head[48:56])
            except error:
                return fmt, width, height
        elif fmt == 'webp':
            try:
                width, height = webp_dimensions(head)
            except error:
                return fmt, width, height
        elif fmt == 'avif':
            pos = stream.tell()
            try:
                width, height = avif_dimensions(stream)
            except Exception:
                return fmt, width, height
            finally:
                stream.seek(pos)
        elif fmt == 'jxl':
            pos = stream.tell()
            try:
                width, height = jxl_dimensions(stream)
            except Exception:
                return fmt, width, height
            finally:
                stream.seek(pos)
    return fmt, width, height


# ---------------------------------#
# Subroutines per image file type  #
# ---------------------------------#

_tests = []


def test(f):
    _tests.append(f)
    return f


@test
def jpeg(h):
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

    def read_byte():
        return read(1)[0]

    x = None
    while True:
        # Find next marker
        while x != 0xFF:
            x = read_byte()
        # Soak up padding
        marker = 0xFF
        while marker == 0xFF:
            marker = read_byte()
        q = marker
        if 0xC0 <= q <= 0xCF and q not in {0xC4, 0xCC}:
            # SOFn marker
            stream.seek(3, os.SEEK_CUR)
            return unpack(b'>HH', read(4))
        elif 0xD8 <= q <= 0xDA:
            break  # start of image, end of image, start of scan, no point
        elif q == 0:
            return -1, -1  # Corrupted JPEG
        elif q == 0x01 or 0xD0 <= q <= 0xD7:
            # Standalone marker
            continue
        else:
            # skip this section
            size = unpack(b'>H', read(2))[0]
            stream.seek(size - 2, os.SEEK_CUR)
        # standalone marker, keep going

    return -1, -1


@test
def png(h):
    if h[:8] == b'\211PNG\r\n\032\n':
        return 'png'


@test
def gif(h):
    """GIF ('87 and '89 variants)"""
    if h[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'


@test
def tiff(h):
    """TIFF (can be in Motorola or Intel byte order)"""
    if h[:2] in (b'MM', b'II'):
        if h[2:4] == b'\xbc\x01':
            return 'jxr'
        return 'tiff'


@test
def webp(h):
    if h[:4] == b'RIFF' and h[8:12] == b'WEBP':
        return 'webp'


@test
def avif(h):
    """AVIF (still images and image sequences), which is ISOBMFF based, like HEIF"""
    if h[4:8] != b'ftyp':
        return None
    try:
        box_size = unpack(b'>L', h[:4])[0]
    except error:
        return None
    # The major brand is at offset 8 and the compatible brands follow the
    # (four byte) minor version at offset 16
    brands = [h[8:12].tobytes()]
    for pos in range(16, min(box_size, len(h)) - 3, 4):
        brands.append(h[pos : pos + 4].tobytes())
    for brand in brands:
        if brand in (b'avif', b'avis'):
            return 'avif'
    return None


JXL_CODESTREAM_SIGNATURE = b'\xff\x0a'
JXL_CONTAINER_SIGNATURE = b'\x00\x00\x00\x0cJXL \x0d\x0a\x87\x0a'


@test
def jxl(h):
    """JPEG-XL, either a bare codestream or one in the ISOBMFF based container"""
    if h[:2] == JXL_CODESTREAM_SIGNATURE or h[:12] == JXL_CONTAINER_SIGNATURE:
        return 'jxl'
    return None


def webp_dimensions(h: bytes) -> tuple[int, int]:
    """The dimensions of a WebP image, from the header of its first chunk.
    See https://developers.google.com/speed/webp/docs/riff_container"""
    chunk = h[12:16]
    if chunk == b'VP8 ':
        # Lossy: a VP8 key frame, whose three byte frame tag is followed by a
        # start code and then the dimensions in the low 14 bits of two
        # little endian 16 bit numbers, the top two bits being for scaling
        if h[23:26] != b'\x9d\x01\x2a':
            return -1, -1
        width, height = unpack(b'<HH', h[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b'VP8L':
        # Lossless: a signature byte and then the width - 1 and height - 1 as
        # 14 bit numbers packed into a little endian 32 bit one
        if h[20:21] != b'\x2f':
            return -1, -1
        bits = unpack(b'<L', h[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b'VP8X':
        # Extended: the canvas width - 1 and height - 1 as 24 bit little
        # endian numbers, after a byte of flags and three reserved ones
        if len(h) < 30:
            raise error('Truncated WebP header')
        return int.from_bytes(h[24:27], 'little') + 1, int.from_bytes(h[27:30], 'little') + 1
    return -1, -1


# The most of an AVIF file to read looking for its dimensions, which are in
# the meta box, a few hundred bytes long and at the start of the file
AVIF_MAX_META_SIZE = 1024 * 1024
AVIF_MAX_TOP_LEVEL_BOXES = 32


def isobmff_boxes(data: bytes, pos: int = 0, end: int = -1) -> Iterator[tuple[bytes, int, int]]:
    """The type, start and end of the content of each box in data[pos:end]."""
    end = len(data) if end < 0 else end
    while pos + 8 <= end:
        size, box_type = unpack(b'>L4s', data[pos : pos + 8])
        start = pos + 8
        if size == 1:
            size = unpack(b'>Q', data[start : start + 8])[0]
            start += 8
        elif size == 0:
            size = end - pos
        if size < start - pos or pos + size > end:
            raise ValueError(f'Invalid size for the ISOBMFF box: {box_type!r}')
        yield box_type, start, pos + size
        pos += size


def read_avif_meta(stream: IO[bytes]) -> bytes:
    """The content of the top level meta box of an AVIF file."""
    for i in range(AVIF_MAX_TOP_LEVEL_BOXES):
        header = stream.read(8)
        if len(header) < 8:
            break
        size, box_type = unpack(b'>L4s', header)
        header_size = 8
        if size == 1:
            size = unpack(b'>Q', stream.read(8))[0]
            header_size = 16
        if box_type == b'meta':
            if size == 0 or size - header_size > AVIF_MAX_META_SIZE:
                raise ValueError('The AVIF meta box is too large')
            ans = stream.read(size - header_size)
            if len(ans) != size - header_size:
                raise ValueError('Truncated AVIF meta box')
            return ans
        if size < header_size:
            break
        stream.seek(size - header_size, os.SEEK_CUR)
    raise ValueError('No meta box found in the AVIF file')


def avif_dimensions(stream: IO[bytes]) -> tuple[int, int]:
    """The dimensions of the primary image of an AVIF file, as displayed,
    so swapped if it is rotated by 90 or 270 degrees.

    They are in the ispe property of the primary image, as listed in the
    ipma box, which refers to properties by their position in the ipco box,
    starting from one. See ISO/IEC 23008-12 (HEIF), on which AVIF is based.
    """
    meta = read_avif_meta(stream)
    primary = -1
    properties: list[tuple[bytes, int, int]] = []
    associations: dict[int, list[int]] = {}
    # meta is a full box, so its children come after its version and flags
    for box_type, start, end in isobmff_boxes(meta, 4):
        if box_type == b'pitm':
            # The item id is 16 bits in version 0 and 32 bits after that
            primary = unpack_from(b'>H' if meta[start] == 0 else b'>L', meta, start + 4)[0]
        elif box_type == b'iprp':
            for child, cstart, cend in isobmff_boxes(meta, start, end):
                if child == b'ipco':
                    properties = list(isobmff_boxes(meta, cstart, cend))
                elif child == b'ipma':
                    version, flags = meta[cstart], int.from_bytes(meta[cstart + 1 : cstart + 4], 'big')
                    pos = cstart + 4
                    count = unpack(b'>L', meta[pos : pos + 4])[0]
                    pos += 4
                    for e in range(count):
                        if version < 1:
                            item = unpack(b'>H', meta[pos : pos + 2])[0]
                            pos += 2
                        else:
                            item = unpack(b'>L', meta[pos : pos + 4])[0]
                            pos += 4
                        num = meta[pos]
                        pos += 1
                        indices = []
                        for a in range(num):
                            # The top bit of each is the essential flag
                            if flags & 1:
                                indices.append(unpack(b'>H', meta[pos : pos + 2])[0] & 0x7FFF)
                                pos += 2
                            else:
                                indices.append(meta[pos] & 0x7F)
                                pos += 1
                        associations[item] = indices

    def property_of(item: int, name: bytes) -> tuple[int, int] | None:
        for index in associations.get(item, ()):
            if 0 < index <= len(properties) and properties[index - 1][0] == name:
                return properties[index - 1][1:]
        return None

    ispe = property_of(primary, b'ispe')
    if ispe is None:
        # No primary item or one without an ispe property of its own
        ispe = next((p[1:] for p in properties if p[0] == b'ispe'), None)
        if ispe is None:
            raise ValueError('No ispe property found in the AVIF file')
    # ispe is a full box, so the dimensions come after its version and flags
    width, height = unpack(b'>LL', meta[ispe[0] + 4 : ispe[0] + 12])
    irot = property_of(primary, b'irot')
    # irot is the number of 90 degree anti-clockwise rotations
    if irot is not None and meta[irot[0]] & 1:
        width, height = height, width
    return width, height


# The most of the start of a JPEG-XL codestream needed to read the image
# dimensions and orientation, which are at most 89 bits after the signature
JXL_HEADER_SIZE = 16
JXL_MAX_BOXES = 32
# Width to height ratios, indexed by the ratio field of the size header
JXL_RATIOS = ((1, 1), (1, 1), (12, 10), (4, 3), (3, 2), (16, 9), (5, 4), (2, 1))


class BitReader:
    """Read the bits of data starting with the least significant bit of
    the first byte, the bit order used in JPEG-XL codestreams."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def bits(self, n: int) -> int:
        ans = 0
        for i in range(n):
            byte = self.pos >> 3
            if byte >= len(self.data):
                raise ValueError('Truncated JPEG-XL codestream header')
            ans |= ((self.data[byte] >> (self.pos & 7)) & 1) << i
            self.pos += 1
        return ans

    def u32(self, *distribution: tuple[int, int]) -> int:
        """A U32 field: two bits select one of the four (offset, number of bits) pairs."""
        offset, n = distribution[self.bits(2)]
        return offset + self.bits(n)


def read_jxl_codestream_header(stream: IO[bytes]) -> bytes:
    """The first JXL_HEADER_SIZE bytes of the codestream, after its
    signature. In the container the codestream is either in a single jxlc
    box or split over multiple jxlp boxes, which can be interleaved with
    other boxes. See ISO/IEC 18181-2."""
    head = bytes(stream.read(len(JXL_CONTAINER_SIGNATURE)))
    if head[:2] == JXL_CODESTREAM_SIGNATURE:
        return head[2:] + bytes(stream.read(JXL_HEADER_SIZE + 2 - len(head)))
    if head != JXL_CONTAINER_SIGNATURE:
        raise ValueError('Not a JPEG-XL file')
    codestream = b''
    for i in range(JXL_MAX_BOXES):
        header = stream.read(8)
        if len(header) < 8:
            break
        size, box_type = unpack(b'>L4s', header)
        header_size = 8
        if size == 1:
            size = unpack(b'>Q', stream.read(8))[0]
            header_size = 16
        elif size == 0:
            size = 1 << 62  # the box extends to the end of the file
        if size < header_size:
            break
        remaining = size - header_size
        if box_type in (b'jxlc', b'jxlp'):
            last = box_type == b'jxlc'
            if box_type == b'jxlp':
                # A sequence number with the top bit set for the last part
                index = stream.read(4)
                if len(index) < 4:
                    break
                last = bool(index[0] & 0x80)
                remaining -= 4
            data = bytes(stream.read(max(0, min(remaining, JXL_HEADER_SIZE + 2 - len(codestream)))))
            codestream += data
            remaining -= len(data)
            if last or len(codestream) >= JXL_HEADER_SIZE + 2:
                break
        stream.seek(remaining, os.SEEK_CUR)
    if codestream[:2] != JXL_CODESTREAM_SIGNATURE:
        raise ValueError('No codestream found in the JPEG-XL container')
    return codestream[2:]


def jxl_dimensions(stream: IO[bytes]) -> tuple[int, int]:
    """The dimensions of a JPEG-XL image, as displayed, so swapped if its
    orientation transposes it.

    They are in the size header at the start of the codestream, which is
    followed by the image metadata, which starts with the orientation. See
    ISO/IEC 18181-1."""
    r = BitReader(read_jxl_codestream_header(stream))
    small = r.bits(1)
    if small:
        height = (r.bits(5) + 1) * 8
    else:
        height = r.u32((1, 9), (1, 13), (1, 18), (1, 30))
    ratio = r.bits(3)
    if ratio:
        num, den = JXL_RATIOS[ratio]
        width = height * num // den
    elif small:
        width = (r.bits(5) + 1) * 8
    else:
        width = r.u32((1, 9), (1, 13), (1, 18), (1, 30))
    orientation = 1
    all_default = r.bits(1)
    if not all_default:
        extra_fields = r.bits(1)
        if extra_fields:
            orientation = r.bits(3) + 1
    # Orientations from 5 onwards transpose the image
    if orientation > 4:
        width, height = height, width
    return width, height


@test
def rgb(h):
    """SGI image library"""
    if h[:2] == b'\001\332':
        return 'rgb'


@test
def pbm(h):
    """PBM (portable bitmap)"""
    if len(h) >= 3 and h[0] == b'P' and h[1] in b'14' and h[2] in b' \t\n\r':
        return 'pbm'


@test
def pgm(h):
    """PGM (portable graymap)"""
    if len(h) >= 3 and h[0] == b'P' and h[1] in b'25' and h[2] in b' \t\n\r':
        return 'pgm'


@test
def ppm(h):
    """PPM (portable pixmap)"""
    if len(h) >= 3 and h[0] == b'P' and h[1] in b'36' and h[2] in b' \t\n\r':
        return 'ppm'


@test
def rast(h):
    """Sun raster file"""
    if h[:4] == b'\x59\xa6\x6a\x95':
        return 'rast'


@test
def xbm(h):
    """X bitmap (X10 or X11)"""
    s = b'#define '
    if h[: len(s)] == s:
        return 'xbm'


@test
def bmp(h):
    if h[:2] == b'BM':
        return 'bmp'


@test
def emf(h):
    if h[:4] == b'\x01\0\0\0' and h[40:44] == b' EMF':
        return 'emf'


@test
def jpeg2000(h):
    if h[:12] == b'\x00\x00\x00\x0cjP  \r\n\x87\n':
        return 'jpeg2000'


@test
def svg(h):
    if h[:4] == b'<svg' or (h[:2] == b'<?' and h[2:5].tobytes().lower() == b'xml' and b'<svg' in h.tobytes()):
        return 'svg'


tests = tuple(_tests)
