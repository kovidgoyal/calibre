#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct, datetime, sys, os
from collections import OrderedDict
from calibre.utils.date import utc_tz
from calibre.ebooks.mobi.langcodes import main_language, sub_language
from calibre.ebooks.mobi.writer2.utils import decode_hex_number, decint

# PalmDB {{{
class PalmDOCAttributes(object):

    class Attr(object):

        def __init__(self, name, field, val):
            self.name = name
            self.val = val & field

        def __str__(self):
            return '%s: %s'%(self.name, bool(self.val))

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
        attrs = '\n\t'.join([str(x) for x in self.attributes])
        return 'PalmDOC Attributes: %s\n\t%s'%(bin(self.val), attrs)

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
        self.uid_seed = self.raw[68:72]
        self.next_rec_list_id = self.raw[72:76]

        self.number_of_records, = struct.unpack(b'>H', self.raw[76:78])

    def __str__(self):
        ans = ['*'*20 + ' PalmDB Header '+ '*'*20]
        ans.append('Name: %r'%self.name)
        ans.append(str(self.attributes))
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
        ans.append('UID seed: %r'%self.uid_seed)
        ans.append('Next record list id: %r'%self.next_rec_list_id)
        ans.append('Number of records: %s'%self.number_of_records)

        return '\n'.join(ans)
# }}}

class Record(object): # {{{

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

    def __init__(self, type_, data):
        self.type = type_
        self.data = data
        self.name = {
                1 : 'DRM Server id',
                2 : 'DRM Commerce id',
                3 : 'DRM ebookbase book id',
                100 : 'author',
                101 : 'publisher',
                102 : 'imprint',
                103 : 'description',
                104 : 'isbn',
                105 : 'subject',
                106 : 'publishingdate',
                107 : 'review',
                108 : 'contributor',
                109 : 'rights',
                110 : 'subjectcode',
                111 : 'type',
                112 : 'source',
                113 : 'asin',
                114 : 'versionnumber',
                115 : 'sample',
                116 : 'startreading',
                117 : 'adult',
                118 : 'retailprice',
                119 : 'retailpricecurrency',
                201 : 'coveroffset',
                202 : 'thumboffset',
                203 : 'hasfakecover',
                204 : 'Creator Software',
                205 : 'Creator Major Version', # '>I'
                206 : 'Creator Minor Version', # '>I'
                207 : 'Creator Build Number', # '>I'
                208 : 'watermark',
                209 : 'tamper_proof_keys',
                300 : 'fontsignature',
                301 : 'clippinglimit', # percentage '>B'
                402 : 'publisherlimit',
                404 : 'TTS flag', # '>B' 1 - TTS disabled 0 - TTS enabled
                501 : 'cdetype', # 4 chars (PDOC or EBOK)
                502 : 'lastupdatetime',
                503 : 'updatedtitle',
        }.get(self.type, repr(self.type))

        if self.name in ('coveroffset', 'thumboffset', 'hasfakecover',
                'Creator Major Version', 'Creator Minor Version',
                'Creator Build Number', 'Creator Software', 'startreading'):
            self.data, = struct.unpack(b'>I', self.data)

    def __str__(self):
        return '%s (%d): %r'%(self.name, self.type, self.data)

class EXTHHeader(object):

    def __init__(self, raw):
        self.raw = raw
        if not self.raw.startswith(b'EXTH'):
            raise ValueError('EXTH header does not start with EXTH')
        self.length, = struct.unpack(b'>I', self.raw[4:8])
        self.count,  = struct.unpack(b'>I', self.raw[8:12])

        pos = 12
        self.records = []
        for i in xrange(self.count):
            pos = self.read_record(pos)

    def read_record(self, pos):
        type_, length = struct.unpack(b'>II', self.raw[pos:pos+8])
        data = self.raw[(pos+8):(pos+length)]
        self.records.append(EXTHRecord(type_, data))
        return pos + length

    def __str__(self):
        ans = ['*'*20 + ' EXTH Header '+ '*'*20]
        ans.append('EXTH header length: %d'%self.length)
        ans.append('Number of EXTH records: %d'%self.count)
        ans.append('EXTH records...')
        for r in self.records:
            ans.append(str(r))
        return '\n'.join(ans)
# }}}

