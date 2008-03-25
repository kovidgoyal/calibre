#!/usr/bin/env  python 
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''''''

import sys, os, logging
from libprs500.web.feeds.recipes import get_builtin_recipe, compile_recipe, titles
from libprs500.web.fetch.simple import option_parser as _option_parser
from libprs500.web.feeds.news import Profile2Recipe, BasicNewsRecipe
from libprs500.ebooks.lrf.web.profiles import DefaultProfile, FullContentProfile


def option_parser(usage='''\
%%prog [options] ARG

%%prog parses an online source of articles, like an RSS or ATOM feed and 
fetches the article contents organized in a nice hierarchy.

ARG can be one of:

file name            - %%prog will try to load a recipe from the file

builtin recipe title - %%prog will load the builtin recipe and use it to fetch the feed. For e.g. Newsweek or "The BBC" or "The New York Times"

recipe as a string   - %%prog will load the recipe directly from the string arg.

Available builtin recipes are:
%s
'''%(unicode(list(titles))[1:-1])):
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
    p.add_option('--no-progress-bar', dest='progress_bar', default=True, action='store_false',
                 help=_('Dont show the progress bar'))
    p.add_option('--debug', action='store_true', default=False,
                 help=_('Very verbose output, useful for debugging.'))
    p.add_option('--test', action='store_true', default=False, 
                 help=_('Useful for recipe development. Forces max_articles_per_feed to 2 and downloads at most 2 feeds.'))
    
    return p
    
def simple_progress_bar(percent, msg):
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8', 'ignore')
    if not msg:
        print '%d%%'%(percent*100),
    else:
        print '%d%%'%(percent*100), msg
    sys.stdout.flush()
    
def no_progress_bar(percent, msg):
    print msg

class RecipeError(Exception):
    pass

def run_recipe(opts, recipe_arg, parser, notification=None, handler=None):
    if notification is None:
        from libprs500.terminfo import TerminalController, ProgressBar
        term = TerminalController(sys.stdout)
        if opts.progress_bar:
            try:
                pb = ProgressBar(term, _('Fetching feeds...'))
                notification = pb.update
            except ValueError:
                notification = simple_progress_bar
                print _('Fetching feeds...')
        else:
            notification = no_progress_bar
        
    
    recipe, is_profile = None, False
    if opts.feeds is not None:
        recipe = BasicNewsRecipe
    else:
        try:
            if os.access(recipe_arg, os.R_OK):
                try:
                    recipe = compile_recipe(open(recipe_arg).read())
                    is_profile = DefaultProfile in recipe.__bases__ or \
                                 FullContentProfile in recipe.__bases__
                except:
                    import traceback
                    traceback.print_exc()
                    return 1
            else:
                raise Exception('not file')
        except:
            recipe, is_profile = get_builtin_recipe(recipe_arg)
            if recipe is None:
                recipe = compile_recipe(recipe_arg)
                is_profile = DefaultProfile in recipe.__bases__  or \
                                 FullContentProfile in recipe.__bases__
    
    if recipe is None:
        raise RecipeError(recipe_arg+ ' is an invalid recipe')
        
    
    if handler is None:
        from libprs500 import ColoredFormatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG if opts.debug else logging.INFO if opts.verbose else logging.WARN)
        handler.setFormatter(ColoredFormatter('%(levelname)s: %(message)s\n')) # The trailing newline is need because of the progress bar
        logging.getLogger('feeds2disk').addHandler(handler)
    
    if is_profile:
        recipe = Profile2Recipe(recipe, opts, parser, notification)
    else:
        recipe = recipe(opts, parser, notification)
    
    if not os.path.exists(recipe.output_dir):
        os.makedirs(recipe.output_dir)
    recipe.download()
    
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
