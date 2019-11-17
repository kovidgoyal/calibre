#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

# See http://tukaani.org/xz/xz-file-format.txt for file format details

from collections import namedtuple
from io import BytesIO
from hashlib import sha256
from struct import unpack, error as struct_error, pack
from binascii import crc32 as _crc32

from calibre.ptempfile import SpooledTemporaryFile
from .errors import NotXZ, InvalidXZ, lzma
from polyglot.builtins import error_message

HEADER_MAGIC = b'\xfd7zXZ\0'
FOOTER_MAGIC = b'YZ'
DELTA_FILTER_ID = 0x03
LZMA2_FILTER_ID = 0x21


def align(raw):
    extra = len(raw) % 4
    if extra:
        raw += b'\0' * (4 - extra)
    return raw


def as_bytes(*args):
    return bytes(bytearray(args))


def crc32(raw, start=0):
    return 0xFFFFFFFF & _crc32(raw, start)


def decode_var_int(f):
    ans, i, ch = 0, -1, 0x80
    while ch >= 0x80:
        ch = ord(f.read(1))
        i += 1
        if ch == 0:
            return 0
        ans |= (ch & 0x7f) << (i * 7)
    return ans


def decode_var_int2(raw, pos):
    ans, ch, opos = 0, 0x80, pos
    while ch >= 0x80:
        ch = ord(raw[pos:pos+1])
        if ch == 0:
            return 0, pos
        ans |= (ch & 0x7f) << ((pos - opos) * 7)
        pos += 1
    return ans, pos


def encode_var_int(num):
    if num == 0:
        return b'\0'
    buf = bytearray()
    a = buf.append
    while num != 0:
        a(0x80 | (num & 0x7F))
        num >>= 7
    buf[-1] &= 0x7F
    return bytes(buf)


def read_stream_header(f):
    try:
        magic, stream_flags1, stream_flags2, crc = unpack(b'<6s2BI', f.read(12))
    except struct_error as e:
        raise NotXZ('Not an XZ file. Invalid stream header: ' % e)
    if magic != HEADER_MAGIC:
        raise NotXZ('Not an XZ file. Header Magic is: %r' % magic)
    if stream_flags1 != 0:
        raise InvalidXZ('Stream flags first byte is not null')
    check_type, reserved = 0x0f & stream_flags2, 0xf0 & stream_flags2
    if reserved != 0:
        raise InvalidXZ('Stream flags reserved bits not null')
    if crc32(bytes(bytearray([stream_flags1, stream_flags2]))) != crc:
        raise InvalidXZ('Stream flags header CRC incorrect')
    return check_type


class CRCChecker(object):

    def __init__(self, check_type):
        self.code = 0
        if check_type == 0x1:
            self.func = crc32
            self.size = 4
            self.fmt = b'<I'
        else:
            self.func = lzma.crc64
            self.size = 8
            self.fmt = b'<Q'

    def __call__(self, raw):
        self.code = self.func(raw, self.code)

    def finish(self):
        if self.func is not crc32:
            self.code = 0xFFFFFFFFFFFFFFFF & self.code

    @property
    def code_as_bytes(self):
        return pack(self.fmt, self.code)

    def check(self, raw):
        return self.code == unpack(self.fmt, raw)[0]


class Sha256Checker(object):

    def __init__(self, *args):
        self.h = sha256()
        self.func = self.h.update
        self.code = None
        self.size = 32

    def __call__(self, raw):
        self.func(raw)

    def finish(self):
        self.code = self.code_as_bytes = self.h.digest()
        self.h = self.func = None

    def check(self, raw):
        return self.code == raw


class DummyChecker(object):

    size = 0
    code_as_bytes = None

    def __init__(self, *args):
        pass

    def __call__(self, raw):
        pass

    def finish(self):
        pass


