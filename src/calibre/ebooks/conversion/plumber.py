# -*- coding: utf-8 -*-
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, sys, shutil, pprint
from functools import partial

from calibre.customize.conversion import OptionRecommendation, DummyReporter
from calibre.customize.ui import input_profiles, output_profiles, \
        plugin_for_input_format, plugin_for_output_format, \
        available_input_formats, available_output_formats, \
        run_plugins_on_preprocess, run_plugins_on_postprocess
from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.date import parse_date
from calibre.utils.zipfile import ZipFile
from calibre import (extract, walk, isbytestring, filesystem_encoding,
        get_types_map)
from calibre.constants import __version__

DEBUG_README=u'''
This debug directory contains snapshots of the e-book as it passes through the
various stages of conversion. The stages are:

    1. input - This is the result of running the input plugin on the source
    file. Use this directory to debug the input plugin.

    2. parsed - This is the result of preprocessing and parsing the output of
    the input plugin. Note that for some input plugins this will be identical to
    the input sub-directory. Use this directory to debug structure detection,
    etc.

    3. structure - This corresponds to the stage in the pipeline when structure
    detection has run, but before the CSS is flattened. Use this directory to
    debug the CSS flattening, font size conversion, etc.

    4. processed - This corresponds to the e-book as it is passed to the output
    plugin. Use this directory to debug the output plugin.

'''

def supported_input_formats():
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

ARCHIVE_FMTS = ('zip', 'rar', 'oebzip')

class Plumber(object):
    '''
    The `Plumber` manages the conversion pipeline. An UI should call the methods
    :method:`merge_ui_recommendations` and then :method:`run`. The plumber will
    take care of the rest.
    '''

    metadata_option_names = [
        'title', 'authors', 'title_sort', 'author_sort', 'cover', 'comments',
        'publisher', 'series', 'series_index', 'rating', 'isbn',
        'tags', 'book_producer', 'language', 'pubdate', 'timestamp'
        ]

    def __init__(self, input, output, log, report_progress=DummyReporter(),
            dummy=False, merge_plugin_recs=True, abort_after_input_dump=False,
            override_input_metadata=False):
        '''
        :param input: Path to input file.
        :param output: Path to output file/directory
        '''
        if isbytestring(input):
            input = input.decode(filesystem_encoding)
        if isbytestring(output):
            output = output.decode(filesystem_encoding)
        self.original_input_arg = input
        self.input = os.path.abspath(input)
        self.output = os.path.abspath(output)
        self.log = log
        self.ui_reporter = report_progress
        self.abort_after_input_dump = abort_after_input_dump
        self.override_input_metadata = override_input_metadata

        # Pipeline options {{{
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

OptionRecommendation(name='debug_pipeline',
            recommended_value=None, level=OptionRecommendation.LOW,
            short_switch='d',
            help=_('Save the output from different stages of the conversion '
                   'pipeline to the specified '
                   'directory. Useful if you are unsure at which stage '
                   'of the conversion process a bug is occurring.')
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

OptionRecommendation(name='disable_font_rescaling',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Disable all rescaling of font sizes.'
                   )
        ),

OptionRecommendation(name='minimum_line_height',
            recommended_value=120.0, level=OptionRecommendation.LOW,
            help=_(
            'The minimum line height, as a percentage of the element\'s '
            'calculated font size. calibre will ensure that every element '
            'has a line height of at least this setting, irrespective of '
            'what the input document specifies. Set to zero to disable. '
            'Default is 120%. Use this setting in preference to '
            'the direct line height specification, unless you know what '
            'you are doing. For example, you can achieve "double spaced" '
            'text by setting this to 240.'
            )
        ),


OptionRecommendation(name='line_height',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_(
            'The line height in pts. Controls spacing between consecutive '
            'lines of text. Only applies to elements that do not define '
            'their own line height. In most cases, the minimum line height '
            'option is more useful. '
            'By default no line height manipulation is performed.'
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

OptionRecommendation(name='level1_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that '
            'should be added to the Table of Contents at level one. If '
            'this is specified, it takes precedence over other forms '
            'of auto-detection.'
            ' See the XPath Tutorial in the calibre User Manual for examples.'
                )
        ),

OptionRecommendation(name='level2_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that should be '
            'added to the Table of Contents at level two. Each entry is added '
            'under the previous level one entry.'
            ' See the XPath Tutorial in the calibre User Manual for examples.'
                )
        ),

