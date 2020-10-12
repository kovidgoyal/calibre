#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct, datetime, os, numbers, binascii

from calibre.utils.date import utc_tz
from calibre.ebooks.mobi.reader.headers import NULL_INDEX
from calibre.ebooks.mobi.langcodes import main_language, sub_language
from calibre.ebooks.mobi.debug import format_bytes
from calibre.ebooks.mobi.utils import get_trailing_data
from polyglot.builtins import iteritems, range, unicode_type

# PalmDB {{{


class PalmDOCAttributes(object):

    class Attr(object):

        def __init__(self, name, field, val):
            self.name = name
            self.val = val & field

        def __str__(self):
            return '%s: %s'%(self.name, bool(self.val))
        __unicode__ = __str__

    def __init__(self, raw):
        self.val = struct.unpack(b'<H', raw)[0]
        self.attributes = []
        for name, field in [('Read Only', 0x02), ('Dirty AppInfoArea', 0x04),
                ('Backup this database', 0x08),
                ('Okay to install newer over existing copy, if present on PalmPilot', 0x10),
                ('Force the PalmPilot to reset after this database is installed', 0x12),
                ('Don\'t allow copy of file to be beamed to other Pilot',
                    0x14)]:
            self.attributes.append(PalmDOCAttributes.Attr(name, field,
                self.val))

    def __str__(self):
        attrs = '\n\t'.join([unicode_type(x) for x in self.attributes])
        return 'PalmDOC Attributes: %s\n\t%s'%(bin(self.val), attrs)
    __unicode__ = __str__


class PalmDB(object):

    def __init__(self, raw):
        self.raw = raw

        if self.raw.startswith(b'TPZ'):
            raise ValueError('This is a Topaz file')

        self.name     = self.raw[:32].replace(b'\x00', b'')
        self.attributes = PalmDOCAttributes(self.raw[32:34])
        self.version = struct.unpack(b'>H', self.raw[34:36])[0]

        palm_epoch = datetime.datetime(1904, 1, 1, tzinfo=utc_tz)
        self.creation_date_raw = struct.unpack(b'>I', self.raw[36:40])[0]
        self.creation_date = (palm_epoch +
                datetime.timedelta(seconds=self.creation_date_raw))
        self.modification_date_raw = struct.unpack(b'>I', self.raw[40:44])[0]
        self.modification_date = (palm_epoch +
                datetime.timedelta(seconds=self.modification_date_raw))
        self.last_backup_date_raw = struct.unpack(b'>I', self.raw[44:48])[0]
        self.last_backup_date = (palm_epoch +
                datetime.timedelta(seconds=self.last_backup_date_raw))
        self.modification_number = struct.unpack(b'>I', self.raw[48:52])[0]
        self.app_info_id = self.raw[52:56]
        self.sort_info_id = self.raw[56:60]
        self.type = self.raw[60:64]
        self.creator = self.raw[64:68]
        self.ident = self.type + self.creator
        if self.ident not in (b'BOOKMOBI', b'TEXTREAD'):
            raise ValueError('Unknown book ident: %r'%self.ident)
        self.last_record_uid, = struct.unpack(b'>I', self.raw[68:72])
        self.next_rec_list_id = self.raw[72:76]

        self.number_of_records, = struct.unpack(b'>H', self.raw[76:78])

    def __str__(self):
        ans = ['*'*20 + ' PalmDB Header '+ '*'*20]
        ans.append('Name: %r'%self.name)
        ans.append(unicode_type(self.attributes))
        ans.append('Version: %s'%self.version)
        ans.append('Creation date: %s (%s)'%(self.creation_date.isoformat(),
            self.creation_date_raw))
        ans.append('Modification date: %s (%s)'%(self.modification_date.isoformat(),
            self.modification_date_raw))
        ans.append('Backup date: %s (%s)'%(self.last_backup_date.isoformat(),
            self.last_backup_date_raw))
        ans.append('Modification number: %s'%self.modification_number)
        ans.append('App Info ID: %r'%self.app_info_id)
        ans.append('Sort Info ID: %r'%self.sort_info_id)
        ans.append('Type: %r'%self.type)
        ans.append('Creator: %r'%self.creator)
        ans.append('Last record UID +1: %r'%self.last_record_uid)
        ans.append('Next record list id: %r'%self.next_rec_list_id)
        ans.append('Number of records: %s'%self.number_of_records)

        return '\n'.join(ans)
    __unicode__ = __str__
