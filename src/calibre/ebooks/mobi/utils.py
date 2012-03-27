#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct, string, imghdr, zlib
from collections import OrderedDict

from calibre.utils.magick.draw import Image, save_cover_data_to, thumbnail
from calibre.ebooks import normalize

IMAGE_MAX_SIZE = 10 * 1024 * 1024

def decode_string(raw, codec='utf-8', ordt_map=''):
    length, = struct.unpack(b'>B', raw[0])
    raw = raw[1:1+length]
    consumed = length+1
    if ordt_map:
        return ''.join(ordt_map[ord(x)] for x in raw), consumed
    return raw.decode(codec), consumed

def decode_hex_number(raw, codec='utf-8'):
    '''
    Return a variable length number encoded using hexadecimal encoding. These
    numbers have the first byte which tells the number of bytes that follow.
    The bytes that follow are simply the hexadecimal representation of the
    number.

    :param raw: Raw binary data as a bytestring

    :return: The number and the number of bytes from raw that the number
    occupies.
    '''
    raw, consumed = decode_string(raw, codec=codec)
    return int(raw, 16), consumed

def encode_string(raw):
    ans = bytearray(bytes(raw))
    ans.insert(0, len(ans))
    return bytes(ans)

def encode_number_as_hex(num):
    '''
    Encode num as a variable length encoded hexadecimal number. Returns the
    bytestring containing the encoded number. These
    numbers have the first byte which tells the number of bytes that follow.
    The bytes that follow are simply the hexadecimal representation of the
    number.
    '''
    num = bytes(hex(num)[2:].upper())
    nlen = len(num)
    if nlen % 2 != 0:
        num = b'0'+num
    return encode_string(num)

def encint(value, forward=True):
    '''
    Some parts of the Mobipocket format encode data as variable-width integers.
    These integers are represented big-endian with 7 bits per byte in bits 1-7.
    They may be either forward-encoded, in which case only the first byte has bit 8 set,
    or backward-encoded, in which case only the last byte has bit 8 set.
    For example, the number 0x11111 = 0b10001000100010001 would be represented
    forward-encoded as:

        0x04 0x22 0x91 = 0b100 0b100010 0b10010001

    And backward-encoded as:

        0x84 0x22 0x11 = 0b10000100 0b100010 0b10001

    This function encodes the integer ``value`` as a variable width integer and
    returns the bytestring corresponding to it.

    If forward is True the bytes returned are suitable for prepending to the
    output buffer, otherwise they must be append to the output buffer.
    '''
    if value < 0:
        raise ValueError('Cannot encode negative numbers as vwi')
    # Encode vwi
    byts = bytearray()
    while True:
        b = value & 0b01111111
        value >>= 7 # shift value to the right by 7 bits

        byts.append(b)
        if value == 0:
            break
    byts[0 if forward else -1] |= 0b10000000
    byts.reverse()
    return bytes(byts)

def decint(raw, forward=True):
    '''
    Read a variable width integer from the bytestring or bytearray raw and return the
    integer and the number of bytes read. If forward is True bytes are read
    from the start of raw, otherwise from the end of raw.

    This function is the inverse of encint above, see its docs for more
    details.
    '''
    val = 0
    byts = bytearray()
    src = bytearray(raw)
    if not forward:
        src.reverse()
    for bnum in src:
        byts.append(bnum & 0b01111111)
        if bnum & 0b10000000:
            break
    if not forward:
        byts.reverse()
    for byte in byts:
        val <<= 7 # Shift value to the left by 7 bits
        val |= byte

    return val, len(byts)

def test_decint(num):
    for d in (True, False):
        raw = encint(num, forward=d)
        sz = len(raw)
        if (num, sz) != decint(raw, forward=d):
            raise ValueError('Failed for num %d, forward=%r: %r != %r' % (
                num, d, (num, sz), decint(raw, forward=d)))

