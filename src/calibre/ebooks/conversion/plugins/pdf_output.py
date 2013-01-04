# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Convert OEB ebook format to PDF.
'''

import glob, os

from PyQt4.Qt import QRawFont, QFont

from calibre.constants import iswindows
from calibre.customize.conversion import (OutputFormatPlugin,
    OptionRecommendation)
from calibre.ptempfile import TemporaryDirectory

UNITS = ['millimeter', 'centimeter', 'point', 'inch' , 'pica' , 'didot',
         'cicero', 'devicepixel']

PAPER_SIZES = [u'a0', u'a1', u'a2', u'a3', u'a4', u'a5', u'a6', u'b0', u'b1',
               u'b2', u'b3', u'b4', u'b5', u'b6', u'legal', u'letter']

class PDFMetadata(object): # {{{
    def __init__(self, oeb_metadata=None):
        from calibre import force_unicode
        from calibre.ebooks.metadata import authors_to_string
        self.title = _(u'Unknown')
        self.author = _(u'Unknown')
        self.tags = u''

        if oeb_metadata != None:
            if len(oeb_metadata.title) >= 1:
                self.title = oeb_metadata.title[0].value
            if len(oeb_metadata.creator) >= 1:
                self.author = authors_to_string([x.value for x in oeb_metadata.creator])
            if oeb_metadata.subject:
                self.tags = u', '.join(map(unicode, oeb_metadata.subject))

        self.title = force_unicode(self.title)
        self.author = force_unicode(self.author)
# }}}

class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'Kovid Goyal'
    file_type = 'pdf'

    options = set([
        OptionRecommendation(name='override_profile_size', recommended_value=False,
            help=_('Normally, the PDF page size is set by the output profile'
                   ' chosen under page options. This option will cause the '
                   ' page size settings under PDF Output to override the '
                   ' size specified by the output profile.')),
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
            'EG. `123x321` to specify the width and height. '
            'This overrides any specified paper-size.')),
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
        OptionRecommendation(name='pdf_mark_links', recommended_value=False,
            help=_('Surround all links with a red box, useful for debugging.')),
        OptionRecommendation(name='old_pdf_engine', recommended_value=False,
            help=_('Use the old, less capable engine to generate the PDF')),
        OptionRecommendation(name='uncompressed_pdf',
            recommended_value=False, help=_(
                'Generate an uncompressed PDF, useful for debugging, '
                'only works with the new PDF engine.')),
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

    def handle_embedded_fonts(self):
        '''
        Because of QtWebKit's inability to handle embedded fonts correctly, we
        remove the embedded fonts and make them available system wide instead.
        If you ever move to Qt WebKit 2.3+ then this will be unnecessary.
        '''
        from calibre.ebooks.oeb.base import urlnormalize
        from calibre.gui2 import must_use_qt
        from calibre.utils.fonts.utils import remove_embed_restriction
        from PyQt4.Qt import QFontDatabase, QByteArray

        # First find all @font-face rules and remove them, adding the embedded
        # fonts to Qt
        family_map = {}
        for item in list(self.oeb.manifest):
            if not hasattr(item.data, 'cssRules'): continue
            remove = set()
            for i, rule in enumerate(item.data.cssRules):
                if rule.type == rule.FONT_FACE_RULE:
                    remove.add(i)
                    try:
                        s = rule.style
                        src = s.getProperty('src').propertyValue[0].uri
                        font_family = s.getProperty('font-family').propertyValue[0].value
                    except:
                        continue
                    path = item.abshref(src)
                    ff = self.oeb.manifest.hrefs.get(urlnormalize(path), None)
                    if ff is None:
                        continue

                    raw = ff.data
                    self.oeb.manifest.remove(ff)
                    try:
                        raw = remove_embed_restriction(raw)
                    except:
                        continue
                    must_use_qt()
                    fid = QFontDatabase.addApplicationFontFromData(QByteArray(raw))
                    family_name = None
                    if fid > -1:
                        try:
                            family_name = unicode(QFontDatabase.applicationFontFamilies(fid)[0])
                        except (IndexError, KeyError):
                            pass
                    if family_name:
                        family_map[icu_lower(font_family)] = family_name

            for i in sorted(remove, reverse=True):
                item.data.cssRules.pop(i)

        # Now map the font family name specified in the css to the actual
        # family name of the embedded font (they may be different in general).
        font_warnings = set()
        for item in self.oeb.manifest:
            if not hasattr(item.data, 'cssRules'): continue
            for i, rule in enumerate(item.data.cssRules):
                if rule.type != rule.STYLE_RULE: continue
                ff = rule.style.getProperty('font-family')
                if ff is None: continue
                val = ff.propertyValue
                for i in xrange(val.length):
                    k = icu_lower(val[i].value)
                    if k in family_map:
                        val[i].value = family_map[k]
                if iswindows:
                    # On windows, Qt uses GDI which does not support OpenType
                    # (CFF) fonts, so we need to nuke references to OpenType
                    # fonts. Note that you could compile QT with configure
                    # -directwrite, but that requires atleast Vista SP2
                    for i in xrange(val.length):
                        family = val[i].value
                        if family:
                            f = QRawFont.fromFont(QFont(family))
                            if len(f.fontTable('head')) == 0:
                                if family not in font_warnings:
                                    self.log.warn('Ignoring unsupported font: %s'
                                                %family)
                                    font_warnings.add(family)
                                # Either a bitmap or (more likely) a CFF font
                                val[i].value = 'times'

    def convert_text(self, oeb_book):
        from calibre.ebooks.metadata.opf2 import OPF
        if self.opts.old_pdf_engine:
            from calibre.ebooks.pdf.writer import PDFWriter
            PDFWriter
        else:
            from calibre.ebooks.pdf.render.from_html import PDFWriter

        self.log.debug('Serializing oeb input to disk for processing...')
        self.get_cover_data()

        self.handle_embedded_fonts()

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

