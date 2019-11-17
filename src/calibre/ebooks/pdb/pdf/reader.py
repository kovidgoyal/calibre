# -*- coding: utf-8 -*-


'''
Read content from palmdoc pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2010, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ptempfile import PersistentTemporaryFile
from polyglot.builtins import range


class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.header = header
        self.stream = stream
        self.log = log
        self.options = options

    def extract_content(self, output_dir):
        self.log.info('Extracting PDF...')

        pdf = PersistentTemporaryFile('.pdf')
        pdf.close()
        pdf = open(pdf, 'wb')
        for x in range(self.header.section_count()):
            pdf.write(self.header.section_data(x))
        pdf.close()

        from calibre.customize.ui import plugin_for_input_format

        pdf_plugin = plugin_for_input_format('pdf')
        for opt in pdf_plugin.options:
            if not hasattr(self.options, opt.option.name):
                setattr(self.options, opt.option.name, opt.recommended_value)

        return pdf_plugin.convert(open(pdf, 'rb'), self.options, 'pdf', self.log, {})