class MOBIHeader(object): # {{{

    def __init__(self, record0):
        self.raw = record0.raw

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
        self.encryption_type = {0: 'No encryption',
                1: 'Old mobipocket encryption',
                2:'Mobipocket encryption'}.get(self.encryption_type_raw,
                repr(self.encryption_type_raw))
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
        self.file_version = struct.unpack(b'>I', self.raw[36:40])
        self.reserved = self.raw[40:48]
        self.secondary_index_record, = struct.unpack(b'>I', self.raw[48:52])
        self.reserved2 = self.raw[52:80]
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
        self.unknown2 = self.raw[120:128]
        self.exth_flags, = struct.unpack(b'>I', self.raw[128:132])
        self.has_exth = bool(self.exth_flags & 0x40)
        self.has_drm_data = self.length >= 174 and len(self.raw) >= 180
        if self.has_drm_data:
            self.unknown3 = self.raw[132:164]
            self.drm_offset, = struct.unpack(b'>I', self.raw[164:168])
            self.drm_count, = struct.unpack(b'>I', self.raw[168:172])
            self.drm_size, = struct.unpack(b'>I', self.raw[172:176])
            self.drm_flags = bin(struct.unpack(b'>I', self.raw[176:180])[0])
        self.has_extra_data_flags = self.length >= 232 and len(self.raw) >= 232+16
        self.has_fcis_flis = False
        self.has_multibytes = self.has_indexing_bytes = self.has_uncrossable_breaks = False
        if self.has_extra_data_flags:
            self.unknown4 = self.raw[180:192]
            self.first_content_record, self.last_content_record = \
                    struct.unpack(b'>HH', self.raw[192:196])
            self.unknown5, = struct.unpack(b'>I', self.raw[196:200])
            (self.fcis_number, self.fcis_count, self.flis_number,
                    self.flis_count) = struct.unpack(b'>IIII',
                            self.raw[200:216])
            self.unknown6 = self.raw[216:240]
            self.extra_data_flags = struct.unpack(b'>I',
                self.raw[240:244])[0]
            self.has_multibytes = bool(self.extra_data_flags & 0b1)
            self.has_indexing_bytes = bool(self.extra_data_flags & 0b10)
            self.has_uncrossable_breaks = bool(self.extra_data_flags & 0b100)
            self.primary_index_record, = struct.unpack(b'>I',
                    self.raw[244:248])

        if self.has_exth:
            self.exth_offset = 16 + self.length

            self.exth = EXTHHeader(self.raw[self.exth_offset:])

            self.end_of_exth = self.exth_offset + self.exth.length
            self.bytes_after_exth = self.fullname_offset - self.end_of_exth

    def __str__(self):
        ans = ['*'*20 + ' MOBI Header '+ '*'*20]
        ans.append('Compression: %s'%self.compression)
        ans.append('Unused: %r'%self.unused)
        ans.append('Number of text records: %d'%self.number_of_text_records)
        ans.append('Text record size: %d'%self.text_record_size)
        ans.append('Encryption: %s'%self.encryption_type)
        ans.append('Unknown: %r'%self.unknown)
        ans.append('Identifier: %r'%self.identifier)
        ans.append('Header length: %d'% self.length)
        ans.append('Type: %s'%self.type)
        ans.append('Encoding: %s'%self.encoding)
        ans.append('UID: %r'%self.uid)
        ans.append('File version: %d'%self.file_version)
        ans.append('Reserved: %r'%self.reserved)
        ans.append('Secondary index record: %d (null val: %d)'%(
            self.secondary_index_record, 0xffffffff))
        ans.append('Reserved2: %r'%self.reserved2)
        ans.append('First non-book record (null value: %d): %d'%(0xffffffff,
            self.first_non_book_record))
        ans.append('Full name offset: %d'%self.fullname_offset)
        ans.append('Full name length: %d bytes'%self.fullname_length)
        ans.append('Langcode: %r'%self.locale_raw)
        ans.append('Language: %s'%self.language)
        ans.append('Sub language: %s'%self.sublanguage)
        ans.append('Input language: %r'%self.input_language)
        ans.append('Output language: %r'%self.output_langauage)
        ans.append('Min version: %d'%self.min_version)
        ans.append('First Image index: %d'%self.first_image_index)
        ans.append('Huffman record offset: %d'%self.huffman_record_offset)
        ans.append('Huffman record count: %d'%self.huffman_record_count)
        ans.append('Unknown2: %r'%self.unknown2)
        ans.append('EXTH flags: %r (%s)'%(self.exth_flags, self.has_exth))
        if self.has_drm_data:
            ans.append('Unknown3: %r'%self.unknown3)
            ans.append('DRM Offset: %s'%self.drm_offset)
            ans.append('DRM Count: %s'%self.drm_count)
            ans.append('DRM Size: %s'%self.drm_size)
            ans.append('DRM Flags: %r'%self.drm_flags)
        if self.has_extra_data_flags:
            ans.append('Unknown4: %r'%self.unknown4)
            ans.append('First content record: %d'% self.first_content_record)
            ans.append('Last content record: %d'% self.last_content_record)
            ans.append('Unknown5: %d'% self.unknown5)
            ans.append('FCIS number: %d'% self.fcis_number)
            ans.append('FCIS count: %d'% self.fcis_count)
            ans.append('FLIS number: %d'% self.flis_number)
            ans.append('FLIS count: %d'% self.flis_count)
            ans.append('Unknown6: %r'% self.unknown6)
            ans.append(('Extra data flags: %s (has multibyte: %s) '
                '(has indexing: %s) (has uncrossable breaks: %s)')%(
                    bin(self.extra_data_flags), self.has_multibytes,
                    self.has_indexing_bytes, self.has_uncrossable_breaks ))
            ans.append('Primary index record (null value: %d): %d'%(0xffffffff,
                self.primary_index_record))

        ans = '\n'.join(ans)

        if self.has_exth:
            ans += '\n\n' + str(self.exth)
            ans += '\n\nBytes after EXTH: %d'%self.bytes_after_exth

        ans += '\nNumber of bytes after full name: %d' % (len(self.raw) - (self.fullname_offset +
                self.fullname_length))

        ans += '\nRecord 0 length: %d'%len(self.raw)
        return ans
