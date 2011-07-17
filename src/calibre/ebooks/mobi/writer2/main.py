#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, random, time
from cStringIO import StringIO
from struct import pack

from calibre.ebooks import normalize
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES
from calibre.ebooks.mobi.writer2.serializer import Serializer
from calibre.ebooks.compression.palmdoc import compress_doc
from calibre.utils.magick.draw import Image, save_cover_data_to, thumbnail
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.mobi.writer2 import PALMDOC, UNCOMPRESSED

EXTH_CODES = {
    'creator': 100,
    'publisher': 101,
    'description': 103,
    'identifier': 104,
    'subject': 105,
    'pubdate': 106,
    'date': 106,
    'review': 107,
    'contributor': 108,
    'rights': 109,
    'type': 111,
    'source': 112,
    'title': 503,
    }

# Disabled as I dont care about uncrossable breaks
WRITE_UNCROSSABLE_BREAKS = False

RECORD_SIZE = 0x1000 # 4096

IMAGE_MAX_SIZE = 10 * 1024 * 1024
MAX_THUMB_SIZE = 16 * 1024
MAX_THUMB_DIMEN = (180, 240)

# Almost like the one for MS LIT, but not quite.
DECINT_FORWARD = 0
DECINT_BACKWARD = 1

def decint(value, direction):
    '''
    Some parts of the Mobipocket format encode data as variable-width integers.
    These integers are represented big-endian with 7 bits per byte in bits 1-7.
    They may be either forward-encoded, in which case only the LSB has bit 8 set,
    or backward-encoded, in which case only the MSB has bit 8 set.
    For example, the number 0x11111 would be represented forward-encoded as:

        0x04 0x22 0x91

    And backward-encoded as:

        0x84 0x22 0x11

    This function encodes the integer ``value`` as a variable width integer and
    returns the bytestring corresponding to it.
    '''
    # Encode vwi
    byts = bytearray()
    while True:
        b = value & 0x7f
        value >>= 7
        byts.append(b)
        if value == 0:
            break
    if direction == DECINT_FORWARD:
        byts[0] |= 0x80
    elif direction == DECINT_BACKWARD:
        byts[-1] |= 0x80
    return bytes(byts)

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

