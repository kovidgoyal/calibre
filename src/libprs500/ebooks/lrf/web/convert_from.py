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

import sys, time, tempfile, shutil, os, logging
from urlparse import urlsplit

from libprs500 import __appname__, setup_cli_handlers, CommandLineError
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.lrf.html.convert_from import process_file
from libprs500.ebooks.lrf.web.profiles import profiles
from libprs500.web.fetch.simple import create_fetcher

available_profiles = profiles.keys()
available_profiles.remove('default')
available_profiles = ' '.join(available_profiles)

def option_parser():
    parser = lrf_option_parser(usage='''%prog [options] website_profile\n\n'''
                          '''%prog downloads a site from the web and converts it '''
                          '''into a LRF file for use with the SONY Reader. '''
                          '''website_profile is one of '''+available_profiles+\
                          ''' If you specify a website_profile of default or do not specify '''
                          '''it, you must specify the --url option.'''
                          )
    
    parser.add_option('-u', '--url', dest='url', default=None,  
                      help='The URL to download. You only need to specify this if you are not specifying a website_profile.')
    
    parser.add_option('--timeout', help='Timeout in seconds to wait for a response from the server. Default: %default s',
                      default=None, type='int', dest='timeout')
    parser.add_option('-r', '--max-recursions', help='Maximum number of levels to recurse i.e. depth of links to follow. Default %default',
                      default=None, type='int', dest='max_recursions')
    parser.add_option('-n', '--max-files', default=None, type='int', dest='max_files',
                      help='The maximum number of files to download. This only applies to files from <a href> tags. Default is %default')
    parser.add_option('--delay', default=None, dest='delay', type='int',
                      help='Minimum interval in seconds between consecutive fetches. Default is %default s')
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
    if not options.author:
        options.author = __appname__
    options.header = True
    if options.output:
        options.output = os.path.abspath(os.path.expanduser(options.output))
    else:
        options.output = os.path.abspath(os.path.expanduser(options.title + ('.lrs' if options.lrs else '.lrf')))
        
    process_file(htmlfile, options, logger)

def process_profile(args, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('web2lrf')
        setup_cli_handlers(logger, level)
    if len(args) == 2:
        if not profiles.has_key(args[1]):
            raise CommandLineError('Unknown profile: %s\nValid profiles: %s'%(args[1], profiles.keys()))
    profile = profiles[args[1]] if len(args) == 2 else profiles['default']
    
    if profile.has_key('initialize'):
        profile['initialize'](profile)
    
    for opt in ('url', 'timeout', 'max_recursions', 'max_files', 'delay', 'no_stylesheets'):
        val = getattr(options, opt)
        if val is None:
            setattr(options, opt, profile[opt])
        
    if not options.url:
        raise CommandLineError('You must specify the --url option or a profile from one of: %s', available_profiles)
    
    if not options.title:
        title = profile['title']
        if not title:
            title = urlsplit(options.url).netloc
        options.title = title + time.strftime(profile['timefmt'], time.localtime())
    
    options.match_regexps += profile['match_regexps']
    options.preprocess_regexps = profile['preprocess_regexps']
    options.filter_regexps += profile['filter_regexps']
    
    htmlfile, tdir = fetch_website(options, logger)
    create_lrf(htmlfile, options, logger)
    if profile.has_key('finalize'):
        profile['finalize'](profile)
    shutil.rmtree(tdir)

    

def main(args=sys.argv):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) > 2:
        parser.print_help()
        return 1
    try:
        process_profile(args, options)
    except CommandLineError, err:
        print >>sys.stderr, err         
    return 0

if __name__ == '__main__':
    sys.exit(main())