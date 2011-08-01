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

from calibre.ebooks import normalize, generate_masthead
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES
from calibre.ebooks.mobi.writer2.serializer import Serializer
from calibre.ebooks.compression.palmdoc import compress_doc
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.mobi.writer2 import (PALMDOC, UNCOMPRESSED, RECORD_SIZE)
from calibre.ebooks.mobi.utils import (rescale_image, encint,
        encode_trailing_data, align_block, detect_periodical)
from calibre.ebooks.mobi.writer2.indexer import Indexer

EXTH_CODES = {
    'creator': 100,
    'publisher': 101,
    'description': 103,
    'identifier': 104,
    'subject': 105,
    'pubdate': 106,
    'review': 107,
    'contributor': 108,
    'rights': 109,
    'type': 111,
    'source': 112,
    'versionnumber': 114,
    'coveroffset': 201,
    'thumboffset': 202,
    'hasfakecover': 203,
    'lastupdatetime': 502,
    'title': 503,
    }

# Disabled as I dont care about uncrossable breaks
WRITE_UNCROSSABLE_BREAKS = False

MAX_THUMB_SIZE = 16 * 1024
MAX_THUMB_DIMEN = (180, 240)

class MobiWriter(object):
    COLLAPSE_RE = re.compile(r'[ \t\r\n\v]+')

    def __init__(self, opts, write_page_breaks_after_item=True):
        self.opts = opts
        self.write_page_breaks_after_item = write_page_breaks_after_item
        self.compression = UNCOMPRESSED if opts.dont_compress else PALMDOC
        self.prefer_author_sort = opts.prefer_author_sort
        self.last_text_record_idx = 1

    def __call__(self, oeb, path_or_stream):
        self.log = oeb.log
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
        self.is_periodical = detect_periodical(self.oeb.toc, self.oeb.log)
        self.generate_images()
        self.generate_text()
        # The uncrossable breaks trailing entries come before the indexing
        # trailing entries
        self.write_uncrossable_breaks()
        # Index records come after text records
        self.generate_index()

    # Indexing {{{
    def generate_index(self):
        self.primary_index_record_idx = None
        try:
            self.indexer = Indexer(self.serializer, self.last_text_record_idx,
                    len(self.records[self.last_text_record_idx]),
                    self.masthead_offset, self.is_periodical,
                    self.opts, self.oeb)
        except:
            self.log.exception('Failed to generate MOBI index:')
        else:
            self.primary_index_record_idx = len(self.records)
            for i in xrange(len(self.records)):
                if i == 0: continue
                tbs = self.indexer.get_trailing_byte_sequence(i)
                self.records[i] += encode_trailing_data(tbs)
            self.records.extend(self.indexer.records)

    # }}}

    def write_uncrossable_breaks(self): # {{{
        '''
        Write information about uncrossable breaks (non linear items in
        the spine.
        '''
        if not WRITE_UNCROSSABLE_BREAKS:
            return

        breaks = self.serializer.breaks

        for i in xrange(1, self.last_text_record_idx+1):
            offset = i * RECORD_SIZE
            pbreak = 0
            running = offset

            buf = StringIO()

            while breaks and (breaks[0] - offset) < RECORD_SIZE:
                pbreak = (breaks.pop(0) - running) >> 3
                encoded = encint(pbreak)
                buf.write(encoded)
                running += pbreak << 3
            encoded = encode_trailing_data(buf.getvalue())
            self.records[i] += encoded
    # }}}

    # Images {{{

    def generate_images(self):
        oeb = self.oeb
        oeb.logger.info('Serializing images...')
        self.image_records = []

        mh_href = self.masthead_offset = None
        if 'masthead' in oeb.guide:
            mh_href = oeb.guide['masthead'].href
        elif self.is_periodical:
            # Generate a default masthead
            data = generate_masthead(unicode(self.oeb.metadata('title')[0]))
            self.image_records.append(data)
            self.masthead_offset = 0

        cover_href = self.cover_offset = self.thumbnail_offset = None
        if (oeb.metadata.cover and
                unicode(oeb.metadata.cover[0]) in oeb.manifest.ids):
            cover_id = unicode(oeb.metadata.cover[0])
            item = oeb.manifest.ids[cover_id]
            cover_href = item.href

        for item in self.oeb.manifest.values():
            if item.media_type not in OEB_RASTER_IMAGES: continue
            try:
                data = rescale_image(item.data)
            except:
                oeb.logger.warn('Bad image file %r' % item.href)
                continue
            else:
                if item.href == mh_href:
                    self.masthead_offset = len(self.image_records) - 1
                elif item.href == cover_href:
                    self.image_records.append(data)
                    self.cover_offset = len(self.image_records) - 1
                    try:
                        data = rescale_image(item.data, dimen=MAX_THUMB_DIMEN,
                            maxsizeb=MAX_THUMB_SIZE)
                    except:
                        oeb.logger.warn('Failed to generate thumbnail')
                    else:
                        self.image_records.append(data)
                        self.thumbnail_offset = len(self.image_records) - 1
            finally:
                item.unload_data_from_memory()

    # }}}

    # Text {{{

    def generate_text(self):
        self.oeb.logger.info('Serializing markup content...')
        self.serializer = Serializer(self.oeb, self.images,
                write_page_breaks_after_item=self.write_page_breaks_after_item)
        text = self.serializer()
        self.text_length = len(text)
        text = StringIO(text)
        nrecords = 0
        records_size = 0

        if self.compression != UNCOMPRESSED:
            self.oeb.logger.info('  Compressing markup content...')

        while text.tell() < self.text_length:
            data, overlap = self.read_text_record(text)
            if self.compression == PALMDOC:
                data = compress_doc(data)

            data += overlap
            data += pack(b'>B', len(overlap))

            self.records.append(data)
            records_size += len(data)
            nrecords += 1

        self.last_text_record_idx = nrecords
        self.first_non_text_record_idx = nrecords + 1
        # Pad so that the next records starts at a 4 byte boundary
        if records_size % 4 != 0:
            self.records.append(b'\x00'*(records_size % 4))
            self.first_non_text_record_idx += 1

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

    # }}}

    def generate_record0(self): #  MOBI header {{{
        metadata = self.oeb.metadata
        exth = self.build_exth()
        first_image_record = None
        if self.image_records:
            first_image_record  = len(self.records)
            self.records.extend(self.image_records)
        last_content_record = len(self.records) - 1

        # FCIS/FLIS (Seems to serve no purpose)
        flis_number = len(self.records)
        self.records.append(
            b'FLIS\0\0\0\x08\0\x41\0\0\0\0\0\0\xff\xff\xff\xff\0\x01\0\x03\0\0\0\x03\0\0\0\x01'+
            b'\xff'*4)
        fcis = b'FCIS\x00\x00\x00\x14\x00\x00\x00\x10\x00\x00\x00\x01\x00\x00\x00\x00'
        fcis += pack(b'>I', self.text_length)
        fcis += b'\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x00\x08\x00\x01\x00\x01\x00\x00\x00\x00'
        fcis_number = len(self.records)
        self.records.append(fcis)

        # EOF record
        self.records.append(b'\xE9\x8E\x0D\x0A')

        record0 = StringIO()
        # The MOBI Header
        record0.write(pack(b'>HHIHHHH',
            self.compression, # compression type # compression type
            0, # Unused
            self.text_length, # Text length
            self.last_text_record_idx, # Number of text records or last tr idx
            RECORD_SIZE, # Text record size
            0, # Unused
            0  # Unused
        )) # 0 - 15 (0x0 - 0xf)
        uid = random.randint(0, 0xffffffff)
        title = normalize(unicode(metadata.title[0])).encode('utf-8')

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

        bt = 0x002
        if self.primary_index_record_idx is not None:
            if self.indexer.is_flat_periodical:
                bt = 0x102
            elif self.indexer.is_periodical:
                bt = 0x101

        record0.write(pack(b'>IIIII',
            0xe8, bt, 65001, uid, 6))

        # 0x18 - 0x1f : Unknown
        record0.write(b'\xff' * 8)

        # 0x20 - 0x23 : Secondary index record
        record0.write(pack(b'>I', 0xffffffff))

        # 0x24 - 0x3f : Unknown
        record0.write(b'\xff' * 28)

        # 0x40 - 0x43 : Offset of first non-text record
        record0.write(pack(b'>I',
            self.first_non_text_record_idx))

        # 0x44 - 0x4b : title offset, title length
        record0.write(pack(b'>II',
            0xe8 + 16 + len(exth), len(title)))

        # 0x4c - 0x4f : Language specifier
        record0.write(iana2mobi(
            str(metadata.language[0])))

        # 0x50 - 0x57 : Input language and Output language
        record0.write(b'\0' * 8)

        # 0x58 - 0x5b : Format version
        # 0x5c - 0x5f : First image record number
        record0.write(pack(b'>II',
            6, first_image_record if first_image_record else len(self.records)))

        # 0x60 - 0x63 : First HUFF/CDIC record number
        # 0x64 - 0x67 : Number of HUFF/CDIC records
        # 0x68 - 0x6b : First DATP record number
        # 0x6c - 0x6f : Number of DATP records
        record0.write(b'\0' * 16)

        # 0x70 - 0x73 : EXTH flags
        # Bit 6 (0b1000000) being set indicates the presence of an EXTH header
        # The purpose of the other bits is unknown
        exth_flags = 0b1010000
        if self.is_periodical:
            exth_flags |= 0b1000
        record0.write(pack(b'>I', exth_flags))

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
        record0.write(pack(b'>I', fcis_number))

        # 0xbc - 0xbf : Unknown (FCIS record count?)
        record0.write(pack(b'>I', 1))

        # 0xc0 - 0xc3 : FLIS record number
        record0.write(pack(b'>I', flis_number))

        # 0xc4 - 0xc7 : Unknown (FLIS record count?)
        record0.write(pack(b'>I', 1))

        # 0xc8 - 0xcf : Unknown
        record0.write(b'\0'*8)

        # 0xd0 - 0xdf : Unknown
        record0.write(pack(b'>IIII', 0xffffffff, 0, 0xffffffff, 0xffffffff))

        # 0xe0 - 0xe3 : Extra record data
        # Extra record data flags:
        #   - 0b1  : <extra multibyte bytes><size>
        #   - 0b10 : <TBS indexing description of this HTML record><size>
        #   - 0b100: <uncrossable breaks><size>
        # Setting bit 2 (0x2) disables <guide><reference type="start"> functionality
        extra_data_flags = 0b1 # Has multibyte overlap bytes
        if self.primary_index_record_idx is not None:
            extra_data_flags |= 0b10
        if WRITE_UNCROSSABLE_BREAKS:
            extra_data_flags |= 0b100
        record0.write(pack(b'>I', extra_data_flags))

        # 0xe4 - 0xe7 : Primary index record
        record0.write(pack(b'>I', 0xffffffff if self.primary_index_record_idx
            is None else self.primary_index_record_idx))

        record0.write(exth)
        record0.write(title)
        record0 = record0.getvalue()
        # Add some buffer so that Amazon can add encryption information if this
        # MOBI is submitted for publication
        record0 += (b'\0' * (1024*8))
        self.records[0] = align_block(record0)
    # }}}

    def build_exth(self): # EXTH Header {{{
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
        if self.is_periodical:
            data = b'NWPR'
        else:
            data = b'EBOK'
        exth.write(pack(b'>II', 501, len(data)+8))
        exth.write(data)
        nrecs += 1

        # Add a publication date entry
        if oeb.metadata['date']:
            datestr = str(oeb.metadata['date'][0])
        elif oeb.metadata['timestamp']:
            datestr = str(oeb.metadata['timestamp'][0])

        if datestr is None:
            raise ValueError("missing date or timestamp")

        datestr = bytes(datestr)
        exth.write(pack(b'>II', EXTH_CODES['pubdate'], len(datestr) + 8))
        exth.write(datestr)
        nrecs += 1
        if self.is_periodical:
            exth.write(pack(b'>II', EXTH_CODES['lastupdatetime'], len(datestr) + 8))
            exth.write(datestr)
            nrecs += 1
            exth.write(pack(b'>III', EXTH_CODES['versionnumber'], 12, 7))
            nrecs += 1

        if self.is_periodical:
            # Pretend to be amazon's super secret periodical generator
            vals = {204:201, 205:2, 206:0, 207:101}
        else:
            # Pretend to be kindlegen 1.2
            vals = {204:201, 205:1, 206:2, 207:33307}
        for code, val in vals:
            exth.write(pack(b'>III', code, 12, val))
            nrecs += 1

        if self.cover_offset is not None:
            exth.write(pack(b'>III', EXTH_CODES['coveroffset'], 12,
                self.cover_offset))
            exth.write(pack(b'>III', EXTH_CODES['hasfakecover'], 12, 0))
            nrecs += 2
        if self.thumbnail_offset is not None:
            exth.write(pack(b'>III', EXTH_CODES['thumboffset'], 12,
                self.thumbnail_offset))
            nrecs += 1

        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = b'\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = [b'EXTH', pack(b'>II', len(exth) + 12, nrecs), exth, pad]
        return b''.join(exth)
    # }}}

    def write_header(self): # PalmDB header {{{
        '''
        Write the PalmDB header
        '''
        title = ascii_filename(unicode(self.oeb.metadata.title[0])).replace(
                ' ', '_')
        title = title + (b'\0' * (32 - len(title)))
        now = int(time.time())
        nrecords = len(self.records)
        self.write(title, pack(b'>HHIIIIII', 0, 0, now, now, 0, 0, 0, 0),
            b'BOOK', b'MOBI', pack(b'>IIH', (2*nrecords)-1, 0, nrecords))
        offset = self.tell() + (8 * nrecords) + 2
        for i, record in enumerate(self.records):
            self.write(pack(b'>I', offset), b'\0', pack(b'>I', 2*i)[1:])
            offset += len(record)
        self.write(b'\0\0')
    # }}}

    def write_content(self):
        for record in self.records:
            self.write(record)


