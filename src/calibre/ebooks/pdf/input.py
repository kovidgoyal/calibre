# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.pdf.pdftohtml import pdftohtml
from calibre.ebooks.metadata.opf import OPFCreator
from calibre.ebooks.metadata import MetaInformation
#from calibre.ebooks.metadata.meta import metadata_from_formats

class PDFInput(InputFormatPlugin):
    
    name        = 'PDF Input'
    author      = 'John Schember'
    description = 'Convert PDF files to HTML'
    file_types  = set(['pdf'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        html = pdftohtml(stream.name)
        
        with open('index.html', 'wb') as index:
            index.write(html.encode('utf-8'))
            
        #mi = metadata_from_formats([stream.name])
        mi = MetaInformation(_('Unknown'), _('Unknown'))
        opf = OPFCreator(os.getcwd(), mi)
        opf.create_manifest([('index.html', None)])
        opf.create_spine(['index.html'])
        with open('metadata.opf', 'wb') as opffile:
            opf.render(opffile)
        
        return os.path.join(os.getcwd(), 'metadata.opf')
