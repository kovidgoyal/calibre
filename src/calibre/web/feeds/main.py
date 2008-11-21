#!/usr/bin/env  python 
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
CLI for downloading feeds.
'''

import sys, os, logging
from calibre.web.feeds.recipes import get_builtin_recipe, compile_recipe, titles
from calibre.web.fetch.simple import option_parser as _option_parser
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.utils.config import Config, StringConfig

def config(defaults=None):
    desc = _('Options to control the fetching of periodical content from the web.')
    c = Config('feeds2disk', desc) if defaults is None else StringConfig(defaults, desc)
    
    web2disk = c.add_group('web2disk', _('Customize the download engine'))
    web2disk('timeout', ['-t', '--timeout'], default=10.0, 
              help=_('Timeout in seconds to wait for a response from the server. Default: %default s'),)
    web2disk('delay', ['--delay'], default=0, 
              help=_('Minimum interval in seconds between consecutive fetches. Default is %default s'))
    web2disk('encoding', ['--encoding'], default=None, 
              help=_('The character encoding for the websites you are trying to download. The default is to try and guess the encoding.'))
    web2disk('match_regexps', ['--match-regexp'], default=[], action='append',
              help=_('Only links that match this regular expression will be followed. This option can be specified multiple times, in which case as long as a link matches any one regexp, it will be followed. By default all links are followed.'))
    web2disk('filter_regexps', ['--filter-regexp'], default=[], action='append',
              help=_('Any link that matches this regular expression will be ignored. This option can be specified multiple times, in which case as long as any regexp matches a link, it will be ignored.By default, no links are ignored. If both --filter-regexp and --match-regexp are specified, then --filter-regexp is applied first.'))
    web2disk('no_stylesheets', ['--dont-download-stylesheets'], action='store_true', default=False,
              help=_('Do not download CSS stylesheets.'))
    
    c.add_opt('feeds', ['--feeds'], default=None,
                 help=_('''Specify a list of feeds to download. For example: 
"['http://feeds.newsweek.com/newsweek/TopNews', 'http://feeds.newsweek.com/headlines/politics']"
If you specify this option, any argument to %prog is ignored and a default recipe is used to download the feeds.'''))
    c.add_opt('verbose', ['-v', '--verbose'], default=0, action='count',
                 help=_('''Be more verbose while processing.'''))
    c.add_opt('title', ['--title'], default=None,
                 help=_('The title for this recipe. Used as the title for any ebooks created from the downloaded feeds.'))
    c.add_opt('username', ['-u', '--username'], default=None, 
                 help=_('Username for sites that require a login to access content.'))
    c.add_opt('password', ['-p', '--password'], default=None, 
                 help=_('Password for sites that require a login to access content.'))
    c.add_opt('lrf', ['--lrf'], default=False, action='store_true', 
                 help='Optimize fetching for subsequent conversion to LRF.')
    c.add_opt('epub', ['--epub'], default=False, action='store_true', 
                 help='Optimize fetching for subsequent conversion to EPUB.')
    c.add_opt('recursions', ['--recursions'], default=0,
                 help=_('Number of levels of links to follow on webpages that are linked to from feeds. Defaul %default'))
    c.add_opt('output_dir', ['--output-dir'], default='.', 
                 help=_('The directory in which to store the downloaded feeds. Defaults to the current directory.'))
    c.add_opt('no_progress_bar', ['--no-progress-bar'], default=False, action='store_true',
                 help=_("Don't show the progress bar"))
    c.add_opt('debug', ['--debug'], action='store_true', default=False,
                 help=_('Very verbose output, useful for debugging.'))
    c.add_opt('test', ['--test'], action='store_true', default=False, 
                 help=_('Useful for recipe development. Forces max_articles_per_feed to 2 and downloads at most 2 feeds.'))
    
    return c
    
USAGE=_('''\
%%prog [options] ARG

%%prog parses an online source of articles, like an RSS or ATOM feed and 
fetches the article contents organized in a nice hierarchy.

ARG can be one of:

file name            - %%prog will try to load a recipe from the file

