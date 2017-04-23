from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Command line interface to conversion sub-system
'''

import sys, os
from optparse import OptionGroup, Option
from collections import OrderedDict

from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.customize.conversion import OptionRecommendation
from calibre import patheq
from calibre.ebooks.conversion import ConversionUserFeedBack
from calibre.utils.localization import localize_user_manual_link

USAGE = '%prog ' + _('''\
input_file output_file [options]

Convert an ebook from one format to another.

input_file is the input and output_file is the output. Both must be \
specified as the first two arguments to the command.

The output ebook format is guessed from the file extension of \
output_file. output_file can also be of the special format .EXT where \
EXT is the output file extension. In this case, the name of the output \
file is derived from the name of the input file. Note that the filenames must \
not start with a hyphen. Finally, if output_file has no extension, then \
it is treated as a directory and an "open ebook" (OEB) consisting of HTML \
files is written to that directory. These files are the files that would \
normally have been passed to the output plugin.

After specifying the input \
and output file you can customize the conversion by specifying various \
options. The available options depend on the input and output file types. \
To get help on them specify the input and output file and then use the -h \
option.

For full documentation of the conversion system see
''') + localize_user_manual_link('https://manual.calibre-ebook.com/conversion.html')

HEURISTIC_OPTIONS = ['markup_chapter_headings',
                      'italicize_common_cases', 'fix_indents',
                      'html_unwrap_factor', 'unwrap_lines',
                      'delete_blank_paragraphs', 'format_scene_breaks',
                      'dehyphenate', 'renumber_headings',
                      'replace_scene_breaks']

DEFAULT_TRUE_OPTIONS = HEURISTIC_OPTIONS + ['remove_fake_margins']


def print_help(parser, log):
    parser.print_help()


def check_command_line_options(parser, args, log):
    if len(args) < 3 or args[1].startswith('-') or args[2].startswith('-'):
        print_help(parser, log)
        log.error('\n\nYou must specify the input AND output files')
        raise SystemExit(1)

    input = os.path.abspath(args[1])
    if not input.endswith('.recipe') and not os.access(input, os.R_OK) and not \
            ('-h' in args or '--help' in args):
        log.error('Cannot read from', input)
        raise SystemExit(1)
    if input.endswith('.recipe') and not os.access(input, os.R_OK):
        input = args[1]

    output = args[2]
    if (output.startswith('.') and output[:2] not in {'..', '.'} and '/' not in
            output and '\\' not in output):
        output = os.path.splitext(os.path.basename(input))[0]+output
    output = os.path.abspath(output)

    return input, output


def option_recommendation_to_cli_option(add_option, rec):
    opt = rec.option
    switches = ['-'+opt.short_switch] if opt.short_switch else []
    switches.append('--'+opt.long_switch)
    attrs = dict(dest=opt.name, help=opt.help,
                     choices=opt.choices, default=rec.recommended_value)
    if isinstance(rec.recommended_value, type(True)):
        attrs['action'] = 'store_false' if rec.recommended_value else \
                          'store_true'
    else:
        if isinstance(rec.recommended_value, int):
            attrs['type'] = 'int'
        if isinstance(rec.recommended_value, float):
            attrs['type'] = 'float'

    if opt.long_switch == 'verbose':
        attrs['action'] = 'count'
        attrs.pop('type', '')
    if opt.name == 'read_metadata_from_opf':
        switches.append('--from-opf')
    if opt.name == 'transform_css_rules':
        attrs['help'] = _(
            'Path to a file containing rules to transform the CSS styles'
            ' in this book. The easiest way to create such a file is to'
            ' use the wizard for creating rules in the calibre GUI. Access'
            ' it in the "Look & feel->Transform styles" section of the conversion'
            ' dialog. Once you create the rules, you can use the "Export" button'
            ' to save them to a file.'
        )
    if opt.name in DEFAULT_TRUE_OPTIONS and rec.recommended_value is True:
        switches = ['--disable-'+opt.long_switch]
    add_option(Option(*switches, **attrs))


def group_titles():
    return _('INPUT OPTIONS'), _('OUTPUT OPTIONS')


def recipe_test(option, opt_str, value, parser):
    assert value is None
    value = []

    def floatable(str):
        try:
            float(str)
            return True
        except ValueError:
            return False

    for arg in parser.rargs:
        # stop on --foo like options
        if arg[:2] == "--":
            break
        # stop on -a, but not on -3 or -3.0
        if arg[:1] == "-" and len(arg) > 1 and not floatable(arg):
            break
        try:
            value.append(int(arg))
        except (TypeError, ValueError, AttributeError):
            break
        if len(value) == 2:
            break
    del parser.rargs[:len(value)]

    while len(value) < 2:
        value.append(2)

    setattr(parser.values, option.dest, tuple(value))


def add_input_output_options(parser, plumber):
    input_options, output_options = \
                                plumber.input_options, plumber.output_options

    def add_options(group, options):
        for opt in options:
            if plumber.input_fmt == 'recipe' and opt.option.long_switch == 'test':
                group(Option('--test', dest='test', action='callback', callback=recipe_test))
            else:
                option_recommendation_to_cli_option(group, opt)

    if input_options:
        title = group_titles()[0]
        io = OptionGroup(parser, title, _('Options to control the processing'
                          ' of the input %s file')%plumber.input_fmt)
        add_options(io.add_option, input_options)
        parser.add_option_group(io)

    if output_options:
        title = group_titles()[1]
        oo = OptionGroup(parser, title, _('Options to control the processing'
                          ' of the output %s')%plumber.output_fmt)
        add_options(oo.add_option, output_options)
        parser.add_option_group(oo)


def add_pipeline_options(parser, plumber):
    groups = OrderedDict((
              ('' , ('',
                    [
                     'input_profile',
                     'output_profile',
                     ]
                    )),
              (_('LOOK AND FEEL') , (
                  _('Options to control the look and feel of the output'),
                  [
                      'base_font_size', 'disable_font_rescaling',
                      'font_size_mapping', 'embed_font_family',
                      'subset_embedded_fonts', 'embed_all_fonts',
                      'line_height', 'minimum_line_height',
                      'linearize_tables',
                      'extra_css', 'filter_css', 'transform_css_rules', 'expand_css',
                      'smarten_punctuation', 'unsmarten_punctuation',
                      'margin_top', 'margin_left', 'margin_right',
                      'margin_bottom', 'change_justification',
                      'insert_blank_line', 'insert_blank_line_size',
                      'remove_paragraph_spacing',
                      'remove_paragraph_spacing_indent_size',
                      'asciiize', 'keep_ligatures',
                  ]
                  )),

              (_('HEURISTIC PROCESSING') , (
                  _('Modify the document text and structure using common'
                     ' patterns. Disabled by default. Use %(en)s to enable. '
                     ' Individual actions can be disabled with the %(dis)s options.')
                  % dict(en='--enable-heuristics', dis='--disable-*'),
                  ['enable_heuristics'] + HEURISTIC_OPTIONS
                  )),

              (_('SEARCH AND REPLACE') , (
                 _('Modify the document text and structure using user defined patterns.'),
                 [
                     'sr1_search', 'sr1_replace',
                     'sr2_search', 'sr2_replace',
                     'sr3_search', 'sr3_replace',
                     'search_replace',
                 ]
              )),

              (_('STRUCTURE DETECTION') , (
                  _('Control auto-detection of document structure.'),
                  [
                      'chapter', 'chapter_mark',
                      'prefer_metadata_cover', 'remove_first_image',
                      'insert_metadata', 'page_breaks_before',
                      'remove_fake_margins', 'start_reading_at',
                  ]
                  )),

              (_('TABLE OF CONTENTS') , (
                  _('Control the automatic generation of a Table of Contents. By '
                  'default, if the source file has a Table of Contents, it will '
                  'be used in preference to the automatically generated one.'),
                  [
                    'level1_toc', 'level2_toc', 'level3_toc',
                    'toc_threshold', 'max_toc_links', 'no_chapters_in_toc',
                    'use_auto_toc', 'toc_filter', 'duplicate_links_in_toc',
                  ]
                  )),

              (_('METADATA') , (_('Options to set metadata in the output'),
                            plumber.metadata_option_names + ['read_metadata_from_opf'],
                            )),
              (_('DEBUG'), (_('Options to help with debugging the conversion'),
                        [
                         'verbose',
                         'debug_pipeline',
                         ])),

              ))

    for group, (desc, options) in groups.iteritems():
        if group:
            group = OptionGroup(parser, group, desc)
            parser.add_option_group(group)
        add_option = group.add_option if group != '' else parser.add_option

        for name in options:
            rec = plumber.get_option_by_name(name)
            if rec.level < rec.HIGH:
                option_recommendation_to_cli_option(add_option, rec)


def option_parser():
    parser = OptionParser(usage=USAGE)
    parser.add_option('--list-recipes', default=False, action='store_true',
            help=_('List builtin recipe names. You can create an ebook from '
                'a builtin recipe like this: ebook-convert "Recipe Name.recipe" '
                'output.epub'))
    return parser


class ProgressBar(object):

    def __init__(self, log):
        self.log = log

    def __call__(self, frac, msg=''):
        if msg:
            percent = int(frac*100)
            self.log('%d%% %s'%(percent, msg))


def create_option_parser(args, log):
    if '--version' in args:
        from calibre.constants import __appname__, __version__, __author__
        log(os.path.basename(args[0]), '('+__appname__, __version__+')')
        log('Created by:', __author__)
        raise SystemExit(0)
    if '--list-recipes' in args:
        from calibre.web.feeds.recipes.collection import get_builtin_recipe_titles
        log('Available recipes:')
        titles = sorted(get_builtin_recipe_titles())
        for title in titles:
            try:
                log('\t'+title)
            except:
                log('\t'+repr(title))
        log('%d recipes available'%len(titles))
        raise SystemExit(0)

    parser = option_parser()
    if len(args) < 3:
        print_help(parser, log)
        raise SystemExit(1)

    input, output = check_command_line_options(parser, args, log)

    from calibre.ebooks.conversion.plumber import Plumber

    reporter = ProgressBar(log)
    if patheq(input, output):
        raise ValueError('Input file is the same as the output file')

    plumber = Plumber(input, output, log, reporter)
    add_input_output_options(parser, plumber)
    add_pipeline_options(parser, plumber)

    return parser, plumber


def abspath(x):
    if x.startswith('http:') or x.startswith('https:'):
        return x
    return os.path.abspath(os.path.expanduser(x))


def read_sr_patterns(path, log=None):
    import json, re, codecs
    pats = []
    with codecs.open(path, 'r', 'utf-8') as f:
        pat = None
        for line in f.readlines():
            if line.endswith(u'\n'):
                line = line[:-1]

            if pat is None:
                if not line.strip():
                    continue
                try:
                    re.compile(line)
                except:
                    msg = u'Invalid regular expression: %r from file: %r'%(
                            line, path)
                    if log is not None:
                        log.error(msg)
                        raise SystemExit(1)
                    else:
                        raise ValueError(msg)
                pat = line
            else:
                pats.append((pat, line))
                pat = None
    return json.dumps(pats)


def main(args=sys.argv):
    log = Log()
    parser, plumber = create_option_parser(args, log)
    opts, leftover_args = parser.parse_args(args)
    if len(leftover_args) > 3:
        log.error('Extra arguments not understood:', u', '.join(leftover_args[3:]))
        return 1
    for x in ('read_metadata_from_opf', 'cover'):
        if getattr(opts, x, None) is not None:
            setattr(opts, x, abspath(getattr(opts, x)))
    if opts.search_replace:
        opts.search_replace = read_sr_patterns(opts.search_replace, log)
    if opts.transform_css_rules:
        from calibre.ebooks.css_transform_rules import import_rules, validate_rule
        with open(opts.transform_css_rules, 'rb') as tcr:
            opts.transform_css_rules = rules = list(import_rules(tcr.read()))
            for rule in rules:
                title, msg = validate_rule(rule)
                if title and msg:
                    log.error('Failed to parse CSS transform rules')
                    log.error(title)
                    log.error(msg)
                    return 1

    recommendations = [(n.dest, getattr(opts, n.dest),
                        OptionRecommendation.HIGH)
                                        for n in parser.options_iter()
                                        if n.dest]
    plumber.merge_ui_recommendations(recommendations)

    try:
        plumber.run()
    except ConversionUserFeedBack as e:
        ll = {'info': log.info, 'warn': log.warn,
                'error':log.error}.get(e.level, log.info)
        ll(e.title)
        if e.det_msg:
            log.debug(e.detmsg)
        ll(e.msg)
        raise SystemExit(1)

    log(_('Output saved to'), ' ', plumber.output)

    return 0


def manual_index_strings():
    return _('''\
The options and default values for the options change depending on both the
input and output formats, so you should always check with::

    %s

Below are the options that are common to all conversion, followed by the
options specific to every input and output format.''')


if __name__ == '__main__':
    sys.exit(main())
