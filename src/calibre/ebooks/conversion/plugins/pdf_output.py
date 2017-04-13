# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Convert OEB ebook format to PDF.
'''

import glob, os

from calibre.constants import islinux, iswindows
from calibre.customize.conversion import (OutputFormatPlugin,
    OptionRecommendation)
from calibre.ptempfile import TemporaryDirectory

UNITS = ['millimeter', 'centimeter', 'point', 'inch' , 'pica' , 'didot',
         'cicero', 'devicepixel']

PAPER_SIZES = [u'a0', u'a1', u'a2', u'a3', u'a4', u'a5', u'a6', u'b0', u'b1',
               u'b2', u'b3', u'b4', u'b5', u'b6', u'legal', u'letter']


class PDFMetadata(object):  # {{{

    def __init__(self, mi=None):
        from calibre import force_unicode
        from calibre.ebooks.metadata import authors_to_string
        self.title = _(u'Unknown')
        self.author = _(u'Unknown')
        self.tags = u''
        self.mi = mi

        if mi is not None:
            if mi.title:
                self.title = mi.title
            if mi.authors:
                self.author = authors_to_string(mi.authors)
            if mi.tags:
                self.tags = u', '.join(mi.tags)

        self.title = force_unicode(self.title)
        self.author = force_unicode(self.author)
# }}}


class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'Kovid Goyal'
    file_type = 'pdf'

    options = set([
        OptionRecommendation(name='use_profile_size', recommended_value=False,
            help=_('Instead of using the paper size specified in the PDF Output options,'
                   ' use a paper size corresponding to the current output profile.'
                   ' Useful if you want to generate a PDF for viewing on a specific device.')),
        OptionRecommendation(name='unit', recommended_value='inch',
            level=OptionRecommendation.LOW, short_switch='u', choices=UNITS,
            help=_('The unit of measure for page sizes. Default is inch. Choices '
            'are %s '
            'Note: This does not override the unit for margins!') % UNITS),
        OptionRecommendation(name='paper_size', recommended_value='letter',
            level=OptionRecommendation.LOW, choices=PAPER_SIZES,
            help=_('The size of the paper. This size will be overridden when a '
            'non default output profile is used. Default is letter. Choices '
            'are %s') % PAPER_SIZES),
        OptionRecommendation(name='custom_size', recommended_value=None,
            help=_('Custom size of the document. Use the form widthxheight '
            'e.g. `123x321` to specify the width and height. '
            'This overrides any specified paper-size.')),
        OptionRecommendation(name='preserve_cover_aspect_ratio',
            recommended_value=False,
            help=_('Preserve the aspect ratio of the cover, instead'
                ' of stretching it to fill the full first page of the'
                ' generated pdf.')),
        OptionRecommendation(name='pdf_serif_family',
            recommended_value='Liberation Serif' if islinux else 'Times New Roman', help=_(
                'The font family used to render serif fonts')),
        OptionRecommendation(name='pdf_sans_family',
            recommended_value='Liberation Sans' if islinux else 'Helvetica', help=_(
                'The font family used to render sans-serif fonts')),
        OptionRecommendation(name='pdf_mono_family',
            recommended_value='Liberation Mono' if islinux else 'Courier New', help=_(
                'The font family used to render monospace fonts')),
        OptionRecommendation(name='pdf_standard_font', choices=['serif',
            'sans', 'mono'],
            recommended_value='serif', help=_(
                'The font family used to render monospace fonts')),
        OptionRecommendation(name='pdf_default_font_size',
            recommended_value=20, help=_(
                'The default font size')),
        OptionRecommendation(name='pdf_mono_font_size',
            recommended_value=16, help=_(
                'The default font size for monospaced text')),
        OptionRecommendation(name='pdf_mark_links', recommended_value=False,
            help=_('Surround all links with a red box, useful for debugging.')),
        OptionRecommendation(name='uncompressed_pdf',
            recommended_value=False, help=_(
                'Generate an uncompressed PDF, useful for debugging, '
                'only works with the new PDF engine.')),
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
    ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.gui2 import must_use_qt, load_builtin_fonts
        from calibre.ebooks.oeb.transforms.split import Split
        # Turn off hinting in WebKit (requires a patched build of QtWebKit)
        os.environ['CALIBRE_WEBKIT_NO_HINTING'] = '1'
        self.filtered_font_warnings = set()
        try:
            # split on page breaks, as the JS code to convert page breaks to
            # column breaks will not work because of QWebSettings.LocalContentCanAccessFileUrls
            Split()(oeb_book, opts)
            must_use_qt()
            load_builtin_fonts()

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
        finally:
            os.environ.pop('CALIBRE_WEBKIT_NO_HINTING', None)

    def convert_images(self, images):
        from calibre.ebooks.pdf.render.from_html import ImagePDFWriter
        self.write(ImagePDFWriter, images, None)

    def get_cover_data(self):
        oeb = self.oeb
        if (oeb.metadata.cover and
                unicode(oeb.metadata.cover[0]) in oeb.manifest.ids):
            cover_id = unicode(oeb.metadata.cover[0])
            item = oeb.manifest.ids[cover_id]
            self.cover_data = item.data

    def process_fonts(self):
        ''' Make sure all fonts are embeddable. Also remove some fonts that causes problems. '''
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
                elif iswindows and rule.type == rule.STYLE_RULE:
                    from tinycss.fonts3 import parse_font_family, serialize_font_family
                    s = rule.style
                    f = s.getProperty(u'font-family')
                    if f is not None:
                        font_families = parse_font_family(f.propertyValue.cssText)
                        ff = [x for x in font_families if x.lower() != u'courier']
                        if len(ff) != len(font_families):
                            if 'courier' not in self.filtered_font_warnings:
                                # See https://bugs.launchpad.net/bugs/1665835
                                self.filtered_font_warnings.add(u'courier')
                                self.log.warn(u'Removing courier font family as it does not render on windows')
                            f.propertyValue.cssText = serialize_font_family(ff or [u'monospace'])

    def convert_text(self, oeb_book):
        from calibre.ebooks.metadata.opf2 import OPF
        from calibre.ebooks.pdf.render.from_html import PDFWriter

        self.log.debug('Serializing oeb input to disk for processing...')
        self.get_cover_data()

        self.process_fonts()

        with TemporaryDirectory('_pdf_out') as oeb_dir:
            from calibre.customize.ui import plugin_for_output_format
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(oeb_book, oeb_dir, self.input_plugin, self.opts, self.log)

            opfpath = glob.glob(os.path.join(oeb_dir, '*.opf'))[0]
            opf = OPF(opfpath, os.path.dirname(opfpath))

            self.write(PDFWriter, [s.path for s in opf.spine], getattr(opf,
                'toc', None))

    def write(self, Writer, items, toc):
        writer = Writer(self.opts, self.log, cover_data=self.cover_data,
                toc=toc)
        writer.report_progress = self.report_progress

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
        import time
        st = time.time()
        if False:
            import cProfile
            cProfile.runctx('writer.dump(items, out_stream, PDFMetadata(self.metadata))',
                        globals(), locals(), '/tmp/profile')
        else:
            writer.dump(items, out_stream, PDFMetadata(self.metadata))
        self.log('Rendered PDF in %g seconds:'%(time.time()-st))

        if close:
            out_stream.close()
