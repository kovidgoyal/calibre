#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (absolute_import, print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct, re, os

from calibre import replace_entities
from calibre.utils.date import parse_date
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.metadata import MetaInformation, check_isbn
from calibre.ebooks.mobi.langcodes import main_language, sub_language, mobi2iana
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars
from calibre.utils.localization import canonicalize_lang

NULL_INDEX = 0xffffffff

class EXTHHeader(object):  # {{{

    def __init__(self, raw, codec, title):
        self.doctype = raw[:4]
        self.length, self.num_items = struct.unpack('>LL', raw[4:12])
        raw = raw[12:]
        pos = 0
        self.mi = MetaInformation(_('Unknown'), [_('Unknown')])
        self.has_fake_cover = True
        self.start_offset = None
        left = self.num_items
        self.kf8_header = None
        self.uuid = self.cdetype = None

        self.decode = lambda x : clean_ascii_chars(x.decode(codec, 'replace'))

        while left > 0:
            left -= 1
            idx, size = struct.unpack('>LL', raw[pos:pos + 8])
            content = raw[pos + 8:pos + size]
            pos += size
            if idx >= 100 and idx < 200:
                self.process_metadata(idx, content, codec)
            elif idx == 203:
                self.has_fake_cover = bool(struct.unpack('>L', content)[0])
            elif idx == 201:
                co, = struct.unpack('>L', content)
                if co < NULL_INDEX:
                    self.cover_offset = co
            elif idx == 202:
                self.thumbnail_offset, = struct.unpack('>L', content)
            elif idx == 501:
                try:
                    self.cdetype = content.decode('ascii')
                except UnicodeDecodeError:
                    self.cdetype = None
                # cdetype
                if content == b'EBSP':
                    if not self.mi.tags:
                        self.mi.tags = []
                    self.mi.tags.append(_('Sample Book'))
            elif idx == 502:
                # last update time
                pass
            elif idx == 503:  # Long title
                # Amazon seems to regard this as the definitive book title
                # rather than the title from the PDB header. In fact when
                # sending MOBI files through Amazon's email service if the
                # title contains non ASCII chars or non filename safe chars
                # they are messed up in the PDB header
                try:
                    title = self.decode(content)
                except:
                    pass
            elif idx == 524:  # Lang code
                try:
                    lang = content.decode(codec)
                    lang = canonicalize_lang(lang)
                    if lang:
                        self.mi.language = lang
                except:
                    pass
            #else:
            #    print 'unknown record', idx, repr(content)
        if title:
            self.mi.title = replace_entities(clean_xml_chars(clean_ascii_chars(title)))

    def process_metadata(self, idx, content, codec):
        if idx == 100:
            if self.mi.is_null('authors'):
                self.mi.authors = []
            au = clean_xml_chars(self.decode(content).strip())
            self.mi.authors.append(au)
            if self.mi.is_null('author_sort') and re.match(r'\S+?\s*,\s+\S+', au.strip()):
                self.mi.author_sort = au.strip()
        elif idx == 101:
            self.mi.publisher = clean_xml_chars(self.decode(content).strip())
            if self.mi.publisher in {'Unknown', _('Unknown')}:
                self.mi.publisher = None
        elif idx == 103:
            self.mi.comments  = clean_xml_chars(self.decode(content).strip())
        elif idx == 104:
            raw = check_isbn(self.decode(content).strip().replace('-', ''))
            if raw:
                self.mi.isbn = raw
        elif idx == 105:
            if not self.mi.tags:
                self.mi.tags = []
            self.mi.tags.extend([x.strip() for x in clean_xml_chars(self.decode(content)).split(';')])
            self.mi.tags = list(set(self.mi.tags))
        elif idx == 106:
            try:
                self.mi.pubdate = parse_date(content, as_utc=False)
            except:
                pass
        elif idx == 108:
            self.mi.book_producer = clean_xml_chars(self.decode(content).strip())
        elif idx == 112:  # dc:source set in some EBSP amazon samples
            try:
                content = content.decode(codec).strip()
                isig = 'urn:isbn:'
                if content.lower().startswith(isig):
                    raw = check_isbn(content[len(isig):])
                    if raw and not self.mi.isbn:
                        self.mi.isbn = raw
                elif content.startswith('calibre:'):
                    # calibre book uuid is stored here by recent calibre
                    # releases
                    cid = content[len('calibre:'):]
                    if cid:
                        self.mi.application_id = self.mi.uuid = cid
            except:
                pass
        elif idx == 113:  # ASIN or other id
            try:
                self.uuid = content.decode('ascii')
                self.mi.set_identifier('mobi-asin', self.uuid)
            except:
                self.uuid = None
        elif idx == 116:
            self.start_offset, = struct.unpack(b'>L', content)
        elif idx == 121:
            self.kf8_header, = struct.unpack(b'>L', content)
            if self.kf8_header == NULL_INDEX:
                self.kf8_header = None
        #else:
        #    print 'unhandled metadata record', idx, repr(content)
# }}}

