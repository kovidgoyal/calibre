from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re

from calibre.customize.conversion import OptionRecommendation, DummyReporter
from calibre.customize.ui import input_profiles, output_profiles, \
        plugin_for_input_format, plugin_for_output_format
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre import extract, walk

def supported_input_formats():
    from calibre.customize.ui import available_input_formats
    fmts = available_input_formats()
    for x in ('zip', 'rar', 'oebzip'):
        fmts.add(x)
    return fmts

class OptionValues(object):
    pass

class CompositeProgressReporter(object):

    def __init__(self, global_min, global_max, global_reporter):
        self.global_min, self.global_max = global_min, global_max
        self.global_reporter = global_reporter

    def __call__(self, fraction, msg=''):
        global_frac = self.global_min + fraction * \
                (self.global_max - self.global_min)
        self.global_reporter(global_frac, msg)

class Plumber(object):
    '''
    The `Plumber` manages the conversion pipeline. An UI should call the methods
    :method:`merge_ui_recommendations` and then :method:`run`. The plumber will
    take care of the rest.
    '''

    metadata_option_names = [
        'title', 'authors', 'title_sort', 'author_sort', 'cover', 'comments',
        'publisher', 'series', 'series_index', 'rating', 'isbn',
        'tags', 'book_producer', 'language'
        ]

    def __init__(self, input, output, log, report_progress=DummyReporter()):
        '''
        :param input: Path to input file.
        :param output: Path to output file/directory
        '''
        self.input = os.path.abspath(input)
        self.output = os.path.abspath(output)
        self.log = log
        self.ui_reporter = report_progress

        # Initialize the conversion options that are independent of input and
        # output formats. The input and output plugins can still disable these
        # options via recommendations.
        self.pipeline_options = [

OptionRecommendation(name='verbose',
            recommended_value=0, level=OptionRecommendation.LOW,
            short_switch='v',
            help=_('Level of verbosity. Specify multiple times for greater '
                   'verbosity.')
        ),

OptionRecommendation(name='input_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in input_profiles()],
            help=_('Specify the input profile. The input profile gives the '
                   'conversion system information on how to interpret '
                   'various information in the input document. For '
                   'example resolution dependent lengths (i.e. lengths in '
                   'pixels). Choices are:')+\
                        ', '.join([x.short_name for x in input_profiles()])
        ),

OptionRecommendation(name='output_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in output_profiles()],
            help=_('Specify the output profile. The output profile '
                   'tells the conversion system how to optimize the '
                   'created document for the specified device. In some cases, '
                   'an output profile is required to produce documents that '
                   'will work on a device. For example EPUB on the SONY reader. '
                   'Choices are:') + \
                           ', '.join([x.short_name for x in output_profiles()])
        ),

OptionRecommendation(name='base_font_size',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_('The base font size in pts. All font sizes in the produced book '
                   'will be rescaled based on this size. By choosing a larger '
                   'size you can make the fonts in the output bigger and vice '
                   'versa. By default, the base font size is chosen based on '
                   'the output profile you chose.'
                   )
        ),

OptionRecommendation(name='font_size_mapping',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Mapping from CSS font names to font sizes in pts. '
                   'An example setting is 12,12,14,16,18,20,22,24. '
                   'These are the mappings for the sizes xx-small to xx-large, '
                   'with the final size being for huge fonts. The font '
                   'rescaling algorithm uses these sizes to intelligently '
                   'rescale fonts. The default is to use a mapping based on '
                   'the output profile you chose.'
                   )
        ),

OptionRecommendation(name='line_height',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('The line height in pts. Controls spacing between consecutive '
                   'lines of text. By default no line height manipulation is '
                   'performed.'
                   )
        ),

OptionRecommendation(name='linearize_tables',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Some badly designed documents use tables to control the '
                'layout of text on the page. When converted these documents '
                'often have text that runs off the page and other artifacts. '
                'This option will extract the content from the tables and '
                'present it in a linear fashion.'
                )
        ),

OptionRecommendation(name='dont_split_on_page_breaks',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Turn off splitting at page breaks. Normally, input '
                    'files are automatically split at every page break into '
                    'two files. This gives an output ebook that can be '
                    'parsed faster and with less resources. However, '
                    'splitting is slow and if your source file contains a '
                    'very large number of page breaks, you should turn off '
                    'splitting on page breaks.'
                )
        ),

