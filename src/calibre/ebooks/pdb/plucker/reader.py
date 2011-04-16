# -*- coding: utf-8 -*-

#from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__   = 'GPL v3'
__copyright__ = '20011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import struct
import zlib

from collections import OrderedDict

from calibre import CurrentDir
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ptempfile import TemporaryFile
from calibre.utils.magick import Image

DATATYPE_PHTML = 0
DATATYPE_PHTML_COMPRESSED = 1
DATATYPE_TBMP = 2
DATATYPE_TBMP_COMPRESSED = 3
DATATYPE_MAILTO = 4
DATATYPE_LINK_INDEX = 5
DATATYPE_LINKS = 6
DATATYPE_LINKS_COMPRESSED = 7
DATATYPE_BOOKMARKS = 8
DATATYPE_CATEGORY = 9
DATATYPE_METADATA = 10
DATATYPE_STYLE_SHEET = 11
DATATYPE_FONT_PAGE = 12
DATATYPE_TABLE = 13
DATATYPE_TABLE_COMPRESSED = 14
DATATYPE_COMPOSITE_IMAGE = 15
DATATYPE_PAGELIST_METADATA = 16
DATATYPE_SORTED_URL_INDEX = 17
DATATYPE_SORTED_URL = 18
DATATYPE_SORTED_URL_COMPRESSED = 19
DATATYPE_EXT_ANCHOR_INDEX = 20
DATATYPE_EXT_ANCHOR = 21
DATATYPE_EXT_ANCHOR_COMPRESSED = 22

# IETF IANA MIBenum value for the character set.
# See the http://www.iana.org/assignments/character-sets for valid values.
# Not all character sets are handled by Python. This is a small subset that
# the MIBenum maps to Python standard encodings
# from http://docs.python.org/library/codecs.html#standard-encodings
MIBNUM_TO_NAME = {
    3: 'ascii',
    4: 'latin_1',
    5: 'iso8859_2',
    6: 'iso8859_3',
    7: 'iso8859_4',
    8: 'iso8859_5',
    9: 'iso8859_6',
    10: 'iso8859_7',
    11: 'iso8859_8',
    12: 'iso8859_9',
    13: 'iso8859_10',
    17: 'shift_jis',
    18: 'euc_jp',
    27: 'utf_7',
    36: 'euc_kr',
    37: 'iso2022_kr',
    38: 'euc_kr',
    39: 'iso2022_jp',
    40: 'iso2022_jp_2',
    106: 'utf-8',
    109: 'iso8859_13',
    110: 'iso8859_14',
    111: 'iso8859_15',
    112: 'iso8859_16',
    1013: 'utf_16_be',
    1014: 'utf_16_le',
    1015: 'utf_16',
    2009: 'cp850',
    2010: 'cp852',
    2011: 'cp437',
    2013: 'cp862',
    2025: 'gb2312',
    2026: 'big5',
    2028: 'cp037',
    2043: 'cp424',
    2044: 'cp500',
    2046: 'cp855',
    2047: 'cp857',
    2048: 'cp860',
    2049: 'cp861',
    2050: 'cp863',
    2051: 'cp864',
    2052: 'cp865',
    2054: 'cp869',
    2063: 'cp1026',
    2085: 'hz',
    2086: 'cp866',
    2087: 'cp775',
    2089: 'cp858',
    2091: 'cp1140',
    2102: 'big5hkscs',
    2250: 'cp1250',
    2251: 'cp1251',
    2252: 'cp1252',
    2253: 'cp1253',
    2254: 'cp1254',
    2255: 'cp1255',
    2256: 'cp1256',
    2257: 'cp1257',
    2258: 'cp1258',    
}

def decompress_doc(data):
    buffer = [ord(i) for i in data]
    res = []
    i = 0
    while i < len(buffer):
        c = buffer[i]
        i += 1
        if c >= 1 and c <= 8:
            res.extend(buffer[i:i+c])
            i += c
        elif c <= 0x7f:
            res.append(c)
        elif c >= 0xc0:
            res.extend( (ord(' '), c^0x80) )
        else:
            c = (c << 8) + buffer[i]
            i += 1
            di = (c & 0x3fff) >> 3
            j = len(res)
            num = (c & ((1 << 3) - 1)) + 3

            for k in range( num ):
                res.append(res[j - di+k])

    return ''.join([chr(i) for i in res])

