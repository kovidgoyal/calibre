# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.ebooks.pdb import PDBError, IDENTITY_TO_NAME, get_reader
from calibre.ebooks.conversion.utils import PreProcessor

class PDBInput(InputFormatPlugin):

    name        = 'PDB Input'
    author      = 'John Schember'
    description = 'Convert PDB to HTML'
    file_types  = set(['pdb'])

    options = set([
        OptionRecommendation(name='paragraph_format', recommended_value='auto',
            choices=['auto', 'block', 'single', 'print', 'markdown'],
            help=_('How calibre splits text into paragraphs.\n'
                   'choices are [\'auto\', \'block\', \'single\', \'print\', \'markdown\']\n'
                   '* auto: Try to auto detect paragraph format.\n'
                   '* block: Treat a blank line as a paragraph break.\n'
                   '* single: Assume every line is a paragraph.\n'
                   '* print:  Assume every line starting with 2+ spaces or a tab '
                   'starts a paragraph.\n'
                   '* markdown: Run the input though the markdown pre-processor. '
                   'To learn more about markdown see')+' http://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name="markdown_disable_toc", recommended_value=False,
            help=_('Do not insert a Table of Contents into the output text.')),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        header = PdbHeaderReader(stream)
        Reader = get_reader(header.ident)

        if Reader is None:
            raise PDBError('No reader available for format within container.\n Identity is %s. Book type is %s' % (header.ident, IDENTITY_TO_NAME.get(header.ident, _('Unknown'))))

        log.debug('Detected ebook format as: %s with identity: %s' % (IDENTITY_TO_NAME[header.ident], header.ident))

        reader = Reader(header, stream, log, options)
        opf = reader.extract_content(os.getcwd())

        return opf

    def preprocess_html(self, options, html):
        self.options = options
        preprocessor = PreProcessor(self.options, log=getattr(self, 'log', None))
        return preprocessor(html)