def rescale_image(data, maxsizeb=IMAGE_MAX_SIZE, dimen=None):
    '''
    Convert image setting all transparent pixels to white and changing format
    to JPEG. Ensure the resultant image has a byte size less than
    maxsizeb.

    If dimen is not None, generate a thumbnail of
    width=dimen, height=dimen or width, height = dimen (depending on the type
    of dimen)

    Returns the image as a bytestring
    '''
    if dimen is not None:
        if hasattr(dimen, '__len__'):
            width, height = dimen
        else:
            width = height = dimen
        data = thumbnail(data, width=width, height=height,
                compression_quality=90)[-1]
    else:
        # Replace transparent pixels with white pixels and convert to JPEG
        data = save_cover_data_to(data, 'img.jpg', return_data=True)
    if len(data) <= maxsizeb:
        return data
    orig_data = data
    img = Image()
    quality = 95

    img.load(data)
    while len(data) >= maxsizeb and quality >= 10:
        quality -= 5
        img.set_compression_quality(quality)
        data = img.export('jpg')
    if len(data) <= maxsizeb:
        return data
    orig_data = data

    scale = 0.9
    while len(data) >= maxsizeb and scale >= 0.05:
        img = Image()
        img.load(orig_data)
        w, h = img.size
        img.size = (int(scale*w), int(scale*h))
        img.set_compression_quality(quality)
        data = img.export('jpg')
        scale -= 0.05
    return data

def get_trailing_data(record, extra_data_flags):
    '''
    Given a text record as a bytestring and the extra data flags from the MOBI
    header, return the trailing data as a dictionary, mapping bit number to
    data as bytestring. Also returns the record - all trailing data.

    :return: Trailing data, record - trailing data
    '''
    data = OrderedDict()
    flags = extra_data_flags >> 1

    num = 0
    while flags:
        num += 1
        if flags & 0b1:
            sz, consumed = decint(record, forward=False)
            if sz > consumed:
                data[num] = record[-sz:-consumed]
            record = record[:-sz]
        flags >>= 1
    # Read multibyte chars if any
    if extra_data_flags & 0b1:
        # Only the first two bits are used for the size since there can
        # never be more than 3 trailing multibyte chars
        sz = (ord(record[-1]) & 0b11) + 1
        consumed = 1
        if sz > consumed:
            data[0] = record[-sz:-consumed]
        record = record[:-sz]
    return data, record

def encode_trailing_data(raw):
    '''
    Given some data in the bytestring raw, return a bytestring of the form

        <data><size>

    where size is a backwards encoded vwi whose value is the length of the
    entire returned bytestring. data is the bytestring passed in as raw.

    This is the encoding used for trailing data entries at the end of text
    records. See get_trailing_data() for details.
    '''
    lsize = 1
    while True:
        encoded = encint(len(raw) + lsize, forward=False)
        if len(encoded) == lsize:
            break
        lsize += 1
    return raw + encoded

def encode_fvwi(val, flags, flag_size=4):
    '''
    Encode the value val and the flag_size bits from flags as a fvwi. This encoding is
    used in the trailing byte sequences for indexing. Returns encoded
    bytestring.
    '''
    ans = val << flag_size
    for i in xrange(flag_size):
        ans |= (flags & (1 << i))
    return encint(ans)


def decode_fvwi(byts, flag_size=4):
    '''
    Decode encoded fvwi. Returns number, flags, consumed
    '''
    arg, consumed = decint(bytes(byts))
    val = arg >> flag_size
    flags = 0
    for i in xrange(flag_size):
        flags |= (arg & (1 << i))
    return val, flags, consumed