class HeaderRecord(object):

    def __init__(self, raw):
        self.uid, = struct.unpack('>H', raw[0:2])
        # This is labled version in the spec.
        # 2 is ZLIB compressed,
        # 1 is DOC compressed
        self.compression, = struct.unpack('>H', raw[2:4])
        self.records, = struct.unpack('>H', raw[4:6])
        
        self.reserved = {}
        for i in xrange(self.records):
            adv = 4*i
            name, = struct.unpack('>H', raw[6+adv:8+adv])
            id, = struct.unpack('>H', raw[8+adv:10+adv])
            self.reserved[id] = name


class SectionHeader(object):
    
    def __init__(self, raw):
        self.uid, = struct.unpack('>H', raw[0:2])
        self.paragraphs, = struct.unpack('>H', raw[2:4])
        self.size, = struct.unpack('>H', raw[4:6])
        self.type, = struct.unpack('>B', raw[6])
        self.flags, = struct.unpack('>B', raw[7])


class SectionHeaderText(object):
    
    def __init__(self, section_header, raw):
        self.sizes = []
        self.attributes = []

        for i in xrange(section_header.paragraphs):
            adv = 4*i
            self.sizes.append(struct.unpack('>H', raw[adv:2+adv])[0])
            self.attributes.append(struct.unpack('>H', raw[2+adv:4+adv])[0])

class SectionMetadata(object):
    
    def __init__(self, raw):
        self.default_encoding = 'utf-8'
        self.exceptional_uid_encodings = {}
        self.owner_id = None
        
        record_count, = struct.unpack('>H', raw[0:2])
        
        adv = 0
        for i in xrange(record_count):
            type, = struct.unpack('>H', raw[2+adv:4+adv])
            length, = struct.unpack('>H', raw[4+adv:6+adv])
            
            # CharSet
            if type == 1:
                val, = struct.unpack('>H', raw[6+adv:8+adv])
                self.default_encoding = MIBNUM_TO_NAME.get(val, 'utf-8')
            # ExceptionalCharSets
            elif type == 2:
                ii_adv = 0
                for ii in xrange(length / 2):
                    uid, = struct.unpack('>H', raw[6+adv+ii_adv:8+adv+ii_adv])
                    mib, = struct.unpack('>H', raw[8+adv+ii_adv:10+adv+ii_adv])
                    self.exceptional_uid_encodings[uid] = MIBNUM_TO_NAME.get(mib, 'utf-8')
                    ii_adv += 4
            # OwnerID
            elif type == 3:
                self.owner_id = struct.unpack('>I', raw[6+adv:10+adv])
            # Author, Title, PubDate
            # Ignored here. The metadata reader plugin
            # will get this info because if it's missing
            # the metadata reader plugin will use fall
            # back data from elsewhere in the file.
            elif type in (4, 5, 6):
                pass
            # Linked Documents
            elif type == 7:
                pass
             
            adv += 2*length

class SectionText(object):
    
    def __init__(self, section_header, raw):
        self.header = SectionHeaderText(section_header, raw)
        self.data = raw[section_header.paragraphs * 4:]


