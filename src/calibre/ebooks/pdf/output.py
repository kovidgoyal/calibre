# -*- coding: utf-8 -*-
__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Convert OEB ebook format to PDF.
'''

#unit, papersize, orientation, custom_size, profile

import os

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ebooks.pdf.writer import PDFWriter, PDFMargins

class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'John Schember'
    file_type = 'pdf'

    options = set([
                    OptionRecommendation(name='margin_top', recommended_value='1',
                        level=OptionRecommendation.LOW, long_switch='margin_top',
                        help=_('The top margin around the document.')),
                    OptionRecommendation(name='margin_bottom', recommended_value='1',
                        level=OptionRecommendation.LOW, long_switch='margin_bottom',
                        help=_('The bottom margin around the document.')),
                    OptionRecommendation(name='margin_left', recommended_value='1',
                        level=OptionRecommendation.LOW, long_switch='margin_left',
                        help=_('The left margin around the document.')),
                    OptionRecommendation(name='margin_right', recommended_value='1',
                        level=OptionRecommendation.LOW, long_switch='margin_right',
                        help=_('The right margin around the document.')),
                 ])
                 
    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        margins = PDFMargins()
        margins.top = opts.margin_top
        margins.bottom = opts.margin_bottom
        margins.left = opts.margin_left
        margins.right = opts.margin_right
    
        writer = PDFWriter(log, margins)
        
        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path
        
        out_stream.seek(0)
        out_stream.truncate()
        writer.dump(oeb_book.spine, out_stream)
        
        if close:
            out_stream.close()