# }}}

class TagX(object): # {{{

    def __init__(self, raw, control_byte_count):
        self.tag = ord(raw[0])
        self.num_values = ord(raw[1])
        self.bitmask = ord(raw[2])
        # End of file = 1 iff last entry
        # When it is 1 all others are 0
        self.eof = ord(raw[3])

        self.is_eof = (self.eof == 1 and self.tag == 0 and self.num_values == 0
                and self.bitmask == 0)

    def __repr__(self):
        return 'TAGX(tag=%02d, num_values=%d, bitmask=%r, eof=%d)' % (self.tag,
                self.num_values, bin(self.bitmask), self.eof)
    # }}}

class IndexHeader(object): # {{{

    def __init__(self, record):
        self.record = record
        raw = self.record.raw
        if raw[:4] != b'INDX':
            raise ValueError('Invalid Primary Index Record')

        self.header_length, = struct.unpack('>I', raw[4:8])
        self.unknown1 = raw[8:16]
        self.index_type, = struct.unpack('>I', raw[16:20])
        self.index_type_desc = {0: 'normal', 2:
                'inflection'}.get(self.index_type, 'unknown')
        self.idxt_start, = struct.unpack('>I', raw[20:24])
        self.index_count, = struct.unpack('>I', raw[24:28])
        self.index_encoding_num, = struct.unpack('>I', raw[28:32])
        self.index_encoding = {65001: 'utf-8', 1252:
                'cp1252'}.get(self.index_encoding_num, 'unknown')
        if self.index_encoding == 'unknown':
            raise ValueError(
                'Unknown index encoding: %d'%self.index_encoding_num)
        self.locale_raw, = struct.unpack(b'>I', raw[32:36])
        langcode = self.locale_raw
        langid    = langcode & 0xFF
        sublangid = (langcode >> 10) & 0xFF
        self.language = main_language.get(langid, 'ENGLISH')
        self.sublanguage = sub_language.get(sublangid, 'NEUTRAL')
        self.num_index_entries, = struct.unpack('>I', raw[36:40])
        self.ordt_start, = struct.unpack('>I', raw[40:44])
        self.ligt_start, = struct.unpack('>I', raw[44:48])
        self.num_of_ligt_entries, = struct.unpack('>I', raw[48:52])
        self.num_of_cncx_blocks, = struct.unpack('>I', raw[52:56])
        self.unknown2 = raw[56:180]
        self.tagx_offset, = struct.unpack(b'>I', raw[180:184])
        if self.tagx_offset != self.header_length:
            raise ValueError('TAGX offset and header length disagree')
        self.unknown3 = raw[184:self.header_length]

        tagx = raw[self.header_length:]
        if not tagx.startswith(b'TAGX'):
            raise ValueError('Invalid TAGX section')
        self.tagx_header_length, = struct.unpack('>I', tagx[4:8])
        self.tagx_control_byte_count, = struct.unpack('>I', tagx[8:12])
        tag_table = tagx[12:self.tagx_header_length]
        if len(tag_table) % 4 != 0:
            raise ValueError('Invalid Tag table')
        num_tagx_entries = len(tag_table) // 4
        self.tagx_entries = []
        for i in range(num_tagx_entries):
            self.tagx_entries.append(TagX(tag_table[i*4:(i+1)*4],
                self.tagx_control_byte_count))
        if self.tagx_entries and not self.tagx_entries[-1].is_eof:
            raise ValueError('TAGX last entry is not EOF')
        self.tagx_entries = self.tagx_entries[:-1]

        idxt0_pos = self.header_length+self.tagx_header_length
        last_num, consumed = decode_hex_number(raw[idxt0_pos:])
        count_pos = idxt0_pos + consumed
        self.ncx_count, = struct.unpack(b'>H', raw[count_pos:count_pos+2])

        if last_num != self.ncx_count - 1:
            raise ValueError('Last id number in the NCX != NCX count - 1')
        # There may be some alignment zero bytes between the end of the idxt0
        # and self.idxt_start

        idxt = raw[self.idxt_start:]
        if idxt[:4] != b'IDXT':
            raise ValueError('Invalid IDXT header')
        length_check, = struct.unpack(b'>H', idxt[4:6])
        if length_check != self.header_length + self.tagx_header_length:
            raise ValueError('Length check failed')

    def __str__(self):
        ans = ['*'*20 + ' Index Header '+ '*'*20]
        a = ans.append
        def u(w):
            a('Unknown: %r (%d bytes) (All zeros: %r)'%(w,
                len(w), not bool(w.replace(b'\0', b'')) ))

        a('Header length: %d'%self.header_length)
        u(self.unknown1)
        a('Index Type: %s (%d)'%(self.index_type_desc, self.index_type))
        a('Offset to IDXT start: %d'%self.idxt_start)
        a('Number of index records: %d'%self.index_count)
        a('Index encoding: %s (%d)'%(self.index_encoding,
                self.index_encoding_num))
        a('Index language: %s - %s (%s)'%(self.language, self.sublanguage,
            hex(self.locale_raw)))
        a('Number of index entries: %d'% self.num_index_entries)
        a('ORDT start: %d'%self.ordt_start)
        a('LIGT start: %d'%self.ligt_start)
        a('Number of LIGT entries: %d'%self.num_of_ligt_entries)
        a('Number of cncx blocks: %d'%self.num_of_cncx_blocks)
        u(self.unknown2)
        a('TAGX offset: %d'%self.tagx_offset)
        u(self.unknown3)
        a('\n\n')
        a('*'*20 + ' TAGX Header (%d bytes)'%self.tagx_header_length+ '*'*20)
        a('Header length: %d'%self.tagx_header_length)
        a('Control byte count: %d'%self.tagx_control_byte_count)
        for i in self.tagx_entries:
            a('\t' + repr(i))
        a('Number of entries in the NCX: %d'% self.ncx_count)

        return '\n'.join(ans)
    # }}}

