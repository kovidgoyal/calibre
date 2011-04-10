# -*- coding: utf-8 -*-

#from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__   = 'GPL v3'
__copyright__ = '20011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import struct
import zlib

from calibre import CurrentDir
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.pdb.formatreader import FormatReader

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
    
    def __init__(self, data_header, raw):
        self.sizes = []
        self.attributes = []

        for i in xrange(data_header.paragraphs):
            adv = 4*i
            self.sizes.append(struct.unpack('>H', raw[8+adv:10+adv])[0])
            self.attributes.append(struct.unpack('>H', raw[10+adv:12+adv])[0])


class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log
        self.options = options
        
        self.sections = []
        for i in range(1, header.num_sections):
            start = 8
            raw_data = header.section_data(i)
            data_header = SectionHeader(raw_data)
            sub_header = None
            if data_header.type in (DATATYPE_PHTML, DATATYPE_PHTML_COMPRESSED):
                sub_header = SectionHeaderText(data_header, raw_data)
                start += data_header.paragraphs * 4
            self.sections.append((data_header, sub_header, raw_data[start:]))

        self.header_record = HeaderRecord(header.section_data(0))

        from calibre.ebooks.metadata.pdb import get_metadata
        self.mi = get_metadata(stream, False)

    def extract_content(self, output_dir):
        html = u''
        images = []
        
        for header, sub_header, data in self.sections:
            if header.type == DATATYPE_PHTML:
                html += data
            elif header.type == DATATYPE_PHTML_COMPRESSED:
                d = self.decompress_phtml(data).decode('latin-1', 'replace')
                print len(d) == header.size
                html += d
        
        print html
        with CurrentDir(output_dir):
            with open('index.html', 'wb') as index:
                self.log.debug('Writing text to index.html')
                index.write(html.encode('utf-8'))
        
        opf_path = self.create_opf(output_dir, images)

        return opf_path

    def decompress_phtml(self, data):
        if self.header_record.compression == 2:
            raise NotImplementedError
            #return zlib.decompress(data)
        elif self.header_record.compression == 1:
            from calibre.ebooks.compression.palmdoc import decompress_doc
            return decompress_doc(data)
            

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