OptionRecommendation(name='level1_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that '
            'should be added to the Table of Contents at level one. If '
            'this is specified, it takes precedence over other forms '
            'of auto-detection.'
                )
        ),

OptionRecommendation(name='level2_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that should be '
            'added to the Table of Contents at level two. Each entry is added '
            'under the previous level one entry.'
                )
        ),

OptionRecommendation(name='level3_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that should be '
                'added to the Table of Contents at level three. Each entry '
                'is added under the previous level two entry.'
                )
        ),

OptionRecommendation(name='use_auto_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Normally, if the source file already has a Table of '
            'Contents, it is used in preference to the auto-generated one. '
            'With this option, the auto-generated one is always used.'
                )
        ),

OptionRecommendation(name='no_chapters_in_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_("Don't add auto-detected chapters to the Table of "
            'Contents.'
                )
        ),

OptionRecommendation(name='toc_threshold',
            recommended_value=6, level=OptionRecommendation.LOW,
            help=_(
        'If fewer than this number of chapters is detected, then links '
        'are added to the Table of Contents. Default: %default')
        ),

OptionRecommendation(name='max_toc_links',
            recommended_value=50, level=OptionRecommendation.LOW,
            help=_('Maximum number of links to insert into the TOC. Set to 0 '
               'to disable. Default is: %default. Links are only added to the '
            'TOC if less than the threshold number of chapters were detected.'
                )
        ),

OptionRecommendation(name='toc_filter',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Remove entries from the Table of Contents whose titles '
            'match the specified regular expression. Matching entries and all '
            'their children are removed.'
                )
        ),


OptionRecommendation(name='chapter',
        recommended_value="//*[((name()='h1' or name()='h2') and "
              r"re:test(., 'chapter|book|section|part\s+', 'i')) or @class "
              "= 'chapter']", level=OptionRecommendation.LOW,
            help=_('An XPath expression to detect chapter titles. The default '
                'is to consider <h1> or <h2> tags that contain the words '
                '"chapter","book","section" or "part" as chapter titles as '
                'well as any tags that have class="chapter". The expression '
                'used must evaluate to a list of elements. To disable chapter '
                'detection, use the expression "/". See the XPath Tutorial '
                'in the calibre User Manual for further help on using this '
                'feature.'
                )
        ),

OptionRecommendation(name='chapter_mark',
            recommended_value='pagebreak', level=OptionRecommendation.LOW,
            choices=['pagebreak', 'rule', 'both', 'none'],
            help=_('Specify how to mark detected chapters. A value of '
                    '"pagebreak" will insert page breaks before chapters. '
                    'A value of "rule" will insert a line before chapters. '
                    'A value of "none" will disable chapter marking and a '
                    'value of "both" will use both page breaks and lines '
                    'to mark chapters.')
        ),

OptionRecommendation(name='extra_css',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('Either the path to a CSS stylesheet or raw CSS. '
                'This CSS will be appended to the style rules from '
                'the source file, so it can be used to override those '
                'rules.')
        ),

OptionRecommendation(name='page_breaks_before',
            recommended_value="//*[name()='h1' or name()='h2']",
            level=OptionRecommendation.LOW,
            help=_('An XPath expression. Page breaks are inserted '
            'before the specified elements.')
        ),


OptionRecommendation(name='margin_top',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the top margin in pts. Default is %default. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='margin_bottom',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the bottom margin in pts. Default is %default. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='margin_left',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the left margin in pts. Default is %default. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='margin_right',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the right margin in pts. Default is %default. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='dont_justify',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Do not force text to be justified in output. Whether text '
            'is actually displayed justified or not depends on whether '
            'the ebook format and reading device support justification.')
        ),

OptionRecommendation(name='remove_paragraph_spacing',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Remove spacing between paragraphs. Also sets an indent on '
        'paragraphs of 1.5em. Spacing removal will not work '
        'if the source file does not use paragraphs (<p> or <div> tags).')
        ),

OptionRecommendation(name='prefer_metadata_cover',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Use the cover detected from the source file in preference '
        'to the specified cover.')
        ),

