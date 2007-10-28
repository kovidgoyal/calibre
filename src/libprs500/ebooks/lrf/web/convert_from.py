##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
'''Convert known websites into LRF files.'''

import sys, time, tempfile, shutil, os, logging, imp, inspect
from urlparse import urlsplit

from libprs500 import __appname__, setup_cli_handlers, CommandLineError
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.lrf.html.convert_from import process_file

from libprs500.web.fetch.simple import create_fetcher

from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.lrf.web.profiles.nytimes import NYTimes
from libprs500.ebooks.lrf.web.profiles.bbc import BBC
from libprs500.ebooks.lrf.web.profiles.newsweek import Newsweek

builtin_profiles   = [NYTimes, BBC, Newsweek]
available_profiles = [i.__module__.rpartition('.')[2] for i in builtin_profiles] 

def option_parser():
    parser = lrf_option_parser(usage='''%prog [options] website_profile\n\n'''
                          '''%prog downloads a site from the web and converts it '''
                          '''into a LRF file for use with the SONY Reader. '''
                          '''website_profile is one of '''+str(available_profiles)+\
                          ''' If you specify a website_profile of default or do not specify '''
                          '''it, you must specify the --url option.'''
                          )
    
    parser.add_option('-u', '--url', dest='url', default=None,  
                      help='The URL to download. You only need to specify this if you are not specifying a website_profile.')
    parser.add_option('--user-profile', default=None,
                      help='Path to a python file containing a user created profile. For help visit http://libprs500.kovidgoyal.net/wiki/UserProfiles')
    parser.add_option('--username', dest='username', default=None, 
                      help='Specify the username to be used while downloading. Only used if the profile supports it.')
    parser.add_option('--password', dest='password', default=None,
                      help='Specify the password to be used while downloading. Only used if the profile supports it.')
    parser.add_option('--timeout', help='Timeout in seconds to wait for a response from the server. Default: %d s'%DefaultProfile.timeout,
                      default=None, type='int', dest='timeout')
    parser.add_option('-r', '--max-recursions', help='Maximum number of levels to recurse i.e. depth of links to follow. Default %d'%DefaultProfile.timeout,
                      default=None, type='int', dest='max_recursions')
    parser.add_option('-n', '--max-files', default=None, type='int', dest='max_files',
                      help='The maximum number of files to download. This only applies to files from <a href> tags. Default is %d'%DefaultProfile.timeout)
    parser.add_option('--delay', default=None, dest='delay', type='int',
                      help='Minimum interval in seconds between consecutive fetches. Default is %d s'%DefaultProfile.timeout)
    parser.add_option('--dont-download-stylesheets', action='store_true', default=None,
                      help='Do not download CSS stylesheets.', dest='no_stylesheets')    
    
    parser.add_option('--match-regexp', dest='match_regexps', default=[], action='append',
                      help='Only links that match this regular expression will be followed. This option can be specified multiple times, in which case as long as a link matches any one regexp, it will be followed. By default all links are followed.')
    parser.add_option('--filter-regexp', default=[], action='append', dest='filter_regexps',
                      help='Any link that matches this regular expression will be ignored. This option can be specified multiple times, in which case as long as any regexp matches a link, it will be ignored.By default, no links are ignored. If both --filter-regexp and --match-regexp are specified, then --filter-regexp is applied first.')
    return parser
    
def fetch_website(options, logger):
    tdir = tempfile.mkdtemp(prefix=__appname__+'_' )
    options.dir = tdir
    fetcher = create_fetcher(options, logger)
    fetcher.preprocess_regexps = options.preprocess_regexps
    return fetcher.start_fetch(options.url), tdir
    
def create_lrf(htmlfile, options, logger):
    if not options.author or options.author.lower() == 'unknown':
        options.author = __appname__
    options.header = True
    if options.output:
        options.output = os.path.abspath(os.path.expanduser(options.output))
    else:
        options.output = os.path.abspath(os.path.expanduser(options.title + ('.lrs' if options.lrs else '.lrf')))
        
    process_file(htmlfile, options, logger)

def process_profile(args, options, logger=None):
    tdir = None
    try:
        if logger is None:
            level = logging.DEBUG if options.verbose else logging.INFO
            logger = logging.getLogger('web2lrf')
            setup_cli_handlers(logger, level)
        index = -1
        if options.user_profile is not None:
            path = os.path.abspath(options.user_profile)
            name = os.path.splitext(os.path.basename(path))[0]
            res = imp.find_module(name, [os.path.dirname(path)])
            module =  imp.load_module(name, *res)
            classes = inspect.getmembers(module, 
                lambda x : inspect.isclass(x) and issubclass(x, DefaultProfile)\
                           and x is not DefaultProfile)
            if not classes:
                raise CommandLineError('Invalid user profile '+path)
            builtin_profiles.append(classes[0][1])
            available_profiles.append(name)
            if len(args) < 2:
                args.append('')
            args[1] = name
        if len(args) == 2:
            try:
                index = available_profiles.index(args[1])
            except ValueError:
                raise CommandLineError('Unknown profile: %s\nValid profiles: %s'%(args[1], available_profiles))
        profile = DefaultProfile if index == -1 else builtin_profiles[index]
        profile = profile(logger, options.verbose, options.username, options.password)
        if profile.browser is not None:
            options.browser = profile.browser
        
        for opt in ('url', 'timeout', 'max_recursions', 'max_files', 'delay', 'no_stylesheets'):
            val = getattr(options, opt)
            if val is None:
                setattr(options, opt, getattr(profile, opt))
        
        if not options.url:
            options.url = profile.url            
        
        if not options.url:
            raise CommandLineError('You must specify the --url option or a profile from one of: %s'%(available_profiles,))
        
        if not options.title:
            title = profile.title
            if not title:
                title = urlsplit(options.url).netloc
            options.title = title + time.strftime(profile.timefmt, time.localtime())
        
        options.match_regexps += profile.match_regexps
        options.preprocess_regexps = profile.preprocess_regexps
        options.filter_regexps += profile.filter_regexps
        if len(args) == 2 and args[1] != 'default':
            options.anchor_ids = False
        
        htmlfile, tdir = fetch_website(options, logger)
        create_lrf(htmlfile, options, logger)
    finally:
        if tdir and os.path.isdir(tdir):
            shutil.rmtree(tdir)
    

def main(args=sys.argv, logger=None):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) > 2:
        parser.print_help()
        return 1
    try:
        process_profile(args, options, logger=logger)
    except CommandLineError, err:
        print >>sys.stderr, err         
    return 0

if __name__ == '__main__':
    sys.exit(main())