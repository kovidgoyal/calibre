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
        OptionRecommendation(name='inline_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Add Table of Contents to beginning of the book.')),
        OptionRecommendation(name='sectionize_chapters',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Try to turn chapters into individual sections. ' \
                   'WARNING: ' \
                   'This option is experimental. It can cause conversion ' \
                   'to fail. It can also produce unexpected output.')),
        OptionRecommendation(name='sectionize_chapters_using_file_structure',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Try to turn chapters into individual sections using the ' \
                   'internal structure of the ebook. This works well for EPUB ' \
                   'books that have been internally split by chapter.')),
        OptionRecommendation(name='h1_to_title',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Wrap all h1 tags with fb2 title elements.')),
        OptionRecommendation(name='h2_to_title',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Wrap all h2 tags with fb2 title elements.')),
        OptionRecommendation(name='h3_to_title',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Wrap all h3 tags with fb2 title elements.')),
    ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.oeb.transforms.jacket import linearize_jacket
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

