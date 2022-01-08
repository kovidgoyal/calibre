#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, random
from struct import pack

from calibre.ebooks.mobi.utils import RECORD_SIZE, utf8_text
from calibre.ebooks.mobi.writer8.header import Header
from calibre.ebooks.mobi.writer2 import (PALMDOC, UNCOMPRESSED)
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.ebooks.mobi.writer8.exth import build_exth
from calibre.utils.filenames import ascii_filename

NULL_INDEX = 0xffffffff
FLIS = b'FLIS\0\0\0\x08\0\x41\0\0\0\0\0\0\xff\xff\xff\xff\0\x01\0\x03\0\0\0\x03\0\0\0\x01'+ b'\xff'*4


def fcis(text_length):
    fcis = b'FCIS\x00\x00\x00\x14\x00\x00\x00\x10\x00\x00\x00\x02\x00\x00\x00\x00'
    fcis += pack(b'>L', text_length)
    fcis += b'\x00\x00\x00\x00\x00\x00\x00\x28\x00\x00\x00\x00\x00\x00\x00'
    fcis += b'\x28\x00\x00\x00\x08\x00\x01\x00\x01\x00\x00\x00\x00'
    return fcis


class MOBIHeader(Header):  # {{{

    '''
    Represents the first record in a MOBI file, contains all the metadata about
    the file.
    '''

    DEFINITION = '''
    # 0: Compression
    compression = DYN

    # 2: Unused
    unused1 = zeroes(2)

    # 4: Text length
    text_length = DYN

    # 8: Last text record
    last_text_record = DYN

    # 10: Text record size
    record_size = {record_size}

    # 12: Encryption Type
    encryption_type

    # 14: Unused
    unused2

    # 16: Ident
    ident = b'MOBI'

    # 20: Header length
    header_length = 264

    # 24: Book Type (0x2 - Book, 0x101 - News hierarchical, 0x102 - News
    # (flat), 0x103 - News magazine same as 0x101)
    book_type = DYN

    # 28: Text encoding (utf-8 = 65001)
    encoding = 65001

    # 32: UID
    uid = DYN

    # 36: File version
    file_version = {file_version}

    # 40: Meta orth record (used in dictionaries)
    meta_orth_record = NULL

    # 44: Meta infl index
    meta_infl_index = NULL

    # 48: Extra indices
    extra_index0 = NULL
    extra_index1 = NULL
    extra_index2 = NULL
    extra_index3 = NULL
    extra_index4 = NULL
    extra_index5 = NULL
    extra_index6 = NULL
    extra_index7 = NULL

    # 80: First non text record
    first_non_text_record = DYN

    # 84: Title offset
    title_offset

    # 88: Title Length
    title_length = DYN

    # 92: Language code
    language_code = DYN

    # 96: Dictionary in and out languages
    in_lang
    out_lang

    # 104: Min version
    min_version = {file_version}

    # 108: First resource record
    first_resource_record = DYN

    # 112: Huff/CDIC compression
    huff_first_record
    huff_count
    huff_table_offset = zeroes(4)
    huff_table_length = zeroes(4)

    # 128: EXTH flags
    exth_flags = DYN

    # 132: Unknown
    unknown = zeroes(32)

    # 164: Unknown
    unknown_index = NULL

    # 168: DRM
    drm_offset = NULL
    drm_count
    drm_size
    drm_flags

    # 184: Unknown
    unknown2 = zeroes(8)

    # 192: FDST
    # In MOBI 6 the fdst record is instead two two byte fields storing the
    # index of the first and last content records
    fdst_record = DYN
    fdst_count = DYN

    # 200: FCIS
    fcis_record = DYN
    fcis_count = 1

    # 208: FLIS
    flis_record = DYN
    flis_count = 1

    # 216: Unknown
    unknown3 = zeroes(8)

    # 224: SRCS
    srcs_record = NULL
    srcs_count

    # 232: Unknown
    unknown4 = nulls(8)

    # 240: Extra data flags
    # 0b1 - extra multibyte bytes after text records
    # 0b10 - TBS indexing data (only used in MOBI 6)
    # 0b100 - uncrossable breaks only used in MOBI 6
    extra_data_flags = DYN

    # 244: KF8 Indices
    ncx_index = DYN
    chunk_index = DYN
    skel_index = DYN
    datp_index = NULL
    guide_index = DYN

    # 264: Unknown
    unknown5 = nulls(4)
    unknown6 = zeroes(4)
    unknown7 = nulls(4)
    unknown8 = zeroes(4)

    # 280: EXTH
    exth = DYN

    # Full title
    full_title = DYN

    # Padding to allow amazon's DTP service to add data
    padding = zeroes(8192)
    '''

    SHORT_FIELDS = {'compression', 'last_text_record', 'record_size',
            'encryption_type', 'unused2'}
    ALIGN = True
    POSITIONS = {'title_offset':'full_title'}

    def __init__(self, file_version=8):
        self.DEFINITION = self.DEFINITION.format(file_version=file_version,
                record_size=RECORD_SIZE)
        super().__init__()

    def format_value(self, name, val):
        if name == 'compression':
            val = PALMDOC if val else UNCOMPRESSED
        return super().format_value(name, val)

# }}}