OptionRecommendation(name='level3_toc',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('XPath expression that specifies all tags that should be '
                'added to the Table of Contents at level three. Each entry '
                'is added under the previous level two entry.'
            ' See the XPath Tutorial in the calibre User Manual for examples.'
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

OptionRecommendation(name='duplicate_links_in_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('When creating a TOC from links in the input document, '
                'allow duplicate entries, i.e. allow more than one entry '
                'with the same text, provided that they point to a '
                'different location.')
        ),


OptionRecommendation(name='chapter',
        recommended_value="//*[((name()='h1' or name()='h2') and "
              r"re:test(., '\s*((chapter|book|section|part)\s+)|((prolog|prologue|epilogue)(\s+|$))', 'i')) or @class "
              "= 'chapter']", level=OptionRecommendation.LOW,
            help=_('An XPath expression to detect chapter titles. The default '
                'is to consider <h1> or <h2> tags that contain the words '
                '"chapter","book","section", "prologue", "epilogue", or "part" as chapter titles as '
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

OptionRecommendation(name='filter_css',
            recommended_value=None, level=OptionRecommendation.LOW,
            help=_('A comma separated list of CSS properties that '
                'will be removed from all CSS style rules. This is useful '
                'if the presence of some style information prevents it '
                'from being overridden on your device. '
                'For example: '
                'font-family,color,margin-left,margin-right')
        ),

OptionRecommendation(name='page_breaks_before',
            recommended_value="//*[name()='h1' or name()='h2']",
            level=OptionRecommendation.LOW,
            help=_('An XPath expression. Page breaks are inserted '
            'before the specified elements.')
        ),

OptionRecommendation(name='remove_fake_margins',
            recommended_value=True, level=OptionRecommendation.LOW,
            help=_('Some documents specify page margins by '
                'specifying a left and right margin on each individual '
                'paragraph. calibre will try to detect and remove these '
                'margins. Sometimes, this can cause the removal of '
                'margins that should not have been removed. In this '
                'case you can disable the removal.')
        ),


OptionRecommendation(name='margin_top',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the top margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='margin_bottom',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the bottom margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='margin_left',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the left margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='margin_right',
        recommended_value=5.0, level=OptionRecommendation.LOW,
        help=_('Set the right margin in pts. Default is %default. '
            'Setting this to less than zero will cause no margin to be set. '
            'Note: 72 pts equals 1 inch')),

OptionRecommendation(name='change_justification',
        recommended_value='original', level=OptionRecommendation.LOW,
        choices=['left','justify','original'],
        help=_('Change text justification. A value of "left" converts all'
            ' justified text in the source to left aligned (i.e. '
            'unjustified) text. A value of "justify" converts all '
            'unjustified text to justified. A value of "original" '
            '(the default) does not change justification in the '
            'source file. Note that only some output formats support '
            'justification.')),

OptionRecommendation(name='remove_paragraph_spacing',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Remove spacing between paragraphs. Also sets an indent on '
        'paragraphs of 1.5em. Spacing removal will not work '
        'if the source file does not use paragraphs (<p> or <div> tags).')
        ),

OptionRecommendation(name='remove_paragraph_spacing_indent_size',
        recommended_value=1.5, level=OptionRecommendation.LOW,
        help=_('When calibre removes blank lines between paragraphs, it automatically '
            'sets a paragraph indent, to ensure that paragraphs can be easily '
            'distinguished. This option controls the width of that indent (in em). '
            'If you set this value negative, then the indent specified in the input '
            'document is used, that is, calibre does not change the indentation.')
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

OptionRecommendation(name='insert_blank_line_size',
        recommended_value=0.5, level=OptionRecommendation.LOW,
        help=_('Set the height of the inserted blank lines (in em).'
            ' The height of the lines between paragraphs will be twice the value'
            ' set here.')
        ),

OptionRecommendation(name='remove_first_image',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Remove the first image from the input ebook. Useful if the '
        'input document has a cover image that is not identified as a cover. '
        'In this case, if you set a cover in calibre, the output document will '
        'end up with two cover images if you do not specify this option.'
            )
        ),

OptionRecommendation(name='insert_metadata',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Insert the book metadata at the start of '
            'the book. This is useful if your ebook reader does not support '
            'displaying/searching metadata directly.'
            )
        ),

OptionRecommendation(name='smarten_punctuation',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Convert plain quotes, dashes and ellipsis to their '
            'typographically correct equivalents. For details, see '
            'http://daringfireball.net/projects/smartypants'
            )
        ),

