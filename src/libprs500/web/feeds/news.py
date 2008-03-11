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
import logging, os, cStringIO, traceback, time
import urlparse

from libprs500 import browser
from libprs500.ebooks.BeautifulSoup import BeautifulSoup
from libprs500.web.feeds import feed_from_xml, templates
from libprs500.web.fetch.simple import option_parser as web2disk_option_parser
from libprs500.web.fetch.simple import RecursiveFetcher
from libprs500.threadpool import WorkRequest, ThreadPool, NoResultsPending


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
    
    #: Number of simultaneous downloads. Set to 1 if the server is picky.
    #: @type: integer
    simultaneous_downloads = 5
    
    #: Timeout for fetching files from server in seconds
    #: @type: integer
    timeout               = 10
    
    #: The format string for the date shown on the first page
    #: By default: Day Name Day Number Month Name Year
    #: @type: string
    timefmt               = ' %a, %d %b %Y'
    
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
    
    #: List of tags to be removed. Specified tags are removed from downloaded HTML.
    #: A tag is specified as a dictionary of the form::
    #:  {
    #:     name      : 'tag name',   #e.g. 'div'
    #:     attrs     : a dictionary, #e.g. {class: 'advertisment'}
    #:  }
    #: All keys are optional. For a full explanantion of the search criteria, see
    #: U{http://www.crummy.com/software/BeautifulSoup/documentation.html#The basic find method: findAll(name, attrs, recursive, text, limit, **kwargs)}
    #: A common example::
    #:   remove_tags = [dict(name='div', attrs={'class':'advert'})]
    #:   This will remove all <div class="advert"> tags and all their children from the downloaded HTML. 
    remove_tags = []
    
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
    
    def preprocess_html(self, soup):
        '''
        This function is called with the source of each downloaded HTML file. 
        It can be used to do arbitrarily powerful pre-processing on the HTML.
        @param soup: A U{BeautifulSoup<http://www.crummy.com/software/BeautifulSoup/documentation.html>} 
                     instance containing the downloaded HTML.
        @type soup: A U{BeautifulSoup<http://www.crummy.com/software/BeautifulSoup/documentation.html>} instance
        @return: It must return soup (after having done any needed preprocessing)
        @rtype: A U{BeautifulSoup<http://www.crummy.com/software/BeautifulSoup/documentation.html>} instance 
        '''
        return soup
    
    def cleanup(self):
        '''
        Called after all articles have been download. Use it to do any cleanup like 
        logging out of subscription sites, etc.
        '''
        pass
    
    def __init__(self, options, parser, progress_reporter):
        '''
        Initialize the recipe.
        @param options: Parsed commandline options 
        @param parser:  Command line option parser. Used to intelligently merge options.
        @param progress_reporter: A Callable that takes two arguments: progress (a number between 0 and 1) and a string message. The message should be optional.
        '''
        for attr in ('username', 'password', 'lrf', 'output_dir', 'verbose', 'debug'):
            setattr(self, attr, getattr(options, attr))
        self.output_dir = os.path.abspath(self.output_dir)
        
        self.logger = logging.getLogger('feeds2disk')
        
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            self.verbose = True
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
        
        self.browser = self.get_browser()
        self.image_map, self.image_counter = {}, 1
        
        web2disk_cmdline = [ 'web2disk', 
            '--timeout', str(self.timeout),
            '--max-recursions', str(self.recursions),
            '--delay', str(self.delay),
            '--timeout', str(self.timeout),            
            ]
        if self.encoding is not None:
            web2disk_cmdline.extend(['--encoding', self.encoding])
        
        if self.verbose:
            web2disk_cmdline.append('--verbose')
            
        if self.no_stylesheets:
            web2disk_cmdline.append('--dont-download-stylesheets')
            
        for reg in self.match_regexps:
            web2disk_cmdline.extend(['--match-regexp', reg])
            
        for reg in self.filter_regexps:
            web2disk_cmdline.extend(['--filter-regexp', reg])
            
        self.web2disk_options = web2disk_option_parser().parse_args(web2disk_cmdline)[0]
        self.web2disk_options.remove_tags = self.remove_tags
        self.web2disk_options.preprocess_regexps = self.preprocess_regexps
        self.web2disk_options.preprocess_html = self.preprocess_html
        
        if self.delay > 0:
            self.simultaneous_downloads = 1
            
        self.navbar = templates.NavBarTemplate()
            
    def download(self):
        '''
        Download and pre-process all articles from the feeds in this recipe. 
        This method should be called only one on a particular Recipe instance.
        Calling it more than once will lead to undefined behavior.
        @return: Path to index.html
        @rtype: string
        '''
        self.report_progress(0, _('Initialized'))
        res = self.build_index()
        self.cleanup()
        return res
    
    def feeds2index(self, feeds):
        templ = templates.IndexTemplate()
        return templ.generate(self.title, self.timefmt, feeds).render(doctype='xhtml')
    
    def feed2index(self, feed):
        if feed.image_url is not None: # Download feed image
            imgdir = os.path.join(self.output_dir, 'images')
            if not os.path.isdir(imgdir):
                os.makedirs(imgdir)
        
            if self.image_map.has_key(feed.image_url):
                feed.image_url = self.image_map[feed.image_url]
            else:
                bn = urlparse.urlsplit(feed.image_url).path
                if bn:
                    bn = bn.rpartition('/')[-1]
                    if bn:
                        img = os.path.join(imgdir, 'feed_image_%d%s'%(self.image_counter, os.path.splitext(bn)))
                        open(img, 'wb').write(self.browser.open(feed.image_url).read())
                        self.image_counter += 1
                        feed.image_url = img
                        self.image_map[feed.image_url] = img
                
        templ = templates.FeedTemplate()
        return templ.generate(feed).render(doctype='xhtml')
        
    
    def create_logger(self, feed_number, article_number):
        logger = logging.getLogger('feeds2disk.article_%d_%d'%(feed_number, article_number))
        out = cStringIO.StringIO()
        handler = logging.StreamHandler(out)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        handler.setLevel(logging.INFO if self.verbose else logging.WARNING)
        if self.debug:
            handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        return logger, out
    
    def fetch_article(self, url, dir, logger):
        fetcher = RecursiveFetcher(self.web2disk_options, logger, self.image_map)
        fetcher.base_dir = dir
        fetcher.current_dir = dir
        fetcher.show_progress = False
        return fetcher.start_fetch(url)
    
    def build_index(self):
        self.report_progress(0, _('Fetching feeds...'))
        feeds = self.parse_feeds()
        self.has_single_feed = len(feeds) == 1
        
        index = os.path.join(self.output_dir, 'index.html') 
        
        html = self.feeds2index(feeds)
        open(index, 'wb').write(html)
        
        self.jobs = []
        for f, feed in enumerate(feeds):
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            if not os.path.isdir(feed_dir):
                os.makedirs(feed_dir)
                
            for a, article in enumerate(feed):
                art_dir = os.path.join(feed_dir, 'article_%d'%a)
                if not os.path.isdir(art_dir):
                    os.makedirs(art_dir)
                logger, stream = self.create_logger(f, a)
                try:
                    url = self.print_version(article.url)
                except NotImplementedError:
                    url = article.url
                req = WorkRequest(self.fetch_article, (url, art_dir, logger), 
                                  {}, (f, a), self.article_downloaded, 
                                  self.error_in_article_download)
                req.stream = stream
                req.feed = feed
                req.article = article
                self.jobs.append(req)
                    
        self.jobs_done = 0
        tp = ThreadPool(self.simultaneous_downloads)
        for req in self.jobs:
            tp.putRequest(req, block=True, timeout=0)
        
        self.report_progress(0, _('Starting download [%d thread(s)]...')%self.simultaneous_downloads)
        while True:
            try:
                tp.poll(True)
                time.sleep(0.1)
            except NoResultsPending:
                break
        
        html = self.feed2index(feed)
        open(os.path.join(feed_dir, 'index.html'), 'wb').write(html)
        self.report_progress(1, _('Feeds downloaded to %s')%index)
        return index
            
            
    def article_downloaded(self, request, result):
        index = os.path.join(os.path.dirname(result), 'index.html')
        os.rename(result, index)
        src = open(index, 'rb').read().decode('utf-8')
        f, a = request.requestID
        soup = BeautifulSoup(src)
        body = soup.find('body')
        if body is not None:
            top    = self.navbar.generate(False, f, a, len(request.feed), not self.has_single_feed).render(doctype='xhtml')
            bottom = self.navbar.generate(True,  f, a, len(request.feed), not self.has_single_feed).render(doctype='xhtml')
            top    = BeautifulSoup(top).find('div')
            bottom = BeautifulSoup(bottom).find('div')
            body.insert(0, top)
            body.insert(len(body.contents), bottom)
            open(index, 'wb').write(unicode(soup).encode('utf-8'))
        
        article = request.article
        self.logger.debug(_('\nDownloaded article %s from %s\n%s')%(article.title, article.url, request.stream.getvalue()))
        article.url = result
        article.downloaded = True
        self.jobs_done += 1
        self.report_progress(float(self.jobs_done)/len(self.jobs), _('Article downloaded: %s')%article.title)
        
    def error_in_article_download(self, request, exc_info):
        self.jobs_done += 1
        self.logger.error(_('Failed to download article: %s from %s')%(request.article.title, request.article.url))
        self.logger.debug(traceback.format_exc(*exc_info))
        self.logger.debug(request.stream.getvalue())
        self.logger.debug('\n')
        self.report_progress(float(self.jobs_done)/len(self.jobs), _('Article download failed: %s')%request.article.title)
        
        
    def parse_feeds(self):
        '''
        Create a list of articles from a list of feeds.
        @rtype: list
        @return: A list of L{Feed}s.
        '''
        feeds = self.get_feeds()
        parsed_feeds = []
        for obj in feeds:
            if isinstance(obj, basestring):
                title, url = None, obj
            else:
                title, url = obj
            self.report_progress(0, _('Fetching feed %s...'%(title if title else url)))
            parsed_feeds.append(feed_from_xml(self.browser.open(url).read(), 
                                              title=title,
                                              oldest_article=self.oldest_article,
                                              max_articles_per_feed=self.max_articles_per_feed))
            
        return parsed_feeds
    
               
