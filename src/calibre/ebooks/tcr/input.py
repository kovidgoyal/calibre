# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from cStringIO import StringIO

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.compression.tcr import decompress

class TCRInput(InputFormatPlugin):

    name        = 'TCR Input'
    author      = 'John Schember'
    description = 'Convert TCR files to HTML'
    file_types  = set(['tcr'])

    options = set([
        OptionRecommendation(name='single_line_paras', recommended_value=False,
            help=_('Normally calibre treats blank lines as paragraph markers. '
                'With this option it will assume that every line represents '
                'a paragraph instead.')),
        OptionRecommendation(name='print_formatted_paras', recommended_value=False,
            help=_('Normally calibre treats blank lines as paragraph markers. '
                'With this option it will assume that every line starting with '
                'an indent (either a tab or 2+ spaces) represents a paragraph. '
                'Paragraphs end when the next line that starts with an indent '
                'is reached.')),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name='markdown', recommended_value=False,
            help=_('Run the text input through the markdown pre-processor. To '
                'learn more about markdown see')+' http://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name="markdown_disable_toc", recommended_value=False,
            help=_('Do not insert a Table of Contents into the output text.')),
    ])

    def convert(self, stream, options, file_ext, log, accelerators):
        log.info('Decompressing text...')
        raw_txt = decompress(stream)

        log.info('Converting text to OEB...')
        stream = StringIO(raw_txt)
        from calibre.customize.ui import plugin_for_input_format
        stream.seek(0)
        return plugin_for_input_format('txt').convert(stream, options,
                'txt', log, accelerators)