OptionRecommendation(name='unsmarten_punctuation',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=_('Convert fancy quotes, dashes and ellipsis to their '
               'plain equivalents.'
            )
        ),

OptionRecommendation(name='read_metadata_from_opf',
            recommended_value=None, level=OptionRecommendation.LOW,
            short_switch='m',
            help=_('Read metadata from the specified OPF file. Metadata read '
                   'from this file will override any metadata in the source '
                   'file.')
        ),

OptionRecommendation(name='asciiize',
        recommended_value=False, level=OptionRecommendation.LOW,
        help=(_('Transliterate unicode characters to an ASCII '
            'representation. Use with care because this will replace '
            'unicode characters with ASCII. For instance it will replace "%s" '
            'with "Mikhail Gorbachiov". Also, note that in '
            'cases where there are multiple representations of a character '
            '(characters shared by Chinese and Japanese for instance) the '
            'representation based on the current calibre interface language will be '
            'used.')%\
            u'\u041c\u0438\u0445\u0430\u0438\u043b '
            u'\u0413\u043e\u0440\u0431\u0430\u0447\u0451\u0432'
)
        ),

OptionRecommendation(name='keep_ligatures',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Preserve ligatures present in the input document. '
                'A ligature is a special rendering of a pair of '
                'characters like ff, fi, fl et cetera. '
                'Most readers do not have support for '
                'ligatures in their default fonts, so they are '
                'unlikely to render correctly. By default, calibre '
                'will turn a ligature into the corresponding pair of normal '
                'characters. This option will preserve them instead.')
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
    help=_('Set the cover to the specified file or URL')),

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

OptionRecommendation(name='pubdate',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the publication date.')),

OptionRecommendation(name='timestamp',
    recommended_value=None, level=OptionRecommendation.LOW,
    help=_('Set the book timestamp (no longer used anywhere)')),

OptionRecommendation(name='enable_heuristics',
    recommended_value=False, level=OptionRecommendation.LOW,
    help=_('Enable heuristic processing. This option must be set for any '
           'heuristic processing to take place.')),

OptionRecommendation(name='markup_chapter_headings',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Detect unformatted chapter headings and sub headings. Change '
           'them to h2 and h3 tags.  This setting will not create a TOC, '
           'but can be used in conjunction with structure detection to create '
           'one.')),

OptionRecommendation(name='italicize_common_cases',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Look for common words and patterns that denote '
           'italics and italicize them.')),

OptionRecommendation(name='fix_indents',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Turn indentation created from multiple non-breaking space entities '
           'into CSS indents.')),

OptionRecommendation(name='html_unwrap_factor',
    recommended_value=0.40, level=OptionRecommendation.LOW,
    help=_('Scale used to determine the length at which a line should '
            'be unwrapped. Valid values are a decimal between 0 and 1. The '
            'default is 0.4, just below the median line length.  If only a '
            'few lines in the document require unwrapping this value should '
            'be reduced')),

OptionRecommendation(name='unwrap_lines',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Unwrap lines using punctuation and other formatting clues.')),

OptionRecommendation(name='delete_blank_paragraphs',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Remove empty paragraphs from the document when they exist between '
           'every other paragraph')),

OptionRecommendation(name='format_scene_breaks',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Left aligned scene break markers are center aligned. '
           'Replace soft scene breaks that use multiple blank lines with '
           'horizontal rules.')),

OptionRecommendation(name='replace_scene_breaks',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replace scene breaks with the specified text. By default, the '
        'text from the input document is used.')),

OptionRecommendation(name='dehyphenate',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Analyze hyphenated words throughout the document.  The '
           'document itself is used as a dictionary to determine whether hyphens '
           'should be retained or removed.')),

OptionRecommendation(name='renumber_headings',
    recommended_value=True, level=OptionRecommendation.LOW,
    help=_('Looks for occurrences of sequential <h1> or <h2> tags. '
           'The tags are renumbered to prevent splitting in the middle '
           'of chapter headings.')),

