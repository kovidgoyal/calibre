#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>, John Howell <jhowell@acm.org>'

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

# Based on work of John Howell reversing the KFX format
# https://www.mobileread.com/forums/showpost.php?p=3176029&postcount=89

import struct, sys, base64, re
from collections import defaultdict

from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.mobi.utils import decint
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.config_base import tweaks
from calibre.utils.date import parse_only_date
from calibre.utils.localization import canonicalize_lang
from calibre.utils.imghdr import identify


class InvalidKFX(ValueError):
    pass


# magic numbers for data structures
CONTAINER_MAGIC = b'CONT'
ENTITY_MAGIC = b'ENTY'
ION_MAGIC = b'\xe0\x01\x00\xea'

# ION data types (comment shows equivalent python data type produced)
DT_BOOLEAN = 1          # True/False
DT_INTEGER = 2          # int
# str (using non-unicode to distinguish symbols from strings)
DT_PROPERTY = 7
DT_STRING = 8           # unicode
DT_STRUCT = 11          # tuple
DT_LIST = 12            # list
DT_OBJECT = 13          # dict of property/value pairs
DT_TYPED_DATA = 14      # type, name, value

# property names (non-unicode strings to distinguish them from ION strings in this program)
# These are place holders. The correct property names are unknown.
PROP_METADATA = b'P258'
PROP_METADATA2 = b'P490'
PROP_METADATA3 = b'P491'
PROP_METADATA_KEY = b'P492'
PROP_METADATA_VALUE = b'P307'
PROP_IMAGE = b'P417'

METADATA_PROPERTIES = {
    b'P10' : "languages",
    b'P153': "title",
    b'P154': "description",
    b'P222': "author",
    b'P232': "publisher",
}

COVER_KEY = "cover_image_base64"


def hexs(string, sep=' '):
    return sep.join('%02x' % ord(b) for b in string)


class PackedData(object):

    '''
    Simplify unpacking of packed binary data structures
    '''

    def __init__(self, data):
        self.buffer = data
        self.offset = 0

    def unpack_one(self, fmt, advance=True):
        return self.unpack_multi(fmt, advance)[0]

    def unpack_multi(self, fmt, advance=True):
        fmt = fmt.encode('ascii')
        result = struct.unpack_from(fmt, self.buffer, self.offset)
        if advance:
            self.advance(struct.calcsize(fmt))
        return result

    def extract(self, size):
        data = self.buffer[self.offset:self.offset + size]
        self.advance(size)
        return data

    def advance(self, size):
        self.offset += size

    def remaining(self):
        return len(self.buffer) - self.offset


class PackedBlock(PackedData):

    '''
    Common header structure of container and entity blocks
    '''

    def __init__(self, data, magic):
        PackedData.__init__(self, data)

        self.magic = self.unpack_one('4s')
        if self.magic != magic:
            raise InvalidKFX('%s magic number is incorrect (%s)' %
                            (magic, hexs(self.magic)))

        self.version = self.unpack_one('<H')
        self.header_len = self.unpack_one('<L')


class Container(PackedBlock):

    '''
    Container file containing data entities
    '''

    def __init__(self, data):
        self.data = data
        PackedBlock.__init__(self, data, CONTAINER_MAGIC)

        # Unknown data
        self.advance(8)
        self.entities = []

        while self.unpack_one('4s', advance=False) != ION_MAGIC:
            entity_id, entity_type, entity_offset, entity_len = self.unpack_multi('<LLQQ')
            entity_start = self.header_len + entity_offset
            self.entities.append(
                Entity(self.data[entity_start:entity_start + entity_len], entity_type, entity_id))

    def decode(self):
        return [entity.decode() for entity in self.entities]


class Entity(PackedBlock):

    '''
    Data entity inside a container
    '''

    def __init__(self, data, entity_type, entity_id):
        PackedBlock.__init__(self, data, ENTITY_MAGIC)
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_data = data[self.header_len:]

    def decode(self):
        if PackedData(self.entity_data).unpack_one('4s') == ION_MAGIC:
            entity_value = PackedIon(self.entity_data).decode()
        else:
            entity_value = base64.b64encode(self.entity_data)

        return (property_name(self.entity_type), property_name(self.entity_id), entity_value)