class MobiWriter(object):
    COLLAPSE_RE = re.compile(r'[ \t\r\n\v]+')

    def __init__(self, opts, write_page_breaks_after_item=True):
        self.opts = opts
        self.write_page_breaks_after_item = write_page_breaks_after_item
        self.compression = UNCOMPRESSED if opts.dont_compress else PALMDOC
        self.prefer_author_sort = opts.prefer_author_sort

    def __call__(self, oeb, path_or_stream):
        if hasattr(path_or_stream, 'write'):
            return self.dump_stream(oeb, path_or_stream)
        with open(path_or_stream, 'w+b') as stream:
            return self.dump_stream(oeb, stream)

    def write(self, *args):
        for datum in args:
            self.stream.write(datum)

    def tell(self):
        return self.stream.tell()

    def dump_stream(self, oeb, stream):
        self.oeb = oeb
        self.stream = stream
        self.records = [None]
        self.generate_content()
        self.generate_record0()
        self.write_header()
        self.write_content()

    def generate_content(self):
        self.map_image_names()
        self.generate_text()
        # Image records come after text records
        self.generate_images()

    def map_image_names(self):
        '''
        Map image names to record indices, ensuring that the masthead image if
        present has index number 1.
        '''
        index = 1
        self.images = images = {}
        mh_href = None

        if 'masthead' in self.oeb.guide:
            mh_href = self.oeb.guide['masthead'].href
            images[mh_href] = 1
            index += 1

        for item in self.oeb.manifest.values():
            if item.media_type in OEB_RASTER_IMAGES:
                if item.href == mh_href: continue
                images[item.href] = index
                index += 1

    def generate_images(self):
        self.oeb.logger.info('Serializing images...')
        images = [(index, href) for href, index in self.images.iteritems()]
        images.sort()
        self.first_image_record = None
        for _, href in images:
            item = self.oeb.manifest.hrefs[href]
            try:
                data = rescale_image(item.data)
            except:
                self.oeb.logger.warn('Bad image file %r' % item.href)
                continue
            finally:
                item.unload_data_from_memory()
            self.records.append(data)
            if self.first_image_record is None:
                self.first_image_record = len(self.records) - 1

    def generate_text(self):
        self.oeb.logger.info('Serializing markup content...')
        serializer = Serializer(self.oeb, self.images,
                write_page_breaks_after_item=self.write_page_breaks_after_item)
        text = serializer()
        breaks = serializer.breaks
        self.anchor_offset_kindle = serializer.anchor_offset_kindle
        self.id_offsets = serializer.id_offsets
        self.content_length = len(text)
        self.text_length = len(text)
        text = StringIO(text)
        buf = []
        nrecords = 0
        offset = 0

        if self.compression != UNCOMPRESSED:
            self.oeb.logger.info('  Compressing markup content...')
        data, overlap = self.read_text_record(text)

        while len(data) > 0:
            if self.compression == PALMDOC:
                data = compress_doc(data)
            record = StringIO()
            record.write(data)

            self.records.append(record.getvalue())
            buf.append(self.records[-1])
            nrecords += 1
            offset += RECORD_SIZE
            data, overlap = self.read_text_record(text)

            # Write information about the mutibyte character overlap, if any
            record.write(overlap)
            record.write(pack(b'>B', len(overlap)))

            # Write information about uncrossable breaks (non linear items in
            # the spine)
            if WRITE_UNCROSSABLE_BREAKS:
                nextra = 0
                pbreak = 0
                running = offset

                # Write information about every uncrossable break that occurs in
                # the next record.
                while breaks and (breaks[0] - offset) < RECORD_SIZE:
                    pbreak = (breaks.pop(0) - running) >> 3
                    encoded = decint(pbreak, DECINT_FORWARD)
                    record.write(encoded)
                    running += pbreak << 3
                    nextra += len(encoded)
                lsize = 1
                while True:
                    size = decint(nextra + lsize, DECINT_BACKWARD)
                    if len(size) == lsize:
                        break
                    lsize += 1
                record.write(size)

        self.text_nrecords = nrecords + 1

    def read_text_record(self, text):
        '''
        Return a Palmdoc record of size RECORD_SIZE from the text file object.
        In case the record ends in the middle of a multibyte character return
        the overlap as well.

        Returns data, overlap: where both are byte strings. overlap is the
        extra bytes needed to complete the truncated multibyte character.
        '''
        opos = text.tell()
        text.seek(0, 2)
        # npos is the position of the next record
        npos = min((opos + RECORD_SIZE, text.tell()))
        # Number of bytes from the next record needed to complete the last
        # character in this record
        extra = 0

        last = b''
        while not last.decode('utf-8', 'ignore'):
            # last contains no valid utf-8 characters
            size = len(last) + 1
            text.seek(npos - size)
            last = text.read(size)

        # last now has one valid utf-8 char and possibly some bytes that belong
        # to a truncated char

        try:
            last.decode('utf-8', 'strict')
        except UnicodeDecodeError:
            # There are some truncated bytes in last
            prev = len(last)
            while True:
                text.seek(npos - prev)
                last = text.read(len(last) + 1)
                try:
                    last.decode('utf-8')
                except UnicodeDecodeError:
                    pass
                else:
                    break
            extra = len(last) - prev

        text.seek(opos)
        data = text.read(RECORD_SIZE)
        overlap = text.read(extra)
        text.seek(npos)

        return data, overlap

    def generate_end_records(self):
        self.flis_number = len(self.records)
        self.records.append('\xE9\x8E\x0D\x0A')

    def generate_record0(self): # {{{
        metadata = self.oeb.metadata
        exth = self.build_exth()
        last_content_record = len(self.records) - 1

        self.generate_end_records()

        record0 = StringIO()
        # The PalmDOC Header
        record0.write(pack(b'>HHIHHHH', self.compression, 0,
            self.text_length,
            self.text_nrecords-1, RECORD_SIZE, 0, 0)) # 0 - 15 (0x0 - 0xf)
        uid = random.randint(0, 0xffffffff)
        title = normalize(unicode(metadata.title[0])).encode('utf-8')
        # The MOBI Header

        # 0x0 - 0x3
        record0.write(b'MOBI')

        # 0x4 - 0x7   : Length of header
        # 0x8 - 0x11  : MOBI type
        #   type    meaning
        #   0x002   MOBI book (chapter - chapter navigation)
        #   0x101   News - Hierarchical navigation with sections and articles
        #   0x102   News feed - Flat navigation
        #   0x103   News magazine - same as 0x101
        # 0xC - 0xF   : Text encoding (65001 is utf-8)
        # 0x10 - 0x13 : UID
        # 0x14 - 0x17 : Generator version

        record0.write(pack(b'>IIIII',
            0xe8, 0x002, 65001, uid, 6))

        # 0x18 - 0x1f : Unknown
        record0.write(b'\xff' * 8)


        # 0x20 - 0x23 : Secondary index record
        record0.write(pack(b'>I', 0xffffffff))

        # 0x24 - 0x3f : Unknown
        record0.write(b'\xff' * 28)

        # 0x40 - 0x43 : Offset of first non-text record
        record0.write(pack(b'>I',
            self.text_nrecords + 1))

        # 0x44 - 0x4b : title offset, title length
        record0.write(pack(b'>II',
            0xe8 + 16 + len(exth), len(title)))

        # 0x4c - 0x4f : Language specifier
        record0.write(iana2mobi(
            str(metadata.language[0])))

        # 0x50 - 0x57 : Unknown
        record0.write(b'\0' * 8)

        # 0x58 - 0x5b : Format version
        # 0x5c - 0x5f : First image record number
        record0.write(pack(b'>II',
            6, self.first_image_record if self.first_image_record else 0))

        # 0x60 - 0x63 : First HUFF/CDIC record number
        # 0x64 - 0x67 : Number of HUFF/CDIC records
        # 0x68 - 0x6b : First DATP record number
        # 0x6c - 0x6f : Number of DATP records
        record0.write(b'\0' * 16)

        # 0x70 - 0x73 : EXTH flags
        record0.write(pack(b'>I', 0x50))

        # 0x74 - 0x93 : Unknown
        record0.write(b'\0' * 32)

        # 0x94 - 0x97 : DRM offset
        # 0x98 - 0x9b : DRM count
        # 0x9c - 0x9f : DRM size
        # 0xa0 - 0xa3 : DRM flags
        record0.write(pack(b'>IIII',
            0xffffffff, 0xffffffff, 0, 0))


        # 0xa4 - 0xaf : Unknown
        record0.write(b'\0'*12)

        # 0xb0 - 0xb1 : First content record number
        # 0xb2 - 0xb3 : last content record number
        # (Includes Image, DATP, HUFF, DRM)
        record0.write(pack(b'>HH', 1, last_content_record))

        # 0xb4 - 0xb7 : Unknown
        record0.write(b'\0\0\0\x01')

        # 0xb8 - 0xbb : FCIS record number
        record0.write(pack(b'>I', 0xffffffff))

        # 0xbc - 0xbf : Unknown (FCIS record count?)
        record0.write(pack(b'>I', 0xffffffff))

        # 0xc0 - 0xc3 : FLIS record number
        record0.write(pack(b'>I', 0xffffffff))

        # 0xc4 - 0xc7 : Unknown (FLIS record count?)
        record0.write(pack(b'>I', 1))

        # 0xc8 - 0xcf : Unknown
        record0.write(b'\0'*8)

        # 0xd0 - 0xdf : Unknown
        record0.write(pack(b'>IIII', 0xffffffff, 0, 0xffffffff, 0xffffffff))

        # 0xe0 - 0xe3 : Extra record data
        # Extra record data flags:
        #   - 0x1: <extra multibyte bytes><size> (?)
        #   - 0x2: <TBS indexing description of this HTML record><size> GR
        #   - 0x4: <uncrossable breaks><size>
        # GR: Use 7 for indexed files, 5 for unindexed
        # Setting bit 2 (0x2) disables <guide><reference type="start"> functionality

        extra_data_flags = 0b1 # Has multibyte overlap bytes
        if WRITE_UNCROSSABLE_BREAKS:
            extra_data_flags |= 0b100
        record0.write(pack(b'>I', extra_data_flags))

        # 0xe4 - 0xe7 : Primary index record
        record0.write(pack(b'>I', 0xffffffff))

        record0.write(exth)
        record0.write(title)
        record0 = record0.getvalue()
        # Add some buffer so that Amazon can add encryption information if this
        # MOBI is submitted for publication
        record0 += (b'\0' * (1024*8))
        self.records[0] = record0
    # }}}

    def build_exth(self): # {{{
        oeb = self.oeb
        exth = StringIO()
        nrecs = 0
        for term in oeb.metadata:
            if term not in EXTH_CODES: continue
            code = EXTH_CODES[term]
            items = oeb.metadata[term]
            if term == 'creator':
                if self.prefer_author_sort:
                    creators = [normalize(unicode(c.file_as or c)) for c in items]
                else:
                    creators = [normalize(unicode(c)) for c in items]
                items = ['; '.join(creators)]
            for item in items:
                data = self.COLLAPSE_RE.sub(' ', normalize(unicode(item)))
                if term == 'identifier':
                    if data.lower().startswith('urn:isbn:'):
                        data = data[9:]
                    elif item.scheme.lower() == 'isbn':
                        pass
                    else:
                        continue
                data = data.encode('utf-8')
                exth.write(pack(b'>II', code, len(data) + 8))
                exth.write(data)
                nrecs += 1
            if term == 'rights' :
                try:
                    rights = normalize(unicode(oeb.metadata.rights[0])).encode('utf-8')
                except:
                    rights = b'Unknown'
                exth.write(pack(b'>II', EXTH_CODES['rights'], len(rights) + 8))
                exth.write(rights)
                nrecs += 1

        # Write UUID as ASIN
        uuid = None
        from calibre.ebooks.oeb.base import OPF
        for x in oeb.metadata['identifier']:
            if (x.get(OPF('scheme'), None).lower() == 'uuid' or
                    unicode(x).startswith('urn:uuid:')):
                uuid = unicode(x).split(':')[-1]
                break
        if uuid is None:
            from uuid import uuid4
            uuid = str(uuid4())

        if isinstance(uuid, unicode):
            uuid = uuid.encode('utf-8')
        exth.write(pack(b'>II', 113, len(uuid) + 8))
        exth.write(uuid)
        nrecs += 1

        # Write cdetype
        if not self.opts.mobi_periodical:
            data = b'EBOK'
            exth.write(pack(b'>II', 501, len(data)+8))
            exth.write(data)
            nrecs += 1

        # Add a publication date entry
        if oeb.metadata['date'] != [] :
            datestr = str(oeb.metadata['date'][0])
        elif oeb.metadata['timestamp'] != [] :
            datestr = str(oeb.metadata['timestamp'][0])

        if datestr is not None:
            exth.write(pack(b'>II', EXTH_CODES['pubdate'], len(datestr) + 8))
            exth.write(datestr)
            nrecs += 1
        else:
            raise NotImplementedError("missing date or timestamp needed for mobi_periodical")

        if (oeb.metadata.cover and
                unicode(oeb.metadata.cover[0]) in oeb.manifest.ids):
            id = unicode(oeb.metadata.cover[0])
            item = oeb.manifest.ids[id]
            href = item.href
            if href in self.images:
                index = self.images[href] - 1
                exth.write(pack(b'>III', 0xc9, 0x0c, index))
                exth.write(pack(b'>III', 0xcb, 0x0c, 0))
                nrecs += 2
                index = self.add_thumbnail(item)
                if index is not None:
                    exth.write(pack(b'>III', 0xca, 0x0c, index - 1))
                    nrecs += 1

        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = b'\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = [b'EXTH', pack(b'>II', len(exth) + 12, nrecs), exth, pad]
        return b''.join(exth)
    # }}}

    def add_thumbnail(self, item):
        try:
            data = rescale_image(item.data, dimen=MAX_THUMB_DIMEN,
                    maxsizeb=MAX_THUMB_SIZE)
        except IOError:
            self.oeb.logger.warn('Bad image file %r' % item.href)
            return None
        manifest = self.oeb.manifest
        id, href = manifest.generate('thumbnail', 'thumbnail.jpeg')
        manifest.add(id, href, 'image/jpeg', data=data)
        index = len(self.images) + 1
        self.images[href] = index
        self.records.append(data)
        return index

    def write_header(self):
        title = ascii_filename(unicode(self.oeb.metadata.title[0]))
        title = title + (b'\0' * (32 - len(title)))
        now = int(time.time())
        nrecords = len(self.records)
        self.write(title, pack(b'>HHIIIIII', 0, 0, now, now, 0, 0, 0, 0),
            b'BOOK', b'MOBI', pack(b'>IIH', nrecords, 0, nrecords))
        offset = self.tell() + (8 * nrecords) + 2
        for i, record in enumerate(self.records):
            self.write(pack(b'>I', offset), b'\0', pack(b'>I', 2*i)[1:])
            offset += len(record)
        self.write(b'\0\0')

    def write_content(self):
        for record in self.records:
            self.write(record)


