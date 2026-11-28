# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import os
import textwrap
from typing import IO, TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.utils.localization import _
from polyglot.builtins import as_bytes

if TYPE_CHECKING:
    from optparse import Values

    from calibre.utils.logging import Log

ENGINES = 'calibre', 'pdftohtml', 'images'
# The length in pixels of the longer side of the images made by the images
# engine, large enough for text to be sharp on most screens, whatever the size
# of the pages of the PDF
PAGE_IMAGE_SIZE = 1600

PAGE_TEMPLATE = textwrap.dedent('''\
    <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <meta charset="utf-8"/>
            <title>{title}</title>
            <style type="text/css">
                @page {{ padding: 0pt; margin: 0pt }}
                html, body {{ height: 100%; padding: 0pt; margin: 0pt }}
                svg {{ display: block; width: 100%; height: 100% }}
            </style>
        </head>
        <body>
            <svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
                width="100%" height="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet">
                <image width="{width}" height="{height}" xlink:href="{href}"/>
            </svg>
        </body>
    </html>
    ''')


class PDFInput(InputFormatPlugin):
    name = 'PDF Input'
    author = 'Kovid Goyal and John Schember and Alan Pettigrew'
    description = _('Convert PDF files to HTML')
    file_types = {'pdf'}
    commit_name = 'pdf_input'

    options = {
        OptionRecommendation(name='no_images', recommended_value=False, help=_('Do not extract images from the document')),
        OptionRecommendation(
            name='unwrap_factor',
            recommended_value=0.45,
            help=_(
                'Scale used to determine the length at which a line should '
                'be unwrapped. Valid values are a decimal between 0 and 1. The '
                'default is 0.45, just below the median line length.'
            ),
        ),
        OptionRecommendation(
            name='pdf_engine',
            recommended_value='calibre',
            choices=ENGINES,
            help=_(
                'The PDF engine to use, the "calibre" engine is recommended as it has automatic header and footer removal.'
                ' The "images" engine does not extract any text, instead it turns every page into an image, as it looks in the PDF.'
                ' Use it for scanned books that have no text, or whose layout should not change. Choices: {}'
            ).format(', '.join(ENGINES)),
        ),
        OptionRecommendation(
            name='pdf_header_skip',
            recommended_value=-1,
            help=_(
                'Skip everything to the specified number of pixels at the top of a page.'
                ' Negative numbers mean auto-detect and remove headers, zero means do not remove headers and positive numbers'
                ' mean remove headers that appear above that many pixels from the top of the page. Works only'
                ' with the new PDF engine.'
            ),
        ),
        OptionRecommendation(
            name='pdf_footer_skip',
            recommended_value=-1,
            help=_(
                'Skip everything to the specified number of pixels at the bottom of a page.'
                ' Negative numbers mean auto-detect and remove footers, zero means do not remove footers and positive numbers'
                ' mean remove footers that appear below that many pixels from the bottom of the page. Works only'
                ' with the calibre PDF engine.'
            ),
        ),
        OptionRecommendation(
            name='pdf_header_regex',
            recommended_value='',
            help=_(
                'Regular expression to remove lines at the top of a page. '
                'This only looks at the first line of a page and works only with the calibre PDF engine.'
            ),
        ),
        OptionRecommendation(
            name='pdf_footer_regex',
            recommended_value='',
            help=_(
                'Regular expression to remove lines at the bottom of a page. '
                'This only looks at the last line of a page and works only with the calibre PDF engine.'
            ),
        ),
    }

    def convert(self, stream: IO[bytes], options: Values, file_ext: str, log: Log, accelerators: dict[str, str]) -> str:
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.pdf.pdftohtml import pdftohtml

        self.opts, self.log = options, log
        if options.pdf_engine == 'images':
            return self.convert_to_page_images(stream, log)
        log.debug('Converting file to html...')
        # The main html file will be named index.html
        if options.pdf_engine == 'calibre':
            from calibre.ebooks.pdf.reflow import PDFDocument
            from calibre.utils.cleantext import clean_ascii_chars

            pdftohtml(os.getcwd(), stream.name, self.opts.no_images, as_xml=True)
            with open('index.xml', 'rb') as f:
                xml = clean_ascii_chars(f.read())
            PDFDocument(xml, self.opts, self.log, stream.name)
        else:
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
        if os.path.exists('toc.ncx'):
            assert opf.manifest is not None  # created by create_manifest() above
            ncxid = opf.manifest.id_for_path('toc.ncx')
            if ncxid:
                with open('metadata.opf', 'r+b') as f:
                    raw = f.read().replace(b'<spine', b'<spine toc="%s"' % as_bytes(ncxid))
                    f.seek(0)
                    f.write(raw)

        return os.path.join(os.getcwd(), 'metadata.opf')

    def convert_to_page_images(self, stream: IO[bytes], log: Log) -> str:
        """Create a book with one page for every page of the PDF, showing an image of that page"""
        import shutil

        from calibre.ebooks.metadata.opf2 import Guide, OPFCreator
        from calibre.ebooks.metadata.pdf import get_metadata, page_images
        from calibre.ebooks.metadata.toc import TOC
        from calibre.utils.icu import numeric_sort_key
        from calibre.utils.imghdr import identify

        # Lets the output plugins and transforms treat the book as they do comics
        self.is_image_collection = True
        log.debug('Rendering the pages of the PDF as images...')
        # Copy the PDF to an ASCII file name, as there is no safe way to pass
        # non-ASCII paths on the command line on all platforms
        with open(stream.name, 'rb') as src, open('src.pdf', 'wb') as dest:
            shutil.copyfileobj(src, dest)
        try:
            page_images('src.pdf', last=None, prefix='page', scale_to=PAGE_IMAGE_SIZE)
        finally:
            os.remove('src.pdf')
        images = sorted((x for x in os.listdir('.') if x.startswith('page-') and x.endswith('.jpg')), key=numeric_sort_key)
        if not images:
            raise ValueError(_('Could not render any pages of the PDF: {}').format(stream.name))

        manifest, spine = [], []
        toc = TOC()
        for i, img in enumerate(images):
            with open(img, 'rb') as f:
                width, height = identify(f)[1:]
            title = _('Page') + f' {i + 1}'
            page = img.rpartition('.')[0] + '.xhtml'
            with open(page, 'wb') as f:
                f.write(PAGE_TEMPLATE.format(title=title, width=width, height=height, href=img).encode('utf-8'))
            manifest += [(page, None), (img, None)]
            spine.append(page)
            toc.add_item(page, None, title, play_order=i)

        log.debug('Retrieving document metadata...')
        # The cover is the image of the first page, so there is no need to render it again
        mi = get_metadata(stream, cover=False)
        opf = OPFCreator(os.getcwd(), mi)
        opf.create_manifest(manifest)
        opf.create_spine(spine)
        assert opf.guide is not None  # created by OPFCreator.__init__()
        # Guide references need absolute paths, relative paths are resolved
        # against the working directory at the time calibre was started
        opf.guide.set_cover(os.path.abspath(images[0]))
        # Use the first page as the title page, so that no cover page showing it again is added before it
        opf.guide.append(Guide.Reference(os.path.abspath(spine[0]), is_path=True))
        opf.guide[-1].type, opf.guide[-1].title = 'titlepage', ''
        opf.set_toc(toc)
        with open('metadata.opf', 'wb') as m, open('toc.ncx', 'wb') as n:
            opf.render(m, n, 'toc.ncx')
        return os.path.abspath('metadata.opf')
