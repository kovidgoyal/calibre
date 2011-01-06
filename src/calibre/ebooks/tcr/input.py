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
        OptionRecommendation(name='paragraph_type', recommended_value='auto',
            choices=['auto', 'block', 'single', 'print'],
            help=_('Paragraph structure.\n'
                   'choices are [\'auto\', \'block\', \'single\', \'print\', \'markdown\']\n'
                   '* auto: Try to auto detect paragraph type.\n'
                   '* block: Treat a blank line as a paragraph break.\n'
                   '* single: Assume every line is a paragraph.\n'
                   '* print:  Assume every line starting with 2+ spaces or a tab '
                   'starts a paragraph.')),
        OptionRecommendation(name='formatting_type', recommended_value='auto',
            choices=['auto', 'none', 'markdown'],
            help=_('Formatting used within the document.'
                   '* auto: Try to auto detect the document formatting.\n'
                   '* none: Do not modify the paragraph formatting. Everything is a paragraph.\n'
                   '* markdown: Run the input though the markdown pre-processor. '
                   'To learn more about markdown see')+' http://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name="markdown_disable_toc", recommended_value=False,
            help=_('Do not insert a Table of Contents into the output text.')),
    ])

    def convert(self, stream, options, file_ext, log, accelerators):
        log.info('Decompressing text...')
        raw_txt = decompress(stream)

        log.info('Converting text to OEB...')
        stream = StringIO(raw_txt)
        
        from calibre.customize.ui import plugin_for_input_format
        
        txt_plugin = plugin_for_input_format('txt')
        for option in txt_plugin.options:
            if not hasattr(options, option.option.name):
                setattr(options, option.name, option.recommend_val)        
        
        stream.seek(0)
        return txt_plugin.convert(stream, options,
                'txt', log, accelerators)
