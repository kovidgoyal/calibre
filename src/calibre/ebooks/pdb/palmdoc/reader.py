# -*- coding: utf-8 -*-

'''
Read content from palmdoc pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import struct

from calibre.ebooks.compression.palmdoc import decompress_doc
from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.txt.processor import convert_basic, opf_writer, \
    separate_paragraphs_single_line

class HeaderRecord(object):
    '''
    The first record in the file is always the header record. It holds
    information related to the location of text, images, and so on
    in the file. This is used in conjunction with the sections
    defined in the file header.
    '''

    def __init__(self, raw):
        self.compression, = struct.unpack('>H', raw[0:2])
        self.num_records, = struct.unpack('>H', raw[8:10])


class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log
        self.encoding = options.input_encoding
        self.single_line_paras = options.single_line_paras
        self.print_formatted_paras = options.print_formatted_paras

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        self.header_record = HeaderRecord(self.section_data(0))

    def section_data(self, number):
        return self.sections[number]

    def decompress_text(self, number):
        if self.header_record.compression == 1:
            return self.section_data(number).decode('cp1252' if self.encoding is None else self.encoding)
        if self.header_record.compression == 2:
            return decompress_doc(self.section_data(number)).decode('cp1252' if self.encoding is None else self.encoding, 'replace')
        return ''

    def extract_content(self, output_dir):
        txt = ''

        self.log.info('Decompressing text...')
        for i in range(1, self.header_record.num_records + 1):
            self.log.debug('\tDecompressing text section %i' % i)
            txt += self.decompress_text(i)

        self.log.info('Converting text to OEB...')
        if self.single_line_paras:
            txt = separate_paragraphs_single_line(txt)
        if self.print_formatted_paras:
            txt = separate_paragraphs_print_formatted(txt)
        html = convert_basic(txt)
        with open(os.path.join(output_dir, 'index.html'), 'wb') as index:
            index.write(html.encode('utf-8'))

        from calibre.ebooks.metadata.meta import get_metadata
        mi = get_metadata(self.stream, 'pdb')
        manifest = [('index.html', None)]
        spine = ['index.html']
        opf_writer(output_dir, 'metadata.opf', manifest, spine, mi)

        return os.path.join(output_dir, 'metadata.opf')