class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log
        self.options = options

        # Mapping of section uid to our internal
        # list of sections.
        self.uid_section_number = OrderedDict()
        self.uid_text_secion_number = OrderedDict()
        self.uid_text_secion_encoding = {}
        self.uid_image_section_number = {}
        self.metadata_section_number = None
        self.default_encoding = 'utf-8'
        self.owner_id = None
        self.sections = []
        
        self.header_record = HeaderRecord(header.section_data(0))
        
        for i in range(1, header.num_sections):
            section_number = i - 1
            start = 8
            section = None
            
            raw_data = header.section_data(i)
            section_header = SectionHeader(raw_data)
            
            self.uid_section_number[section_header.uid] = section_number
            
            if section_header.type in (DATATYPE_PHTML, DATATYPE_PHTML_COMPRESSED):
                self.uid_text_secion_number[section_header.uid] = section_number
                section = SectionText(section_header, raw_data[start:])
            elif section_header.type in (DATATYPE_TBMP, DATATYPE_TBMP_COMPRESSED):
                self.uid_image_section_number[section_header.uid] = section_number
                section = raw_data[start:]
            elif section_header.type == DATATYPE_METADATA:
                self.metadata_section_number = section_number
                section = SectionMetadata(raw_data[start:])
            #elif section_header.type == DATATYPE_COMPOSITE_IMAGE:
                

            self.sections.append((section_header, section))

        if self.metadata_section_number:
            mdata_section = self.sections[self.metadata_section_number][1]
            for k, v in mdata_section.exceptional_uid_encodings.items():
                self.uid_text_secion_encoding[k] = v
            self.default_encoding = mdata_section.default_encoding
            self.owner_id = mdata_section.owner_id

        from calibre.ebooks.metadata.pdb import get_metadata
        self.mi = get_metadata(stream, False)

    def extract_content(self, output_dir):
        html = u'<html><body>'
        images = []

        for uid, num in self.uid_text_secion_number.items():
            section_header, section_data = self.sections[num]
            if section_header.type == DATATYPE_PHTML:
                html += self.process_phtml(section_data.header, section_data.data)
            elif section_header.type == DATATYPE_PHTML_COMPRESSED:
                d = self.decompress_phtml(section_data.data)
                html += self.process_phtml(section_header.uid, section_data.header, d).decode(self.get_text_uid_encoding(section_header.uid), 'replace')

        html += '</body></html>'

        with CurrentDir(output_dir):
            with open('index.html', 'wb') as index:
                self.log.debug('Writing text to index.html')
                index.write(html.encode('utf-8'))

        if not os.path.exists(os.path.join(output_dir, 'images/')):
            os.makedirs(os.path.join(output_dir, 'images/'))
        with CurrentDir(os.path.join(output_dir, 'images/')):
            for uid, num in self.uid_image_section_number.items():
                section_header, section_data = self.sections[num]
                if section_data:
                    idata = None
                    if section_header.type == DATATYPE_TBMP:
                        idata = section_data
                    elif section_header.type == DATATYPE_TBMP_COMPRESSED:
                        if self.header_record.compression == 1:
                            idata = decompress_doc(section_data)
                        elif self.header_record.compression == 2:
                            idata = zlib.decompress(section_data)
                    try:
                        with TemporaryFile(suffix='.palm') as itn:
                            with open(itn, 'wb') as itf: 
                                itf.write(idata)
                            im = Image()
                            im.read(itn)
                            im.set_compression_quality(70)
                            im.save('%s.jpg' % uid)
                            self.log.debug('Wrote image with uid %s to images/%s.jpg' % (uid, uid))
                    except Exception as e:
                        self.log.error('Failed to write image with uid %s: %s' % (uid, e))
                    images.append('%s.jpg' % uid)
                else:
                    self.log.error('Failed to write image with uid %s: No data.' % uid)

        opf_path = self.create_opf(output_dir, images)

        return opf_path

    def decompress_phtml(self, data):
        if self.header_record.compression == 2:
            if self.owner_id:
                raise NotImplementedError
            return zlib.decompress(data)
        elif self.header_record.compression == 1:
            #from calibre.ebooks.compression.palmdoc import decompress_doc
            return decompress_doc(data)
            
    def process_phtml(self, uid, sub_header, d):
        html = u'<a id="p%s" /><p id="p%s-0">' % (uid, uid)
        offset = 0
        paragraph_open = True
        need_set_p_id = False
        p_num = 1
        paragraph_offsets = []
        running_offset = 0
        for size in sub_header.sizes:
            running_offset += size
            paragraph_offsets.append(running_offset)
        
        while offset < len(d):
            if not paragraph_open:
                if need_set_p_id:
                    html += u'<p id="p%s-%s">' % (uid, p_num)
                    p_num += 1
                    need_set_p_id = False
                else:
                    html += u'<p>'
                paragraph_open = True

            c = ord(d[offset])
            if c == 0x0:
                offset += 1
                c = ord(d[offset])
                # Page link begins
                # 2 Bytes
                # record ID
                if c == 0x0a:
                    offset += 1
                    id = struct.unpack('>H', d[offset:offset+2])[0]
                    html += '<a href="#p%s">' % id
                    offset += 1
                # Targeted page link begins
                # 3 Bytes
                # record ID, target
                elif c == 0x0b:
                    offset += 3
                    html += '<a>'
                # Paragraph link begins
                # 4 Bytes
                # record ID, paragraph number
                elif c == 0x0c:
                    offset += 1
                    id = struct.unpack('>H', d[offset:offset+2])[0]
                    offset += 2
                    pid = struct.unpack('>H', d[offset:offset+2])[0]
                    html += '<a href="#p%s-%s">' % (id, pid)
                    offset += 1
                # Targeted paragraph link begins
                # 5 Bytes
                # record ID, paragraph number, target
                elif c == 0x0d:
                    offset += 5
                    html += '<a>'
                # Link ends
                # 0 Bytes
                elif c == 0x08:
                    html += '</a>'
                # Set font
                # 1 Bytes
                # font specifier
                elif c == 0x11:
                    offset += 1
                # Embedded image
                # 2 Bytes
                # image record ID
                elif c == 0x1a:
                    offset += 1
                    uid = struct.unpack('>H', d[offset:offset+2])[0]
                    html += '<img src="images/%s.jpg" />' % uid
                    offset += 1
                # Set margin
                # 2 Bytes
                # left margin, right margin
                elif c == 0x22:
                    offset += 2
                # Alignment of text
                # 1 Bytes
                # alignment
                elif c == 0x29:
                    offset += 1
                # Horizontal rule
                # 3 Bytes
                # 8-bit height, 8-bit width (pixels), 8-bit width (%, 1-100)
                elif c == 0x33:
                    offset += 3
                    if paragraph_open:
                        html += u'</p>'
                        paragraph_open = False
                    html += u'<hr />'
                # New line
                # 0 Bytes
                elif c == 0x38:
                    if paragraph_open:
                        html += u'</p>\n'
                        paragraph_open = False
                # Italic text begins
                # 0 Bytes
                elif c == 0x40:
                    html += u'<i>'
                # Italic text ends
                # 0 Bytes
                elif c == 0x48:
                    html += u'</i>'
                # Set text color
                # 3 Bytes
                # 8-bit red, 8-bit green, 8-bit blue
                elif c == 0x53:
                    offset += 3
                # Multiple embedded image
                # 4 Bytes
                # alternate image record ID, image record ID
                elif c == 0x5c:
                    offset += 4
                # Underline text begins
                # 0 Bytes
                elif c == 0x60:
                    html += u'<u>'
                # Underline text ends
                # 0 Bytes
                elif c == 0x68:
                    html += u'</u>'
                # Strike-through text begins
                # 0 Bytes
                elif c == 0x70:
                    html += u'<s>'
                # Strike-through text ends
                # 0 Bytes
                elif c == 0x78:
                    html += u'</s>'
                # 16-bit Unicode character
                # 3 Bytes
                # alternate text length, 16-bit unicode character
                elif c == 0x83:
                    #offset += 2
                    #c16 = d[offset:offset+2]
                    #html += c16.decode('utf-16')
                    #offset += 1
                    offset += 3
                # 32-bit Unicode character
                # 5 Bytes
                # alternate text length, 32-bit unicode character
                elif c == 0x85:
                    #offset += 2
                    #c32 = d[offset:offset+4]
                    #html += c32.decode('utf-32')
                    #offset += 3
                    offset += 5
                # Begin custom font span
                # 6 Bytes
                # font page record ID, X page position, Y page position
                elif c == 0x8e:
                    offset += 6
                # Adjust custom font glyph position
                # 4 Bytes
                # X page position, Y page position
                elif c == 0x8c:
                    offset += 4
                # Change font page
                # 2 Bytes
                # font record ID
                elif c == 0x8a:
                    offset += 2
                # End custom font span
                # 0 Bytes
                elif c == 0x88:
                    pass
                # Begin new table row
                # 0 Bytes
                elif c == 0x90:
                    pass
                # Insert table (or table link)
                # 2 Bytes
                # table record ID
                elif c == 0x92:
                    offset += 2
                # Table cell data
                # 7 Bytes
                # 8-bit alignment, 16-bit image record ID, 8-bit columns, 8-bit rows, 16-bit text length
                elif c == 0x97:
                    offset += 7
                # Exact link modifier
                # 2 Bytes
                # Paragraph Offset (The Exact Link Modifier modifies a Paragraph Link or Targeted Paragraph Link function to specify an exact byte offset within the paragraph. This function must be followed immediately by the function it modifies).
                elif c == 0x9a:
                    offset += 2
            else:
                html += unichr(c)
            offset += 1
            if offset in paragraph_offsets:
                need_set_p_id = True
                if paragraph_open:
                    html += u'</p>\n'
                    paragraph_open = False

        if paragraph_open:
            html += u'</p>'
        
        return html

    def get_text_uid_encoding(self, uid):
        return self.uid_text_secion_encoding.get(uid, self.default_encoding)

    def create_opf(self, output_dir, images):
        with CurrentDir(output_dir):
            opf = OPFCreator(output_dir, self.mi)

            manifest = [('index.html', None)]

            for i in images:
                manifest.append((os.path.join('images/', i), None))

            opf.create_manifest(manifest)
            opf.create_spine(['index.html'])
            with open('metadata.opf', 'wb') as opffile:
                opf.render(opffile)

        return os.path.join(output_dir, 'metadata.opf')
