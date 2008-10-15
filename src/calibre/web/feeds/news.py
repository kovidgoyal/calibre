from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Defines various abstract base classes that can be subclassed to create powerful news fetching recipes.
'''
__docformat__ = "restructuredtext en"


import logging, os, cStringIO, time, traceback, re, urlparse, sys
from collections import defaultdict
from functools import partial
from contextlib import nested, closing

from calibre import browser, __appname__, iswindows, LoggingInterface, strftime
from calibre.ebooks.BeautifulSoup import BeautifulSoup, NavigableString, CData, Tag
from calibre.ebooks.metadata.opf import OPFCreator
from calibre.ebooks.lrf import entity_to_unicode
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.metadata import MetaInformation
from calibre.web.feeds import feed_from_xml, templates, feeds_from_index, Feed
from calibre.web.fetch.simple import option_parser as web2disk_option_parser
from calibre.web.fetch.simple import RecursiveFetcher
from calibre.utils.threadpool import WorkRequest, ThreadPool, NoResultsPending
from calibre.ebooks.lrf.web.profiles import FullContentProfile
from calibre.ptempfile import PersistentTemporaryFile


class BasicNewsRecipe(object, LoggingInterface):
    '''
    Abstract base class that contains logic needed in all feed fetchers.
    '''
    
    #: The title to use for the ebook
    title                  = _('Unknown News Source')
    
    #: A couple of lines that describe the content this recipe downloads.
    #: This will be used primarily in a GUI that presents a list of recipes.
    description = ''
    
    #: The author of this recipe
    __author__             = __appname__    
    
    #: Maximum number of articles to download from each feed. This is primarily
    #: useful for feeds that don't have article dates. For most feeds, you should
    #: use :attr:`BasicNewsRecipe.oldest_article`
    max_articles_per_feed  = 100
    
    #: Oldest article to download from this news source. In days.
    oldest_article         = 7.0 
    
    #: Number of levels of links to follow on article webpages 
    recursions             = 0
    
    #: Delay between consecutive downloads in seconds
    delay                  = 0
    
    #: Number of simultaneous downloads. Set to 1 if the server is picky.
    #: Automatically reduced to 1 if :attr:`BasicNewsRecipe.delay` > 0
    simultaneous_downloads = 5
    
    #: Timeout for fetching files from server in seconds
    timeout                = 120.0
    
    #: The format string for the date shown on the first page.
    #: By default: Day_Name, Day_Number Month_Name Year
    timefmt                = ' [%a, %d %b %Y]'
    
    #: List of feeds to download
    #: Can be either ``[url1, url2, ...]`` or ``[('title1', url1), ('title2', url2),...]``
    feeds = None
    
    #: Max number of characters in the short description
    summary_length         = 500
    
    #: Convenient flag to disable loading of stylesheets for websites
    #: that have overly complex stylesheets unsuitable for conversion
    #: to ebooks formats
    #: If True stylesheets are not downloaded and processed
    no_stylesheets         = False
    
    #: If True the GUI will ask the user for a username and password 
    #: to use while downloading
    #: @type: boolean
    needs_subscription     = False
    
    #: If True the navigation bar is center aligned, otherwise it is left aligned
    center_navbar = True
    
    #: Specify an override encoding for sites that have an incorrect
    #: charset specification. The most common being specifying ``latin1`` and
    #: using ``cp1252``. If None, try to detect the encoding. 
    encoding               = None
    
    #: Normally we try to guess if a feed has full articles embedded in it
    #: based on the length of the embedded content. If `None`, then the
    #: default guessing is used. If `True` then the we always assume the feeds has 
    #: embedded content and if `False` we always assume the feed does not have
    #: embedded content.
    use_embedded_content   = None
    
    #: Set to True and implement :method:`get_obfuscated_article` to handle
    #: websites that try to make it difficult to scrape content.
    articles_are_obfuscated = False
    
    #: Specify any extra :term:`CSS` that should be addded to downloaded :term:`HTML` files
    #: It will be inserted into `<style>` tags, just before the closing
    #: `</head>` tag thereby overrinding all :term:`CSS` except that which is
    #: declared using the style attribute on individual :term:`HTML` tags. 
    #: For example::
    #: 
    #:     extra_css = '.heading { font: serif x-large }'
    #: 
    extra_css              = None
    
    #: List of regular expressions that determines which links to follow
    #: If empty, it is ignored. For example::
    #:    
    #:     match_regexps = [r'page=[0-9]+']
    #:
    #: will match all URLs that have `page=some number` in them.
    #:
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or 
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    match_regexps         = []
    
    #: List of regular expressions that determines which links to ignore
    #: If empty it is ignored. For example::
    #:     
    #:     filter_regexps = [r'ads\.doubleclick\.net']
    #:
    #: will remove all URLs that have `ads.doubleclick.net` in them.
    #: 
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or 
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    filter_regexps        = []
    
    #: List of options to pass to html2lrf, to customize generation of LRF ebooks.
    html2lrf_options      = []
    
    #: Options to pass to html2epub to customize generation of EPUB ebooks.
    html2epub_options     = ''
    
    #: List of tags to be removed. Specified tags are removed from downloaded HTML.
    #: A tag is specified as a dictionary of the form::
    #:    
    #:    {
    #:     name      : 'tag name',   #e.g. 'div'
    #:     attrs     : a dictionary, #e.g. {class: 'advertisment'}
    #:    }
    #:
    #: All keys are optional. For a full explanantion of the search criteria, see
    #: `Beautiful Soup <http://www.crummy.com/software/BeautifulSoup/documentation.html#The basic find method: findAll(name, attrs, recursive, text, limit, **kwargs)>`_
    #: A common example::
    #: 
    #:   remove_tags = [dict(name='div', attrs={'class':'advert'})]
    #: 
    #: This will remove all `<div class="advert">` tags and all 
    #: their children from the downloaded :term:`HTML`.
    remove_tags           = []
    
    #: Remove all tags that occur after the specified tag. 
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: For example::
    #:
    #:     remove_tags_after = [dict(id='content')]
    #:
    #: will remove all
    #: tags after the first element with `id="content"`.
    remove_tags_after     = None
    
    #: Remove all tags that occur before the specified tag.
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: For example::
    #:
    #:     remove_tags_before = [dict(id='content')]
    #:
    #: will remove all
    #: tags before the first element with `id="content"`.
    remove_tags_before    = None
    
    #: Keep only the specified tags and their children. 
    #: For the format for specifying a tag see :attr:`BasicNewsRecipe.remove_tags`.
    #: If this list is not empty, then the `<body>` tag will be emptied and re-filled with
    #: the tags that match the entries in this list. For example::
    #: 
    #:     keep_only_tags = [dict(id=['content', 'heading'])]
    #: 
    #: will keep only tags that have an `id` attribute of `"content"` or `"heading"`.
    keep_only_tags        = []
    
    #: List of :term:`regexp` substitution rules to run on the downloaded :term:`HTML`. 
    #: Each element of the 
    #: list should be a two element tuple. The first element of the tuple should
    #: be a compiled regular expression and the second a callable that takes
    #: a single match object and returns a string to replace the match. For example::
    #:
    #:     preprocess_regexps = [
    #:        (re.compile(r'<!--Article ends here-->.*</body>', re.DOTALL|re.IGNORECASE), 
    #:         lambda match: '</body>'),
    #:     ]
    #:
    #: will remove everythong from `<!--Article ends here-->` to `</body>`.
    preprocess_regexps    = []
    
    # See the built-in profiles for examples of these settings.
    
    def get_cover_url(self):
        '''
        Return a :term:`URL` to the cover image for this issue or `None`.
        By default it returns the value of the member `self.cover_url` which
        is normally `None`. If you want your recipe to download a cover for the e-book
        override this method in your subclass, or set the member variable `self.cover_url`
        before this method is called.
        '''
        return getattr(self, 'cover_url', None)
    
    def get_feeds(self):
        '''
        Return a list of :term:RSS feeds to fetch for this profile. Each element of the list
        must be a 2-element tuple of the form (title, url). If title is None or an
        empty string, the title from the feed is used. This method is useful if your recipe
        needs to do some processing to figure out the list of feeds to download. If
        so, override in your subclass.
        '''
        if not self.feeds:
            raise NotImplementedError
        if self.test:
            return self.feeds[:2]
        return self.feeds
    
    @classmethod
    def print_version(self, url):
        '''
        Take a `url` pointing to the webpage with article content and return the 
        :term:`URL` pointing to the print version of the article. By default does
        nothing. For example::
        
            def print_version(self, url):
                return url + '?&pagewanted=print'
        
        '''
        raise NotImplementedError
    
    @classmethod
    def get_browser(self):
        '''
        Return a browser instance used to fetch documents from the web. By default
        it returns a `mechanize <http://wwwsearch.sourceforge.net/mechanize/>`_
        browser instance that supports cookies, ignores robots.txt, handles
        refreshes and has a mozilla firefox user agent.
        
        If your recipe requires that you login first, override this method
        in your subclass. For example, the following code is used in the New York
        Times recipe to login for full access::
        
            def get_browser(self):
                br = BasicNewsRecipe.get_browser()
                if self.username is not None and self.password is not None:
                    br.open('http://www.nytimes.com/auth/login')
                    br.select_form(name='login')
                    br['USERID']   = self.username
                    br['PASSWORD'] = self.password
                    br.submit()
                return br
        
        '''
        return browser()
    
    def get_article_url(self, article):
        '''
        Override in a subclass to customize extraction of the :term:`URL` that points
        to the content for each article. Return the 
        article URL. It is called with `article`, an object representing a parsed article
        from a feed. See `feedsparser <http://www.feedparser.org/docs/>`_.
        By default it returns `article.link <http://www.feedparser.org/docs/reference-entry-link.html>`_.
        '''
        return article.get('link',  None)
    
    def preprocess_html(self, soup):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        it is parsed for links and images. 
        It can be used to do arbitrarily powerful pre-processing on the :term:`HTML`.
        It should return `soup` after processing it.
        
        `soup`: A `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_ 
        instance containing the downloaded :term:`HTML`.
        '''
        return soup
    
    def postprocess_html(self, soup, first_fetch):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, after
        it is parsed for links and images. 
        It can be used to do arbitrarily powerful post-processing on the :term:`HTML`.
        It should return `soup` after processing it. 
        
        :param soup: A `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_ 
        instance containing the downloaded :term:`HTML`.
        :param first_fetch: True if this is the first page of an article.
        '''
        return soup
    
    def cleanup(self):
        '''
        Called after all articles have been download. Use it to do any cleanup like 
        logging out of subscription sites, etc.
        '''
        pass
    
    def index_to_soup(self, url_or_raw):
        '''
        Convenience method that takes an URL to the index page and returns
        a `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        of it.
        
        `url_or_raw`: Either a URL or the downloaded index page as a string
        '''
        if re.match(r'\w+://', url_or_raw):
            f = self.browser.open(url_or_raw)
            raw = f.read()
            f.close()
            if not raw:
                raise RuntimeError('Could not fetch index from %s'%url_or_raw)
        else:
            raw = url_or_raw
        if not isinstance(raw, unicode) and self.encoding:
            raw = raw.decode(self.encoding)
        massage = list(BeautifulSoup.MARKUP_MASSAGE)
        massage.append((re.compile(r'&(\S+?);'), lambda match: entity_to_unicode(match, encoding=self.encoding))) 
        return BeautifulSoup(raw, markupMassage=massage)
        
    
    def sort_index_by(self, index, weights):
        '''
        Convenience method to sort the titles in `index` according to `weights`.
        `index` is sorted in place. Returns `index`.
        
        `index`: A list of titles.
        
        `weights`: A dictionary that maps weights to titles. If any titles
        in index are not in weights, they are assumed to have a weight of 0.
        '''
        weights = defaultdict(lambda : 0, weights)
        index.sort(cmp=lambda x, y: cmp(weights[x], weights[y]))
        return index
    
    def parse_index(self):
        '''
        This method should be implemented in recipes that parse a website
        instead of feeds to generate a list of articles. Typical uses are for
        news sources that have a "Print Edition" webpage that lists all the 
        articles in the current print edition. If this function is implemented,
        it will be used in preference to :meth:`BasicNewsRecipe.parse_feeds`.
        
        It must return a list. Each element of the list must be a 2-element tuple
        of the form ``('feed title', list of articles)``.
         
        Each list of articles must contain dictionaries of the form::
        
            {
            'title'       : article title,
            'url'         : URL of print version,
            'date'        : The publication date of the article as a string,
            'description' : A summary of the article
            'content'     : The full article (can be an empty string). This is used by FullContentProfile
            }
        
        For an example, see the recipe for downloading `The Atlantic`.
        '''
        raise NotImplementedError
    
    def get_obfuscated_article(self, url, logger):
        '''
        If you set :member:`articles_are_obfuscated` this method is called with
        every article URL. It should return the path to a file on the filesystem
        that contains the article HTML. That file is processed by the recursive
        HTML fetching engine, so it can contain links to pages/images on the web.
        
        This method is typically useful for sites that try to make it difficult to
        access article content automatically. See for example the 
        :module:`calibre.web.recipes.iht` recipe.
        '''
        raise NotImplementedError
    
    def __init__(self, options, parser, progress_reporter):
        '''
        Initialize the recipe.
        :param options: Parsed commandline options 
        :param parser:  Command line option parser. Used to intelligently merge options.
        :param progress_reporter: A Callable that takes two arguments: progress (a number between 0 and 1) and a string message. The message should be optional.
        '''
        LoggingInterface.__init__(self, logging.getLogger('feeds2disk'))
        if not isinstance(self.title, unicode):
            self.title = unicode(self.title, 'utf-8', 'replace')
        
        for attr in ('username', 'password', 'lrf', 'output_dir', 'verbose', 'debug', 'test'):
            setattr(self, attr, getattr(options, attr))
        self.output_dir = os.path.abspath(self.output_dir)
        if options.test:
            self.max_articles_per_feed = 2
            self.simultaneous_downloads = min(4, self.simultaneous_downloads)
        
        
        if self.debug:
            logging.getLogger('feeds2disk').setLevel(logging.DEBUG)
            self.verbose = True
        self.report_progress = progress_reporter
        
        self.username = self.password = None
        #: If True optimize downloading for eventual conversion to LRF
        self.lrf = False
        defaults = parser.get_default_values()
        
        for opt in options.__dict__.keys():
            if getattr(options, opt) != getattr(defaults, opt, None):
                setattr(self, opt, getattr(options, opt))
        
        if isinstance(self.feeds, basestring):
            self.feeds = eval(self.feeds)
            if isinstance(self.feeds, basestring):
                self.feeds = [self.feeds]
            
        if self.needs_subscription and (self.username is None or self.password is None):
            raise ValueError('The %s recipe needs a username and password.'%self.title)
        
        self.browser = self.get_browser()
        self.image_map, self.image_counter = {}, 1
        self.css_map = {}
        
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
        for extra in ('keep_only_tags', 'remove_tags', 'preprocess_regexps', 
                      'preprocess_html', 'remove_tags_after', 'remove_tags_before'):
            setattr(self.web2disk_options, extra, getattr(self, extra))
        self.web2disk_options.postprocess_html = self._postprocess_html
        
        if self.delay > 0:
            self.simultaneous_downloads = 1
            
        self.navbar = templates.NavBarTemplate()
        self.html2lrf_options.extend(['--page-break-before', '$', '--use-spine', '--header', '--encoding', 'utf-8'])
        if '--base-font-size' not in self.html2lrf_options:
            self.html2lrf_options.extend(['--base-font-size', '12'])
        self.failed_downloads = []
        self.partial_failures = []
                
            
    def _postprocess_html(self, soup, first_fetch, job_info):
        if self.extra_css is not None:
            head = soup.find('head')
            if head:
                style = BeautifulSoup(u'<style type="text/css">%s</style>'%self.extra_css).find('style')
                head.insert(len(head.contents), style)
        if first_fetch and job_info:
            url, f, a, feed_len = job_info
            body = soup.find('body')
            if body is not None:
                templ = self.navbar.generate(False, f, a, feed_len, 
                                             not self.has_single_feed, 
                                             url, __appname__, center=self.center_navbar)
                elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8')).find('div')
                body.insert(0, elem)
        if self.no_stylesheets:
            for link in list(soup.findAll('link', type=re.compile('css'))):
                link.extract()
        return self.postprocess_html(soup, first_fetch)
        
    
    def download(self):
        '''
        Download and pre-process all articles from the feeds in this recipe. 
        This method should be called only one on a particular Recipe instance.
        Calling it more than once will lead to undefined behavior.
        @return: Path to index.html
        @rtype: string
        '''
        try:
            res = self.build_index()
            self.report_progress(1, _('Download finished'))
            if self.failed_downloads:
                self.log_warning(_('Failed to download the following articles:'))
                for feed, article, debug in self.failed_downloads:
                    self.log_warning(article.title+_(' from ')+feed.title)
                    self.log_debug(article.url)
                    self.log_debug(debug)
            if self.partial_failures:
                self.log_warning(_('Failed to download parts of the following articles:'))
                for feed, atitle, aurl, debug in self.partial_failures:
                    self.log_warning(atitle + _(' from ') + feed)
                    self.log_debug(aurl)
                    self.log_warning(_('\tFailed links:'))
                    for l, tb in debug:
                        self.log_warning(l)
                        self.log_debug(tb) 
            return res
        finally:
            self.cleanup()
    
    def feeds2index(self, feeds):
        templ = templates.IndexTemplate()
        return templ.generate(self.title, self.timefmt, feeds).render(doctype='xhtml')
    
    @classmethod
    def description_limiter(cls, src):
        pos = cls.summary_length
        fuzz = 50
        si = src.find(';', pos)
        if si > 0 and si-pos > fuzz:
            si = -1
        gi = src.find('>', pos)
        if gi > 0 and gi-pos > fuzz:
            gi = -1
        npos = max(si, gi)
        if npos < 0:
            npos = pos
        
        return src[:npos+1]+u'\u2026'

        
    
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
                        try:
                            with nested(open(img, 'wb'), closing(self.browser.open(feed.image_url))) as (fi, r):
                                fi.write(r.read())
                            self.image_counter += 1
                            feed.image_url = img
                            self.image_map[feed.image_url] = img
                        except:
                            pass
            if isinstance(feed.image_url, str):
                feed.image_url = feed.image_url.decode(sys.getfilesystemencoding(), 'strict')
                
                
        templ = templates.FeedTemplate()
        return templ.generate(feed, self.description_limiter).render(doctype='xhtml')
        
    
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
    
    def _fetch_article(self, url, dir, logger, f, a, num_of_feeds):
        fetcher = RecursiveFetcher(self.web2disk_options, logger, self.image_map, self.css_map, (url, f, a, num_of_feeds))
        fetcher.base_dir = dir
        fetcher.current_dir = dir
        fetcher.show_progress = False
        res, path, failures = fetcher.start_fetch(url), fetcher.downloaded_paths, fetcher.failed_links
        if not res or not os.path.exists(res):
            raise Exception(_('Could not fetch article. Run with --debug to see the reason'))
        return res, path, failures
    
    def fetch_article(self, url, dir, logger, f, a, num_of_feeds):
        return self._fetch_article(url, dir, logger, f, a, num_of_feeds)
    
    def fetch_obfuscated_article(self, url, dir, logger, f, a, num_of_feeds):
        path = os.path.abspath(self.get_obfuscated_article(url, logger))
        url = ('file:'+path) if iswindows else ('file://'+path)
        return self._fetch_article(url, dir, logger, f, a, num_of_feeds)
    
    def fetch_embedded_article(self, article, dir, logger, f, a, num_of_feeds):
        templ = templates.EmbeddedContent()
        raw = templ.generate(article).render('html')
        with PersistentTemporaryFile('_feeds2disk.html') as pt:
            pt.write(raw)
            url = ('file:'+pt.name) if iswindows else ('file://'+pt.name)
        return self._fetch_article(url, dir, logger, f, a, num_of_feeds)
        
    
    def build_index(self):
        self.report_progress(0, _('Fetching feeds...'))
        try:
            feeds = feeds_from_index(self.parse_index(), oldest_article=self.oldest_article,
                                     max_articles_per_feed=self.max_articles_per_feed)
            self.report_progress(0, _('Got feeds from index page'))
        except NotImplementedError:
            feeds = self.parse_feeds()
        
        #feeds = FeedCollection(feeds)
        
        self.report_progress(0, _('Trying to download cover...'))
        self.download_cover()
        if self.test:
            feeds = feeds[:2]
        self.has_single_feed = len(feeds) == 1
        
        if self.use_embedded_content is None:
            self.use_embedded_content = feeds[0].has_embedded_content()
        
        index = os.path.join(self.output_dir, 'index.html') 
        
        html = self.feeds2index(feeds)
        with open(index, 'wb') as fi:
            fi.write(html)
        
        self.jobs = []
        for f, feed in enumerate(feeds):
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            if not os.path.isdir(feed_dir):
                os.makedirs(feed_dir)
                
            for a, article in enumerate(feed):
                if a >= self.max_articles_per_feed:
                    break
                art_dir = os.path.join(feed_dir, 'article_%d'%a)
                if not os.path.isdir(art_dir):
                    os.makedirs(art_dir)
                logger, stream = self.create_logger(f, a)
                try:
                    url = self.print_version(article.url)
                except NotImplementedError:
                    url = article.url
                if not url:
                    continue
                func, arg = (self.fetch_embedded_article, article) if self.use_embedded_content else \
                            ((self.fetch_obfuscated_article if self.articles_are_obfuscated \
                              else self.fetch_article), url)
                req = WorkRequest(func, (arg, art_dir, logger, f, a, len(feed)), 
                                      {}, (f, a), self.article_downloaded, 
                                      self.error_in_article_download)
                req.stream = stream
                req.feed = feed
                req.article = article
                req.feed_dir = feed_dir
                self.jobs.append(req)
            
                    
        self.jobs_done = 0
        tp = ThreadPool(self.simultaneous_downloads)
        for req in self.jobs:
            tp.putRequest(req, block=True, timeout=0)
        
        
        self.report_progress(0, _('Starting download [%d thread(s)]...')%self.simultaneous_downloads)
        while True:
            try:
                tp.poll()
                time.sleep(0.1)
            except NoResultsPending:
                break
        
        #feeds.restore_duplicates()
        
        for f, feed in enumerate(feeds):
            html = self.feed2index(feed)
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            with open(os.path.join(feed_dir, 'index.html'), 'wb') as fi:
                fi.write(html)
        self.create_opf(feeds)
        self.report_progress(1, _('Feeds downloaded to %s')%index)
        
        return index
    
    def download_cover(self):
        self.cover_path = None
        try:
            cu = self.get_cover_url()
        except Exception, err:
            cu = None
            self.log_error(_('Could not download cover: %s')%str(err))
            self.log_debug(traceback.format_exc())
        if cu is not None:
            ext = cu.rpartition('.')[-1]
            ext = ext.lower() if ext else 'jpg'
            self.report_progress(1, _('Downloading cover from %s')%cu)
            cpath = os.path.join(self.output_dir, 'cover.'+ext)
            with nested(open(cpath, 'wb'), closing(self.browser.open(cu))) as (cfile, r):
                cfile.write(r.read())
            self.cover_path = cpath
            
    
    def create_opf(self, feeds, dir=None):
        if dir is None:
            dir = self.output_dir
        mi = MetaInformation(self.title + strftime(self.timefmt), [__appname__])
        mi.publisher = __appname__
        mi.author_sort = __appname__
        opf_path = os.path.join(dir, 'index.opf')
        ncx_path = os.path.join(dir, 'index.ncx')
        opf = OPFCreator(dir, mi)
        
        manifest = [os.path.join(dir, 'feed_%d'%i) for i in range(len(feeds))]
        manifest.append(os.path.join(dir, 'index.html'))
        cpath = getattr(self, 'cover_path', None) 
        if cpath is not None and os.access(cpath, os.R_OK):
            opf.cover = cpath
            manifest.append(cpath)
        opf.create_manifest_from_files_in(manifest)
        
        entries = ['index.html']
        toc = TOC(base_path=dir)
        self.play_order_counter = 0
        self.play_order_map = {}
        
        def feed_index(num, parent):
            f = feeds[num]
            for j, a in enumerate(f):
                if getattr(a, 'downloaded', False):
                    adir = 'feed_%d/article_%d/'%(num, j)
                    entries.append('%sindex.html'%adir)
                    po = self.play_order_map.get(entries[-1], None)
                    if po is None:
                        self.play_order_counter += 1
                        po = self.play_order_counter
                    parent.add_item('%sindex.html'%adir, None, a.title if a.title else _('Untitled Article'),
                                    play_order=po)
                    last = os.path.join(self.output_dir, ('%sindex.html'%adir).replace('/', os.sep))
                    for sp in a.sub_pages:
                        prefix = os.path.commonprefix([opf_path, sp])
                        relp = sp[len(prefix):]
                        entries.append(relp.replace(os.sep, '/'))
                        last = sp
                    
                    if os.path.exists(last):
                        with open(last, 'rb') as fi:
                            src = fi.read().decode('utf-8')
                        soup = BeautifulSoup(src)
                        body = soup.find('body')
                        if body is not None:
                            prefix = '/'.join('..'for i in range(2*len(re.findall(r'link\d+', last))))
                            templ = self.navbar.generate(True, num, j, len(f), 
                                             not self.has_single_feed, 
                                             a.orig_url, __appname__, prefix=prefix,
                                             center=self.center_navbar)
                            elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8')).find('div')
                            body.insert(len(body.contents), elem)
                            with open(last, 'wb') as fi:
                                fi.write(unicode(soup).encode('utf-8'))
        
        if len(feeds) > 1:
            for i, f in enumerate(feeds):
                entries.append('feed_%d/index.html'%i)
                po = self.play_order_map.get(entries[-1], None)
                if po is None:
                    self.play_order_counter += 1
                    po = self.play_order_counter
                feed_index(i, toc.add_item('feed_%d/index.html'%i, None, f.title, play_order=po))
        else:
            entries.append('feed_%d/index.html'%0)
            feed_index(0, toc)
        
        for i, p in enumerate(entries):
            entries[i] = os.path.join(dir, p.replace('/', os.sep))
        opf.create_spine(entries)
        opf.set_toc(toc)
        
        with nested(open(opf_path, 'wb'), open(ncx_path, 'wb')) as (opf_file, ncx_file):
            opf.render(opf_file, ncx_file)
        
    
    def article_downloaded(self, request, result):
        index = os.path.join(os.path.dirname(result[0]), 'index.html')
        if index != result[0]:
            if os.path.exists(index):
                os.remove(index)
            os.rename(result[0], index)
        a = request.requestID[1]        
        
        article = request.article
        self.log_debug(_('\nDownloaded article %s from %s\n%s')%(article.title, article.url, request.stream.getvalue().decode('utf-8', 'ignore')))
        article.orig_url = article.url
        article.url = 'article_%d/index.html'%a
        article.downloaded = True
        article.sub_pages  = result[1][1:]
        self.jobs_done += 1
        self.report_progress(float(self.jobs_done)/len(self.jobs), _('Article downloaded: %s')%article.title)
        if result[2]:
            self.partial_failures.append((request.feed.title, article.title, article.url, result[2]))
        
    def error_in_article_download(self, request, traceback):
        self.jobs_done += 1
        self.log_error(_('Failed to download article: %s from %s\n')%(request.article.title, request.article.url))
        debug = request.stream.getvalue().decode('utf-8', 'ignore')
        self.log_debug(debug)
        self.log_debug(traceback)
        self.log_debug('\n')
        self.report_progress(float(self.jobs_done)/len(self.jobs), _('Article download failed: %s')%request.article.title)
        self.failed_downloads.append((request.feed, request.article, debug))
        
    def parse_feeds(self):
        '''
        Create a list of articles from the list of feeds returned by :meth:`BasicNewsRecipe.get_feeds`. 
        Return a list of :class:`Feed` objects.
        '''
        feeds = self.get_feeds()
        parsed_feeds = []
        for obj in feeds:
            if isinstance(obj, basestring):
                title, url = None, obj
            else:
                title, url = obj
            self.report_progress(0, _('Fetching feed')+' %s...'%(title if title else url))
            try:
                with closing(self.browser.open(url)) as f:
                    parsed_feeds.append(feed_from_xml(f.read(), 
                                          title=title,
                                          oldest_article=self.oldest_article,
                                          max_articles_per_feed=self.max_articles_per_feed,
                                          get_article_url=self.get_article_url))
            except Exception, err:
                feed = Feed()
                msg = 'Failed feed: %s'%(title if title else url)
                feed.populate_from_preparsed_feed(msg, [])
                feed.description = unicode(err)
                parsed_feeds.append(feed)
                self.log_exception(msg)
                
        return parsed_feeds
    
    @classmethod
    def tag_to_string(self, tag, use_alt=True):
        '''
        Convenience method to take a 
        `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        `Tag` and extract the text from it recursively, including any CDATA sections 
        and alt tag attributes. Return a possibly empty unicode string.
        
        `use_alt`: If `True` try to use the alt attribute for tags that don't 
        have any textual content
        
        `tag`: `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        `Tag`
        '''
        if not tag:
            return ''
        if isinstance(tag, basestring):
            return tag
        strings = []
        for item in tag.contents:
            if isinstance(item, (NavigableString, CData)):
                strings.append(item.string)
            elif isinstance(item, Tag):
                res = self.tag_to_string(item)
                if res:
                    strings.append(res)
                elif use_alt and item.has_key('alt'):
                    strings.append(item['alt'])
        return u''.join(strings)
    
    @classmethod
    def soup(cls, raw):
        entity_replace = [(re.compile(ur'&(\S+?);'), partial(entity_to_unicode, 
                                                           exceptions=[]))]
        nmassage = list(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(entity_replace)
        return BeautifulSoup(raw, markupMassage=nmassage)
    
class Profile2Recipe(BasicNewsRecipe):
    '''
    Used to migrate the old news Profiles to the new Recipes. Uses the settings
    from the old Profile to populate the settings in the Recipe. Also uses, the 
    Profile's get_browser and parse_feeds.
    '''
    def __init__(self, profile_class, options, parser, progress_reporter):
        self.old_profile = profile_class(logging.getLogger('feeds2disk'), 
                                         username=options.username, 
                                         password=options.password,
                                         lrf=options.lrf)
        for attr in ('preprocess_regexps', 'oldest_article', 'delay', 'timeout',
                     'match_regexps', 'filter_regexps', 'html2lrf_options', 
                     'timefmt', 'needs_subscription', 'summary_length',
                     'max_articles_per_feed', 'title','no_stylesheets', 'encoding'):
            setattr(self, attr, getattr(self.old_profile, attr))
        
        self.simultaneous_downloads = 1
        BasicNewsRecipe.__init__(self, options, parser, progress_reporter)
        self.browser = self.old_profile.browser
        self.use_embedded_content = isinstance(self.old_profile, FullContentProfile) 
        
    def parse_index(self):
        feeds = []
        for key, val in self.old_profile.parse_feeds().items():
            feeds.append((key, val))
        return feeds
        
class CustomIndexRecipe(BasicNewsRecipe):
    
    def custom_index(self):
        '''
        Return the filesystem path to a custom HTML document that will serve as the index for 
        this recipe. The index document will typically contain many `<a href="...">`
        tags that point to resources on the internet that should be downloaded.
        '''
        raise NotImplementedError
    
    def create_opf(self):
        mi = MetaInformation(self.title + strftime(self.timefmt), [__appname__])
        mi.publisher = __appname__
        mi.author_sort = __appname__        
        mi = OPFCreator(self.output_dir, mi)
        mi.create_manifest_from_files_in([self.output_dir])
        mi.create_spine([os.path.join(self.output_dir, 'index.html')])
        with open(os.path.join(self.output_dir, 'index.opf'), 'wb') as opf_file:
            mi.render(opf_file)
    
    def download(self):
        index = os.path.abspath(self.custom_index())
        url = 'file:'+index if iswindows else 'file://'+index
        fetcher = RecursiveFetcher(self.web2disk_options, self.logger)
        fetcher.base_dir = self.output_dir
        fetcher.current_dir = self.output_dir
        fetcher.show_progress = False
        res = fetcher.start_fetch(url)
        self.create_opf()
        return res
    
class AutomaticNewsRecipe(BasicNewsRecipe):
    
    keep_only_tags = [dict(name=['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]
    
    def fetch_embedded_article(self, article, dir, logger, f, a, num_of_feeds):
        if self.use_embedded_content:
            self.web2disk_options.keep_only_tags = []
        return BasicNewsRecipe.fetch_embedded_article(self, article, dir, logger, f, a, num_of_feeds)