class LZMA2Filter(object):

    BUFSIZE = 10  # MB

    def __init__(self, props, check_type, bufsize=None):
        if len(props) != 1:
            raise InvalidXZ('Invalid properties length for LZMA2 filter')
        props = ord(props)
        self.dictionary_size = props & 0x3F
        if props & 0xC0 != 0:
            raise InvalidXZ('Invalid high bytes for LZMA2 filter properties')
        self.props = props
        if check_type in (0x1, 0x4):
            self.crc = CRCChecker(check_type)
        elif check_type == 0x0A:
            self.crc = Sha256Checker()
        else:
            if check_type:
                raise InvalidXZ('Unsupported CRC check type: %s' % check_type)
            self.crc = DummyChecker()
        if bufsize is None:
            bufsize = self.BUFSIZE
        self.bufsize = int(bufsize * 1024 * 1024)

    def __call__(self, f, outfile, filters=()):
        w = outfile.write
        c = self.crc

        def write(raw):
            if filters:
                raw = bytearray(raw)
                for flt in filters:
                    raw = flt(raw)
                raw = bytes(raw)
            w(raw), c(raw)

        try:
            lzma.decompress2(f.read, f.seek, write, self.props, self.bufsize)
        except lzma.error as e:
            raise InvalidXZ(
                'Failed to decode LZMA2 block with error code: %s' % error_message(e)
            )
        self.crc.finish()


class DeltaFilter(object):

    def __init__(self, props, *args):
        if len(props) != 1:
            raise InvalidXZ('Invalid properties length for Delta filter')
        self.distance = ord(props) + 1
        self.pos = 0
        self.history = bytearray(256)

    def __call__(self, raw):
        self.pos = lzma.delta_decode(raw, self.history, self.pos, self.distance)
        return raw


def test_delta_filter():
    raw = b'\xA1\xB1\x01\x02\x01\x02\x01\x02'
    draw = b'\xA1\xB1\xA2\xB3\xA3\xB5\xA4\xB7'

    def eq(s, d):
        if s != d:
            raise ValueError('%r != %r' % (s, d))

    eq(draw, bytes(DeltaFilter(b'\x01')(bytearray(raw))))
    f = DeltaFilter(b'\x01')
    for ch, dch in zip(raw, draw):
        eq(dch, bytes(f(bytearray(ch))))


Block = namedtuple('Block', 'unpadded_size uncompressed_size')


def read_block_header(f, block_header_size_, check_type):
    block_header_size = 4 * (ord(block_header_size_) + 1)
    if block_header_size < 8:
        raise InvalidXZ('Invalid block header size: %d' % block_header_size)
    header, crc = unpack(
        b'<%dsI' % (block_header_size - 5), f.read(block_header_size - 1)
    )
    if crc != crc32(block_header_size_ + header):
        raise InvalidXZ('Block header CRC mismatch')
    block_flags = ord(header[0:1])
    number_of_filters = (0x03 & block_flags) + 1
    if not (0 < number_of_filters <= 4):
        raise InvalidXZ('Invalid number of filters: %d' % number_of_filters)
    if block_flags & 0x3c != 0:
        raise InvalidXZ('Non-zero reserved bits in block flags')
    has_compressed_size = block_flags & 0x40
    has_uncompressed_size = block_flags & 0x80
    compressed_size = uncompressed_size = None
    pos = 1
    if has_compressed_size:
        compressed_size, pos = decode_var_int2(header, pos)
    if has_uncompressed_size:
        uncompressed_size, pos = decode_var_int2(header, pos)
    filters = []
    while number_of_filters:
        number_of_filters -= 1
        filter_id, pos = decode_var_int2(header, pos)
        size_of_properties, pos = decode_var_int2(header, pos)
        if filter_id >= 0x4000000000000000:
            raise InvalidXZ('Invalid filter id: %d' % filter_id)
        if filter_id not in (LZMA2_FILTER_ID, DELTA_FILTER_ID):
            raise InvalidXZ('Unsupported filter ID: 0x%x' % filter_id)
        props = header[pos:pos + size_of_properties]
        pos += size_of_properties
        if len(props) != size_of_properties:
            raise InvalidXZ('Incomplete filter properties')
        if filter_id == LZMA2_FILTER_ID and number_of_filters:
            raise InvalidXZ('LZMA2 filter must be the last filter')
        elif filter_id == DELTA_FILTER_ID and not number_of_filters:
            raise InvalidXZ('Delta filter cannot be the last filter')
        filters.append(
            (LZMA2Filter
             if filter_id == LZMA2_FILTER_ID else DeltaFilter)(props, check_type)
        )
    padding = header[pos:]
    if padding.lstrip(b'\0'):
        raise InvalidXZ('Non-null block header padding: %r' % padding)
    filters.reverse()
    return filters, compressed_size, uncompressed_size