HEADER_FIELDS = {'compression', 'text_length', 'last_text_record', 'book_type',
                    'first_non_text_record', 'title_length', 'language_code',
                    'first_resource_record', 'exth_flags', 'fdst_record',
                    'fdst_count', 'ncx_index', 'chunk_index', 'skel_index',
                    'guide_index', 'exth', 'full_title', 'extra_data_flags',
                    'flis_record', 'fcis_record', 'uid'}


class KF8Book:

    def __init__(self, writer, for_joint=False):
        self.build_records(writer, for_joint)
        self.used_images = writer.used_images
        self.page_progression_direction = writer.oeb.spine.page_progression_direction
        self.primary_writing_mode = writer.oeb.metadata.primary_writing_mode
        if self.page_progression_direction == 'rtl' and not self.primary_writing_mode:
            # Without this the Kindle renderer does not respect
            # page_progression_direction
            self.primary_writing_mode = 'horizontal-rl'

    def build_records(self, writer, for_joint):
        metadata = writer.oeb.metadata
        # The text records
        for x in ('last_text_record_idx', 'first_non_text_record_idx'):
            setattr(self, x.rpartition('_')[0], getattr(writer, x))
        self.records = writer.records
        self.text_length = writer.text_length

        # KF8 Indices
        self.chunk_index = len(self.records)
        self.records.extend(writer.chunk_records)
        self.skel_index = len(self.records)
        self.records.extend(writer.skel_records)
        self.guide_index = NULL_INDEX
        if writer.guide_records:
            self.guide_index = len(self.records)
            self.records.extend(writer.guide_records)
        self.ncx_index = NULL_INDEX
        if writer.ncx_records:
            self.ncx_index = len(self.records)
            self.records.extend(writer.ncx_records)

        # Resources
        resources = writer.resources
        for x in ('cover_offset', 'thumbnail_offset', 'masthead_offset'):
            setattr(self, x, getattr(resources, x))

        self.first_resource_record = NULL_INDEX
        before = len(self.records)
        if resources.records:
            self.first_resource_record = len(self.records)
            if not for_joint:
                resources.serialize(self.records, writer.used_images)
        self.num_of_resources = len(self.records) - before

        # FDST
        self.fdst_count = writer.fdst_count
        self.fdst_record = len(self.records)
        self.records.extend(writer.fdst_records)

        # FLIS/FCIS
        self.flis_record = len(self.records)
        self.records.append(FLIS)
        self.fcis_record = len(self.records)
        self.records.append(fcis(self.text_length))

        # EOF
        self.records.append(b'\xe9\x8e\r\n')  # EOF record

        # Miscellaneous header fields
        self.compression = writer.compress
        self.book_type = 0x101 if writer.opts.mobi_periodical else 2
        self.full_title = utf8_text(str(metadata.title[0]))
        self.title_length = len(self.full_title)
        self.extra_data_flags = 0b1
        if writer.has_tbs:
            self.extra_data_flags |= 0b10
        self.uid = random.randint(0, 0xffffffff)

        self.language_code = iana2mobi(str(metadata.language[0]))
        self.exth_flags = 0b1010000
        if writer.opts.mobi_periodical:
            self.exth_flags |= 0b1000
        if resources.has_fonts:
            self.exth_flags |= 0b1000000000000

        self.opts = writer.opts
        self.start_offset = writer.start_offset
        self.metadata = metadata
        self.kuc = 0 if len(resources.records) > 0 else None

    @property
    def record0(self):
        ''' We generate the EXTH header and record0 dynamically, to allow other
        code to customize various values after build_records() has been
        called'''
        opts = self.opts
        self.exth = build_exth(
            self.metadata,
            prefer_author_sort=opts.prefer_author_sort,
            is_periodical=opts.mobi_periodical,
            share_not_sync=opts.share_not_sync,
            cover_offset=self.cover_offset,
            thumbnail_offset=self.thumbnail_offset,
            num_of_resources=self.num_of_resources,
            kf8_unknown_count=self.kuc, be_kindlegen2=True,
            start_offset=self.start_offset, mobi_doctype=self.book_type,
            page_progression_direction=self.page_progression_direction,
            primary_writing_mode=self.primary_writing_mode
        )

        kwargs = {field:getattr(self, field) for field in HEADER_FIELDS}
        return MOBIHeader()(**kwargs)

    def write(self, outpath):
        records = [self.record0] + self.records[1:]

        with open(outpath, 'wb') as f:

            # Write PalmDB Header

            title = ascii_filename(self.full_title.decode('utf-8')).replace(' ', '_')
            if not isinstance(title, bytes):
                title = title.encode('ascii')
            title = title[:31]
            title += (b'\0' * (32 - len(title)))
            now = int(time.time())
            nrecords = len(records)
            f.write(title)
            f.write(pack(b'>HHIIIIII', 0, 0, now, now, 0, 0, 0, 0))
            f.write(b'BOOKMOBI')
            f.write(pack(b'>IIH', (2*nrecords)-1, 0, nrecords))
            offset = f.tell() + (8 * nrecords) + 2
            for i, record in enumerate(records):
                f.write(pack(b'>I', offset))
                f.write(b'\0' + pack(b'>I', 2*i)[1:])
                offset += len(record)
            f.write(b'\0\0')

            for rec in records:
                f.write(rec)
