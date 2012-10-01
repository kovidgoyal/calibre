# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Convert OEB ebook format to PDF.
'''

import glob
import os

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ptempfile import TemporaryDirectory
from calibre.constants import iswindows
from calibre import walk

UNITS = [
            'millimeter',
            'point',
            'inch' ,
            'pica' ,
            'didot',
            'cicero',
            'devicepixel',
        ]

PAPER_SIZES = ['b2',
     'a9',
     'executive',
     'tabloid',
     'b4',
     'b5',
     'b6',
     'b7',
     'b0',
     'b1',
     'letter',
     'b3',
     'a7',
     'a8',
     'b8',
     'b9',
     'a3',
     'a1',
     'folio',
     'c5e',
     'dle',
     'a0',
     'ledger',
     'legal',
     'a6',
     'a2',
     'b10',
     'a5',
     'comm10e',
     'a4']

ORIENTATIONS = ['portrait', 'landscape']

class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'Kovid Goyal'
    file_type = 'pdf'

    options = set([
        OptionRecommendation(name='unit', recommended_value='inch',
            level=OptionRecommendation.LOW, short_switch='u', choices=UNITS,
            help=_('The unit of measure. Default is inch. Choices '
            'are %s '
            'Note: This does not override the unit for margins!') % UNITS),
        OptionRecommendation(name='paper_size', recommended_value='letter',
            level=OptionRecommendation.LOW, choices=PAPER_SIZES,
            help=_('The size of the paper. This size will be overridden when a '
            'non default output profile is used. Default is letter. Choices '
            'are %s') % PAPER_SIZES),
        OptionRecommendation(name='custom_size', recommended_value=None,
            help=_('Custom size of the document. Use the form widthxheight '
            'EG. `123x321` to specify the width and height. '
            'This overrides any specified paper-size.')),
        OptionRecommendation(name='orientation', recommended_value='portrait',
            level=OptionRecommendation.LOW, choices=ORIENTATIONS,
            help=_('The orientation of the page. Default is portrait. Choices '
            'are %s') % ORIENTATIONS),
        OptionRecommendation(name='preserve_cover_aspect_ratio',
            recommended_value=False,
            help=_('Preserve the aspect ratio of the cover, instead'
                ' of stretching it to fill the full first page of the'
                ' generated pdf.')),
        OptionRecommendation(name='pdf_serif_family',
            recommended_value='Times New Roman', help=_(
                'The font family used to render serif fonts')),
        OptionRecommendation(name='pdf_sans_family',
            recommended_value='Helvetica', help=_(
                'The font family used to render sans-serif fonts')),
        OptionRecommendation(name='pdf_mono_family',
            recommended_value='Courier New', help=_(
                'The font family used to render monospaced fonts')),
        OptionRecommendation(name='pdf_standard_font', choices=['serif',
            'sans', 'mono'],
            recommended_value='serif', help=_(
                'The font family used to render monospaced fonts')),
        OptionRecommendation(name='pdf_default_font_size',
            recommended_value=20, help=_(
                'The default font size')),
        OptionRecommendation(name='pdf_mono_font_size',
            recommended_value=16, help=_(
                'The default font size for monospaced text')),
        ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.oeb = oeb_book
        self.input_plugin, self.opts, self.log = input_plugin, opts, log
        self.output_path = output_path
        self.metadata = oeb_book.metadata
        self.cover_data = None


        if input_plugin.is_image_collection:
            log.debug('Converting input as an image collection...')
            self.convert_images(input_plugin.get_images())
        else:
            log.debug('Converting input as a text based book...')
            self.convert_text(oeb_book)

    def convert_images(self, images):
        from calibre.ebooks.pdf.writer import ImagePDFWriter
        self.write(ImagePDFWriter, images, None)

    def get_cover_data(self):
        oeb = self.oeb
        if (oeb.metadata.cover and
                unicode(oeb.metadata.cover[0]) in oeb.manifest.ids):
            cover_id = unicode(oeb.metadata.cover[0])
            item = oeb.manifest.ids[cover_id]
            self.cover_data = item.data

    def convert_text(self, oeb_book):
        from calibre.ebooks.pdf.writer import PDFWriter
        from calibre.ebooks.metadata.opf2 import OPF

        self.log.debug('Serializing oeb input to disk for processing...')
        self.get_cover_data()

        with TemporaryDirectory('_pdf_out') as oeb_dir:
            from calibre.customize.ui import plugin_for_output_format
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(oeb_book, oeb_dir, self.input_plugin, self.opts, self.log)

            if iswindows:
                # from calibre.utils.fonts.utils import remove_embed_restriction
                # On windows Qt generates an image based PDF if the html uses
                # embedded fonts. See https://launchpad.net/bugs/1053906
                for f in walk(oeb_dir):
                    if f.rpartition('.')[-1].lower() in {'ttf', 'otf'}:
                        os.remove(f)
                        # It's not the font embedding restriction that causes
                        # this, even after removing the restriction, Qt still
                        # generates an image based document. Theoretically, it
                        # fixed = False
                        # with open(f, 'r+b') as s:
                        #     raw = s.read()
                        #     try:
                        #         raw = remove_embed_restriction(raw)
                        #     except:
                        #         self.log.exception('Failed to remove embedding'
                        #             ' restriction from font %s, ignoring it'%
                        #             os.path.basename(f))
                        #     else:
                        #         s.seek(0)
                        #         s.truncate()
                        #         s.write(raw)
                        #         fixed = True

                        # if not fixed:
                        #     os.remove(f)

            opfpath = glob.glob(os.path.join(oeb_dir, '*.opf'))[0]
            opf = OPF(opfpath, os.path.dirname(opfpath))

            self.write(PDFWriter, [s.path for s in opf.spine], getattr(opf,
                'toc', None))

    def write(self, Writer, items, toc):
        from calibre.ebooks.pdf.writer import PDFMetadata
        writer = Writer(self.opts, self.log, cover_data=self.cover_data,
                toc=toc)

        close = False
        if not hasattr(self.output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(self.output_path)) and os.path.dirname(self.output_path) != '':
                os.makedirs(os.path.dirname(self.output_path))
            out_stream = open(self.output_path, 'wb')
        else:
            out_stream = self.output_path

        out_stream.seek(0)
        out_stream.truncate()
        self.log.debug('Rendering pages to PDF...')
        writer.dump(items, out_stream, PDFMetadata(self.metadata))

        if close:
            out_stream.close()

