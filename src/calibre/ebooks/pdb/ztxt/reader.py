# -*- coding: utf-8 -*-


'''
Read content from ztxt pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import struct
import zlib
import io


from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.pdb.ztxt import zTXTError

SUPPORTED_VERSION = (1, 40)


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
        self.flags, = struct.unpack('>B', raw[18:19])


class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log
        self.options = options

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        self.header_record = HeaderRecord(self.section_data(0))

        vmajor = (self.header_record.version & 0x0000FF00) >> 8
        vminor = self.header_record.version & 0x000000FF
        if vmajor < 1 or (vmajor == 1 and vminor < 40):
            raise zTXTError('Unsupported ztxt version (%i.%i). Only versions newer than %i.%i are supported.' %
                            (vmajor, vminor, SUPPORTED_VERSION[0], SUPPORTED_VERSION[1]))

        if (self.header_record.flags & 0x01) == 0:
            raise zTXTError('Only compression method 1 (random access) is supported')

        self.log.debug('Foud ztxt version: %i.%i' % (vmajor, vminor))

        # Initalize the decompressor
        self.uncompressor = zlib.decompressobj()
        self.uncompressor.decompress(self.section_data(1))

    def section_data(self, number):
        return self.sections[number]

    def decompress_text(self, number):
        if number == 1:
            self.uncompressor = zlib.decompressobj()
        return self.uncompressor.decompress(self.section_data(number))

    def extract_content(self, output_dir):
        raw_txt = b''

        self.log.info('Decompressing text...')
        for i in range(1, self.header_record.num_records + 1):
            self.log.debug('\tDecompressing text section %i' % i)
            raw_txt += self.decompress_text(i)

        self.log.info('Converting text to OEB...')
        stream = io.BytesIO(raw_txt)

        from calibre.customize.ui import plugin_for_input_format

        txt_plugin = plugin_for_input_format('txt')
        for opt in txt_plugin.options:
            if not hasattr(self.options, opt.option.name):
                setattr(self.options, opt.option.name, opt.recommended_value)

        stream.seek(0)
        return txt_plugin.convert(stream, self.options, 'txt', self.log, {})