# }}}


class Record(object):  # {{{

    def __init__(self, raw, header):
        self.offset, self.flags, self.uid = header
        self.raw = raw

    @property
    def header(self):
        return 'Offset: %d Flags: %d UID: %d First 4 bytes: %r Size: %d'%(self.offset, self.flags,
                self.uid, self.raw[:4], len(self.raw))
# }}}

# EXTH {{{


class EXTHRecord(object):

    def __init__(self, type_, data, length):
        self.type = type_
        self.data = data
        self.length = length
        self.name = {
                1   : 'Drm Server Id',
                2   : 'Drm Commerce Id',
                3   : 'Drm Ebookbase Book Id',
                100 : 'Creator',
                101 : 'Publisher',
                102 : 'Imprint',
                103 : 'Description',
                104 : 'ISBN',
                105 : 'Subject',
                106 : 'Published',
                107 : 'Review',
                108 : 'Contributor',
                109 : 'Rights',
                110 : 'SubjectCode',
                111 : 'Type',
                112 : 'Source',
                113 : 'ASIN',
                114 : 'versionNumber',
                115 : 'sample',
                116 : 'StartOffset',
                117 : 'Adult',
                118 : 'Price',
                119 : 'Currency',
                121 : 'KF8_Boundary_Section',
                122 : 'fixed-layout',
                123 : 'book-type',
                124 : 'orientation-lock',
                125 : 'KF8_Count_of_Resources_Fonts_Images',
                126 : 'original-resolution',
                127 : 'zero-gutter',
                128 : 'zero-margin',
                129 : 'KF8_Masthead/Cover_Image',
                131 : 'KF8_Unidentified_Count',
                132 : 'RegionMagnification',
                200 : 'DictShortName',
                201 : 'CoverOffset',
                202 : 'ThumbOffset',
                203 : 'Fake Cover',
                204 : 'Creator Software',
                205 : 'Creator Major Version',  # '>I'
                206 : 'Creator Minor Version',  # '>I'
                207 : 'Creator Build Number',  # '>I'
                208 : 'Watermark',
                209 : 'Tamper Proof Keys [hex]',
                300 : 'Font Signature [hex]',
                301 : 'Clipping Limit [3xx]',  # percentage '>B'
                401 : 'Clipping Limit',  # percentage '>B'
                402 : 'Publisher Limit',
                404 : 'Text to Speech Disabled',  # '>B' 1 - TTS disabled 0 - TTS enabled
                501 : 'CDE Type',  # 4 chars (PDOC, EBOK, MAGZ, ...)
                502 : 'last_update_time',
                503 : 'Updated Title',
                504 : 'ASIN [5xx]',
                508 : 'Unknown Title Furigana?',
                517 : 'Unknown Creator Furigana?',
                522 : 'Unknown Publisher Furigana?',
                524 : 'Language',
                525 : 'primary-writing-mode',
                527 : 'page-progression-direction',
                528 : 'Override Kindle fonts',
                534 : 'Input Source Type',
                535 : 'Kindlegen Build-Rev Number',
                536 : 'Container Info',  # CONT_Header is 0, Ends with CONTAINER_BOUNDARY (or Asset_Type?)
                538 : 'Container Resolution',
                539 : 'Container Mimetype',
                543 : 'Container id',  # FONT_CONTAINER, BW_CONTAINER, HD_CONTAINER
        }.get(self.type, repr(self.type))

        if (self.name in {'sample', 'StartOffset', 'CoverOffset', 'ThumbOffset', 'Fake Cover',
                'Creator Software', 'Creator Major Version', 'Creator Minor Version',
                'Creator Build Number', 'Clipping Limit (3xx)', 'Clipping Limit',
                'Publisher Limit', 'Text to Speech Disabled'} or
                self.type in {121, 125, 131}):
            if self.length == 9:
                self.data, = struct.unpack(b'>B', self.data)
            elif self.length == 10:
                self.data, = struct.unpack(b'>H', self.data)
            else:
                self.data, = struct.unpack(b'>L', self.data)
        elif self.type in {209, 300}:
            self.data = binascii.hexlify(self.data)

    def __str__(self):
        return '%s (%d): %r'%(self.name, self.type, self.data)


