from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Command line interface to conversion sub-system
'''

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
options. the available options depend on the input and output file types. \
To get help on them specify the input and output file and then use the -h \
option.

For full documentation of the conversion system see
''') + 'http://calibre.kovidgoyal.net/user_manual/conversion.html'

import sys, os
from optparse import OptionGroup, Option

from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.customize.conversion import OptionRecommendation

def print_help(parser, log):
    help = parser.format_help().encode(preferred_encoding, 'replace')
    log(help)

def check_command_line_options(parser, args, log):
    if len(args) < 3 or args[1].startswith('-') or args[2].startswith('-'):
        print_help(parser)
        log.error('\n\nYou must specify the input AND output files')
        raise SystemExit(1)

    input = os.path.abspath(args[1])
    if not os.access(input, os.R_OK):
        log.error('Cannot read from', input)
        raise SystemExit(1)

    output = args[2]
    if output.startswith('.'):
        output = os.path.splitext(os.path.basename(input))[0]+output
    output = os.path.abspath(output)

    if '.' in output:
        if os.path.exists(output):
            log.warn('WARNING:', output, 'exists. Deleting.')
            os.remove(output)

    return input, output

def option_recommendation_to_cli_option(add_option, rec):
    opt = rec.option
    switches = ['-'+opt.short_switch] if opt.short_switch else []
    switches.append('--'+opt.long_switch)
    attrs = dict(dest=opt.name, help=opt.help,
                     choices=opt.choices, default=rec.recommended_value)
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
                      'base_font_size',
                      'font_size_mapping',
                      'line_height',
                      'linearize_tables',
                  ]
                  ),

              'METADATA' : (_('Options to set metadata in the output'),
                            plumber.metadata_option_names,
                            ),
              'DEBUG': (_('Options to help with debugging the conversion'),
                        [
                         'verbose',
                         ]),


              }

    group_order = ['', 'LOOK AND FEEL', 'METADATA', 'DEBUG']

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

def option_parser():
    return OptionParser(usage=USAGE)

def main(args=sys.argv):
    log = Log()
    parser = option_parser()
    if len(args) < 3:
        print_help(parser, log)
        return 1

    input, output = check_command_line_options(parser, args, log)

    from calibre.ebooks.conversion.plumber import Plumber

    plumber = Plumber(input, output, log)
    add_input_output_options(parser, plumber)
    add_pipeline_options(parser, plumber)

    opts = parser.parse_args(args)[0]
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