def decode_tbs(byts, flag_size=4):
    '''
    Trailing byte sequences for indexing consists of series of fvwi numbers.
    This function reads the fvwi number and its associated flags. It them uses
    the flags to read any more numbers that belong to the series. The flags are
    the lowest 4 bits of the vwi (see the encode_fvwi function above).

    Returns the fvwi number, a dictionary mapping flags bits to the associated
    data and the number of bytes consumed.
    '''
    byts = bytes(byts)
    val, flags, consumed = decode_fvwi(byts, flag_size=flag_size)
    extra = {}
    byts = byts[consumed:]
    if flags & 0b1000 and flag_size > 3:
        extra[0b1000] = True
    if flags & 0b0010:
        x, consumed2 = decint(byts)
        byts = byts[consumed2:]
        extra[0b0010] = x
        consumed += consumed2
    if flags & 0b0100:
        extra[0b0100] = ord(byts[0])
        byts = byts[1:]
        consumed += 1
    if flags & 0b0001:
        x, consumed2 = decint(byts)
        byts = byts[consumed2:]
        extra[0b0001] = x
        consumed += consumed2
    return val, extra, consumed

def encode_tbs(val, extra, flag_size=4):
    '''
    Encode the number val and the extra data in the extra dict as an fvwi. See
    decode_tbs above.
    '''
    flags = 0
    for flag in extra:
        flags |= flag
    ans = encode_fvwi(val, flags, flag_size=flag_size)

    if 0b0010 in extra:
        ans += encint(extra[0b0010])
    if 0b0100 in extra:
        ans += bytes(bytearray([extra[0b0100]]))
    if 0b0001 in extra:
        ans += encint(extra[0b0001])
    return ans

def utf8_text(text):
    '''
    Convert a possibly null string to utf-8 bytes, guaranteeing to return a non
    empty, normalized bytestring.
    '''
    if text and text.strip():
        text = text.strip()
        if not isinstance(text, unicode):
            text = text.decode('utf-8', 'replace')
        text = normalize(text).encode('utf-8')
    else:
        text = _('Unknown').encode('utf-8')
    return text

def align_block(raw, multiple=4, pad=b'\0'):
    '''
    Return raw with enough pad bytes append to ensure its length is a multiple
    of 4.
    '''
    extra = len(raw) % multiple
    if extra == 0: return raw
    return raw + pad*(multiple - extra)


def detect_periodical(toc, log=None):
    '''
    Detect if the TOC object toc contains a periodical that conforms to the
    structure required by kindlegen to generate a periodical.
    '''
    if toc.count() < 1 or not toc[0].klass == 'periodical':
        return False
    for node in toc.iterdescendants():
        if node.depth() == 1 and node.klass != 'article':
            if log is not None:
                log.debug(
                'Not a periodical: Deepest node does not have '
                'class="article"')
            return False
        if node.depth() == 2 and node.klass != 'section':
            if log is not None:
                log.debug(
                'Not a periodical: Second deepest node does not have'
                ' class="section"')
            return False
        if node.depth() == 3 and node.klass != 'periodical':
            if log is not None:
                log.debug('Not a periodical: Third deepest node'
                    ' does not have class="periodical"')
            return False
        if node.depth() > 3:
            if log is not None:
                log.debug('Not a periodical: Has nodes of depth > 3')
            return False
    return True

def count_set_bits(num):
    if num < 0:
        num = -num
    ans = 0
    while num > 0:
        ans += (num & 0b1)
        num >>= 1
    return ans

def to_base(num, base=32):
    digits = string.digits + string.ascii_uppercase
    sign = 1 if num >= 0 else -1
    if num == 0: return '0'
    num *= sign
    ans = []
    while num:
        ans.append(digits[(num % base)])
        num //= base
    if sign < 0:
        ans.append('-')
    ans.reverse()
    return ''.join(ans)

def mobify_image(data):
    'Convert PNG images to GIF as the idiotic Kindle cannot display some PNG'
    what = imghdr.what(None, data)

    if what == 'png':
        im = Image()
        im.load(data)
        data = im.export('gif')
    return data

