#!/usr/bin/env  python
from libprs500.web.feeds.news import BasicNewsRecipe

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
''''''

import sys, os
from libprs500.web.recipes import get_feed, compile_recipe
from libprs500.web.fetch.simple import option_parser as _option_parser


def option_parser(usage='''\
%prog [options] ARG

%prog parsers an online source of articles, like an RSS or ATOM feed and 
fetches the article contents organized in a nice hierarchy.

ARG can be one of:
file name            - %prog will try to load a recipe from the file
builtin recipe title - %prog will load the builtin recipe and use it to fetch the feed. For e.g. Newsweek or "The BBC" or "The New York Times"
recipe as a string   - $prog will load the recipe directly from the string arg.
'''):
    p = _option_parser(usage=usage)
    p.remove_option('--max-recursions')
    p.remove_option('--base-dir')
    p.remove_option('--verbose')
    p.remove_option('--max-files')
    p.subsume('WEB2DISK OPTIONS', 'Options to control web2disk (used to fetch websites linked from feeds)')
    
    p.add_option('--feeds', default=None,
                 help=_('''Specify a list of feeds to download. For example: 
"['http://feeds.newsweek.com/newsweek/TopNews', 'http://feeds.newsweek.com/headlines/politics']"
If you specify this option, any argument to %prog is ignored and a default recipe is used to download the feeds.'''))
    p.add_option('--verbose', default=False, action='store_true',
                 help=_('''Be more verbose while processing.'''))
    p.add_option('--username', default=None, help=_('Username for sites that require a login to access content.'))
    p.add_option('--password', default=None, help=_('Password for sites that require a login to access content.'))
    p.add_option('--lrf', default=False, action='store_true', help='Optimize fetching for subsequent conversion to LRF.')
    p.add_option('--recursions', default=0, type='int',
                 help=_('Number of levels of links to follow on webpages that are linked to from feeds. Defaul %default'))
    
    return p
    
def simple_progress_bar(*args):
    print '%d%%'%(args[0]*100),
    sys.stdout.flush()

def main(args=sys.argv, notification=None):
    p = option_parser()
    opts, args = p.parse_args(args)
    
    if notification is None:
        from libprs500.terminfo import TerminalController, ProgressBar
        term = TerminalController(sys.stdout)
        try:
            pb = ProgressBar(term, _('Fetching feeds...'))
            notification = pb.update
        except ValueError:
            notification = simple_progress_bar
            print _('Fetching feeds...')
        
    if len(args) != 2:
        p.print_help()
        return 1
    
    recipe = None
    if opts.feeds is not None:
        recipe = BasicNewsRecipe
    else:
        try:
            if os.access(args[1], os.R_OK):
                recipe = compile_recipe(open(args[1]).read())
            else:
                raise Exception('')
        except:
            recipe = get_feed(args[1])
            if recipe is None:
                recipe = compile_recipe(args[1])
    
    if recipe is None:
        p.print_help()
        print
        print args[1], 'is an invalid recipe'
        return 1
    
    recipe = recipe(opts, p, notification)
    index  = recipe.download()
     

    
    return 0

if __name__ == '__main__':
    sys.exit(main())
