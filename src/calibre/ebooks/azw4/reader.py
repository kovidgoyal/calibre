# -*- coding: utf-8 -*-

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
        data = ''
        mo = re.search(r'(?ums)%PDF.*%%EOF.', raw_data)
        if mo:
            data = mo.group()
        
        pdf_n = os.path.join(os.getcwdu(), 'tmp.pdf')
        pdf = open(pdf_n, 'wb')
        pdf.write(data)
        pdf.close()
    
        from calibre.customize.ui import plugin_for_input_format
        
        pdf_plugin = plugin_for_input_format('pdf')
        for opt in pdf_plugin.options:
            if not hasattr(self.options, opt.option.name):
                setattr(self.options, opt.option.name, opt.recommended_value)

        return pdf_plugin.convert(open(pdf_n, 'rb'), self.options, 'pdf', self.log, {})