class PackedIon(PackedData):

    '''
    Packed structured binary data format used by KFX
    '''

    def __init__(self, data):
        PackedData.__init__(self, data)

    def decode(self):
        if self.unpack_one('4s') != ION_MAGIC:
            raise Exception('ION marker missing at start of data')

        return self.unpack_typed_value()

    def unpack_typed_value(self):
        cmd = self.unpack_one('B')

        data_type = cmd >> 4
        data_len = cmd & 0x0f
        if data_len == 14:
            data_len = self.unpack_number()

        # print('cmd=%02x, len=%s: %s' % (cmd, data_len, hexs(self.buffer[self.offset:][:data_len])))

        if data_type == DT_BOOLEAN:
            return data_len != 0  # length is actually value

        if data_type == DT_INTEGER:
            return self.unpack_unsigned_int(data_len)

        if data_type == DT_PROPERTY:
            return property_name(self.unpack_unsigned_int(data_len))

        if data_type == DT_STRING:
            return self.extract(data_len).decode('utf8')

        if data_type == DT_STRUCT or data_type == DT_LIST:
            ion = PackedIon(self.extract(data_len))
            result = []

            while ion.remaining():
                result.append(ion.unpack_typed_value())

            if data_type == DT_STRUCT:
                result = tuple(result)

            return result

        if data_type == DT_OBJECT:
            ion = PackedIon(self.extract(data_len))
            result = {}

            while (ion.remaining()):
                symbol = property_name(ion.unpack_number())
                result[symbol] = ion.unpack_typed_value()

            return result

        if data_type == DT_TYPED_DATA:
            ion = PackedIon(self.extract(data_len))
            ion.unpack_number()
            ion.unpack_number()
            return ion.unpack_typed_value()

        # ignore unknown types
        self.advance(data_len)
        return None

    def unpack_number(self):
        # variable length numbers, MSB first, 7 bits per byte, last byte is
        # flagged by MSB set
        raw = self.buffer[self.offset:self.offset+10]
        number, consumed = decint(raw)
        self.advance(consumed)
        return number

    def unpack_unsigned_int(self, length):
        # unsigned big-endian (MSB first)
        return struct.unpack_from(b'>Q', chr(0) * (8 - length) + self.extract(length))[0]


def property_name(property_number):
    # This should be changed to translate property numbers to the proper
    # strings using a symbol table
    return b"P%d" % property_number


def extract_metadata(container_data):
    metadata = defaultdict(list)

    # locate book metadata within the container data structures

    for entity_type, entity_id, entity_value in container_data:
        if entity_type == PROP_METADATA:
            for key, value in entity_value.items():
                if key in METADATA_PROPERTIES:
                    metadata[METADATA_PROPERTIES[key]].append(value)

        elif entity_type == PROP_METADATA2:
            if entity_value is not None:
                for value1 in entity_value[PROP_METADATA3]:
                    for meta in value1[PROP_METADATA]:
                        metadata[meta[PROP_METADATA_KEY]].append(meta[PROP_METADATA_VALUE])

        elif entity_type == PROP_IMAGE and COVER_KEY not in metadata:
            # assume first image is the cover
            metadata[COVER_KEY] = entity_value

    return metadata


def dump_metadata(m):
    d = dict(m)
    d[COVER_KEY] = bool(d.get(COVER_KEY))
    from pprint import pprint
    pprint(d)


def read_metadata_kfx(stream, read_cover=True):
    ' Read the metadata.kfx file that is found in the sdr book folder for KFX files '
    c = Container(stream.read())
    m = extract_metadata(c.decode())
    # dump_metadata(m)

    def has(x):
        return m[x] and m[x][0]

    def get(x, single=True):
        ans = m[x]
        if single:
            ans = clean_xml_chars(ans[0]) if ans else ''
        else:
            ans = [clean_xml_chars(y) for y in ans]
        return ans

    title = get('title') or _('Unknown')
    authors = get('author', False) or [_('Unknown')]
    auth_pat = re.compile(r'([^,]+?)\s*,\s+([^,]+)$')

    def fix_author(x):
        if tweaks['author_sort_copy_method'] != 'copy':
            m = auth_pat.match(x.strip())
            if m is not None:
                return m.group(2) + ' ' + m.group(1)
        return x

    unique_authors = []     # remove duplicates while retaining order
    for f in [fix_author(x) for x in authors]:
        if f not in unique_authors:
            unique_authors.append(f)

    mi = Metadata(title, unique_authors)
    if has('author'):
        mi.author_sort = get('author')
    if has('ASIN'):
        mi.set_identifier('mobi-asin', get('ASIN'))
    elif has('content_id'):
        mi.set_identifier('mobi-asin', get('content_id'))
    if has('languages'):
        langs = list(filter(None, (canonicalize_lang(x) for x in get('languages', False))))
        if langs:
            mi.languages = langs
    if has('issue_date'):
        try:
            mi.pubdate = parse_only_date(get('issue_date'))
        except Exception:
            pass
    if has('publisher') and get('publisher') != 'Unknown':
        mi.publisher = get('publisher')
    if read_cover and m[COVER_KEY]:
        try:
            data = base64.standard_b64decode(m[COVER_KEY])
            fmt, w, h = identify(bytes(data))
        except Exception:
            w, h, fmt = 0, 0, None
        if fmt and w > -1 and h > -1:
            mi.cover_data = (fmt, data)

    return mi


if __name__ == '__main__':
    from calibre import prints
    with open(sys.argv[-1], 'rb') as f:
        mi = read_metadata_kfx(f)
        prints(unicode(mi))
