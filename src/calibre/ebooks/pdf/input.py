# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.pdf.pdftohtml import pdftohtml
from calibre.ebooks.metadata.opf2 import OPFCreator

class PDFInput(InputFormatPlugin):

    name        = 'PDF Input'
    author      = 'John Schember'
    description = 'Convert PDF files to HTML'
    file_types  = set(['pdf'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        html = pdftohtml(stream.name)

        with open('index.html', 'wb') as index:
            index.write(html)

        from calibre.ebooks.metadata.meta import get_metadata
        mi = get_metadata(stream, 'pdf')
        opf = OPFCreator(os.getcwd(), mi)
        opf.create_manifest([('index.html', None)])
        opf.create_spine(['index.html'])
        with open('metadata.opf', 'wb') as opffile:
            opf.render(opffile)

        return os.path.join(os.getcwd(), 'metadata.opf')