def read_zlib_header(header):
    header = bytearray(header)
    # See sec 2.2 of RFC 1950 for the zlib stream format
    # http://www.ietf.org/rfc/rfc1950.txt
    if (header[0]*256 + header[1])%31 != 0:
        return None, 'Bad zlib header, FCHECK failed'

    cmf = header[0] & 0b1111
    cinfo = header[0] >> 4
    if cmf != 8:
        return None, 'Unknown zlib compression method: %d'%cmf
    if cinfo > 7:
        return None, 'Invalid CINFO field in zlib header: %d'%cinfo
    fdict = (header[1]&0b10000)>>5
    if fdict != 0:
        return None, 'FDICT based zlib compression not supported'
    wbits = cinfo + 8
    return wbits, None


def read_font_record(data, extent=1040): # {{{
    '''
    Return the font encoded in the MOBI FONT record represented by data.
    The return value in a dict with fields raw_data, font_data, err, ext,
    headers.

    :param extent: The number of obfuscated bytes. So far I have only
    encountered files with 1040 obfuscated bytes. If you encounter an
    obfuscated record for which this function fails, try different extent
    values (easily automated).

    raw_data is the raw data in the font record
    font_data is the decoded font_data or None if an error occurred
    err is not None if some error occurred
    ext is the font type (ttf for TrueType, dat for unknown and failed if an
    error occurred)
    headers is the list of decoded headers from the font record or None if
    decoding failed
    '''
    # Format:
    # bytes  0 -  3:  'FONT'
    # bytes  4 -  7:  Uncompressed size
    # bytes  8 - 11:  flags
    #                   bit 1 - zlib compression
    #                   bit 2 - XOR obfuscated
    # bytes 12 - 15:  offset to start of compressed data
    # bytes 16 - 19:  length of XOR string
    # bytes 19 - 23:  offset to start of XOR data
    # The zlib compressed data begins with 2 bytes of header and
    # has 4 bytes of checksum at the end
    ans = {'raw_data':data, 'font_data':None, 'err':None, 'ext':'failed',
            'headers':None, 'encrypted':False}

    try:
        usize, flags, dstart, xor_len, xor_start = struct.unpack_from(
                b'>LLLLL', data, 4)
    except:
        ans['err'] = 'Failed to read font record header fields'
        return ans
    font_data = data[dstart:]
    ans['headers'] = {'usize':usize, 'flags':bin(flags), 'xor_len':xor_len,
            'xor_start':xor_start, 'dstart':dstart}

    if flags & 0b10:
        # De-obfuscate the data
        key = bytearray(data[xor_start:xor_start+xor_len])
        buf = bytearray(font_data)
        extent = len(font_data) if extent is None else extent
        extent = min(extent, len(font_data))

        for n in xrange(extent):
            buf[n] ^= key[n%xor_len] # XOR of buf and key

        font_data = bytes(buf)
        ans['encrypted'] = True

    if flags & 0b1:
        # ZLIB compressed data
        wbits, err = read_zlib_header(font_data[:2])
        if err is not None:
            ans['err'] = err
            return ans
        adler32, = struct.unpack_from(b'>I', font_data, len(font_data) - 4)
        try:
            # remove two bytes of zlib header and 4 bytes of trailing checksum
            # negative wbits indicates no standard gzip header
            font_data = zlib.decompress(font_data[2:-4], -wbits, usize)
        except Exception as e:
            ans['err'] = 'Failed to zlib decompress font data (%s)'%e
            return ans

        if len(font_data) != usize:
            ans['err'] = 'Uncompressed font size mismatch'
            return ans

        if False:
            # For some reason these almost never match, probably Amazon has a
            # buggy Adler32 implementation
            sig = (zlib.adler32(font_data) & 0xffffffff)
            if sig != adler32:
                ans['err'] = ('Adler checksum did not match. Stored: %d '
                        'Calculated: %d')%(adler32, sig)
                return ans

    ans['font_data'] = font_data
    sig = font_data[:4]
    ans['ext'] = ('ttf' if sig in {b'\0\1\0\0', b'true', b'ttcf'}
                    else 'otf' if sig == b'OTTO' else 'dat')

    return ans
# }}}




