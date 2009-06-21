# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.txt.processor import txt_to_markdown, opf_writer

class TXTInput(InputFormatPlugin):

    name        = 'TXT Input'
    author      = 'John Schember'
    description = 'Convert TXT files to HTML'
    file_types  = set(['txt'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        ienc = stream.encoding if stream.encoding else 'utf-8'
        if options.input_encoding:
            ienc = options.input_encoding
        log.debug('Reading text from file...')
        txt = stream.read().decode(ienc)

        log.debug('Running text though markdown conversion...')
        try:
            html = txt_to_markdown(txt)
        except RuntimeError:
            raise ValueError('This txt file has malformed markup, it cannot be'
                'converted by calibre. See http://daringfireball.net/projects/markdown/syntax')

        log.debug('Writing html output...')
        with open('index.html', 'wb') as index:
            index.write(html.encode('utf-8'))

        from calibre.ebooks.metadata.meta import get_metadata
        log.debug('Retrieving source document metadata...')
        mi = get_metadata(stream, 'txt')
        manifest = [('index.html', None)]
        spine = ['index.html']
        log.debug('Generating manifest...')
        opf_writer(os.getcwd(), 'metadata.opf', manifest, spine, mi)

        return os.path.join(os.getcwd(), 'metadata.opf')

