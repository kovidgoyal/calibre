'''
Read content from palmdoc pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import struct, io


from calibre.ebooks.pdb.formatreader import FormatReader


class HeaderRecord:
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
        self.options = options

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        self.header_record = HeaderRecord(self.section_data(0))

    def section_data(self, number):
        return self.sections[number]

    def decompress_text(self, number):
        if self.header_record.compression == 1:
            return self.section_data(number)
        if self.header_record.compression == 2 or self.header_record.compression == 258:
            from calibre.ebooks.compression.palmdoc import decompress_doc
            return decompress_doc(self.section_data(number))
        return b''

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
