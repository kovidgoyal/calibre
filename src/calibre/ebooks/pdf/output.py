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
from calibre.ebooks.pdf.writer import PDFWriter
from calibre.ebooks.pdf.pageoptions import UNITS, unit, PAPER_SIZES, \
    paper_size, ORIENTATIONS, orientation, PageOptions

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
                        
                    OptionRecommendation(name='unit', recommended_value='inch',
                        level=OptionRecommendation.LOW, short_switch='u',
                        long_switch='unit', choices=UNITS.keys(),
                        help=_('The unit of measure. Default is inch. Choices '
                        'are %s' % UNITS.keys())),
                    OptionRecommendation(name='paper_size', recommended_value='letter',
                        level=OptionRecommendation.LOW,
                        long_switch='paper_size', choices=PAPER_SIZES.keys(),
                        help=_('The size of the paper. Default is letter. Choices '
                        'are %s' % PAPER_SIZES.keys())),
                    OptionRecommendation(name='orientation', recommended_value='portrait',
                        level=OptionRecommendation.LOW,
                        long_switch='orientation', choices=ORIENTATIONS.keys(),
                        help=_('The orientation of the page. Default is portrait. Choices '
                        'are %s' % ORIENTATIONS.keys())),
                 ])
                 
    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        popts = PageOptions()
        
        popts.set_margin_top(opts.margin_top)
        popts.set_margin_bottom(opts.margin_bottom)
        popts.set_margin_left(opts.margin_left)
        popts.set_margin_right(opts.margin_right)
        
        popts.unit = unit(opts.unit)
        popts.paper_size = paper_size(opts.paper_size)
        popts.orientation = orientation(opts.orientation)
    
        writer = PDFWriter(log, popts)
        
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
