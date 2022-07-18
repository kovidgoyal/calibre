__license__ = 'GPL 3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Convert OEB ebook format to PDF.
'''

import glob, os

from calibre.customize.conversion import (OutputFormatPlugin,
    OptionRecommendation)
from calibre.ptempfile import TemporaryDirectory
from polyglot.builtins import iteritems

UNITS = ('millimeter', 'centimeter', 'point', 'inch' , 'pica' , 'didot',
        'cicero', 'devicepixel')

PAPER_SIZES = ('a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'b0', 'b1',
        'b2', 'b3', 'b4', 'b5', 'b6', 'legal', 'letter')


class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'Kovid Goyal'
    file_type = 'pdf'
    commit_name = 'pdf_output'
    ui_data = {'paper_sizes': PAPER_SIZES, 'units': UNITS, 'font_types': ('serif', 'sans', 'mono')}

    options = {
        OptionRecommendation(name='use_profile_size', recommended_value=False,
            help=_('Instead of using the paper size specified in the PDF Output options,'
                   ' use a paper size corresponding to the current output profile.'
                   ' Useful if you want to generate a PDF for viewing on a specific device.')),
        OptionRecommendation(name='unit', recommended_value='inch',
            level=OptionRecommendation.LOW, short_switch='u', choices=UNITS,
            help=_('The unit of measure for page sizes. Default is inch. Choices '
            'are {} '
            'Note: This does not override the unit for margins!').format(', '.join(UNITS))),
        OptionRecommendation(name='paper_size', recommended_value='letter',
            level=OptionRecommendation.LOW, choices=PAPER_SIZES,
            help=_('The size of the paper. This size will be overridden when a '
            'non default output profile is used. Default is letter. Choices '
            'are {}').format(', '.join(PAPER_SIZES))),
        OptionRecommendation(name='custom_size', recommended_value=None,
            help=_('Custom size of the document. Use the form width x height '
            'e.g. `123x321` to specify the width and height. '
            'This overrides any specified paper-size.')),
        OptionRecommendation(name='preserve_cover_aspect_ratio',
            recommended_value=False,
            help=_('Preserve the aspect ratio of the cover, instead'
                ' of stretching it to fill the full first page of the'
                ' generated PDF.')),
        OptionRecommendation(name='pdf_serif_family',
            recommended_value='Times', help=_(
                'The font family used to render serif fonts. Will work only if the font is available system-wide.')),
        OptionRecommendation(name='pdf_sans_family',
            recommended_value='Helvetica', help=_(
                'The font family used to render sans-serif fonts. Will work only if the font is available system-wide.')),
        OptionRecommendation(name='pdf_mono_family',
            recommended_value='Courier', help=_(
                'The font family used to render monospace fonts. Will work only if the font is available system-wide.')),
        OptionRecommendation(name='pdf_standard_font', choices=ui_data['font_types'],
            recommended_value='serif', help=_(
                'The font family used to render monospace fonts')),
        OptionRecommendation(name='pdf_default_font_size',
            recommended_value=20, help=_(
                'The default font size (in pixels)')),
        OptionRecommendation(name='pdf_mono_font_size',
            recommended_value=16, help=_(
                'The default font size for monospaced text (in pixels)')),
        OptionRecommendation(name='pdf_hyphenate', recommended_value=False,
            help=_('Break long words at the end of lines. This can give the text at the right margin a more even appearance.'
                   ' Note that depending on the fonts used this option can break the copying of text from the PDF file.')),
        OptionRecommendation(name='pdf_mark_links', recommended_value=False,
            help=_('Surround all links with a red box, useful for debugging.')),
        OptionRecommendation(name='pdf_page_numbers', recommended_value=False,
            help=_('Add page numbers to the bottom of every page in the generated PDF file. If you '
                   'specify a footer template, it will take precedence '
                   'over this option.')),
        OptionRecommendation(name='pdf_footer_template', recommended_value=None,
            help=_('An HTML template used to generate %s on every page.'
                   ' The strings _PAGENUM_, _TITLE_, _AUTHOR_ and _SECTION_ will be replaced by their current values.')%_('footers')),
        OptionRecommendation(name='pdf_header_template', recommended_value=None,
            help=_('An HTML template used to generate %s on every page.'
                   ' The strings _PAGENUM_, _TITLE_, _AUTHOR_ and _SECTION_ will be replaced by their current values.')%_('headers')),
        OptionRecommendation(name='pdf_add_toc', recommended_value=False,
            help=_('Add a Table of Contents at the end of the PDF that lists page numbers. '
                   'Useful if you want to print out the PDF. If this PDF is intended for electronic use, use the PDF Outline instead.')),
        OptionRecommendation(name='toc_title', recommended_value=None,
            help=_('Title for generated table of contents.')
        ),

        OptionRecommendation(name='pdf_page_margin_left', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help=_('The size of the left page margin, in pts. Default is 72pt.'
                   ' Overrides the common left page margin setting.')
        ),

        OptionRecommendation(name='pdf_page_margin_top', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help=_('The size of the top page margin, in pts. Default is 72pt.'
                   ' Overrides the common top page margin setting, unless set to zero.')
        ),

        OptionRecommendation(name='pdf_page_margin_right', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help=_('The size of the right page margin, in pts. Default is 72pt.'
                   ' Overrides the common right page margin setting, unless set to zero.')
        ),

        OptionRecommendation(name='pdf_page_margin_bottom', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help=_('The size of the bottom page margin, in pts. Default is 72pt.'
                   ' Overrides the common bottom page margin setting, unless set to zero.')
        ),
        OptionRecommendation(name='pdf_use_document_margins', recommended_value=False,
            help=_('Use the page margins specified in the input document via @page CSS rules.'
            ' This will cause the margins specified in the conversion settings to be ignored.'
            ' If the document does not specify page margins, the conversion settings will be used as a fallback.')
        ),
        OptionRecommendation(name='pdf_page_number_map', recommended_value=None,
            help=_('Adjust page numbers, as needed. Syntax is a JavaScript expression for the page number.'
                ' For example, "if (n < 3) 0; else n - 3;", where n is current page number.')
        ),
        OptionRecommendation(name='uncompressed_pdf',
            recommended_value=False, help=_(
                'Generate an uncompressed PDF, useful for debugging.')
        ),
        OptionRecommendation(name='pdf_odd_even_offset', recommended_value=0.0,
            level=OptionRecommendation.LOW,
            help=_(
                'Shift the text horizontally by the specified offset (in pts).'
                ' On odd numbered pages, it is shifted to the right and on even'
                ' numbered pages to the left. Use negative numbers for the opposite'
                ' effect. Note that this setting is ignored on pages where the margins'
                ' are smaller than the specified offset. Shifting is done by setting'
                ' the PDF CropBox, not all software respects the CropBox.'
            )
        ),

    }

    def specialize_options(self, log, opts, input_fmt):
        # Ensure Qt is setup to be used with WebEngine
        # specialize_options is called early enough in the pipeline
        # that hopefully no Qt application has been constructed as yet
        from qt.webengine import QWebEnginePage  # noqa
        from calibre.gui2 import must_use_qt
        from calibre.utils.webengine import setup_fake_protocol, setup_default_profile
        setup_fake_protocol()
        must_use_qt()
        setup_default_profile()
        self.input_fmt = input_fmt

        if opts.pdf_use_document_margins:
            # Prevent the conversion pipeline from overwriting document margins
            opts.margin_left = opts.margin_right = opts.margin_top = opts.margin_bottom = -1

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.stored_page_margins = getattr(opts, '_stored_page_margins', {})

        self.oeb = oeb_book
        self.input_plugin, self.opts, self.log = input_plugin, opts, log
        self.output_path = output_path
        from calibre.ebooks.oeb.base import OPF, OPF2_NS
        from lxml import etree
        from io import BytesIO
        package = etree.Element(OPF('package'),
            attrib={'version': '2.0', 'unique-identifier': 'dummy'},
            nsmap={None: OPF2_NS})
        from calibre.ebooks.metadata.opf2 import OPF
        self.oeb.metadata.to_opf2(package)
        self.metadata = OPF(BytesIO(etree.tostring(package))).to_book_metadata()
        self.cover_data = None

        if input_plugin.is_image_collection:
            log.debug('Converting input as an image collection...')
            self.convert_images(input_plugin.get_images())
        else:
            log.debug('Converting input as a text based book...')
            self.convert_text(oeb_book)

    def convert_images(self, images):
        from calibre.ebooks.pdf.image_writer import convert
        convert(images, self.output_path, self.opts, self.metadata, self.report_progress)

    def get_cover_data(self):
        oeb = self.oeb
        if (oeb.metadata.cover and str(oeb.metadata.cover[0]) in oeb.manifest.ids):
            cover_id = str(oeb.metadata.cover[0])
            item = oeb.manifest.ids[cover_id]
            if isinstance(item.data, bytes):
                self.cover_data = item.data

    def process_fonts(self):
        ''' Make sure all fonts are embeddable '''
        from calibre.ebooks.oeb.base import urlnormalize
        from calibre.utils.fonts.utils import remove_embed_restriction

        processed = set()
        for item in list(self.oeb.manifest):
            if not hasattr(item.data, 'cssRules'):
                continue
            for i, rule in enumerate(item.data.cssRules):
                if rule.type == rule.FONT_FACE_RULE:
                    try:
                        s = rule.style
                        src = s.getProperty('src').propertyValue[0].uri
                    except:
                        continue
                    path = item.abshref(src)
                    ff = self.oeb.manifest.hrefs.get(urlnormalize(path), None)
                    if ff is None:
                        continue

                    raw = nraw = ff.data
                    if path not in processed:
                        processed.add(path)
                        try:
                            nraw = remove_embed_restriction(raw)
                        except:
                            continue
                        if nraw != raw:
                            ff.data = nraw
                            self.oeb.container.write(path, nraw)

    def convert_text(self, oeb_book):
        import json
        from calibre.ebooks.pdf.html_writer import convert
        self.get_cover_data()
        self.process_fonts()

        if self.opts.pdf_use_document_margins and self.stored_page_margins:
            for href, margins in iteritems(self.stored_page_margins):
                item = oeb_book.manifest.hrefs.get(href)
                if item is not None:
                    root = item.data
                    if hasattr(root, 'xpath') and margins:
                        root.set('data-calibre-pdf-output-page-margins', json.dumps(margins))

        with TemporaryDirectory('_pdf_out') as oeb_dir:
            from calibre.customize.ui import plugin_for_output_format
            oeb_dir = os.path.realpath(oeb_dir)
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(oeb_book, oeb_dir, self.input_plugin, self.opts, self.log)
            opfpath = glob.glob(os.path.join(oeb_dir, '*.opf'))[0]
            convert(
                opfpath, self.opts, metadata=self.metadata, output_path=self.output_path,
                log=self.log, cover_data=self.cover_data, report_progress=self.report_progress
            )
