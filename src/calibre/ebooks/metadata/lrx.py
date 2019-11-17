#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Read metadata from LRX files
'''

import struct
from zlib import decompress

from calibre.ebooks.metadata import MetaInformation, string_to_authors
from calibre.utils.xml_parse import safe_xml_fromstring


def _read(f, at, amount):
    f.seek(at)
    return f.read(amount)


def word_be(buf):
    return struct.unpack('>L', buf)[0]


def word_le(buf):
    return struct.unpack('<L', buf)[0]


def short_le(buf):
    return struct.unpack('<H', buf)[0]


def short_be(buf):
    return struct.unpack('>H', buf)[0]


def get_metadata(f):
    read = lambda at, amount: _read(f, at, amount)
    f.seek(0)
    buf = f.read(12)
    if buf[4:] == b'ftypLRX2':
        offset = 0
        while True:
            offset += word_be(buf[:4])
            try:
                buf = read(offset, 8)
            except:
                raise ValueError('Not a valid LRX file')
            if buf[4:] == b'bbeb':
                break
        offset += 8
        buf = read(offset, 16)
        if buf[:8].decode('utf-16-le') != 'LRF\x00':
            raise ValueError('Not a valid LRX file')
        lrf_version = word_le(buf[8:12])
        offset += 0x4c
        compressed_size = short_le(read(offset, 2))
        offset += 2
        if lrf_version >= 800:
            offset += 6
        compressed_size -= 4
        uncompressed_size = word_le(read(offset, 4))
        info = decompress(f.read(compressed_size))
        if len(info) != uncompressed_size:
            raise ValueError('LRX file has malformed metadata section')
        root = safe_xml_fromstring(info)
        bi = root.find('BookInfo')
        title = bi.find('Title')
        title_sort = title.get('reading', None)
        title = title.text
        author = bi.find('Author')
        author_sort = author.get('reading', None)
        mi = MetaInformation(title, string_to_authors(author.text))
        mi.title_sort, mi.author_sort = title_sort, author_sort
        author = author.text
        publisher = bi.find('Publisher')
        mi.publisher = getattr(publisher, 'text', None)
        mi.tags = [x.text for x in bi.findall('Category')]
        mi.language = root.find('DocInfo').find('Language').text
        return mi

    elif buf[4:8] == b'LRX':
        raise ValueError('Librie LRX format not supported')
    else:
        raise ValueError('Not a LRX file')
