#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
'''
import sys, os
from calibre.ebooks.lrf.comic.convert_from import do_convert, option_parser, \
                        ProgressBar, terminal_controller
from calibre.ebooks.mobi.from_any import config, any2mobi
from calibre.ptempfile import PersistentTemporaryFile


def convert(path_to_file, opts, notification=lambda m, p: p):
    pt = PersistentTemporaryFile('_comic2mobi.epub')
    pt.close()
    orig_output = opts.output
    opts.output = pt.name
    do_convert(path_to_file, opts, notification=notification, output_format='epub')
    opts = config('').parse()
    if orig_output is None:
        orig_output = os.path.splitext(path_to_file)[0]+'.mobi'
    opts.output = orig_output
    any2mobi(opts, pt.name)

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print '\nYou must specify a file to convert'
        return 1
    
    pb = ProgressBar(terminal_controller, _('Rendering comic pages...'), 
                     no_progress_bar=opts.no_progress_bar or getattr(opts, 'no_process', False))
    notification = pb.update
    
    source = os.path.abspath(args[1])
    convert(source, opts, notification=notification)
    return 0

if __name__ == '__main__':
    sys.exit(main())