class Tag(object): # {{{

    '''
    Index entries are a collection of tags. Each tag is represented by this
    class.
    '''

    TAG_MAP = {
            1: ('offset', 'Offset in HTML'),
            2: ('size', 'Size in HTML'),
            3: ('label_offset', 'Offset to label in CNCX'),
            4: ('depth', 'Depth of this entry in TOC'),

            # The remaining tag types have to be interpreted subject to the type
            # of index entry they are present in
    }

    INTERPRET_MAP = {
            'subchapter': {
                    5  : ('Parent chapter index', 'parent_index')
            },

            'article'   : {
                    5  : ('Class offset in cncx', 'class_offset'),
                    21 : ('Parent section index', 'parent_index'),
                    22 : ('Description offset in cncx', 'desc_offset'),
                    23 : ('Author offset in cncx', 'author_offset'),
            },

            'chapter_with_subchapters' : {
                    22 : ('First subchapter index', 'first_subchapter_index'),
                    23 : ('Last subchapter index', 'last_subchapter_index'),
            },

            'periodical' : {
                    5  : ('Class offset in cncx', 'class_offset'),
                    22 : ('First section index', 'first_section_index'),
                    23 : ('Last section index', 'last_section_index'),
            },

            'section' : {
                    5  : ('Class offset in cncx', 'class_offset'),
                    21 : ('Periodical index', 'periodical_index'),
                    22 : ('First article index', 'first_article_index'),
                    23 : ('Last article index', 'last_article_index'),
            },
    }


    def __init__(self, tagx, vals, entry_type, cncx):
        self.value = vals if len(vals) > 1 else vals[0]
        self.entry_type = entry_type
        self.cncx_value = None
        if tagx.tag in self.TAG_MAP:
            self.attr, self.desc = self.TAG_MAP[tagx.tag]
        else:
            try:
                td = self.INTERPRET_MAP[entry_type]
            except:
                raise ValueError('Unknown entry type: %s'%entry_type)
            try:
                self.desc, self.attr = td[tagx.tag]
            except:
                raise ValueError('Unknown tag: %d for entry type: %s'%(
                    tagx.tag, entry_type))
        if '_offset' in self.attr:
            self.cncx_value = cncx[self.value]

    def __str__(self):
        if self.cncx_value is not None:
            return '%s : %r [%r]'%(self.desc, self.value, self.cncx_value)
        return '%s : %r'%(self.desc, self.value)