class BookHeader(object):

    def __init__(self, raw, ident, user_encoding, log, try_extra_data_fix=False):
        self.log = log
        self.compression_type = raw[:2]
        self.records, self.records_size = struct.unpack('>HH', raw[8:12])
        self.encryption_type, = struct.unpack('>H', raw[12:14])
        if ident == 'TEXTREAD':
            self.codepage = 1252
        if len(raw) <= 16:
            self.codec = 'cp1252'
            self.extra_flags = 0
            self.title = _('Unknown')
            self.language = 'ENGLISH'
            self.sublanguage = 'NEUTRAL'
            self.exth_flag, self.exth = 0, None
            self.ancient = True
            self.first_image_index = -1
            self.mobi_version = 1
        else:
            self.ancient = False
            self.doctype = raw[16:20]
            self.length, self.type, self.codepage, self.unique_id, \
                self.version = struct.unpack('>LLLLL', raw[20:40])

            try:
                self.codec = {
                    1252: 'cp1252',
                    65001: 'utf-8',
                    }[self.codepage]
            except (IndexError, KeyError):
                self.codec = 'cp1252' if not user_encoding else user_encoding
                log.warn('Unknown codepage %d. Assuming %s' % (self.codepage,
                    self.codec))
            # Some KF8 files have header length == 256 (generated by kindlegen
            # 2.7?). See https://bugs.launchpad.net/bugs/1067310
            max_header_length = 0x100

            if (ident == 'TEXTREAD' or self.length < 0xE4 or
                    self.length > max_header_length or
                    (try_extra_data_fix and self.length == 0xE4)):
                self.extra_flags = 0
            else:
                self.extra_flags, = struct.unpack('>H', raw[0xF2:0xF4])

            if self.compression_type == 'DH':
                self.huff_offset, self.huff_number = struct.unpack('>LL',
                        raw[0x70:0x78])

            toff, tlen = struct.unpack('>II', raw[0x54:0x5c])
            tend = toff + tlen
            self.title = raw[toff:tend] if tend < len(raw) else _('Unknown')
            langcode  = struct.unpack('!L', raw[0x5C:0x60])[0]
            langid    = langcode & 0xFF
            sublangid = (langcode >> 10) & 0xFF
            self.language = main_language.get(langid, 'ENGLISH')
            self.sublanguage = sub_language.get(sublangid, 'NEUTRAL')
            self.mobi_version = struct.unpack('>I', raw[0x68:0x6c])[0]
            self.first_image_index = struct.unpack('>L', raw[0x6c:0x6c + 4])[0]

            self.exth_flag, = struct.unpack('>L', raw[0x80:0x84])
            self.exth = None
            if not isinstance(self.title, unicode):
                self.title = self.title.decode(self.codec, 'replace')
            if self.exth_flag & 0x40:
                try:
                    self.exth = EXTHHeader(raw[16 + self.length:], self.codec,
                            self.title)
                    self.exth.mi.uid = self.unique_id
                    if self.exth.mi.is_null('language'):
                        try:
                            self.exth.mi.language = mobi2iana(langid, sublangid)
                        except:
                            self.log.exception('Unknown language code')
                except:
                    self.log.exception('Invalid EXTH header')
                    self.exth_flag = 0

            self.ncxidx = NULL_INDEX
            if len(raw) >= 0xF8:
                self.ncxidx, = struct.unpack_from(b'>L', raw, 0xF4)

            # Ancient PRC files from Baen can have random values for
            # mobi_version, so be conservative
            if self.mobi_version == 8 and len(raw) >= (0xF8 + 16):
                self.dividx, self.skelidx, self.datpidx, self.othidx = \
                        struct.unpack_from(b'>4L', raw, 0xF8)

                # need to use the FDST record to find out how to properly
                # unpack the raw_ml into pieces it is simply a table of start
                # and end locations for each flow piece
                self.fdstidx, self.fdstcnt = struct.unpack_from(b'>2L', raw, 0xC0)
                # if cnt is 1 or less, fdst section number can be garbage
                if self.fdstcnt <= 1:
                    self.fdstidx = NULL_INDEX
            else:  # Null values
                self.skelidx = self.dividx = self.othidx = self.fdstidx = \
                        NULL_INDEX

class MetadataHeader(BookHeader):

    def __init__(self, stream, log):
        self.stream = stream
        self.ident = self.identity()
        self.num_sections = self.section_count()
        if self.num_sections >= 2:
            header = self.header()
            BookHeader.__init__(self, header, self.ident, None, log)
        else:
            self.exth = None

    @property
    def kf8_type(self):
        if (self.mobi_version == 8 and getattr(self, 'skelidx', NULL_INDEX) !=
                NULL_INDEX):
            return u'standalone'

        kf8_header_index = getattr(self.exth, 'kf8_header', None)
        if kf8_header_index is None:
            return None
        try:
            if self.section_data(kf8_header_index-1) == b'BOUNDARY':
                return u'joint'
        except:
            pass
        return None

    def identity(self):
        self.stream.seek(60)
        ident = self.stream.read(8).upper()
        if ident not in ['BOOKMOBI', 'TEXTREAD']:
            raise MobiError('Unknown book type: %s' % ident)
        return ident

    def section_count(self):
        self.stream.seek(76)
        return struct.unpack('>H', self.stream.read(2))[0]

    def section_offset(self, number):
        self.stream.seek(78 + number * 8)
        return struct.unpack('>LBBBB', self.stream.read(8))[0]

    def header(self):
        section_headers = []
        # First section with the metadata
        section_headers.append(self.section_offset(0))
        # Second section used to get the length of the first
        section_headers.append(self.section_offset(1))

        end_off = section_headers[1]
        off = section_headers[0]
        self.stream.seek(off)
        return self.stream.read(end_off - off)

    def section_data(self, number):
        start = self.section_offset(number)
        if number == self.num_sections -1:
            end = os.stat(self.stream.name).st_size
        else:
            end = self.section_offset(number + 1)
        self.stream.seek(start)
        try:
            return self.stream.read(end - start)
        except OverflowError:
            self.stream.seek(start)
            return self.stream.read()