class EXTHHeader(object):

    def __init__(self, raw):
        self.raw = raw
        if not self.raw.startswith(b'EXTH'):
            raise ValueError('EXTH header does not start with EXTH')
        self.length, = struct.unpack(b'>L', self.raw[4:8])
        self.count,  = struct.unpack(b'>L', self.raw[8:12])

        pos = 12
        self.records = []
        for i in range(self.count):
            pos = self.read_record(pos)
        self.records.sort(key=lambda x:x.type)
        self.rmap = {x.type:x for x in self.records}

    def __getitem__(self, type_):
        return self.rmap.__getitem__(type_).data

    def get(self, type_, default=None):
        ans = self.rmap.get(type_, default)
        return getattr(ans, 'data', default)

    def read_record(self, pos):
        type_, length = struct.unpack(b'>LL', self.raw[pos:pos+8])
        data = self.raw[(pos+8):(pos+length)]
        self.records.append(EXTHRecord(type_, data, length))
        return pos + length

    @property
    def kf8_header_index(self):
        ans = self.get(121, None)
        if ans == NULL_INDEX:
            ans = None
        return ans

    def __str__(self):
        ans = ['*'*20 + ' EXTH Header '+ '*'*20]
        ans.append('EXTH header length: %d'%self.length)
        ans.append('Number of EXTH records: %d'%self.count)
        ans.append('EXTH records...')
        for r in self.records:
            ans.append(unicode_type(r))
        return '\n'.join(ans)
    __unicode__ = __str__

# }}}


