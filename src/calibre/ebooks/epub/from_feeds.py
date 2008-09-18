from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert periodical content into EPUB ebooks.
'''
import sys, glob, os
from calibre.web.feeds.main import config as feeds2disk_config, USAGE, run_recipe
from calibre.ebooks.epub.from_html import config as html2epub_config
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.epub.from_html import convert as html2epub
from calibre import strftime, sanitize_file_name

def config(defaults=None):
    c = feeds2disk_config(defaults=defaults)
    c.remove('lrf')
    c.remove('epub')
    c.remove('output_dir')
    c.update(html2epub_config(defaults=defaults))
    c.remove('chapter_mark')
    return c

def option_parser():
    c = config()
    return c.option_parser(usage=USAGE)

def convert(opts, recipe_arg, notification=None):
    opts.lrf  = False
    opts.epub = True
    opts.chapter_mark = 'none'
    if opts.debug:
        opts.verbose = 2
    parser = option_parser()
    with TemporaryDirectory('_feeds2epub') as tdir:
        opts.output_dir = tdir
        recipe = run_recipe(opts, recipe_arg, parser, notification=notification)
        c = config()
        recipe_opts = c.parse_string(recipe.html2epub_options)
        c.smart_update(recipe_opts, opts)
        opts = recipe_opts
        opf = glob.glob(os.path.join(tdir, '*.opf'))
        if not opf:
            raise Exception('Downloading of recipe: %s failed'%recipe_arg)
        opf = opf[0]
        
        if opts.output is None:
            fname = recipe.title + strftime(recipe.timefmt) + '.epub'
            opts.output = os.path.join(os.getcwd(), sanitize_file_name(fname))
        
        print 'Generating epub...'
        html2epub(opf, opts, notification=notification)
    

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2 and opts.feeds is None:
        parser.print_help()
        return 1
    recipe_arg = args[1] if len(args) > 1 else None
    convert(opts, recipe_arg)
        
    return 0

if __name__ == '__main__':
    sys.exit(main())