def read_block(f, block_header_size_, check_type, outfile):
    start_pos = f.tell() - 1
    filters, compressed_size, uncompressed_size = read_block_header(
        f, block_header_size_, check_type
    )
    fpos, opos = f.tell(), outfile.tell()
    filters[0](f, outfile, filters[1:])
    actual_compressed_size = f.tell() - fpos
    uncompressed_actual_size = outfile.tell() - opos
    if uncompressed_size is not None and uncompressed_size != uncompressed_actual_size:
        raise InvalidXZ('Uncompressed size for block does not match')
    if compressed_size is not None and compressed_size != actual_compressed_size:
        raise InvalidXZ('Compressed size for block does not match')
    padding_count = f.tell() % 4
    if padding_count:
        padding_count = 4 - padding_count
        padding = f.read(padding_count)
        if len(padding) != padding_count:
            raise InvalidXZ('Block is not aligned')
        if padding.lstrip(b'\0'):
            raise InvalidXZ('Block padding has non null bytes')
    if check_type:
        q = f.read(filters[0].crc.size)
        if not filters[0].crc.check(q):
            raise InvalidXZ('CRC for data does not match')
    return Block(f.tell() - padding_count - start_pos, uncompressed_actual_size)


def read_index(f):
    pos = f.tell() - 1
    number_of_records = decode_var_int(f)
    while number_of_records:
        number_of_records -= 1
        unpadded_size = decode_var_int(f)
        if unpadded_size < 1:
            raise InvalidXZ('Invalid unpadded size in index: %d' % unpadded_size)
        yield Block(unpadded_size, decode_var_int(f))
    if f.tell() % 4:
        padding_count = 4 - f.tell() % 4
        padding = f.read(padding_count)
        if len(padding) != padding_count or padding.lstrip(b'\0'):
            raise InvalidXZ('Incorrect Index padding')
    epos = f.tell()
    f.seek(pos)
    raw = f.read(epos - pos)
    crc, = unpack(b'<I', f.read(4))
    if crc != crc32(raw):
        raise InvalidXZ('Index field CRC mismatch')


def read_stream_footer(f, check_type, index_size):
    crc, = unpack(b'<I', f.read(4))
    raw = f.read(6)
    backward_size, stream_flags1, stream_flags2 = unpack(b'<I2B', raw)
    if stream_flags1 != 0 or stream_flags2 & 0xf0 != 0 or stream_flags2 & 0xf != check_type:
        raise InvalidXZ('Footer stream flags != header stream flags')
    backward_size = 4 * (1 + backward_size)
    if backward_size != index_size:
        raise InvalidXZ('Footer backward size != actual index size')
    if f.read(2) != FOOTER_MAGIC:
        raise InvalidXZ('Stream footer has incorrect magic bytes')
    if crc != crc32(raw):
        raise InvalidXZ('Stream footer CRC mismatch')


def read_stream(f, outfile):
    check_type = read_stream_header(f)
    blocks, index = [], None
    index_size = 0
    while True:
        sz = f.read(1)
        if sz == b'\0':
            pos = f.tell() - 1
            index = tuple(read_index(f))
            index_size = f.tell() - pos
            break
        else:
            blocks.append(read_block(f, sz, check_type, outfile))
    if index != tuple(blocks):
        raise InvalidXZ('Index does not match actual blocks in file')
    read_stream_footer(f, check_type, index_size)


def decompress(raw, outfile=None):
    '''
    Decompress the specified data.

    :param raw: A bytestring or a file-like object open for reading
    :outfile: A file like object open for writing.
              The decompressed data is written into it. If not specified then a SpooledTemporaryFile
              is created and returned by this function.
    '''
    if isinstance(raw, bytes):
        raw = BytesIO(raw)
    outfile = outfile or SpooledTemporaryFile(50 * 1024 * 1024, '_xz_decompress')
    while True:
        read_stream(raw, outfile)
        pos = raw.tell()
        trail = raw.read(1024)
        if len(trail) < 20:
            break
        idx = trail.find(HEADER_MAGIC)
        if idx == -1:
            break
        if idx > -1:
            # Found another stream
            raw.seek(pos)
            if idx:
                padding = raw.read(idx)
                if padding.lstrip(b'\0') or len(padding) % 4:
                    raise InvalidXZ('Found trailing garbage between streams')
    return outfile