class MOBIHeader(object):  # {{{

    def __init__(self, record0, offset):
        self.raw = record0.raw
        self.header_offset = offset

        self.compression_raw = self.raw[:2]
        self.compression = {1: 'No compression', 2: 'PalmDoc compression',
                17480: 'HUFF/CDIC compression'}.get(struct.unpack(b'>H',
                    self.compression_raw)[0],
                    repr(self.compression_raw))
        self.unused = self.raw[2:4]
        self.text_length, = struct.unpack(b'>I', self.raw[4:8])
        self.number_of_text_records, self.text_record_size = \
                struct.unpack(b'>HH', self.raw[8:12])
        self.encryption_type_raw, = struct.unpack(b'>H', self.raw[12:14])
        self.encryption_type = {
                0: 'No encryption',
                1: 'Old mobipocket encryption',
                2: 'Mobipocket encryption'
            }.get(self.encryption_type_raw, repr(self.encryption_type_raw))
        self.unknown = self.raw[14:16]

        self.identifier = self.raw[16:20]
        if self.identifier != b'MOBI':
            raise ValueError('Identifier %r unknown'%self.identifier)

        self.length, = struct.unpack(b'>I', self.raw[20:24])
        self.type_raw, = struct.unpack(b'>I', self.raw[24:28])
        self.type = {
                2 : 'Mobipocket book',
                3 : 'PalmDOC book',
                4 : 'Audio',
                257 : 'News',
                258 : 'News Feed',
                259 : 'News magazine',
                513 : 'PICS',
                514 : 'Word',
                515 : 'XLS',
                516 : 'PPT',
                517 : 'TEXT',
                518 : 'HTML',
            }.get(self.type_raw, repr(self.type_raw))

        self.encoding_raw, = struct.unpack(b'>I', self.raw[28:32])
        self.encoding = {
                1252 : 'cp1252',
                65001: 'utf-8',
            }.get(self.encoding_raw, repr(self.encoding_raw))
        self.uid = self.raw[32:36]
        self.file_version, = struct.unpack(b'>I', self.raw[36:40])
        self.meta_orth_indx, self.meta_infl_indx = struct.unpack(
                b'>II', self.raw[40:48])
        self.secondary_index_record, = struct.unpack(b'>I', self.raw[48:52])
        self.reserved = self.raw[52:80]
        self.first_non_book_record, = struct.unpack(b'>I', self.raw[80:84])
        self.fullname_offset, = struct.unpack(b'>I', self.raw[84:88])
        self.fullname_length, = struct.unpack(b'>I', self.raw[88:92])
        self.locale_raw, = struct.unpack(b'>I', self.raw[92:96])
        langcode = self.locale_raw
        langid    = langcode & 0xFF
        sublangid = (langcode >> 10) & 0xFF
        self.language = main_language.get(langid, 'ENGLISH')
        self.sublanguage = sub_language.get(sublangid, 'NEUTRAL')

        self.input_language = self.raw[96:100]
        self.output_langauage = self.raw[100:104]
        self.min_version, = struct.unpack(b'>I', self.raw[104:108])
        self.first_image_index, = struct.unpack(b'>I', self.raw[108:112])
        self.huffman_record_offset, = struct.unpack(b'>I', self.raw[112:116])
        self.huffman_record_count, = struct.unpack(b'>I', self.raw[116:120])
        self.datp_record_offset, = struct.unpack(b'>I', self.raw[120:124])
        self.datp_record_count, = struct.unpack(b'>I', self.raw[124:128])
        self.exth_flags, = struct.unpack(b'>I', self.raw[128:132])
        self.has_exth = bool(self.exth_flags & 0x40)
        self.has_drm_data = self.length >= 174 and len(self.raw) >= 184
        if self.has_drm_data:
            self.unknown3 = self.raw[132:168]
            self.drm_offset, self.drm_count, self.drm_size, self.drm_flags = \
                    struct.unpack(b'>4I', self.raw[168:184])
        self.has_extra_data_flags = self.length >= 232 and len(self.raw) >= 232+16
        self.has_fcis_flis = False
        self.has_multibytes = self.has_indexing_bytes = self.has_uncrossable_breaks = False
        self.extra_data_flags = 0
        if self.has_extra_data_flags:
            self.unknown4 = self.raw[184:192]
            if self.file_version < 8:
                self.first_text_record, self.last_text_record = \
                    struct.unpack_from(b'>HH', self.raw, 192)
                self.fdst_count = struct.unpack_from(b'>L', self.raw, 196)
            else:
                self.fdst_idx, self.fdst_count = struct.unpack_from(b'>LL',
                        self.raw, 192)
                if self.fdst_count <= 1:
                    self.fdst_idx = NULL_INDEX
            (self.fcis_number, self.fcis_count, self.flis_number,
                    self.flis_count) = struct.unpack(b'>IIII',
                            self.raw[200:216])
            self.unknown6 = self.raw[216:224]
            self.srcs_record_index = struct.unpack(b'>I',
                self.raw[224:228])[0]
            self.num_srcs_records = struct.unpack(b'>I',
                self.raw[228:232])[0]
            self.unknown7 = self.raw[232:240]
            self.extra_data_flags = struct.unpack(b'>I',
                self.raw[240:244])[0]
            self.has_multibytes = bool(self.extra_data_flags & 0b1)
            self.has_indexing_bytes = bool(self.extra_data_flags & 0b10)
            self.has_uncrossable_breaks = bool(self.extra_data_flags & 0b100)
            self.primary_index_record, = struct.unpack(b'>I',
                    self.raw[244:248])

        if self.length >= 248:
            (self.sect_idx, self.skel_idx, self.datp_idx, self.oth_idx
                    ) = struct.unpack_from(b'>4L', self.raw, 248)
            self.unknown9 = self.raw[264:self.length+16]
            if self.meta_orth_indx not in {NULL_INDEX, self.sect_idx}:
                raise ValueError('KF8 header has different Meta orth and '
                        'section indices')

        # The following are all relative to the position of the header record
        # make them absolute for ease of debugging
        self.relative_records = {'sect_idx', 'skel_idx', 'datp_idx', 'oth_idx',
                'meta_orth_indx', 'huffman_record_offset',
                'first_non_book_record', 'datp_record_offset', 'fcis_number',
                'flis_number', 'primary_index_record', 'fdst_idx',
                'first_image_index'}
        for x in self.relative_records:
            if hasattr(self, x) and getattr(self, x) != NULL_INDEX:
                setattr(self, x, self.header_offset+getattr(self, x))

        # Try to find the first non-text record
        self.first_resource_record = offset + 1 + self.number_of_text_records  # Default to first record after all text records
        pointer = min(getattr(self, 'first_non_book_record', NULL_INDEX), getattr(self, 'first_image_index', NULL_INDEX))
        if pointer != NULL_INDEX:
            self.first_resource_record = max(pointer, self.first_resource_record)
        self.last_resource_record = NULL_INDEX

        if self.has_exth:
            self.exth_offset = 16 + self.length

            self.exth = EXTHHeader(self.raw[self.exth_offset:])

            self.end_of_exth = self.exth_offset + self.exth.length
            self.bytes_after_exth = self.raw[self.end_of_exth:self.fullname_offset]

            if self.exth.kf8_header_index is not None and offset == 0:
                # MOBI 6 header in a joint file, adjust self.last_resource_record
                self.last_resource_record = self.exth.kf8_header_index - 2

    def __str__(self):
        ans = ['*'*20 + ' MOBI %d Header '%self.file_version+ '*'*20]

        a = ans.append

        def i(d, x):
            x = 'NULL' if x == NULL_INDEX else x
            a('%s: %s'%(d, x))

        def r(d, attr):
            x = getattr(self, attr)
            if attr in self.relative_records and x != NULL_INDEX:
                a('%s: Absolute: %d Relative: %d'%(d, x, x-self.header_offset))
            else:
                i(d, x)

        a('Compression: %s'%self.compression)
        a('Unused: %r'%self.unused)
        a('Text length: %d'%self.text_length)
        a('Number of text records: %d'%self.number_of_text_records)
        a('Text record size: %d'%self.text_record_size)
        a('Encryption: %s'%self.encryption_type)
        a('Unknown: %r'%self.unknown)
        a('Identifier: %r'%self.identifier)
        a('Header length: %d'% self.length)
        a('Type: %s'%self.type)
        a('Encoding: %s'%self.encoding)
        a('UID: %r'%self.uid)
        a('File version: %d'%self.file_version)
        r('Meta Orth Index', 'meta_orth_indx')
        r('Meta Infl Index', 'meta_infl_indx')
        r('Secondary index record', 'secondary_index_record')
        a('Reserved: %r'%self.reserved)
        r('First non-book record', 'first_non_book_record')
        a('Full name offset: %d'%self.fullname_offset)
        a('Full name length: %d bytes'%self.fullname_length)
        a('Langcode: %r'%self.locale_raw)
        a('Language: %s'%self.language)
        a('Sub language: %s'%self.sublanguage)
        a('Input language: %r'%self.input_language)
        a('Output language: %r'%self.output_langauage)
        a('Min version: %d'%self.min_version)
        r('First Image index', 'first_image_index')
        r('Huffman record offset', 'huffman_record_offset')
        a('Huffman record count: %d'%self.huffman_record_count)
        r('Huffman table offset', 'datp_record_offset')
        a('Huffman table length: %r'%self.datp_record_count)
        a('EXTH flags: %s (%s)'%(bin(self.exth_flags)[2:], self.has_exth))
        if self.has_drm_data:
            a('Unknown3: %r'%self.unknown3)
            r('DRM Offset', 'drm_offset')
            a('DRM Count: %s'%self.drm_count)
            a('DRM Size: %s'%self.drm_size)
            a('DRM Flags: %r'%self.drm_flags)
        if self.has_extra_data_flags:
            a('Unknown4: %r'%self.unknown4)
            if hasattr(self, 'first_text_record'):
                a('First content record: %d'%self.first_text_record)
                a('Last content record: %d'%self.last_text_record)
            else:
                r('FDST Index', 'fdst_idx')
            a('FDST Count: %d'% self.fdst_count)
            r('FCIS number', 'fcis_number')
            a('FCIS count: %d'% self.fcis_count)
            r('FLIS number', 'flis_number')
            a('FLIS count: %d'% self.flis_count)
            a('Unknown6: %r'% self.unknown6)
            r('SRCS record index', 'srcs_record_index')
            a('Number of SRCS records?: %d'%self.num_srcs_records)
            a('Unknown7: %r'%self.unknown7)
            a(('Extra data flags: %s (has multibyte: %s) '
                '(has indexing: %s) (has uncrossable breaks: %s)')%(
                    bin(self.extra_data_flags), self.has_multibytes,
                    self.has_indexing_bytes, self.has_uncrossable_breaks))
            r('NCX index', 'primary_index_record')
        if self.length >= 248:
            r('Sections Index', 'sect_idx')
            r('SKEL Index', 'skel_idx')
            r('DATP Index', 'datp_idx')
            r('Other Index', 'oth_idx')
            if self.unknown9:
                a('Unknown9: %r'%self.unknown9)

        ans = '\n'.join(ans)

        if self.has_exth:
            ans += '\n\n' + unicode_type(self.exth)
            ans += '\n\nBytes after EXTH (%d bytes): %s'%(
                    len(self.bytes_after_exth),
                    format_bytes(self.bytes_after_exth))

        ans += '\nNumber of bytes after full name: %d' % (len(self.raw) - (self.fullname_offset +
                self.fullname_length))

        ans += '\nRecord 0 length: %d'%len(self.raw)
        return ans
