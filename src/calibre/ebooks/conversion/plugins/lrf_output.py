#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os

from calibre.customize.conversion import OutputFormatPlugin
from calibre.customize.conversion import OptionRecommendation


class LRFOptions:

    def __init__(self, output, opts, oeb):
        def f2s(f):
            try:
                return str(f[0])
            except:
                return ''
        m = oeb.metadata
        for x in ('left', 'top', 'right', 'bottom'):
            attr = 'margin_'+x
            val = getattr(opts, attr)
            if val < 0:
                setattr(opts, attr, 0)
        self.title = None
        self.author = self.publisher = _('Unknown')
        self.title_sort = self.author_sort = ''
        for x in m.creator:
            if x.role == 'aut':
                self.author = str(x)
                fa = str(getattr(x, 'file_as', ''))
                if fa:
                    self.author_sort = fa
        for x in m.title:
            if str(x.file_as):
                self.title_sort = str(x.file_as)
        self.freetext = f2s(m.description)
        self.category = f2s(m.subject)
        self.cover = None
        self.use_metadata_cover = True
        self.output = output
        self.ignore_tables = opts.linearize_tables
        if opts.disable_font_rescaling:
            self.base_font_size = 0
        else:
            self.base_font_size = opts.base_font_size
        self.blank_after_para = opts.insert_blank_line
        self.use_spine = True
        self.font_delta = 0
        self.ignore_colors = False
        from calibre.ebooks.lrf import PRS500_PROFILE
        self.profile = PRS500_PROFILE
        self.link_levels = sys.maxsize
        self.link_exclude = '@'
        self.no_links_in_toc = True
        self.disable_chapter_detection = True
        self.chapter_regex = 'dsadcdswcdec'
        self.chapter_attr = '$,,$'
        self.override_css = self._override_css = ''
        self.page_break = 'h[12]'
        self.force_page_break = '$'
        self.force_page_break_attr = '$'
        self.add_chapters_to_toc = False
        self.baen = self.pdftohtml = self.book_designer = False
        self.verbose = opts.verbose
        self.encoding = 'utf-8'
        self.lrs = False
        self.minimize_memory_usage = False
        self.autorotation = opts.enable_autorotation
        self.header_separation = (self.profile.dpi/72.) * opts.header_separation
        self.headerformat = opts.header_format

        for x in ('top', 'bottom', 'left', 'right'):
            setattr(self, x+'_margin',
                (self.profile.dpi/72.) * float(getattr(opts, 'margin_'+x)))

        for x in ('wordspace', 'header', 'header_format',
                'minimum_indent', 'serif_family',
                'render_tables_as_images', 'sans_family', 'mono_family',
                'text_size_multiplier_for_rendered_tables'):
            setattr(self, x, getattr(opts, x))


class LRFOutput(OutputFormatPlugin):

    name = 'LRF Output'
    author = 'Kovid Goyal'
    file_type = 'lrf'
    commit_name = 'lrf_output'

    options = {
        OptionRecommendation(name='enable_autorotation', recommended_value=False,
            help=_('Enable auto-rotation of images that are wider than the screen width.')
        ),
        OptionRecommendation(name='wordspace',
            recommended_value=2.5, level=OptionRecommendation.LOW,
            help=_('Set the space between words in pts. Default is %default')
        ),
        OptionRecommendation(name='header', recommended_value=False,
            help=_('Add a header to all the pages with title and author.')
        ),
        OptionRecommendation(name='header_format', recommended_value="%t by %a",
            help=_('Set the format of the header. %a is replaced by the author '
            'and %t by the title. Default is %default')
        ),
        OptionRecommendation(name='header_separation', recommended_value=0,
            help=_('Add extra spacing below the header. Default is %default pt.')
        ),
        OptionRecommendation(name='minimum_indent', recommended_value=0,
            help=_('Minimum paragraph indent (the indent of the first line '
            'of a paragraph) in pts. Default: %default')
        ),
        OptionRecommendation(name='render_tables_as_images',
            recommended_value=False,
            help=_('This option has no effect')
        ),
        OptionRecommendation(name='text_size_multiplier_for_rendered_tables',
            recommended_value=1.0,
            help=_('Multiply the size of text in rendered tables by this '
            'factor. Default is %default')
        ),
        OptionRecommendation(name='serif_family', recommended_value=None,
            help=_('The serif family of fonts to embed')
        ),
        OptionRecommendation(name='sans_family', recommended_value=None,
            help=_('The sans-serif family of fonts to embed')
        ),
        OptionRecommendation(name='mono_family', recommended_value=None,
            help=_('The monospace family of fonts to embed')
        ),

    }

    recommendations = {
        ('change_justification', 'original', OptionRecommendation.HIGH)}

    def convert_images(self, pages, opts, wide):
        from calibre.ebooks.lrf.pylrs.pylrs import Book, BookSetting, ImageStream, ImageBlock
        from uuid import uuid4
        from calibre.constants import __appname__, __version__

        width, height = (784, 1012) if wide else (584, 754)

        ps = {}
        ps['topmargin']      = 0
        ps['evensidemargin'] = 0
        ps['oddsidemargin']  = 0
        ps['textwidth']      = width
        ps['textheight']     = height
        book = Book(title=opts.title, author=opts.author,
                bookid=uuid4().hex,
                publisher='%s %s'%(__appname__, __version__),
                category=_('Comic'), pagestyledefault=ps,
                booksetting=BookSetting(screenwidth=width, screenheight=height))
        for page in pages:
            imageStream = ImageStream(page)
            _page = book.create_page()
            _page.append(ImageBlock(refstream=imageStream,
                        blockwidth=width, blockheight=height, xsize=width,
                        ysize=height, x1=width, y1=height))
            book.append(_page)

        book.renderLrf(open(opts.output, 'wb'))

    def flatten_toc(self):
        from calibre.ebooks.oeb.base import TOC
        nroot = TOC()
        for x in self.oeb.toc.iterdescendants():
            nroot.add(x.title, x.href)
        self.oeb.toc = nroot

    def convert(self, oeb, output_path, input_plugin, opts, log):
        self.log, self.opts, self.oeb = log, opts, oeb

        lrf_opts = LRFOptions(output_path, opts, oeb)

        if input_plugin.is_image_collection:
            self.convert_images(input_plugin.get_images(), lrf_opts,
                    getattr(opts, 'wide', False))
            return

        self.flatten_toc()

        from calibre.ptempfile import TemporaryDirectory
        with TemporaryDirectory('_lrf_output') as tdir:
            from calibre.customize.ui import plugin_for_output_format
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(oeb, tdir, input_plugin, opts, log)
            opf = [x for x in os.listdir(tdir) if x.endswith('.opf')][0]
            from calibre.ebooks.lrf.html.convert_from import process_file
            process_file(os.path.join(tdir, opf), lrf_opts, self.log)
