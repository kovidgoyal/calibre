from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert feeds to MOBI ebook
'''

import sys, glob, os
from calibre.web.feeds.main import config as feeds2disk_config, USAGE, run_recipe
from calibre.ebooks.mobi.writer import config as oeb2mobi_config, oeb2mobi
from calibre.ptempfile import TemporaryDirectory
from calibre import strftime, sanitize_file_name

def config(defaults=None):
    c = feeds2disk_config(defaults=defaults)
    c.remove('lrf')
    c.remove('epub')
    c.remove('mobi')
    c.remove('output_dir')
    c.update(oeb2mobi_config(defaults=defaults))
    c.remove('encoding')
    c.remove('source_profile')
    c.add_opt('output', ['-o', '--output'], default=None,
              help=_('Output file. Default is derived from input filename.'))
    return c

def option_parser():
    c = config()
    return c.option_parser(usage=USAGE)

def convert(opts, recipe_arg, notification=None):
    opts.lrf  = False
    opts.epub = False
    opts.mobi = True
    if opts.debug:
        opts.verbose = 2
    parser = option_parser()
    with TemporaryDirectory('_feeds2mobi') as tdir:
        opts.output_dir = tdir
        recipe = run_recipe(opts, recipe_arg, parser, notification=notification)
        c = config()
        recipe_opts = c.parse_string(recipe.oeb2mobi_options)
        c.smart_update(recipe_opts, opts)
        opts = recipe_opts
        opf = glob.glob(os.path.join(tdir, '*.opf'))
        if not opf:
            raise Exception('Downloading of recipe: %s failed'%recipe_arg)
        opf = opf[0]
        
        if opts.output is None:
            fname = recipe.title + strftime(recipe.timefmt) + '.mobi'
            opts.output = os.path.join(os.getcwd(), sanitize_file_name(fname))
        
        print 'Generating MOBI...'
        opts.encoding = 'utf-8'
        opts.source_profile = 'Browser'
        oeb2mobi(opts, opf)
    

def main(args=sys.argv, notification=None, handler=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2 and opts.feeds is None:
        parser.print_help()
        return 1
    recipe_arg = args[1] if len(args) > 1 else None
    convert(opts, recipe_arg, notification=notification)
        
    return 0

if __name__ == '__main__':
    sys.exit(main())