# }}}

class IndexEntry(object): # {{{

    '''
    The index is made up of entries, each of which is represented by an
    instance of this class. Index entries typically point to offsets int eh
    HTML, specify HTML sizes and point to text strings in the CNCX that are
    used in the navigation UI.
    '''

    TYPES = {
            # Present in book type files
            0x0f : 'chapter',
            0x6f : 'chapter_with_subchapters',
            0x1f : 'subchapter',
            # Present in periodicals
            0xdf : 'periodical',
            0xff : 'section',
            0x3f : 'article',
    }

    def __init__(self, ident, entry_type, raw, cncx, tagx_entries):
        self.index = ident
        self.raw = raw
        self.tags = []

        try:
            self.entry_type = self.TYPES[entry_type]
        except KeyError:
            raise ValueError('Unknown Index Entry type: %s'%hex(entry_type))

        expected_tags = [tag for tag in tagx_entries if tag.bitmask &
                entry_type]

        for tag in expected_tags:
            vals = []
            for i in range(tag.num_values):
                if not raw:
                    raise ValueError('Index entry does not match TAGX header')
                val, consumed = decint(raw)
                raw = raw[consumed:]
                vals.append(val)
            self.tags.append(Tag(tag, vals, self.entry_type, cncx))

    def __str__(self):
        ans = ['Index Entry(index=%s, entry_type=%s, length=%d)'%(
            self.index, self.entry_type, len(self.tags))]
        for tag in self.tags:
            ans.append('\t'+str(tag))
        return '\n'.join(ans)

# }}}

