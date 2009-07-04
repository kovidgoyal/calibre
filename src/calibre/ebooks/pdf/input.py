# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.pdf.pdftohtml import pdftohtml
from calibre.ebooks.metadata.opf2 import OPFCreator

class PDFInput(InputFormatPlugin):

    name        = 'PDF Input'
    author      = 'John Schember'
    description = 'Convert PDF files to HTML'
    file_types  = set(['pdf'])

    options = set([
        OptionRecommendation(name='no_images', recommended_value=False,
            help=_('Do not extract images from the document')),
        OptionRecommendation(name='unwrap_factor', recommended_value=0.5,
            help=_('Scale used to determine the length at which a line should '
            'be unwrapped. Valid values are a decimal between 0 and 1. The '
            'default is 0.5, this is the median line length.')),
        OptionRecommendation(name='remove_header', recommended_value=False,
            help=_('Use a regular expression to try and remove the header.')),
        OptionRecommendation(name='header_regex',
            recommended_value='(?i)(?<=<hr>)((\s*<a name=\d+></a>((<img.+?>)*<br>\s*)?\d+<br>\s*.*?\s*)|(\s*<a name=\d+></a>((<img.+?>)*<br>\s*)?.*?<br>\s*\d+))(?=<br>)',
            help=_('The regular expression to use to remove the header.')),
        OptionRecommendation(name='remove_footer', recommended_value=False,
            help=_('Use a regular expression to try and remove the footer.')),
        OptionRecommendation(name='footer_regex',
            recommended_value='(?i)(?<=<hr>)((\s*<a name=\d+></a>((<img.+?>)*<br>\s*)?\d+<br>\s*.*?\s*)|(\s*<a name=\d+></a>((<img.+?>)*<br>\s*)?.*?<br>\s*\d+))(?=<br>)',
            help=_('The regular expression to use to remove the footer.')),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        log.debug('Converting file to html...')
        # The main html file will be named index.html
        pdftohtml(os.getcwd(), stream.name, options.no_images)

        from calibre.ebooks.metadata.meta import get_metadata
        log.debug('Retrieving document metadata...')
        mi = get_metadata(stream, 'pdf')
        opf = OPFCreator(os.getcwd(), mi)

        manifest = [('index.html', None)]

        images = os.listdir(os.getcwd())
        images.remove('index.html')
        for i in images:
            manifest.append((i, None))
        log.debug('Generating manifest...')
        opf.create_manifest(manifest)

        opf.create_spine(['index.html'])
        log.debug('Rendering manifest...')
        with open('metadata.opf', 'wb') as opffile:
            opf.render(opffile)

        return os.path.join(os.getcwd(), 'metadata.opf')
