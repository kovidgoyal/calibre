# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation
from calibre.ebooks.fb2.fb2ml import FB2MLizer

class FB2Output(OutputFormatPlugin):

    name = 'FB2 Output'
    author = 'John Schember'
    file_type = 'fb2'

    options = set([
        OptionRecommendation(name='sectionize',
            recommended_value='files', level=OptionRecommendation.LOW,
            choices=['toc', 'files', 'nothing'],
            help=_('Specify the sectionization of elements. '
                'A value of "nothing" turns the book into a single section. '
                'A value of "files" turns each file into a separate section; use this if your device is having trouble. '
                'A value of "Table of Contents" turns the entries in the Table of Contents into titles and creates sections; '
                'if it fails, adjust the "Structure Detection" and/or "Table of Contents" settings '
                '(turn on "Force use of auto-generated Table of Contents).')),
    ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.oeb.transforms.jacket import linearize_jacket
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer, Unavailable
        
        try:
            rasterizer = SVGRasterizer()
            rasterizer(oeb_book, opts)
        except Unavailable:
            self.log.warn('SVG rasterizer unavailable, SVG will not be converted')

        linearize_jacket(oeb_book)

        fb2mlizer = FB2MLizer(log)
        fb2_content = fb2mlizer.extract_content(oeb_book, opts)

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
        out_stream.write(fb2_content.encode('utf-8', 'replace'))

        if close:
            out_stream.close()

