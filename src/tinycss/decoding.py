# coding: utf8
"""
    tinycss.decoding
    ----------------

    Decoding stylesheets from bytes to Unicode.
    http://www.w3.org/TR/CSS21/syndata.html#charset

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals

from binascii import unhexlify
import operator
import re
import sys


__all__ = ['decode']  # Everything else is implementation detail


def decode(css_bytes, protocol_encoding=None,
           linking_encoding=None, document_encoding=None):
    """
    Determine the character encoding from the passed metadata and the
    ``@charset`` rule in the stylesheet (if any); and decode accordingly.
    If no encoding information is available or decoding fails,
    decoding defaults to UTF-8 and then fall back on ISO-8859-1.

    :param css_bytes:
        a CSS stylesheet as a byte string
    :param protocol_encoding:
        The "charset" parameter of a "Content-Type" HTTP header (if any),
        or similar metadata for other protocols.
    :param linking_encoding:
        ``<link charset="">`` or other metadata from the linking mechanism
        (if any)
    :param document_encoding:
        Encoding of the referring style sheet or document (if any)
    :return:
        A tuple of an Unicode string, with any BOM removed, and the
        encoding that was used.

    """
    if protocol_encoding:
        css_unicode = try_encoding(css_bytes, protocol_encoding)
        if css_unicode is not None:
            return css_unicode, protocol_encoding
    for encoding, pattern in ENCODING_MAGIC_NUMBERS:
        match = pattern(css_bytes)
        if match:
            has_at_charset = isinstance(encoding, tuple)
            if has_at_charset:
                extract, endianness = encoding
                encoding = extract(match.group(1))
                # Get an ASCII-only unicode value.
                # This is the only thing that works on both Python 2 and 3
                # for bytes.decode()
                # Non-ASCII encoding names are invalid anyway,
                # but make sure they stay invalid.
                encoding = encoding.decode('ascii', 'replace')
                encoding = encoding.replace('\ufffd', '?')
                if encoding.replace('-', '').replace('_', '').lower() in [
                        'utf16', 'utf32']:
                    encoding += endianness
                encoding = encoding.encode('ascii', 'replace').decode('ascii')
            css_unicode = try_encoding(css_bytes, encoding)
            if css_unicode and not (has_at_charset and not
                                    css_unicode.startswith('@charset "')):
                return css_unicode, encoding
            break
    for encoding in [linking_encoding, document_encoding]:
        if encoding:
            css_unicode = try_encoding(css_bytes, encoding)
            if css_unicode is not None:
                return css_unicode, encoding
    css_unicode = try_encoding(css_bytes, 'UTF-8')
    if css_unicode is not None:
        return css_unicode, 'UTF-8'
    return try_encoding(css_bytes, 'ISO-8859-1', fallback=False), 'ISO-8859-1'


def try_encoding(css_bytes, encoding, fallback=True):
    if fallback:
        try:
            css_unicode = css_bytes.decode(encoding)
        # LookupError means unknown encoding
        except (UnicodeDecodeError, LookupError):
            return None
    else:
        css_unicode = css_bytes.decode(encoding)
    if css_unicode and css_unicode[0] == '\ufeff':
        # Remove any Byte Order Mark
        css_unicode = css_unicode[1:]
    return css_unicode


def hex2re(hex_data):
    return re.escape(unhexlify(hex_data.replace(' ', '').encode('ascii')))


class Slicer(object):
    """Slice()[start:stop:end] == slice(start, stop, end)"""
    def __getitem__(self, slice_):
        return operator.itemgetter(slice_)

Slice = Slicer()


# List of (bom_size, encoding, pattern)
#   bom_size is in bytes and can be zero
#   encoding is a string or (slice_, endianness) for "as specified"
#   slice_ is a slice object.How to extract the specified

ENCODING_MAGIC_NUMBERS = [
    ((Slice[:], ''), re.compile(
        hex2re('EF BB BF 40 63 68 61 72 73 65 74 20 22')
        + b'([^\x22]*?)'
        + hex2re('22 3B')).match),

    ('UTF-8', re.compile(
        hex2re('EF BB BF')).match),

    ((Slice[:], ''), re.compile(
        hex2re('40 63 68 61 72 73 65 74 20 22')
        + b'([^\x22]*?)'
        + hex2re('22 3B')).match),

    ((Slice[1::2], '-BE'), re.compile(
        hex2re('FE FF 00 40 00 63 00 68 00 61 00 72 00 73 00 65 00'
               '74 00 20 00 22')
        + b'((\x00[^\x22])*?)'
        + hex2re('00 22 00 3B')).match),

    ((Slice[1::2], '-BE'), re.compile(
        hex2re('00 40 00 63 00 68 00 61 00 72 00 73 00 65 00 74 00'
               '20 00 22')
        + b'((\x00[^\x22])*?)'
        + hex2re('00 22 00 3B')).match),

    ((Slice[::2], '-LE'), re.compile(
        hex2re('FF FE 40 00 63 00 68 00 61 00 72 00 73 00 65 00 74'
               '00 20 00 22 00')
        + b'(([^\x22]\x00)*?)'
        + hex2re('22 00 3B 00')).match),

    ((Slice[::2], '-LE'), re.compile(
        hex2re('40 00 63 00 68 00 61 00 72 00 73 00 65 00 74 00 20'
               '00 22 00')
        + b'(([^\x22]\x00)*?)'
        + hex2re('22 00 3B 00')).match),

    ((Slice[3::4], '-BE'), re.compile(
        hex2re('00 00 FE FF 00 00 00 40 00 00 00 63 00 00 00 68 00'
               '00 00 61 00 00 00 72 00 00 00 73 00 00 00 65 00 00'
               '00 74 00 00 00 20 00 00 00 22')
        + b'((\x00\x00\x00[^\x22])*?)'
        + hex2re('00 00 00 22 00 00 00 3B')).match),

    ((Slice[3::4], '-BE'), re.compile(
        hex2re('00 00 00 40 00 00 00 63 00 00 00 68 00 00 00 61 00'
               '00 00 72 00 00 00 73 00 00 00 65 00 00 00 74 00 00'
               '00 20 00 00 00 22')
        + b'((\x00\x00\x00[^\x22])*?)'
        + hex2re('00 00 00 22 00 00 00 3B')).match),


# Python does not support 2143 or 3412 endianness, AFAIK.
# I guess we could fix it up ourselves but meh. Patches welcome.

#    ((Slice[2::4], '-2143'), re.compile(
#        hex2re('00 00 FF FE 00 00 40 00 00 00 63 00 00 00 68 00 00'
#               '00 61 00 00 00 72 00 00 00 73 00 00 00 65 00 00 00'
#               '74 00 00 00 20 00 00 00 22 00')
#        + b'((\x00\x00[^\x22]\x00)*?)'
#        + hex2re('00 00 22 00 00 00 3B 00')).match),

#    ((Slice[2::4], '-2143'), re.compile(
#        hex2re('00 00 40 00 00 00 63 00 00 00 68 00 00 00 61 00 00'
#               '00 72 00 00 00 73 00 00 00 65 00 00 00 74 00 00 00'
#               '20 00 00 00 22 00')
#        + b'((\x00\x00[^\x22]\x00)*?)'
#        + hex2re('00 00 22 00 00 00 3B 00')).match),

#    ((Slice[1::4], '-3412'), re.compile(
#        hex2re('FE FF 00 00 00 40 00 00 00 63 00 00 00 68 00 00 00'
#               '61 00 00 00 72 00 00 00 73 00 00 00 65 00 00 00 74'
#               '00 00 00 20 00 00 00 22 00 00')
#        + b'((\x00[^\x22]\x00\x00)*?)'
#        + hex2re('00 22 00 00 00 3B 00 00')).match),

#    ((Slice[1::4], '-3412'), re.compile(
#        hex2re('00 40 00 00 00 63 00 00 00 68 00 00 00 61 00 00 00'
#               '72 00 00 00 73 00 00 00 65 00 00 00 74 00 00 00 20'
#               '00 00 00 22 00 00')
#        + b'((\x00[^\x22]\x00\x00)*?)'
#        + hex2re('00 22 00 00 00 3B 00 00')).match),

    ((Slice[::4], '-LE'), re.compile(
        hex2re('FF FE 00 00 40 00 00 00 63 00 00 00 68 00 00 00 61'
               '00 00 00 72 00 00 00 73 00 00 00 65 00 00 00 74 00'
               '00 00 20 00 00 00 22 00 00 00')
        + b'(([^\x22]\x00\x00\x00)*?)'
        + hex2re('22 00 00 00 3B 00 00 00')).match),

    ((Slice[::4], '-LE'), re.compile(
        hex2re('40 00 00 00 63 00 00 00 68 00 00 00 61 00 00 00 72'
               '00 00 00 73 00 00 00 65 00 00 00 74 00 00 00 20 00'
               '00 00 22 00 00 00')
        + b'(([^\x22]\x00\x00\x00)*?)'
        + hex2re('22 00 00 00 3B 00 00 00')).match),

    ('UTF-32-BE', re.compile(
        hex2re('00 00 FE FF')).match),

    ('UTF-32-LE', re.compile(
        hex2re('FF FE 00 00')).match),

#    ('UTF-32-2143', re.compile(
#        hex2re('00 00 FF FE')).match),

#    ('UTF-32-3412', re.compile(
#        hex2re('FE FF 00 00')).match),

    ('UTF-16-BE', re.compile(
        hex2re('FE FF')).match),

    ('UTF-16-LE', re.compile(
        hex2re('FF FE')).match),


# Some of there are supported by Python, but I didn’t bother.
# You know the story with patches ...

#    # as specified, transcoded from EBCDIC to ASCII
#    ('as_specified-EBCDIC', re.compile(
#        hex2re('7C 83 88 81 99 A2 85 A3 40 7F')
#        + b'([^\x7F]*?)'
#        + hex2re('7F 5E')).match),

#    # as specified, transcoded from IBM1026 to ASCII
#    ('as_specified-IBM1026', re.compile(
#        hex2re('AE 83 88 81 99 A2 85 A3 40 FC')
#        + b'([^\xFC]*?)'
#        + hex2re('FC 5E')).match),

#    # as specified, transcoded from GSM 03.38 to ASCII
#    ('as_specified-GSM_03.38', re.compile(
#        hex2re('00 63 68 61 72 73 65 74 20 22')
#        + b'([^\x22]*?)'
#        + hex2re('22 3B')).match),
]
