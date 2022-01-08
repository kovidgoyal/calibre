'''
Read content from azw4 file.

azw4 is essentially a PDF stuffed into a MOBI container.
'''

__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


import os
import re

from calibre.ebooks.pdb.formatreader import FormatReader


def unwrap(stream, output_path):
    raw_data = stream.read()
    m = re.search(br'%PDF.+%%EOF', raw_data, flags=re.DOTALL)
    if m is None:
        raise ValueError('No embedded PDF found in AZW4 file')
    with open(output_path, 'wb') as f:
        f.write(m.group())


class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.header = header
        self.stream = stream
        self.log = log
        self.options = options

    def extract_content(self, output_dir):
        self.log.info('Extracting PDF from AZW4 Container...')

        self.stream.seek(0)
        raw_data = self.stream.read()
        data = b''
        mo = re.search(br'%PDF.+%%EOF', raw_data, flags=re.DOTALL)
        if mo:
            data = mo.group()

        pdf_n = os.path.join(os.getcwd(), 'tmp.pdf')
        with open(pdf_n, 'wb') as pdf:
            pdf.write(data)
        from calibre.customize.ui import plugin_for_input_format

        pdf_plugin = plugin_for_input_format('pdf')
        for opt in pdf_plugin.options:
            if not hasattr(self.options, opt.option.name):
                setattr(self.options, opt.option.name, opt.recommended_value)

        return pdf_plugin.convert(open(pdf_n, 'rb'), self.options, 'pdf', self.log, {})