OptionRecommendation(name='insert_blank_line',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Insert a blank line between paragraphs. Will not work '
            'if the source file does not use paragraphs (<p> or <div> tags).'
            )
        ),

OptionRecommendation(name='remove_first_image',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Remove the first image from the input ebook. Useful if the '
        'first image in the source file is a cover and you are specifying '
        'an external cover.'
            )
        ),

OptionRecommendation(name='insert_metadata',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Insert the book metadata at the start of '
            'the book. This is useful if your ebook reader does not support '
            'displaying/searching metadata directly.'
            )
        ),

OptionRecommendation(name='preprocess_html',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Attempt to detect and correct hard line breaks and other '
            'problems in the source file. This may make things worse, so use '
            'with care.'
            )
        ),


OptionRecommendation(name='read_metadata_from_opf',
            recommended_value=None, level=OptionRecommendation.LOW,
            short_switch='m',
            help=_('Read metadata from the specified OPF file. Metadata read '
                   'from this file will override any metadata in the source '
                   'file.')
        ),


OptionRecommendation(name='title',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the title.')),

OptionRecommendation(name='authors',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the authors. Multiple authors should be separated by '
    'ampersands.')),

OptionRecommendation(name='title_sort',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('The version of the title to be used for sorting. ')),

OptionRecommendation(name='author_sort',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('String to be used when sorting by author. ')),