OptionRecommendation(name='sr1_search',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Search pattern (regular expression) to be replaced with '
           'sr1-replace.')),

OptionRecommendation(name='sr1_replace',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replacement to replace the text found with sr1-search.')),

OptionRecommendation(name='sr2_search',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Search pattern (regular expression) to be replaced with '
           'sr2-replace.')),

OptionRecommendation(name='sr2_replace',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replacement to replace the text found with sr2-search.')),

OptionRecommendation(name='sr3_search',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Search pattern (regular expression) to be replaced with '
           'sr3-replace.')),

OptionRecommendation(name='sr3_replace',
    recommended_value='', level=OptionRecommendation.LOW,
    help=_('Replacement to replace the text found with sr3-search.')),

OptionRecommendation(name='search_replace',
    recommended_value=None, level=OptionRecommendation.LOW, help=_(
        'Path to a file containing search and replace regular expressions. '
        'The file must contain alternating lines of regular expression '
        'followed by replacement pattern (which can be an empty line). '
        'The regular expression must be in the python regex syntax and '
        'the file must be UTF-8 encoded.')),
]
        # }}}

        input_fmt = os.path.splitext(self.input)[1]
        if not input_fmt:
            raise ValueError('Input file must have an extension')
        input_fmt = input_fmt[1:].lower().replace('original_', '')
        self.archive_input_tdir = None
        if input_fmt in ARCHIVE_FMTS:
            self.log('Processing archive...')
            tdir = PersistentTemporaryDirectory('_plumber_archive')
            self.input, input_fmt = self.unarchive(self.input, tdir)
            self.archive_input_tdir = tdir
        if os.access(self.input, os.R_OK):
            nfp = run_plugins_on_preprocess(self.input, input_fmt)
            if nfp != self.input:
                self.input = nfp
                input_fmt = os.path.splitext(self.input)[1]
                if not input_fmt:
                    raise ValueError('Input file must have an extension')
                input_fmt = input_fmt[1:].lower()

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


        self.all_format_options = set()
        self.input_options = set()
        self.output_options = set()
        # Build set of all possible options. Two options are equal if their
        # names are the same.
        if not dummy:
            self.input_options  = self.input_plugin.options.union(
                                        self.input_plugin.common_options)
            self.output_options = self.output_plugin.options.union(
                                    self.output_plugin.common_options)
        else:
            for fmt in available_input_formats():
                input_plugin = plugin_for_input_format(fmt)
                if input_plugin:
                    self.all_format_options = self.all_format_options.union(
                        input_plugin.options.union(input_plugin.common_options))
            for fmt in available_output_formats():
                output_plugin = plugin_for_output_format(fmt)
                if output_plugin:
                    self.all_format_options = self.all_format_options.union(
                        output_plugin.options.union(output_plugin.common_options))

        # Remove the options that have been disabled by recommendations from the
        # plugins.
        for w in ('input_options', 'output_options',
                'all_format_options'):
            temp = set([])
            for x in getattr(self, w):
                temp.add(x.clone())
            setattr(self, w, temp)
        if merge_plugin_recs:
            self.merge_plugin_recommendations()

    @classmethod
    def unarchive(self, path, tdir):
        extract(path, tdir)
        files = list(walk(tdir))
        files = [f if isinstance(f, unicode) else f.decode(filesystem_encoding)
                for f in files]
        from calibre.customize.ui import available_input_formats
        fmts = set(available_input_formats())
        fmts -= {'htm', 'html', 'xhtm', 'xhtml'}
        fmts -= set(ARCHIVE_FMTS)

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
                      self.output_options, self.all_format_options):
            for rec in group:
                if rec.option == name:
                    return rec

    def get_option_help(self, name):
        rec = self.get_option_by_name(name)
        help = getattr(rec, 'help', None)
        if help is not None:
            return help.replace('%default', str(rec.recommended_value))

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

    def opts_to_mi(self, mi):
        from calibre.ebooks.metadata import string_to_authors
        for x in self.metadata_option_names:
            val = getattr(self.opts, x, None)
            if val is not None:
                if x == 'authors':
                    val = string_to_authors(val)
                elif x == 'tags':
                    val = [i.strip() for i in val.split(',')]
                elif x in ('rating', 'series_index'):
                    try:
                        val = float(val)
                    except ValueError:
                        self.log.warn(_('Values of series index and rating must'
                        ' be numbers. Ignoring'), val)
                        continue
                elif x in ('timestamp', 'pubdate'):
                    try:
                        val = parse_date(val, assume_utc=x=='pubdate')
                    except:
                        self.log.exception(_('Failed to parse date/time') + ' ' +
                                unicode(val))
                        continue
                setattr(mi, x, val)

    def download_cover(self, url):
        from calibre import browser
        from PIL import Image
        from cStringIO import StringIO
        from calibre.ptempfile import PersistentTemporaryFile
        self.log('Downloading cover from %r'%url)
        br = browser()
        raw = br.open_novisit(url).read()
        buf = StringIO(raw)
        pt = PersistentTemporaryFile('.jpg')
        pt.close()
        img = Image.open(buf)
        img.convert('RGB').save(pt.name)
        return pt.name

    def read_user_metadata(self):
        '''
        Read all metadata specified by the user. Command line options override
        metadata from a specified OPF file.
        '''
        from calibre.ebooks.metadata import MetaInformation
        from calibre.ebooks.metadata.opf2 import OPF
        mi = MetaInformation(None, [])
        if self.opts.read_metadata_from_opf is not None:
            self.opts.read_metadata_from_opf = os.path.abspath(
                                            self.opts.read_metadata_from_opf)
            opf = OPF(open(self.opts.read_metadata_from_opf, 'rb'),
                      os.path.dirname(self.opts.read_metadata_from_opf))
            mi = opf.to_book_metadata()
        self.opts_to_mi(mi)
        if mi.cover:
            if mi.cover.startswith('http:') or mi.cover.startswith('https:'):
                mi.cover = self.download_cover(mi.cover)
            ext = mi.cover.rpartition('.')[-1].lower().strip()
            if ext not in ('png', 'jpg', 'jpeg', 'gif'):
                ext = 'jpg'
            mi.cover_data = (ext, open(mi.cover, 'rb').read())
            mi.cover = None
        self.user_metadata = mi

    def setup_options(self):
        '''
        Setup the `self.opts` object.
        '''
        self.opts = OptionValues()
        for group in (self.input_options, self.pipeline_options,
                  self.output_options, self.all_format_options):
            for rec in group:
                setattr(self.opts, rec.option.name, rec.recommended_value)

        def set_profile(profiles, which):
            attr = which + '_profile'
            sval = getattr(self.opts, attr)
            for x in profiles():
                if x.short_name == sval:
                    setattr(self.opts, attr, x)
                    return
            self.log.warn(
                'Profile (%s) %r is no longer available, using default'%(which, sval))
            for x in profiles():
                if x.short_name == 'default':
                    setattr(self.opts, attr, x)
                    break

        set_profile(input_profiles, 'input')
        set_profile(output_profiles, 'output')

        self.read_user_metadata()
        self.opts.no_inline_navbars = self.opts.output_profile.supports_mobi_indexing \
                and self.output_fmt == 'mobi'
        if self.opts.verbose:
            self.log.filter_level = self.log.DEBUG
        if self.opts.verbose > 1:
            self.log.debug('Resolved conversion options')
            try:
                self.log.debug('calibre version:', __version__)
                odict = dict(self.opts.__dict__)
                for x in ('username', 'password'):
                    odict.pop(x, None)
                self.log.debug(pprint.pformat(odict))
            except:
                self.log.exception('Failed to get resolved conversion options')

    def flush(self):
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass

    def dump_oeb(self, oeb, out_dir):
        from calibre.ebooks.oeb.writer import OEBWriter
        w = OEBWriter(pretty_print=self.opts.pretty_print)
        w(oeb, out_dir)

    def dump_input(self, ret, output_dir):
        out_dir = os.path.join(self.opts.debug_pipeline, 'input')
        if isinstance(ret, basestring):
            shutil.copytree(output_dir, out_dir)
        else:
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            self.dump_oeb(ret, out_dir)
        if self.input_fmt == 'recipe':
            zf = ZipFile(os.path.join(self.opts.debug_pipeline,
                'periodical.downloaded_recipe'), 'w')
            zf.add_dir(out_dir)
            with self.input_plugin:
                self.input_plugin.save_download(zf)
            zf.close()

        self.log.info('Input debug saved to:', out_dir)


    def run(self):
        '''
        Run the conversion pipeline
        '''
        # Setup baseline option values
        self.setup_options()
        if self.opts.verbose:
            self.log.filter_level = self.log.DEBUG
        self.flush()
        import cssutils, logging
        cssutils.log.setLevel(logging.WARN)
        get_types_map() # Ensure the mimetypes module is intialized

        if self.opts.debug_pipeline is not None:
            self.opts.verbose = max(self.opts.verbose, 4)
            self.opts.debug_pipeline = os.path.abspath(self.opts.debug_pipeline)
            if not os.path.exists(self.opts.debug_pipeline):
                os.makedirs(self.opts.debug_pipeline)
            open(os.path.join(self.opts.debug_pipeline, 'README.txt'),
                    'w').write(DEBUG_README.encode('utf-8'))
            for x in ('input', 'parsed', 'structure', 'processed'):
                x = os.path.join(self.opts.debug_pipeline, x)
                if os.path.exists(x):
                    shutil.rmtree(x)

        # Run any preprocess plugins
        from calibre.customize.ui import run_plugins_on_preprocess
        self.input = run_plugins_on_preprocess(self.input)

        self.flush()
        # Create an OEBBook from the input file. The input plugin does all the
        # heavy lifting.
        accelerators = {}

        tdir = PersistentTemporaryDirectory('_plumber')
        stream = self.input if self.input_fmt == 'recipe' else \
                open(self.input, 'rb')
        if self.input_fmt == 'recipe':
            self.opts.original_recipe_input_arg = self.original_input_arg

        if hasattr(self.opts, 'lrf') and self.output_plugin.file_type == 'lrf':
            self.opts.lrf = True

        self.ui_reporter(0.01, _('Converting input to HTML...'))
        ir = CompositeProgressReporter(0.01, 0.34, self.ui_reporter)
        self.input_plugin.report_progress = ir
        with self.input_plugin:
            self.oeb = self.input_plugin(stream, self.opts,
                                        self.input_fmt, self.log,
                                        accelerators, tdir)
            if self.opts.debug_pipeline is not None:
                self.dump_input(self.oeb, tdir)
                if self.abort_after_input_dump:
                    return
            if self.input_fmt in ('recipe', 'downloaded_recipe'):
                self.opts_to_mi(self.user_metadata)
            if not hasattr(self.oeb, 'manifest'):
                self.oeb = create_oebbook(self.log, self.oeb, self.opts,
                        encoding=self.input_plugin.output_encoding)
            self.input_plugin.postprocess_book(self.oeb, self.opts, self.log)
            self.opts.is_image_collection = self.input_plugin.is_image_collection
            pr = CompositeProgressReporter(0.34, 0.67, self.ui_reporter)
            self.flush()
            if self.opts.debug_pipeline is not None:
                out_dir = os.path.join(self.opts.debug_pipeline, 'parsed')
                self.dump_oeb(self.oeb, out_dir)
                self.log('Parsed HTML written to:', out_dir)
            self.input_plugin.specialize(self.oeb, self.opts, self.log,
                    self.output_fmt)

        pr(0., _('Running transforms on ebook...'))

        from calibre.ebooks.oeb.transforms.guide import Clean
        Clean()(self.oeb, self.opts)
        pr(0.1)
        self.flush()

        self.opts.source = self.opts.input_profile
        self.opts.dest = self.opts.output_profile

        from calibre.ebooks.oeb.transforms.metadata import MergeMetadata
        MergeMetadata()(self.oeb, self.user_metadata, self.opts,
                override_input_metadata=self.override_input_metadata)
        pr(0.2)
        self.flush()

        from calibre.ebooks.oeb.transforms.structure import DetectStructure
        DetectStructure()(self.oeb, self.opts)
        pr(0.35)
        self.flush()

        if self.output_plugin.file_type != 'epub':
            # Remove the toc reference to the html cover, if any, except for
            # epub, as the epub output plugin will do the right thing with it.
            item = getattr(self.oeb.toc, 'item_that_refers_to_cover', None)
            if item is not None and item.count() == 0:
                self.oeb.toc.remove(item)

        from calibre.ebooks.oeb.transforms.flatcss import CSSFlattener
        fbase = self.opts.base_font_size
        if fbase < 1e-4:
            fbase = float(self.opts.dest.fbase)
        fkey = self.opts.font_size_mapping
        if fkey is None:
            fkey = self.opts.dest.fkey
        else:
            try:
                fkey = map(float, fkey.split(','))
            except:
                self.log.error('Invalid font size key: %r ignoring'%fkey)
                fkey = self.opts.dest.fkey

        from calibre.ebooks.oeb.transforms.jacket import Jacket
        Jacket()(self.oeb, self.opts, self.user_metadata)
        pr(0.4)
        self.flush()

        if self.opts.debug_pipeline is not None:
            out_dir = os.path.join(self.opts.debug_pipeline, 'structure')
            self.dump_oeb(self.oeb, out_dir)
            self.log('Structured HTML written to:', out_dir)


        if self.opts.extra_css and os.path.exists(self.opts.extra_css):
            self.opts.extra_css = open(self.opts.extra_css, 'rb').read()

        oibl = self.opts.insert_blank_line
        orps  = self.opts.remove_paragraph_spacing
        if self.output_plugin.file_type == 'lrf':
            self.opts.insert_blank_line = False
            self.opts.remove_paragraph_spacing = False
        line_height = self.opts.line_height
        if line_height < 1e-4:
            line_height = None

        if self.opts.linearize_tables and \
                self.output_plugin.file_type not in ('mobi', 'lrf'):
            from calibre.ebooks.oeb.transforms.linearize_tables import LinearizeTables
            LinearizeTables()(self.oeb, self.opts)

        if self.opts.unsmarten_punctuation:
            from calibre.ebooks.oeb.transforms.unsmarten import UnsmartenPunctuation
            UnsmartenPunctuation()(self.oeb, self.opts)

        flattener = CSSFlattener(fbase=fbase, fkey=fkey,
                lineh=line_height,
                untable=self.output_plugin.file_type in ('mobi','lit'),
                unfloat=self.output_plugin.file_type in ('mobi', 'lit'),
                page_break_on_body=self.output_plugin.file_type in ('mobi',
                    'lit'),
                specializer=partial(self.output_plugin.specialize_css_for_output,
                    self.log, self.opts))
        flattener(self.oeb, self.opts)

        self.opts.insert_blank_line = oibl
        self.opts.remove_paragraph_spacing = orps

        from calibre.ebooks.oeb.transforms.page_margin import \
            RemoveFakeMargins, RemoveAdobeMargins
        RemoveFakeMargins()(self.oeb, self.log, self.opts)
        RemoveAdobeMargins()(self.oeb, self.log, self.opts)

        pr(0.9)
        self.flush()

        from calibre.ebooks.oeb.transforms.trimmanifest import ManifestTrimmer

        self.log.info('Cleaning up manifest...')
        trimmer = ManifestTrimmer()
        trimmer(self.oeb, self.opts)

        self.oeb.toc.rationalize_play_orders()
        pr(1.)
        self.flush()

        if self.opts.debug_pipeline is not None:
            out_dir = os.path.join(self.opts.debug_pipeline, 'processed')
            self.dump_oeb(self.oeb, out_dir)
            self.log('Processed HTML written to:', out_dir)

        self.log.info('Creating %s...'%self.output_plugin.name)
        our = CompositeProgressReporter(0.67, 1., self.ui_reporter)
        self.output_plugin.report_progress = our
        our(0., _('Creating')+' %s'%self.output_plugin.name)
        with self.output_plugin:
            self.output_plugin.convert(self.oeb, self.output, self.input_plugin,
                self.opts, self.log)
        self.oeb.clean_temp_files()
        self.ui_reporter(1.)
        run_plugins_on_postprocess(self.output, self.output_fmt)

        self.log(self.output_fmt.upper(), 'output written to', self.output)
        self.flush()

def create_oebbook(log, path_or_stream, opts, reader=None,
        encoding='utf-8', populate=True):
    '''
    Create an OEBBook.
    '''
    from calibre.ebooks.oeb.base import OEBBook
    html_preprocessor = HTMLPreProcessor(log, opts)
    if not encoding:
        encoding = None
    oeb = OEBBook(log, html_preprocessor,
            pretty_print=opts.pretty_print, input_encoding=encoding)
    if not populate:
        return oeb
    # Read OEB Book into OEBBook
    log('Parsing all content...')
    if reader is None:
        from calibre.ebooks.oeb.reader import OEBReader
        reader = OEBReader

    reader()(oeb, path_or_stream)
    return oeb
