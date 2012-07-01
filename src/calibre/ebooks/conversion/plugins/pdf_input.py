# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

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
        from calibre.ebooks.pdf.pdftohtml import pdftohtml
        from calibre.utils.cleantext import clean_ascii_chars
        from calibre.ebooks.pdf.reflow import PDFDocument

        pdftohtml(os.getcwdu(), stream.name, self.opts.no_images, as_xml=True)
        with open(u'index.xml', 'rb') as f:
            xml = clean_ascii_chars(f.read())
        PDFDocument(xml, self.opts, self.log)
        return os.path.join(os.getcwdu(), u'metadata.opf')

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.pdf.pdftohtml import pdftohtml

        log.debug('Converting file to html...')
        # The main html file will be named index.html
        self.opts, self.log = options, log
        if options.new_pdf_engine:
            return self.convert_new(stream, accelerators)
        pdftohtml(os.getcwdu(), stream.name, options.no_images)

        from calibre.ebooks.metadata.meta import get_metadata
        log.debug('Retrieving document metadata...')
        mi = get_metadata(stream, 'pdf')
        opf = OPFCreator(os.getcwdu(), mi)

        manifest = [(u'index.html', None)]

        images = os.listdir(os.getcwdu())
        images.remove('index.html')
        for i in images:
            manifest.append((i, None))
        log.debug('Generating manifest...')
        opf.create_manifest(manifest)

        opf.create_spine([u'index.html'])
        log.debug('Rendering manifest...')
        with open(u'metadata.opf', 'wb') as opffile:
            opf.render(opffile)

        return os.path.join(os.getcwdu(), u'metadata.opf')