OptionRecommendation(name='cover',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the cover to the specified file.')),

OptionRecommendation(name='comments',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the ebook description.')),

OptionRecommendation(name='publisher',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the ebook publisher.')),

OptionRecommendation(name='series',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the series this ebook belongs to.')),

OptionRecommendation(name='series_index',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the index of the book in this series.')),

OptionRecommendation(name='rating',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the rating. Should be a number between 1 and 5.')),

OptionRecommendation(name='isbn',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the ISBN of the book.')),

OptionRecommendation(name='tags',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the tags for the book. Should be a comma separated list.')),

OptionRecommendation(name='book_producer',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the book producer.')),

OptionRecommendation(name='language',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the language.')),

OptionRecommendation(name='list_recipes',
    recommended_value=False, help=_('List available recipes.')),

]

        input_fmt = os.path.splitext(self.input)[1]
        if not input_fmt:
            raise ValueError('Input file must have an extension')
        input_fmt = input_fmt[1:].lower()
        if input_fmt in ('zip', 'rar', 'oebzip'):
            self.log('Processing archive...')
            tdir = PersistentTemporaryDirectory('_plumber')
            self.input, input_fmt = self.unarchive(self.input, tdir)

        if os.path.exists(self.output) and os.path.isdir(self.output):
            output_fmt = 'oeb'
        else:
            output_fmt = os.path.splitext(self.output)[1]
            if not output_fmt:
                output_fmt = '.oeb'
            output_fmt = output_fmt[1:].lower()

        self.input_plugin  = plugin_for_input_format(input_fmt)
        self.output_plugin = plugin_for_output_format(output_fmt)

        if self.input_plugin is None:
            raise ValueError('No plugin to handle input format: '+input_fmt)

        if self.output_plugin is None:
            raise ValueError('No plugin to handle output format: '+output_fmt)

        self.input_fmt = input_fmt
        self.output_fmt = output_fmt

        # Build set of all possible options. Two options are equal if their
        # names are the same.
        self.input_options  = self.input_plugin.options.union(
                                    self.input_plugin.common_options)
        self.output_options = self.output_plugin.options.union(
                                    self.output_plugin.common_options)

        # Remove the options that have been disabled by recommendations from the
        # plugins.
        self.merge_plugin_recommendations()

    @classmethod
    def unarchive(self, path, tdir):
        extract(path, tdir)
        files = list(walk(tdir))
        from calibre.customize.ui import available_input_formats
        fmts = available_input_formats()
        for x in ('htm', 'html', 'xhtm', 'xhtml'): fmts.remove(x)

        for ext in fmts:
            for f in files:
                if f.lower().endswith('.'+ext):
                    if ext in ['txt', 'rtf'] and os.stat(f).st_size < 2048:
                        continue
                    return f, ext
        return self.find_html_index(files)

    @classmethod
    def find_html_index(self, files):
        '''
        Given a list of files, find the most likely root HTML file in the
        list.
        '''
        html_pat = re.compile(r'\.(x){0,1}htm(l){0,1}$', re.IGNORECASE)
        html_files = [f for f in files if html_pat.search(f) is not None]
        if not html_files:
            raise ValueError(_('Could not find an ebook inside the archive'))
        html_files = [(f, os.stat(f).st_size) for f in html_files]
        html_files.sort(cmp = lambda x, y: cmp(x[1], y[1]))
        html_files = [f[0] for f in html_files]
        for q in ('toc', 'index'):
            for f in html_files:
                if os.path.splitext(os.path.basename(f))[0].lower() == q:
                    return f, os.path.splitext(f)[1].lower()[1:]
        return html_files[-1], os.path.splitext(html_files[-1])[1].lower()[1:]



    def get_option_by_name(self, name):
        for group in (self.input_options, self.pipeline_options,
                      self.output_options):
            for rec in group:
                if rec.option == name:
                    return rec

    def merge_plugin_recommendations(self):
        for source in (self.input_plugin, self.output_plugin):
            for name, val, level in source.recommendations:
                rec = self.get_option_by_name(name)
                if rec is not None and rec.level <= level:
                    rec.recommended_value = val
                    rec.level = level

    def merge_ui_recommendations(self, recommendations):
        '''
        Merge recommendations from the UI. As long as the UI recommendation
        level is >= the baseline recommended level, the UI value is used,
        *except* if the baseline has a recommendation level of `HIGH`.
        '''
        for name, val, level in recommendations:
            rec = self.get_option_by_name(name)
            if rec is not None and rec.level <= level and rec.level < rec.HIGH:
                rec.recommended_value = val
                rec.level = level

    def read_user_metadata(self):
        '''
        Read all metadata specified by the user. Command line options override
        metadata from a specified OPF file.
        '''
        from calibre.ebooks.metadata import MetaInformation, string_to_authors
        from calibre.ebooks.metadata.opf2 import OPF
        mi = MetaInformation(None, [])
        if self.opts.read_metadata_from_opf is not None:
            self.opts.read_metadata_from_opf = os.path.abspath(
                                            self.opts.read_metadata_from_opf)
            opf = OPF(open(self.opts.read_metadata_from_opf, 'rb'),
                      os.path.dirname(self.opts.read_metadata_from_opf))
            mi = MetaInformation(opf)
        for x in self.metadata_option_names:
            val = getattr(self.opts, x, None)
            if val is not None:
                if x == 'authors':
                    val = string_to_authors(val)
                elif x == 'tags':
                    val = [i.strip() for i in val.split(',')]
                elif x in ('rating', 'series_index'):
                    val = float(val)
                setattr(mi, x, val)
        if mi.cover:
            mi.cover_data = ('', open(mi.cover, 'rb').read())
            mi.cover = None
        self.user_metadata = mi

    def setup_options(self):
        '''
        Setup the `self.opts` object.
        '''
        self.opts = OptionValues()
        for group in (self.input_options, self.pipeline_options,
                  self.output_options):
            for rec in group:
                setattr(self.opts, rec.option.name, rec.recommended_value)

        for x in input_profiles():
            if x.short_name == self.opts.input_profile:
                self.opts.input_profile = x
                break

        for x in output_profiles():
            if x.short_name == self.opts.output_profile:
                self.opts.output_profile = x
                break

        self.read_user_metadata()

    def run(self):
        '''
        Run the conversion pipeline
        '''
        # Setup baseline option values
        self.setup_options()
        if self.opts.verbose:
            self.log.filter_level = self.log.DEBUG
        if self.opts.list_recipes:
            from calibre.web.feeds.recipes import titles
            self.log('Available recipes:')
            for title in sorted(titles):
                self.log('\t'+title)
            self.log('%d recipes available'%len(titles))
            raise SystemExit(0)

        # Run any preprocess plugins
        from calibre.customize.ui import run_plugins_on_preprocess
        self.input = run_plugins_on_preprocess(self.input)

        # Create an OEBBook from the input file. The input plugin does all the
        # heavy lifting.
        accelerators = {}

        tdir = PersistentTemporaryDirectory('_plumber')
        stream = self.input if self.input_fmt == 'recipe' else \
                open(self.input, 'rb')

        if hasattr(self.opts, 'lrf') and self.output_plugin.file_type == 'lrf':
            self.opts.lrf = True

        self.ui_reporter(0.01, _('Converting input to HTML...'))
        ir = CompositeProgressReporter(0.01, 0.34, self.ui_reporter)
        self.input_plugin.report_progress = ir
        self.oeb = self.input_plugin(stream, self.opts,
                                    self.input_fmt, self.log,
                                    accelerators, tdir)
        if self.opts.debug_input is not None:
            self.log('Debug input called, aborting the rest of the pipeline.')
            return
        if not hasattr(self.oeb, 'manifest'):
            self.oeb = create_oebbook(self.log, self.oeb, self.opts,
                    self.input_plugin)
        pr = CompositeProgressReporter(0.34, 0.67, self.ui_reporter)
        pr(0., _('Running transforms on ebook...'))

        from calibre.ebooks.oeb.transforms.guide import Clean
        Clean()(self.oeb, self.opts)
        pr(0.1)

        self.opts.source = self.opts.input_profile
        self.opts.dest = self.opts.output_profile

        from calibre.ebooks.oeb.transforms.metadata import MergeMetadata
        MergeMetadata()(self.oeb, self.user_metadata,
                self.opts.prefer_metadata_cover)
        pr(0.2)

        from calibre.ebooks.oeb.transforms.structure import DetectStructure
        DetectStructure()(self.oeb, self.opts)
        pr(0.35)

        from calibre.ebooks.oeb.transforms.flatcss import CSSFlattener
        fbase = self.opts.base_font_size
        if fbase == 0:
            fbase = float(self.opts.dest.fbase)
        fkey = self.opts.font_size_mapping
        if fkey is None:
            fkey = self.opts.dest.fkey
        else:
            fkey = map(float, fkey.split(','))

        from calibre.ebooks.oeb.transforms.jacket import Jacket
        Jacket()(self.oeb, self.opts, self.user_metadata)
        pr(0.4)

        if self.opts.extra_css and os.path.exists(self.opts.extra_css):
            self.opts.extra_css = open(self.opts.extra_css, 'rb').read()

        flattener = CSSFlattener(fbase=fbase, fkey=fkey,
                lineh=self.opts.line_height,
                untable=self.opts.linearize_tables)
        flattener(self.oeb, self.opts)

        if self.opts.linearize_tables:
            from calibre.ebooks.oeb.transforms.linearize_tables import LinearizeTables
            LinearizeTables()(self.oeb, self.opts)
        pr(0.7)

        from calibre.ebooks.oeb.transforms.split import Split
        pbx = accelerators.get('pagebreaks', None)
        split = Split(not self.opts.dont_split_on_page_breaks,
                max_flow_size=self.opts.output_profile.flow_size,
                page_breaks_xpath=pbx)
        split(self.oeb, self.opts)
        pr(0.9)

        from calibre.ebooks.oeb.transforms.trimmanifest import ManifestTrimmer

        self.log.info('Cleaning up manifest...')
        trimmer = ManifestTrimmer()
        trimmer(self.oeb, self.opts)

        self.oeb.toc.rationalize_play_orders()
        pr(1.)

        self.log.info('Creating %s...'%self.output_plugin.name)
        our = CompositeProgressReporter(0.67, 1., self.ui_reporter)
        self.output_plugin.report_progress = our
        our(0., _('Creating')+' %s'%self.output_plugin.name)
        self.output_plugin.convert(self.oeb, self.output, self.input_plugin,
                self.opts, self.log)
        self.ui_reporter(1.)

def create_oebbook(log, path_or_stream, opts, input_plugin, reader=None):
    '''
    Create an OEBBook.
    '''
    from calibre.ebooks.oeb.base import OEBBook
    html_preprocessor = HTMLPreProcessor(input_plugin.preprocess_html,
            opts.preprocess_html)
    oeb = OEBBook(log, html_preprocessor=html_preprocessor,
            pretty_print=opts.pretty_print)
    # Read OEB Book into OEBBook
    log('Parsing all content...')
    if reader is None:
        from calibre.ebooks.oeb.reader import OEBReader
        reader = OEBReader

    reader()(oeb, path_or_stream)
    return oeb
