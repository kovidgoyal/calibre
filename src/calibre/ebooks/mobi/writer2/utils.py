#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct
from collections import OrderedDict

from calibre.utils.magick.draw import Image, save_cover_data_to, thumbnail

IMAGE_MAX_SIZE = 10 * 1024 * 1024

def decode_hex_number(raw):
    '''
    Return a variable length number encoded using hexadecimal encoding. These
    numbers have the first byte which tells the number of bytes that follow.
    The bytes that follow are simply the hexadecimal representation of the
    number.

    :param raw: Raw binary data as a bytestring

    :return: The number and the number of bytes from raw that the number
    occupies
    '''
    length, = struct.unpack(b'>B', raw[0])
    raw = raw[1:1+length]
    consumed = length+1
    return int(raw, 16), consumed

def encode_number_as_hex(num):
    '''
    Encode num as a variable length encoded hexadecimal number. Returns the
    bytestring containing the encoded number. These
    numbers have the first byte which tells the number of bytes that follow.
    The bytes that follow are simply the hexadecimal representation of the
    number.
    '''
    num = bytes(hex(num)[2:])
    ans = bytearray(num)
    ans.insert(0, len(num))
    return bytes(ans)

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
    Read a variable width integer from the bytestring raw and return the
    integer and the number of bytes read. If forward is True bytes are read
    from the start of raw, otherwise from the end of raw.

    This function is the inverse of encint above, see its docs for more
    details.
    '''
    val = 0
    byts = bytearray()
    for byte in raw if forward else reversed(raw):
        bnum = ord(byte)
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

    If dimen is not None, generate a thumbnail of width=dimen, height=dimen

    Returns the image as a bytestring
    '''
    if dimen is not None:
        data = thumbnail(data, width=dimen, height=dimen,
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
    for i in xrange(16, -1, -1):
        flag = 2**i
        if flag & extra_data_flags:
            if i == 0:
                # Only the first two bits are used for the size since there can
                # never be more than 3 trailing multibyte chars
                sz = ord(record[-1]) & 0b11
                consumed = 1
            else:
                sz, consumed = decint(record, forward=False)
            data[i] = record[-(sz+consumed):-consumed]
            record = record[:-(sz+consumed)]
    return data, record