# }}}


class MOBIFile(object):

    def __init__(self, stream):
        self.raw = stream.read()
        self.palmdb = PalmDB(self.raw[:78])

        self.record_headers = []
        self.records = []
        for i in range(self.palmdb.number_of_records):
            pos = 78 + i * 8
            offset, a1, a2, a3, a4 = struct.unpack(b'>LBBBB', self.raw[pos:pos+8])
            flags, val = a1, a2 << 16 | a3 << 8 | a4
            self.record_headers.append((offset, flags, val))

        def section(section_number):
            if section_number == self.palmdb.number_of_records - 1:
                end_off = len(self.raw)
            else:
                end_off = self.record_headers[section_number + 1][0]
            off = self.record_headers[section_number][0]
            return self.raw[off:end_off]

        for i in range(self.palmdb.number_of_records):
            self.records.append(Record(section(i), self.record_headers[i]))

        self.mobi_header = MOBIHeader(self.records[0], 0)
        self.huffman_record_nums = []

        self.kf8_type = None
        mh = mh8 = self.mobi_header
        if mh.file_version >= 8:
            self.kf8_type = 'standalone'
        elif mh.has_exth and mh.exth.kf8_header_index is not None:
            kf8i = mh.exth.kf8_header_index
            try:
                rec = self.records[kf8i-1]
            except IndexError:
                pass
            else:
                if rec.raw == b'BOUNDARY':
                    self.kf8_type = 'joint'
                    mh8 = MOBIHeader(self.records[kf8i], kf8i)
        self.mobi8_header = mh8

        if 'huff' in self.mobi_header.compression.lower():
            from calibre.ebooks.mobi.huffcdic import HuffReader

            def huffit(off, cnt):
                huffman_record_nums = list(range(off, off+cnt))
                huffrecs = [self.records[r].raw for r in huffman_record_nums]
                huffs = HuffReader(huffrecs)
                return huffman_record_nums, huffs.unpack

            if self.kf8_type == 'joint':
                recs6, d6 = huffit(mh.huffman_record_offset,
                        mh.huffman_record_count)
                recs8, d8 = huffit(mh8.huffman_record_offset,
                        mh8.huffman_record_count)
                self.huffman_record_nums = recs6 + recs8
            else:
                self.huffman_record_nums, d6 = huffit(mh.huffman_record_offset,
                        mh.huffman_record_count)
                d8 = d6
        elif 'palmdoc' in self.mobi_header.compression.lower():
            from calibre.ebooks.compression.palmdoc import decompress_doc
            d8 = d6 = decompress_doc
        else:
            d8 = d6 = lambda x: x

        self.decompress6, self.decompress8 = d6, d8