def compress(raw, outfile=None, level=5, check_type='crc64'):
    '''
    Compress the specified data into a .xz stream (which can be written directly as
    an .xz file.

    :param raw: A bytestring or a file-like object open for reading
    :outfile: A file like object open for writing.
              The .xz stream is written into it. If not specified then a SpooledTemporaryFile
              is created and returned by this function.
    :level: An integer between 0 and 9 with 0 being fastest/worst compression and 9 being
            slowest/best compression
    :check_type: The type of data integrity check to write into the output .xz stream.
                 Should be one of: 'crc32', 'crc64', 'sha256', or None
    '''
    if isinstance(raw, bytes):
        raw = BytesIO(raw)
    outfile = outfile or SpooledTemporaryFile(50 * 1024 * 1024, '_xz_decompress')

    # Write stream header
    outfile.write(HEADER_MAGIC)
    check_type = {
        'crc': 1,
        'crc32': 1,
        'sha256': 0xa,
        None: 0,
        '': 0,
        'none': 0,
        'None': 0
    }.get(check_type, 4)
    stream_flags = as_bytes(0, check_type)
    outfile.write(stream_flags)
    outfile.write(pack(b'<I', crc32(stream_flags)))

    # Write block header
    filter_flags = encode_var_int(LZMA2_FILTER_ID
                                  ) + encode_var_int(1) + lzma.preset_map[level]
    block_header = align(b'\0\0' + filter_flags)
    bhs = ((4 + len(block_header)) // 4) - 1
    block_header = as_bytes(bhs) + block_header[1:]
    block_header += pack(b'<I', crc32(block_header))
    start = outfile.tell()
    outfile.write(block_header)

    # Write compressed data and check
    checker = {
        0: DummyChecker,
        1: CRCChecker,
        4: CRCChecker,
        0xa: Sha256Checker
    }[check_type](check_type)
    uncompressed_size = [0]

    def read(n):
        ans = raw.read(n)
        if ans:
            uncompressed_size[0] += len(ans)
            checker(ans)
        return ans

    lzma.compress(read, outfile.write, None, level)
    unpadded_size = outfile.tell() - start
    pos = outfile.tell()
    if pos % 4:
        outfile.write(b'\0' * (4 - (pos % 4)))
    checker.finish()
    if check_type:
        cc = checker.code_as_bytes
        outfile.write(cc)
        unpadded_size += len(cc)

    # Write index
    index = b'\0' + encode_var_int(1)
    index += encode_var_int(unpadded_size) + encode_var_int(uncompressed_size[0])
    if len(index) % 4:
        index += b'\0' * (4 - len(index) % 4)
    outfile.write(index), outfile.write(pack(b'<I', crc32(index)))

    # Write stream footer
    backwards_size = pack(b'<I', ((len(index) + 4) // 4) - 1)
    outfile.write(pack(b'<I', crc32(backwards_size + stream_flags)))
    outfile.write(backwards_size), outfile.write(stream_flags
                                                 ), outfile.write(FOOTER_MAGIC)


def test_lzma2():
    raw = P('template-functions.json', allow_user_override=False, data=True)
    ibuf, obuf = BytesIO(raw), BytesIO()
    props = lzma.compress(ibuf.read, obuf.write, False)
    cc = obuf.getvalue()
    ibuf, obuf = BytesIO(cc), BytesIO()
    LZMA2Filter(props, 0, 1)(ibuf, obuf)
    if obuf.getvalue() != raw:
        raise ValueError('Roundtripping via LZMA2 failed')


def test_xz():
    raw = P('template-functions.json', allow_user_override=False, data=True)
    ibuf, obuf = BytesIO(raw), BytesIO()
    compress(ibuf, obuf, check_type='sha256')
    cc = obuf.getvalue()
    ibuf, obuf = BytesIO(cc), BytesIO()
    decompress(ibuf, obuf)
    if obuf.getvalue() != raw:
        raise ValueError('Roundtripping via XZ failed')


if __name__ == '__main__':
    import sys
    decompress(open(sys.argv[-1], 'rb'))