class IndexRecord(object): # {{{

    '''
    Represents all indexing information in the MOBI, apart from indexing info
    in the trailing data of the text records.
    '''

    def __init__(self, record, index_header, cncx):
        self.record = record
        raw = self.record.raw
        if raw[:4] != b'INDX':
            raise ValueError('Invalid Primary Index Record')

        u = struct.unpack

        self.header_length, = u('>I', raw[4:8])
        self.unknown1 = raw[8:12]
        self.header_type, = u('>I', raw[12:16])
        self.unknown2 = raw[16:20]
        self.idxt_offset, self.idxt_count = u(b'>II', raw[20:28])
        if self.idxt_offset < 192:
            raise ValueError('Unknown Index record structure')
        self.unknown3 = raw[28:36]
        self.unknown4 = raw[36:192] # Should be 156 bytes

        self.index_offsets = []
        indices = raw[self.idxt_offset:]
        if indices[:4] != b'IDXT':
            raise ValueError("Invalid IDXT index table")
        indices = indices[4:]
        for i in range(self.idxt_count):
            off, = u(b'>H', indices[i*2:(i+1)*2])
            self.index_offsets.append(off-192)

        indxt = raw[192:self.idxt_offset]
        self.indices = []
        for i, off in enumerate(self.index_offsets):
            try:
                next_off = self.index_offsets[i+1]
            except:
                next_off = len(indxt)
            index, consumed = decode_hex_number(indxt[off:])
            entry_type = ord(indxt[off+consumed])
            self.indices.append(IndexEntry(index, entry_type,
                indxt[off+consumed+1:next_off], cncx, index_header.tagx_entries))


    def __str__(self):
        ans = ['*'*20 + ' Index Record (%d bytes) '%len(self.record.raw)+ '*'*20]
        a = ans.append
        def u(w):
            a('Unknown: %r (%d bytes) (All zeros: %r)'%(w,
                len(w), not bool(w.replace(b'\0', b'')) ))
        a('Header length: %d'%self.header_length)
        u(self.unknown1)
        a('Header Type: %d'%self.header_type)
        u(self.unknown2)
        a('IDXT Offset: %d'%self.idxt_offset)
        a('IDXT Count: %d'%self.idxt_count)
        u(self.unknown3)
        u(self.unknown4)
        a('Index offsets: %r'%self.index_offsets)
        a('\nIndex Entries:')
        for entry in self.indices:
            a(str(entry)+'\n')

        return '\n'.join(ans)

# }}}

class CNCX(object) : # {{{

    '''
    Parses the records that contain the compiled NCX (all strings from the
    NCX). Presents a simple offset : string mapping interface to access the
    data.
    '''

    def __init__(self, records, codec):
        self.records = OrderedDict()
        pos = 0
        for record in records:
            raw = record.raw
            while pos < len(raw):
                length, consumed = decint(raw[pos:])
                if length > 0:
                    self.records[pos] = raw[pos+consumed:pos+consumed+length].decode(
                        codec)
                pos += consumed+length

    def __getitem__(self, offset):
        return self.records.get(offset)

    def __str__(self):
        ans = ['*'*20 + ' cncx (%d strings) '%len(self.records)+ '*'*20]
        for k, v in self.records.iteritems():
            ans.append('%10d : %s'%(k, v))
        return '\n'.join(ans)


# }}}

class MOBIFile(object): # {{{

    def __init__(self, stream):
        self.raw = stream.read()

        self.palmdb = PalmDB(self.raw[:78])

        self.record_headers = []
        self.records = []
        for i in xrange(self.palmdb.number_of_records):
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

        self.mobi_header = MOBIHeader(self.records[0])

        self.index_header = None
        pir = self.mobi_header.primary_index_record
        if pir != 0xffffffff:
            self.index_header = IndexHeader(self.records[pir])
            self.cncx = CNCX(self.records[
                pir+2:pir+2+self.index_header.num_of_cncx_blocks],
                self.index_header.index_encoding)
            self.index_record = IndexRecord(self.records[pir+1],
                    self.index_header, self.cncx)


    def print_header(self, f=sys.stdout):
        print (str(self.palmdb).encode('utf-8'), file=f)
        print (file=f)
        print ('Record headers:', file=f)
        for i, r in enumerate(self.records):
            print ('%6d. %s'%(i, r.header), file=f)

        print (file=f)
        print (str(self.mobi_header).encode('utf-8'), file=f)
# }}}

def inspect_mobi(path_or_stream):
    stream = (path_or_stream if hasattr(path_or_stream, 'read') else
            open(path_or_stream, 'rb'))
    f = MOBIFile(stream)
    ddir = 'debug_' + os.path.splitext(os.path.basename(stream.name))[0]
    if not os.path.exists(ddir):
        os.mkdir(ddir)
    with open(os.path.join(ddir, 'header.txt'), 'wb') as out:
        f.print_header(f=out)
    if f.index_header is not None:
        with open(os.path.join(ddir, 'index.txt'), 'wb') as out:
            print(str(f.index_header), file=out)
            print('\n\n', file=out)
            print(str(f.cncx).encode('utf-8'), file=out)
            print('\n\n', file=out)
            print(str(f.index_record), file=out)

    print ('Debug data saved to:', ddir)

def main():
    inspect_mobi(sys.argv[1])

if __name__ == '__main__':
    main()

