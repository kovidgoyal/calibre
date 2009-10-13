# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.txt.processor import convert_basic, opf_writer, \
    separate_paragraphs_single_line, separate_paragraphs_print_formatted

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
    ])

    def convert(self, stream, options, file_ext, log, accelerators):
        txt = []

        log.debug('Checking TCR header...')
        if stream.read(9) != '!!8-Bit!!':
            raise ValueError('File %s contaions an invalid TCR header.' % stream.name)

        log.debug('Building string dictionary...')
        # Dictionary codes that the file contents are broken down into.
        entries = []
        for i in xrange(256):
            entry_len = ord(stream.read(1))
            entries.append(stream.read(entry_len))

        log.info('Decompressing text...')
        # Map the values in the file to locations in the string list.
        entry_loc = stream.read(1)
        while entry_loc != '': # EOF
            txt.append(entries[ord(entry_loc)])
            entry_loc = stream.read(1)

        ienc = options.input_encoding if options.input_encoding else 'utf-8'
        txt = ''.join(txt).decode(ienc, 'replace')

        log.info('Converting text to OEB...')
        if options.single_line_paras:
            txt = separate_paragraphs_single_line(txt)
        if options.print_formatted_paras:
            txt = separate_paragraphs_print_formatted(txt)
        html = convert_basic(txt)
        with open(os.path.join(os.getcwd(), 'index.html'), 'wb') as index:
            index.write(html.encode('utf-8'))

        from calibre.ebooks.metadata.meta import get_metadata
        mi = get_metadata(stream, 'tcr')
        manifest = [('index.html', None)]
        spine = ['index.html']
        opf_writer(os.getcwd(), 'metadata.opf', manifest, spine, mi)

        return os.path.join(os.getcwd(), 'metadata.opf')
