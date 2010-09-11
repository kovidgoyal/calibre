# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.pdf.pdftohtml import pdftohtml
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.constants import plugins
pdfreflow, pdfreflow_err = plugins['pdfreflow']

class PDFInput(InputFormatPlugin):

    name        = 'PDF Input'
    author      = 'Kovid Goyal and John Schember'
    description = 'Convert PDF files to HTML'
    file_types  = set(['pdf'])

    options = set([
        OptionRecommendation(name='no_images', recommended_value=False,
            help=_('Do not extract images from the document')),
        OptionRecommendation(name='unwrap_factor', recommended_value=0.45,
            help=_('Scale used to determine the length at which a line should '
            'be unwrapped. Valid values are a decimal between 0 and 1. The '
            'default is 0.45, just below the median line length.')),
        OptionRecommendation(name='new_pdf_engine', recommended_value=False,
            help=_('Use the new PDF conversion engine.'))
    ])

    def convert_new(self, stream, accelerators):
        from calibre.ebooks.pdf.reflow import PDFDocument
        if pdfreflow_err:
            raise RuntimeError('Failed to load pdfreflow: ' + pdfreflow_err)
        pdfreflow.reflow(stream.read())
        xml = open('index.xml', 'rb').read()
        PDFDocument(xml, self.opts, self.log)
        return os.path.join(os.getcwd(), 'metadata.opf')


    def convert(self, stream, options, file_ext, log,
                accelerators):
        log.debug('Converting file to html...')
        # The main html file will be named index.html
        self.opts, self.log = options, log
        if options.new_pdf_engine:
            return self.convert_new(stream, accelerators)
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