class TextRecord(object):  # {{{

    def __init__(self, idx, record, extra_data_flags, decompress):
        self.trailing_data, self.raw = get_trailing_data(record.raw, extra_data_flags)
        raw_trailing_bytes = record.raw[len(self.raw):]
        self.raw = decompress(self.raw)

        if 0 in self.trailing_data:
            self.trailing_data['multibyte_overlap'] = self.trailing_data.pop(0)
        if 1 in self.trailing_data:
            self.trailing_data['indexing'] = self.trailing_data.pop(1)
        if 2 in self.trailing_data:
            self.trailing_data['uncrossable_breaks'] = self.trailing_data.pop(2)
        self.trailing_data['raw_bytes'] = raw_trailing_bytes

        for typ, val in iteritems(self.trailing_data):
            if isinstance(typ, numbers.Integral):
                print('Record %d has unknown trailing data of type: %d : %r'%
                        (idx, typ, val))

        self.idx = idx

    def dump(self, folder):
        name = '%06d'%self.idx
        with open(os.path.join(folder, name+'.txt'), 'wb') as f:
            f.write(self.raw)
        with open(os.path.join(folder, name+'.trailing_data'), 'wb') as f:
            for k, v in iteritems(self.trailing_data):
                raw = '%s : %r\n\n'%(k, v)
                f.write(raw.encode('utf-8'))

    def __len__(self):
        return len(self.raw)

# }}}
