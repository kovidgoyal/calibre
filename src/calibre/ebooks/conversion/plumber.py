from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OptionRecommendation
from calibre.customize.ui import input_profiles, output_profiles, \
        plugin_for_input_format, plugin_for_output_format
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor

class OptionValues(object):
    pass

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

    def __init__(self, input, output, log):
        '''
        :param input: Path to input file.
        :param output: Path to output file/directory
        '''
        self.input = input
        self.output = output
        self.log = log

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
                   'pixels).')
        ),

OptionRecommendation(name='output_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in output_profiles()],
            help=_('Specify the output profile. The output profile '
                   'tells the conversion system how to optimize the '
                   'created document for the specified device. In some cases, '
                   'an output profile is required to produce documents that '
                   'will work on a device. For example EPUB on the SONY reader.'
                   )
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
                   'lines of text. By default ??'
                   )
        ),

OptionRecommendation(name='linearize_tables',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Some badly designed documents use tables to control the '
                'layout of text on the page. When converted these documents '
                'often have text that runs of the page and other artifacts. '
                'This option will extract the content from the tables and '
                'present it in a linear fashion.'
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
    help=_('Set the authors. Multiple authors should be separated ')),

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
]


        input_fmt = os.path.splitext(input)[1]
        if not input_fmt:
            raise ValueError('Input file must have an extension')
        input_fmt = input_fmt[1:].lower()

        output_fmt = os.path.splitext(output)[1]
        if not output_fmt:
            output_fmt = '.oeb'
        output_fmt = output_fmt[1:].lower()

        self.input_plugin = plugin_for_input_format(input_fmt)
        self.output_plugin = plugin_for_output_format(output_fmt)

        if self.input_plugin is None:
            raise ValueError('No plugin to handle input format: '+input_fmt)

        if self.output_plugin is None:
            raise ValueError('No plugin to handle output format: '+output_fmt)

        self.input_fmt = input_fmt
        self.output_fmt = output_fmt

        # Build set of all possible options. Two options are equal iff their
        # names are the same.
        self.input_options  = self.input_plugin.options.union(
                                    self.input_plugin.common_options)
        self.output_options = self.output_plugin.options.union(
                                    self.output_plugin.common_options)

        # Remove the options that have been disabled by recommendations from the
        # plugins.
        self.merge_plugin_recommendations()

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

        # Run any preprocess plugins
        from calibre.customize.ui import run_plugins_on_preprocess
        self.input = run_plugins_on_preprocess(self.input)

        # Create an OEBBook from the input file. The input plugin does all the
        # heavy lifting.
        from calibre.ebooks.oeb.reader import OEBReader
        from calibre.ebooks.oeb.base import OEBBook
        accelerators = {}

        opfpath = self.input_plugin(open(self.input, 'rb'), self.opts,
                                    self.input_fmt, self.log,
                                    accelerators)
        html_preprocessor = HTMLPreProcessor()
        self.reader = OEBReader()
        self.oeb = OEBBook(self.log, html_preprocessor=html_preprocessor)
        # Read OEB Book into OEBBook
        self.log.info('Parsing all content...')
        self.reader(self.oeb, opfpath)

        self.opts.source = self.opts.input_profile
        self.opts.dest = self.opts.output_profile

        from calibre.ebooks.oeb.transforms.flatcss import CSSFlattener
        fbase = self.opts.base_font_size
        if fbase == 0:
            fbase = self.opts.dest.fbase
        fkey = self.opts.font_size_mapping
        if fkey is None:
            fkey = self.opts.dest.fsizes

        flattener = CSSFlattener(fbase=fbase, fkey=fkey,
                lineh=self.opts.line_height,
                untable=self.opts.linearize_tables)
        self.log.info('Flattening CSS...')
        flattener(self.oeb, self.opts)

        from calibre.ebooks.oeb.transforms.trimmanifest import ManifestTrimmer

        self.log.info('Cleaning up manifest...')
        trimmer = ManifestTrimmer()
        trimmer(self.oeb, self.opts)

        self.log.info('Creating %s output...'%self.output_plugin.name)
        self.output_plugin(self.oeb, self.output, self.input_plugin, self.opts,
                self.log)


