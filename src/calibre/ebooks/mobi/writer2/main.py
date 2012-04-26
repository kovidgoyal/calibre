#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import random, time
from cStringIO import StringIO
from struct import pack

from calibre.ebooks import normalize
from calibre.ebooks.mobi.writer2.serializer import Serializer
from calibre.ebooks.compression.palmdoc import compress_doc
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.mobi.writer2 import (PALMDOC, UNCOMPRESSED)
from calibre.ebooks.mobi.utils import (encint, encode_trailing_data,
        align_block, detect_periodical, RECORD_SIZE, create_text_record)
from calibre.ebooks.mobi.writer2.indexer import Indexer

# Disabled as I dont care about uncrossable breaks
WRITE_UNCROSSABLE_BREAKS = False
NULL_INDEX = 0xffffffff

class MobiWriter(object):

    def __init__(self, opts, resources, kf8, write_page_breaks_after_item=True):
        self.opts = opts
        self.resources = resources
        self.kf8 = kf8
        self.for_joint = kf8 is not None
        self.write_page_breaks_after_item = write_page_breaks_after_item
        self.compression = UNCOMPRESSED if opts.dont_compress else PALMDOC
        self.prefer_author_sort = opts.prefer_author_sort
        self.last_text_record_idx = 1

    def __call__(self, oeb, path_or_stream):
        self.log = oeb.log
        pt = None
        if oeb.metadata.publication_type:
            x = unicode(oeb.metadata.publication_type[0]).split(':')
            if len(x) > 1:
                pt = x[1].lower()
        self.publication_type = pt

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
        self.generate_joint_record0() if self.for_joint else self.generate_record0()
        self.write_header()
        self.write_content()

    def generate_content(self):
        self.is_periodical = detect_periodical(self.oeb.toc, self.oeb.log)
        # Image records are stored in their own list, they are merged into the
        # main record list at the end
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
        if self.oeb.toc.count() < 1:
            self.log.warn('No TOC, MOBI index not generated')
            return
        try:
            self.indexer = Indexer(self.serializer, self.last_text_record_idx,
                    len(self.records[self.last_text_record_idx]),
                    self.masthead_offset, self.is_periodical,
                    self.opts, self.oeb)
        except:
            self.log.exception('Failed to generate MOBI index:')
        else:
            self.primary_index_record_idx = len(self.records)
            for i in xrange(self.last_text_record_idx + 1):
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
        resources = self.resources
        image_records = resources.records
        self.image_map = resources.item_map
        self.masthead_offset = resources.masthead_offset
        self.cover_offset = resources.cover_offset
        self.thumbnail_offset = resources.thumbnail_offset

        if image_records and image_records[0] is None:
            raise ValueError('Failed to find masthead image in manifest')

    # }}}

    def generate_text(self): # {{{
        self.oeb.logger.info('Serializing markup content...')
        self.serializer = Serializer(self.oeb, self.image_map,
                self.is_periodical,
                write_page_breaks_after_item=self.write_page_breaks_after_item)
        text = self.serializer()
        self.text_length = len(text)
        text = StringIO(text)
        nrecords = 0
        records_size = 0

        if self.compression != UNCOMPRESSED:
            self.oeb.logger.info('  Compressing markup content...')

        while text.tell() < self.text_length:
            data, overlap = create_text_record(text)
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
    # }}}

    def generate_record0(self): #  MOBI header {{{
        metadata = self.oeb.metadata
        bt = 0x002
        if self.primary_index_record_idx is not None:
            if False and self.indexer.is_flat_periodical:
                # Disabled as setting this to 0x102 causes the Kindle to not
                # auto archive the issues
                bt = 0x102
            elif self.indexer.is_periodical:
                # If you change this, remember to change the cdetype in the EXTH
                # header as well
                bt = 0x103 if self.indexer.is_flat_periodical else 0x101

        from calibre.ebooks.mobi.writer8.exth import build_exth
        exth = build_exth(metadata,
                prefer_author_sort=self.opts.prefer_author_sort,
                is_periodical=self.is_periodical,
                share_not_sync=self.opts.share_not_sync,
                cover_offset=self.cover_offset,
                thumbnail_offset=self.thumbnail_offset,
                start_offset=self.serializer.start_offset, mobi_doctype=bt
                )
        first_image_record = None
        if self.resources:
            used_images = self.serializer.used_images
            first_image_record  = len(self.records)
            self.resources.serialize(self.records, used_images)
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

        record0.write(pack(b'>IIIII',
            0xe8, bt, 65001, uid, 6))

        # 0x18 - 0x1f : Unknown
        record0.write(b'\xff' * 8)

        # 0x20 - 0x23 : Secondary index record
        sir = 0xffffffff
        if (self.primary_index_record_idx is not None and
                self.indexer.secondary_record_offset is not None):
            sir = (self.primary_index_record_idx +
                    self.indexer.secondary_record_offset)
        record0.write(pack(b'>I', sir))

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

    def generate_joint_record0(self): # {{{
        from calibre.ebooks.mobi.writer8.mobi import (MOBIHeader,
                HEADER_FIELDS)
        from calibre.ebooks.mobi.writer8.exth import build_exth

        # Insert resource records
        first_image_record = None
        old = len(self.records)
        if self.resources:
            used_images = self.serializer.used_images | self.kf8.used_images
            first_image_record  = len(self.records)
            self.resources.serialize(self.records, used_images)
        resource_record_count = len(self.records) - old

        # Insert KF8 records
        self.records.append(b'BOUNDARY')
        kf8_header_index = len(self.records)
        self.kf8.start_offset = (self.serializer.start_offset,
                self.kf8.start_offset)
        self.records.append(self.kf8.record0)
        self.records.extend(self.kf8.records[1:])

        first_image_record if first_image_record else len(self.records)

        header_fields = {k:getattr(self.kf8, k) for k in HEADER_FIELDS}

        # Now change the header fields that need to be different in the MOBI 6
        # header
        header_fields['first_resource_record'] = first_image_record
        header_fields['exth_flags'] = 0b100001010000 # Kinglegen uses this
        header_fields['fdst_record'] = NULL_INDEX
        header_fields['fdst_count'] = 1 # Why not 0? Kindlegen uses 1
        extra_data_flags = 0b1 # Has multibyte overlap bytes
        if self.primary_index_record_idx is not None:
            extra_data_flags |= 0b10
        header_fields['extra_data_flags'] = extra_data_flags

        for k, v in {'last_text_record':'last_text_record_idx',
                'first_non_text_record':'first_non_text_record_idx',
                'ncx_index':'primary_index_record_idx',
                }.iteritems():
            header_fields[k] = getattr(self, v)

        for x in ('skel', 'chunk', 'guide'):
            header_fields[x+'_index'] = NULL_INDEX

        # Create the MOBI 6 EXTH
        opts = self.opts
        kuc = 0 if resource_record_count > 0 else None

        header_fields['exth'] = build_exth(self.oeb.metadata,
                prefer_author_sort=opts.prefer_author_sort,
                is_periodical=opts.mobi_periodical,
                share_not_sync=opts.share_not_sync,
                cover_offset=self.cover_offset,
                thumbnail_offset=self.thumbnail_offset,
                num_of_resources=resource_record_count,
                kf8_unknown_count=kuc, be_kindlegen2=True,
                kf8_header_index=kf8_header_index,
                start_offset=self.serializer.start_offset,
                mobi_doctype=2)
        self.records[0] = MOBIHeader(file_version=6)(**header_fields)

    # }}}

    def write_header(self): # PalmDB header {{{
        '''
        Write the PalmDB header
        '''
        title = ascii_filename(unicode(self.oeb.metadata.title[0])).replace(
                ' ', '_')[:31]
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


