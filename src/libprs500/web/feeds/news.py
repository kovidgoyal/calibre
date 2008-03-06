#!/usr/bin/env  python

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
'''
The backend to parse feeds and create HTML that can then be converted
to an ebook.
'''
import logging

from libprs500 import browser

class BasicNewsRecipe(object):
    '''
    Abstract base class that contains logic needed in all feed fetchers.
    '''
    
    #: The title to use for the ebook
    #: @type: string    
    title                 = 'Unknown News Source'    
    
    #: Maximum number of articles to download from each feed
    #: @type: integer
    max_articles_per_feed = 100
    
    #: Oldest article to download from this news source. In days.
    #: @type: float
    oldest_article = 7.0 
    
    #: Number of levels of links to follow on webpages that are linked
    #: to by the feed.
    #: @type: integer
    recursions        = 0
    
    #: Delay between consecutive downloads in seconds
    #: @type: integer
    delay                 = 0
    
    #: Timeout for fetching files from server in seconds
    #: @type: integer
    timeout               = 10
    
    #: The format string for the date shown on the first page
    #: By default: Day Name Day Number Month Name Year
    #: @type: string
    timefmt               = ' [%a %d %b %Y]'
    
    #: Max number of characters in the short description.
    #: @type: integer
    summary_length        = 500
    
    #: If True stylesheets are not downloaded and processed
    #: Convenient flag to disable loading of stylesheets for websites
    #: that have overly complex stylesheets unsuitable for conversion
    #: to ebooks formats
    #: @type: boolean
    no_stylesheets        = False
    
    #: If True the GUI will ask the user for a username and password 
    #: to use while downloading
    #: @type: boolean
    needs_subscription    = False
    
    #: Specify an override encoding for sites that have an incorrect
    #: charset specification. The most common being specifying latin1 and
    #: using cp1252. If None, try to detect the encoding. 
    encoding = None
    
    #: List of regular expressions that determines which links to follow
    #: If empty, it is ignored.
    #: Only one of L{match_regexps} or L{filter_regexps} should be defined
    #: @type: list of strings
    match_regexps         = []
    
    #: List of regular expressions that determines which links to ignore
    #: If empty it is ignored
    #: Only one of L{match_regexps} or L{filter_regexps} should be defined
    #: @type: list of strings
    filter_regexps        = []
    
    #: List of options to pass to html2lrf, to customize generation of LRF ebooks.
    #: @type: list of strings
    html2lrf_options   = []
    
    #: List of regexp substitution rules to run on the downloaded HTML. Each element of the 
    #: list should be a two element tuple. The first element of the tuple should
    #: be a compiled regular expression and the second a callable that takes
    #: a single match object and returns a string to replace the match.
    #: @type: list of tuples
    preprocess_regexps = []
    
    # See the built-in profiles for examples of these settings.
    
    def get_feeds(self):
        '''
        Return a list of RSS feeds to fetch for this profile. Each element of the list
        must be a 2-element tuple of the form (title, url). If title is None or an
        empty string, the title from the feed is used.
        '''
        if not self.feeds:
            raise NotImplementedError
        return self.feeds
    
    @classmethod
    def print_version(cls, url):
        '''
        Take a URL pointing to an article and returns the URL pointing to the
        print version of the article.
        '''
        raise NotImplementedError
    
    @classmethod
    def get_browser(cls):
        '''
        Return a browser instance used to fetch documents from the web.
        
        If your profile requires that you login first, override this method
        in your subclass. See for example the nytimes profile.
        '''
        return browser()
    
    def __init__(self, options, parser, progress_reporter):
        '''
        Initialize the recipe.
        @param options: Parsed commandline options 
        @param parser:  Command line option parser. Used to intelligently merge options.
        @param progress_reporter: A Callable that takes two arguments: progress (a number between 0 and 1) and a string message. The message should be optional.
        '''
        for attr in ('username', 'password', 'lrf'):
            setattr(self, attr, getattr(options, attr))
        self.logger = logging.getLogger('feeds2disk')
        self.report_progress = progress_reporter
        
        self.username = self.password = None
        #: If True optimize downloading for eventual conversion to LRF
        self.lrf = False
        defaults = parser.get_default_values()
        
        for opt in options.__dict__.keys():
            if getattr(options, opt) != getattr(defaults, opt):
                setattr(self, opt, getattr(options, opt))
        
        if isinstance(self.feeds, basestring):
            self.feeds = eval(self.feeds)
            if isinstance(self.feeds, basestring):
                self.feeds = [self.feeds]
            
        if self.needs_subscription and (self.username is None or self.password is None):
            raise ValueError('The %s recipe needs a username and password.'%self.title)
        
    def download(self):
        self.report_progress(0, 'Starting download...')
        return self.build_index()
    
    def build_index(self):
        self.parse_feeds()
        
    def parse_feeds(self):
        '''
        Create list of articles from a list of feeds.
        @rtype: list
        @return: A list whose items are 2-tuples C{('feed title', articles)}, 
        where C{articles} is a list of dictionaries each of the form::
            {
            'title'       : article title,
            'url'         : URL of print version,
            'date'        : The publication date of the article as a string,
            'description' : A summary of the article
            'content'     : The full article (can be an empty string). This is used by FullContentProfile
            }
        '''