builtin recipe title - %%prog will load the builtin recipe and use it to fetch the feed. For e.g. Newsweek or "The BBC" or "The New York Times"

recipe as a string   - %%prog will load the recipe directly from the string arg.

Available builtin recipes are:
%s
''')%(unicode(list(titles))[1:-1])

def option_parser(usage=USAGE):
    p = _option_parser(usage=usage)
    p.remove_option('--max-recursions')
    p.remove_option('--base-dir')
    p.remove_option('--verbose')
    p.remove_option('--max-files')
    p.subsume('WEB2DISK OPTIONS', _('Options to control web2disk (used to fetch websites linked from feeds)'))
    
    p.add_option('--feeds', default=None,
                 help=_('''Specify a list of feeds to download. For example: 
"['http://feeds.newsweek.com/newsweek/TopNews', 'http://feeds.newsweek.com/headlines/politics']"
If you specify this option, any argument to %prog is ignored and a default recipe is used to download the feeds.'''))
    p.add_option('--verbose', default=False, action='store_true',
                 help=_('''Be more verbose while processing.'''))
    p.add_option('--title', default=None,
                 help=_('The title for this recipe. Used as the title for any ebooks created from the downloaded feeds.'))
    p.add_option('--username', default=None, help=_('Username for sites that require a login to access content.'))
    p.add_option('--password', default=None, help=_('Password for sites that require a login to access content.'))
    p.add_option('--lrf', default=False, action='store_true', help='Optimize fetching for subsequent conversion to LRF.')
    p.add_option('--recursions', default=0, type='int',
                 help=_('Number of levels of links to follow on webpages that are linked to from feeds. Defaul %default'))
    p.add_option('--output-dir', default=os.getcwd(), 
                 help=_('The directory in which to store the downloaded feeds. Defaults to the current directory.'))
    p.add_option('--no-progress-bar', dest='no_progress_bar', default=False, action='store_true',
                 help=_('Dont show the progress bar'))
    p.add_option('--debug', action='store_true', default=False,
                 help=_('Very verbose output, useful for debugging.'))
    p.add_option('--test', action='store_true', default=False, 
                 help=_('Useful for recipe development. Forces max_articles_per_feed to 2 and downloads at most 2 feeds.'))
    
    return p
    
class RecipeError(Exception):
    pass

def run_recipe(opts, recipe_arg, parser, notification=None, handler=None):
    if notification is None:
        from calibre.utils.terminfo import TerminalController, ProgressBar
        term = TerminalController(sys.stdout)
        pb = ProgressBar(term, _('Fetching feeds...'), no_progress_bar=opts.no_progress_bar)
        notification = pb.update
    
    recipe = None
    if opts.feeds is not None:
        recipe = BasicNewsRecipe
    else:
        try:
            if os.access(recipe_arg, os.R_OK):
                recipe = compile_recipe(open(recipe_arg).read())                
            else:
                raise Exception('not file')
        except:
            recipe = get_builtin_recipe(recipe_arg)
            if recipe is None:
                recipe = compile_recipe(recipe_arg)
    
    if recipe is None:
        raise RecipeError(recipe_arg+ ' is an invalid recipe')
        
    
    if handler is None:
        from calibre import ColoredFormatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG if opts.debug else logging.INFO if opts.verbose else logging.WARN)
        handler.setFormatter(ColoredFormatter('%(levelname)s: %(message)s\n')) # The trailing newline is need because of the progress bar
        logging.getLogger('feeds2disk').addHandler(handler)
    
    recipe = recipe(opts, parser, notification)
    
    if not os.path.exists(recipe.output_dir):
        os.makedirs(recipe.output_dir)
    recipe.download(for_lrf=True)
    
    return recipe

def main(args=sys.argv, notification=None, handler=None):
    p = option_parser()
    opts, args = p.parse_args(args=args[1:])
    
    if len(args) != 1 and opts.feeds is None:
        p.print_help()
        return 1
    recipe_arg = args[0] if len(args) > 0 else None
    run_recipe(opts, recipe_arg, p, notification=notification, handler=handler)    
            
    return 0

if __name__ == '__main__':
    sys.exit(main())
