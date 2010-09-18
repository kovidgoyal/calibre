from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Command line interface to conversion sub-system
'''

import sys, os
from optparse import OptionGroup, Option

from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.customize.conversion import OptionRecommendation
from calibre import patheq

USAGE = '%prog ' + _('''\
input_file output_file [options]

Convert an ebook from one format to another.

input_file is the input and output_file is the output. Both must be \
specified as the first two arguments to the command.

The output ebook format is guessed from the file extension of \
output_file. output_file can also be of the special format .EXT where \
EXT is the output file extension. In this case, the name of the output \
file is derived the name of the input file. Note that the filenames must \
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
''') + 'http://calibre-ebook.com/user_manual/conversion.html'

def print_help(parser, log):
    help = parser.format_help().encode(preferred_encoding, 'replace')
    log(help)

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

    output = args[2]
    if output.startswith('.') and output != '.':
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
    add_option(Option(*switches, **attrs))

def add_input_output_options(parser, plumber):
    input_options, output_options = \
                                plumber.input_options, plumber.output_options

    def add_options(group, options):
        for opt in options:
            option_recommendation_to_cli_option(group, opt)

    if input_options:
        title = _('INPUT OPTIONS')
        io = OptionGroup(parser, title, _('Options to control the processing'
                          ' of the input %s file')%plumber.input_fmt)
        add_options(io.add_option, input_options)
        parser.add_option_group(io)

    if output_options:
        title = _('OUTPUT OPTIONS')
        oo = OptionGroup(parser, title, _('Options to control the processing'
                          ' of the output %s')%plumber.output_fmt)
        add_options(oo.add_option, output_options)
        parser.add_option_group(oo)

def add_pipeline_options(parser, plumber):
    groups = {
              '' : ('',
                    [
                     'input_profile',
                     'output_profile',
                     ]
                    ),
              'LOOK AND FEEL' : (
                  _('Options to control the look and feel of the output'),
                  [
                      'base_font_size', 'disable_font_rescaling',
                      'font_size_mapping',
                      'line_height',
                      'linearize_tables',
                      'extra_css', 'smarten_punctuation',
                      'margin_top', 'margin_left', 'margin_right',
                      'margin_bottom', 'change_justification',
                      'insert_blank_line', 'remove_paragraph_spacing','remove_paragraph_spacing_indent_size',
                      'asciiize', 'remove_header', 'header_regex',
                      'remove_footer', 'footer_regex',
                  ]
                  ),

              'STRUCTURE DETECTION' : (
                  _('Control auto-detection of document structure.'),
                  [
                      'chapter', 'chapter_mark',
                      'prefer_metadata_cover', 'remove_first_image',
                      'insert_metadata', 'page_breaks_before',
                      'preprocess_html', 'html_unwrap_factor',
                  ]
                  ),

              'TABLE OF CONTENTS' : (
                  _('Control the automatic generation of a Table of Contents. By '
                  'default, if the source file has a Table of Contents, it will '
                  'be used in preference to the automatically generated one.'),
                  [
                    'level1_toc', 'level2_toc', 'level3_toc',
                    'toc_threshold', 'max_toc_links', 'no_chapters_in_toc',
                    'use_auto_toc', 'toc_filter',
                  ]
                  ),

              'METADATA' : (_('Options to set metadata in the output'),
                            plumber.metadata_option_names,
                            ),
              'DEBUG': (_('Options to help with debugging the conversion'),
                        [
                         'verbose',
                         'debug_pipeline',
                         ]),


              }

    group_order = ['', 'LOOK AND FEEL', 'STRUCTURE DETECTION',
            'TABLE OF CONTENTS', 'METADATA', 'DEBUG']

    for group in group_order:
        desc, options = groups[group]
        if group:
            group = OptionGroup(parser, group, desc)
            parser.add_option_group(group)
        add_option = group.add_option if group != '' else parser.add_option

        for name in options:
            rec = plumber.get_option_by_name(name)
            if rec.level < rec.HIGH:
                option_recommendation_to_cli_option(add_option, rec)

    parser.add_option('--list-recipes', default=False, action='store_true',
            help=_('List builtin recipes'))

def option_parser():
    return OptionParser(usage=USAGE)


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

def main(args=sys.argv):
    log = Log()
    parser, plumber = create_option_parser(args, log)
    opts = parser.parse_args(args)[0]
    for x in ('read_metadata_from_opf', 'cover'):
        if getattr(opts, x, None) is not None:
            setattr(opts, x, abspath(getattr(opts, x)))
    recommendations = [(n.dest, getattr(opts, n.dest),
                        OptionRecommendation.HIGH) \
                                        for n in parser.options_iter()
                                        if n.dest]
    plumber.merge_ui_recommendations(recommendations)

    plumber.run()

    log(_('Output saved to'), ' ', plumber.output)

    return 0

if __name__ == '__main__':
    sys.exit(main())
