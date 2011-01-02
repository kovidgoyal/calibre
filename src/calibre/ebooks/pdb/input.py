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
        OptionRecommendation(name='single_line_paras', recommended_value=False,
            help=_('Normally calibre treats blank lines as paragraph markers. '
                'With this option it will assume that every line represents '
                'a paragraph instead. This option is ignored by eReader format.')),
        OptionRecommendation(name='print_formatted_paras', recommended_value=False,
            help=_('Normally calibre treats blank lines as paragraph markers. '
                'With this option it will assume that every line starting with '
                'an indent (either a tab or 2+ spaces) represents a paragraph. '
                'Paragraphs end when the next line that starts with an indent '
                'is reached. This option is ignored by eReader format.')),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed. This option '
                'is ignored by eReader format.')),
        OptionRecommendation(name='markdown', recommended_value=False,
            help=_('Run the text input through the markdown pre-processor. To '
                'learn more about markdown see')+' http://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name="markdown_disable_toc", recommended_value=False,
            help=_('Do not insert a Table of Contents into the output text. '
                   'This option is ignored by eReader format.')),
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