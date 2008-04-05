__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Convert websites into LRF files.'''

import sys, time, tempfile, shutil, os, logging, imp, inspect, re
from urlparse import urlsplit

from calibre import __appname__, setup_cli_handlers, CommandLineError
from calibre.ebooks.lrf import option_parser as lrf_option_parser
from calibre.ebooks.lrf.html.convert_from import process_file

from calibre.web.fetch.simple import create_fetcher

from calibre.ebooks.lrf.web.profiles import DefaultProfile, FullContentProfile, create_class
from calibre.ebooks.lrf.web import builtin_profiles, available_profiles
 

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
                      help='Path to a python file containing a user created profile. For help visit http://%s.kovidgoyal.net/wiki/UserProfiles'%__appname__)
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
    parser.add_option('--keep-downloaded-files', default=False, action='store_true',
                      help='''Do not delete the downloaded files after creating the LRF''')
    return parser
    
def fetch_website(options, logger):
    tdir = tempfile.mkdtemp(prefix=__appname__+'_', suffix='_web2lrf')
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
        
        if len(args) == 2 and re.search(r'class\s+\S+\(\S+\)\s*\:', args[1]):
            profile = create_class(args[1])
        else:        
            if options.user_profile is not None:
                path = os.path.abspath(options.user_profile)
                name = os.path.splitext(os.path.basename(path))[0]
                res = imp.find_module(name, [os.path.dirname(path)])
                module =  imp.load_module(name, *res)
                classes = inspect.getmembers(module, 
                    lambda x : inspect.isclass(x) and issubclass(x, DefaultProfile)\
                               and x is not DefaultProfile and x is not FullContentProfile)
                if not classes:
                    raise CommandLineError('Invalid user profile '+path)
                builtin_profiles.append(classes[0][1])
                available_profiles.append(name)
                if len(args) < 2:
                    args.append(name)
                args[1] = name
            index = -1
            if len(args) == 2:
                try:
                    if isinstance(args[1], basestring):
                        if args[1] != 'default':
                            index = available_profiles.index(args[1])
                except ValueError:
                    raise CommandLineError('Unknown profile: %s\nValid profiles: %s'%(args[1], available_profiles))
            else:
                raise CommandLineError('Only one profile at a time is allowed.')
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
        
        options.encoding = profile.encoding if options.encoding is None else options.encoding 
        
        if len(args) == 2 and args[1] != 'default':
            options.anchor_ids = False
        
        htmlfile, tdir = fetch_website(options, logger)
        options.encoding = 'utf-8'
        cwd = os.getcwdu()
        if not options.output:
            options.output = os.path.join(cwd, options.title+('.lrs' if options.lrs else '.lrf'))
        if not os.path.isabs(options.output):
            options.output = os.path.join(cwd, options.output)
        
        option_parser().parse_args(profile.html2lrf_options, options)
            
        try:
            os.chdir(os.path.dirname(htmlfile))
            create_lrf(os.path.basename(htmlfile), options, logger)
        finally:
            os.chdir(cwd)
    finally:
        try:
            profile.cleanup()
        except:
            pass
        if tdir and os.path.isdir(tdir):
            if options.keep_downloaded_files:
                print 'Downloaded files in ', tdir
            else:
                shutil.rmtree(tdir)
    

def main(args=sys.argv, logger=None):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) > 2 or (len(args) == 1 and not options.user_profile):
        parser.print_help()
        return 1
    try:
        process_profile(args, options, logger=logger)
    except CommandLineError, err:
        print >>sys.stderr, err         
    return 0

if __name__ == '__main__':
    sys.exit(main())