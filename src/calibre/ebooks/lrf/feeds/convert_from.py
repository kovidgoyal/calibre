from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Convert web feeds to LRF files.
'''
from calibre.ebooks.lrf import option_parser as lrf_option_parser
from calibre.ebooks.lrf.html.convert_from import process_file
from calibre.web.feeds.main import option_parser as feeds_option_parser
from calibre.web.feeds.main import run_recipe
from calibre.ptempfile import TemporaryDirectory
from calibre import sanitize_file_name, strftime
from calibre.ebooks import ConversionError

import sys, os

def option_parser():
    parser = feeds_option_parser()
    parser.remove_option('--output-dir')
    parser.remove_option('--lrf')
    parser.subsume('FEEDS2DISK OPTIONS', _('Options to control the behavior of feeds2disk'))
    lrf_parser = lrf_option_parser('')
    lrf_parser.subsume('HTML2LRF OPTIONS', _('Options to control the behavior of html2lrf'))
    parser.merge(lrf_parser)
    return parser

def main(args=sys.argv, notification=None, handler=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    opts.lrf = True
    
    if len(args) != 2 and opts.feeds is None:
        parser.print_help()
        return 1
    
    recipe_arg = args[1] if len(args) > 1 else None
    
    with TemporaryDirectory('_feeds2lrf') as tdir:
        opts.output_dir = tdir
        
        recipe = run_recipe(opts, recipe_arg, parser, notification=notification, handler=handler)
        
        htmlfile = os.path.join(tdir, 'index.html')
        if not os.access(htmlfile, os.R_OK):
            raise RuntimeError(_('Fetching of recipe failed: ')+recipe_arg)
        
        lparser = lrf_option_parser('')
        ropts = lparser.parse_args(['html2lrf']+recipe.html2lrf_options)[0]
        parser.merge_options(ropts, opts)
        
        if not opts.output:
            ext = '.lrs' if opts.lrs else '.lrf'
            fname = recipe.title + strftime(recipe.timefmt)+ext
            opts.output = os.path.join(os.getcwd(), sanitize_file_name(fname))
        print 'Generating LRF...'
        process_file(htmlfile, opts)
        if os.stat(opts.output).st_size < 100: # This can happen if the OS runs out of file handles
            raise ConversionError(_('Failed to convert downloaded recipe: ')+recipe_arg)
    return 0

if __name__ == '__main__':
    sys.exit(main())
