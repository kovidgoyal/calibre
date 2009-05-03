# -*- coding: utf-8 -*-

'''
Read content from ztxt pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import StringIO, os, struct, zlib

from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.pdb.ztxt import zTXTError
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.txt.processor import txt_to_markdown, opf_writer

class HeaderRecord(object):
    '''
    The first record in the file is always the header record. It holds
    information related to the location of text, images, and so on
    in the file. This is used in conjunction with the sections
    defined in the file header.
    '''

    def __init__(self, raw):
        self.version, = struct.unpack('>H', raw[0:2])
        self.num_records, = struct.unpack('>H', raw[2:4])
        self.size, = struct.unpack('>L', raw[4:8])
        self.record_size, = struct.unpack('>H', raw[8:10])
        self.crc32, = struct.unpack('>L', raw[18:22])
        
    
class Reader(FormatReader):
    
    def __init__(self, header, stream, log, encoding=None):
        self.stream = stream
        self.log = log
        self.encoding = encoding
    
        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        self.header_record = HeaderRecord(self.section_data(0))

        # Initalize the decompressor
        self.uncompressor = zlib.decompressobj()
        self.uncompressor.decompress(self.section_data(1))
        
#        if self.header_record.version not in (1, 2) or self.header_record.uid != 1:
#            raise zTXTError('Unknown book version %i.' % self.header_record.version)


    def section_data(self, number):
        return self.sections[number]

    def decompress_text(self, number):
        if number == 1:
            self.uncompressor = zlib.decompressobj()
        return self.uncompressor.decompress(self.section_data(number)).decode('cp1252' if self.encoding is None else self.encoding)

    def extract_content(self, output_dir):
        txt = ''
        
        for i in range(1, self.header_record.num_records + 1):
            txt += self.decompress_text(i)

        html = txt_to_markdown(txt)
        with open(os.path.join(output_dir, 'index.html'), 'wb') as index:
            index.write(html.encode('utf-8'))
                        
        from calibre.ebooks.metadata.meta import get_metadata
        mi = get_metadata(self.stream, 'pdb')
        manifest = [('index.html', None)]
        spine = ['index.html']
        opf_writer(output_dir, 'metadata.opf', manifest, spine, mi)
        
        return os.path.join(output_dir, 'metadata.opf')

