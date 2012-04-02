from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Defines various abstract base classes that can be subclassed to create powerful news fetching recipes.
'''
__docformat__ = "restructuredtext en"


import os, time, traceback, re, urlparse, sys, cStringIO
from collections import defaultdict
from functools import partial
from contextlib import nested, closing


from calibre import (browser, __appname__, iswindows, force_unicode,
                    strftime, preferred_encoding, as_unicode)
from calibre.ebooks.BeautifulSoup import BeautifulSoup, NavigableString, CData, Tag
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre import entity_to_unicode
from calibre.web import Recipe
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.metadata import MetaInformation
from calibre.web.feeds import feed_from_xml, templates, feeds_from_index, Feed
from calibre.web.fetch.simple import option_parser as web2disk_option_parser
from calibre.web.fetch.simple import RecursiveFetcher
from calibre.utils.threadpool import WorkRequest, ThreadPool, NoResultsPending
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import now as nowf
from calibre.utils.magick.draw import save_cover_data_to, add_borders_to_image
from calibre.utils.localization import canonicalize_lang

class LoginFailed(ValueError):
    pass

class DownloadDenied(ValueError):
    pass

class BasicNewsRecipe(Recipe):
    '''
    Base class that contains logic needed in all recipes. By overriding
    progressively more of the functionality in this class, you can make
    progressively more customized/powerful recipes. For a tutorial introduction
    to creating recipes, see :doc:`news`.
    '''

    #: The title to use for the ebook
    title                  = _('Unknown News Source')

    #: A couple of lines that describe the content this recipe downloads.
    #: This will be used primarily in a GUI that presents a list of recipes.
    description = u''

    #: The author of this recipe
    __author__             = __appname__

    #: Minimum calibre version needed to use this recipe
    requires_version = (0, 6, 0)

    #: The language that the news is in. Must be an ISO-639 code either
    #: two or three characters long
    language               = 'und'

    #: Maximum number of articles to download from each feed. This is primarily
    #: useful for feeds that don't have article dates. For most feeds, you should
    #: use :attr:`BasicNewsRecipe.oldest_article`
    max_articles_per_feed  = 100

    #: Oldest article to download from this news source. In days.
    oldest_article         = 7.0

    #: Number of levels of links to follow on article webpages
    recursions             = 0

    #: Delay between consecutive downloads in seconds. The argument may be a
    #: floating point number to indicate a more precise time.
    delay                  = 0

    #: Publication type
    #: Set to newspaper, magazine or blog
    publication_type = 'unknown'

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

    #: Convenient flag to strip all javascript tags from the downloaded HTML
    remove_javascript      = True

    #: If True the GUI will ask the user for a username and password
    #: to use while downloading
    #: If set to "optional" the use of a username and password becomes optional
    needs_subscription     = False

    #: If True the navigation bar is center aligned, otherwise it is left aligned
    center_navbar = True

    #: Specify an override encoding for sites that have an incorrect
    #: charset specification. The most common being specifying ``latin1`` and
    #: using ``cp1252``. If None, try to detect the encoding. If it is a
    #: callable, the callable is called with two arguments: The recipe object
    #: and the source to be decoded. It must return the decoded source.
    encoding               = None

    #: Normally we try to guess if a feed has full articles embedded in it
    #: based on the length of the embedded content. If `None`, then the
    #: default guessing is used. If `True` then the we always assume the feeds has
    #: embedded content and if `False` we always assume the feed does not have
    #: embedded content.
    use_embedded_content   = None

    #: Set to True and implement :meth:`get_obfuscated_article` to handle
    #: websites that try to make it difficult to scrape content.
    articles_are_obfuscated = False

    #: Reverse the order of articles in each feed
    reverse_article_order = False

    #: Automatically extract all the text from downloaded article pages. Uses
    #: the algorithms from the readability project. Setting this to True, means
    #: that you do not have to worry about cleaning up the downloaded HTML
    #: manually (though manual cleanup will always be superior).
    auto_cleanup = False

    #: Specify elements that the auto cleanup algorithm should never remove
    #: The syntax is a XPath expression. For example::
    #:
    #:   auto_cleanup_keep = '//div[@id="article-image"]' will keep all divs with
    #:                                                  id="article-image"
    #:   auto_cleanup_keep = '//*[@class="important"]' will keep all elements
    #:                                               with class="important"
    #:   auto_cleanup_keep = '//div[@id="article-image"]|//span[@class="important"]'
    #:                     will keep all divs with id="article-image" and spans
    #:                     with class="important"
    #:
    auto_cleanup_keep = None

    #: Specify any extra :term:`CSS` that should be added to downloaded :term:`HTML` files
    #: It will be inserted into `<style>` tags, just before the closing
    #: `</head>` tag thereby overriding all :term:`CSS` except that which is
    #: declared using the style attribute on individual :term:`HTML` tags.
    #: For example::
    #:
    #:     extra_css = '.heading { font: serif x-large }'
    #:
    extra_css              = None

    #: If True empty feeds are removed from the output.
    #: This option has no effect if parse_index is overriden in
    #: the sub class. It is meant only for recipes that return a list
    #: of feeds using `feeds` or :meth:`get_feeds`.
    remove_empty_feeds = False

    #: List of regular expressions that determines which links to follow
    #: If empty, it is ignored. Used only if is_link_wanted is
    #: not implemented. For example::
    #:
    #:     match_regexps = [r'page=[0-9]+']
    #:
    #: will match all URLs that have `page=some number` in them.
    #:
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    match_regexps         = []

    #: List of regular expressions that determines which links to ignore
    #: If empty it is ignored. Used only if is_link_wanted is not
    #: implemented. For example::
    #:
    #:     filter_regexps = [r'ads\.doubleclick\.net']
    #:
    #: will remove all URLs that have `ads.doubleclick.net` in them.
    #:
    #: Only one of :attr:`BasicNewsRecipe.match_regexps` or
    #: :attr:`BasicNewsRecipe.filter_regexps` should be defined.
    filter_regexps        = []

    #: Recipe specific options to control the conversion of the downloaded
    #: content into an e-book. These will override any user or plugin specified
    #: values, so only use if absolutely necessary. For example::
    #:
    #:   conversion_options = {
    #:     'base_font_size'   : 16,
    #:     'tags'             : 'mytag1,mytag2',
    #:     'title'            : 'My Title',
    #:     'linearize_tables' : True,
    #:   }
    #:
    conversion_options = {}

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
    #:     remove_tags_before = dict(id='content')
    #:
    #: will remove all
    #: tags before the first element with `id="content"`.
    remove_tags_before    = None

    #: List of attributes to remove from all tags
    #: For example::
    #:
    #:   remove_attributes = ['style', 'font']
    remove_attributes = []

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

    #: The CSS that is used to style the templates, i.e., the navigation bars and
    #: the Tables of Contents. Rather than overriding this variable, you should
    #: use `extra_css` in your recipe to customize look and feel.
    template_css = u'''
            .article_date {
                color: gray; font-family: monospace;
            }

            .article_description {
                text-indent: 0pt;
            }

            a.article {
                font-weight: bold; text-align:left;
            }

            a.feed {
                font-weight: bold;
            }

            .calibre_navbar {
                font-family:monospace;
            }
    '''

    #: By default, calibre will use a default image for the masthead (Kindle only).
    #: Override this in your recipe to provide a url to use as a masthead.
    masthead_url = None

    #: By default, the cover image returned by get_cover_url() will be used as
    #: the cover for the periodical.  Overriding this in your recipe instructs
    #: calibre to render the downloaded cover into a frame whose width and height
    #: are expressed as a percentage of the downloaded cover.
    #: cover_margins = (10, 15, '#ffffff') pads the cover with a white margin
    #: 10px on the left and right, 15px on the top and bottom.
    #: Color names defined at http://www.imagemagick.org/script/color.php
    #: Note that for some reason, white does not always work on windows. Use
    #: #ffffff instead
    cover_margins = (0, 0, '#ffffff')

    #: Set to a non empty string to disable this recipe
    #: The string will be used as the disabled message
    recipe_disabled = None


    # See the built-in profiles for examples of these settings.

    def short_title(self):
        return self.title

    def is_link_wanted(self, url, tag):
        '''
        Return True if the link should be followed or False otherwise. By
        default, raises NotImplementedError which causes the downloader to
        ignore it.

        :param url: The URL to be followed
        :param tag: The Tag from which the URL was derived
        '''
        raise NotImplementedError

    def get_cover_url(self):
        '''
        Return a :term:`URL` to the cover image for this issue or `None`.
        By default it returns the value of the member `self.cover_url` which
        is normally `None`. If you want your recipe to download a cover for the e-book
        override this method in your subclass, or set the member variable `self.cover_url`
        before this method is called.
        '''
        return getattr(self, 'cover_url', None)

    def get_masthead_url(self):
        '''
        Return a :term:`URL` to the masthead image for this issue or `None`.
        By default it returns the value of the member `self.masthead_url` which
        is normally `None`. If you want your recipe to download a masthead for the e-book
        override this method in your subclass, or set the member variable `self.masthead_url`
        before this method is called.
        Masthead images are used in Kindle MOBI files.
        '''
        return getattr(self, 'masthead_url', None)

    def get_feeds(self):
        '''
        Return a list of :term:`RSS` feeds to fetch for this profile. Each element of the list
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
    def image_url_processor(cls, baseurl, url):
        '''
        Perform some processing on image urls (perhaps removing size restrictions for
        dynamically generated images, etc.) and return the precessed URL.
        '''
        return url

    @classmethod
    def get_browser(cls, *args, **kwargs):
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
        br = browser(*args, **kwargs)
        br.addheaders += [('Accept', '*/*')]
        return br

    def clone_browser(self, br):
        '''
        Clone the browser br. Cloned browsers are used for multi-threaded
        downloads, since mechanize is not thread safe. The default cloning
        routines should capture most browser customization, but if you do
        something exotic in your recipe, you should override this method in
        your recipe and clone manually.

        Cloned browser instances use the same, thread-safe CookieJar by
        default, unless you have customized cookie handling.
        '''
        if callable(getattr(br, 'clone_browser', None)):
            return br.clone_browser()

        # Uh-oh recipe using something exotic, call get_browser
        return self.get_browser()

    @property
    def cloned_browser(self):
        if self.get_browser.im_func is BasicNewsRecipe.get_browser.im_func:
            # We are using the default get_browser, which means no need to
            # clone
            br = BasicNewsRecipe.get_browser(self)
        else:
            br = self.clone_browser(self.browser)
        return br

    def get_article_url(self, article):
        '''
        Override in a subclass to customize extraction of the :term:`URL` that points
        to the content for each article. Return the
        article URL. It is called with `article`, an object representing a parsed article
        from a feed. See `feedparser <http://www.feedparser.org/docs/>`_.
        By default it looks for the original link (for feeds syndicated via a
        service like feedburner or pheedo) and if found,
        returns that or else returns
        `article.link <http://www.feedparser.org/docs/reference-entry-link.html>`_.
        '''
        for key in article.keys():
            if key.endswith('_origlink'):
                url = article[key]
                if url and url.startswith('http://'):
                    return url
        return article.get('link',  None)

    def skip_ad_pages(self, soup):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        any of the cleanup attributes like remove_tags, keep_only_tags are
        applied. Note that preprocess_regexps will have already been applied.
        It is meant to allow the recipe to skip ad pages. If the soup represents
        an ad page, return the HTML of the real page. Otherwise return
        None.

        `soup`: A `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        instance containing the downloaded :term:`HTML`.
        '''
        return None

    def preprocess_raw_html(self, raw_html, url):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        it is parsed into an object tree. raw_html is a unicode string
        representing the raw HTML downloaded from the web. url is the URL from
        which the HTML was downloaded.

        Note that this method acts *before* preprocess_regexps.

        This method must return the processed raw_html as a unicode object.
        '''
        return raw_html

    def preprocess_raw_html_(self, raw_html, url):
        raw_html = self.preprocess_raw_html(raw_html, url)
        if self.auto_cleanup:
            try:
                raw_html = self.extract_readable_article(raw_html, url)
            except:
                self.log.exception('Auto cleanup of URL: %r failed'%url)

        return raw_html

    def preprocess_html(self, soup):
        '''
        This method is called with the source of each downloaded :term:`HTML` file, before
        it is parsed for links and images. It is called after the cleanup as
        specified by remove_tags etc.
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

        :param soup: A `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_  instance containing the downloaded :term:`HTML`.
        :param first_fetch: True if this is the first page of an article.

        '''
        return soup

    def cleanup(self):
        '''
        Called after all articles have been download. Use it to do any cleanup like
        logging out of subscription sites, etc.
        '''
        pass

    def index_to_soup(self, url_or_raw, raw=False):
        '''
        Convenience method that takes an URL to the index page and returns
        a `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/documentation.html>`_
        of it.

        `url_or_raw`: Either a URL or the downloaded index page as a string
        '''
        if re.match(r'\w+://', url_or_raw):
            # We may be called in a thread (in the skip_ad_pages method), so
            # clone the browser to be safe. We cannot use self.cloned_browser
            # as it may or may not actually clone the browser, depending on if
            # the recipe implements get_browser() or not
            br = self.clone_browser(self.browser)
            open_func = getattr(br, 'open_novisit', br.open)
            with closing(open_func(url_or_raw)) as f:
                _raw = f.read()
            if not _raw:
                raise RuntimeError('Could not fetch index from %s'%url_or_raw)
        else:
            _raw = url_or_raw
        if raw:
            return _raw
        if not isinstance(_raw, unicode) and self.encoding:
            if callable(self.encoding):
                _raw = self.encoding(_raw)
            else:
                _raw = _raw.decode(self.encoding, 'replace')
        massage = list(BeautifulSoup.MARKUP_MASSAGE)
        enc = 'cp1252' if callable(self.encoding) or self.encoding is None else self.encoding
        massage.append((re.compile(r'&(\S+?);'), lambda match:
            entity_to_unicode(match, encoding=enc)))
        return BeautifulSoup(_raw, markupMassage=massage)

    def extract_readable_article(self, html, url):
        '''
        Extracts main article content from 'html', cleans up and returns as a (article_html, extracted_title) tuple.
        Based on the original readability algorithm by Arc90.
        '''
        from calibre.ebooks.readability import readability
        from lxml.html import (fragment_fromstring, tostring,
                document_fromstring)

        doc = readability.Document(html, self.log, url=url,
                keep_elements=self.auto_cleanup_keep)
        article_html = doc.summary()
        extracted_title = doc.title()

        try:
            frag = fragment_fromstring(article_html)
        except:
            doc = document_fromstring(article_html)
            frag = doc.xpath('//body')[-1]
        if frag.tag == 'html':
            root = frag
        elif frag.tag == 'body':
            root = document_fromstring(
                u'<html><head><title>%s</title></head></html>' %
                extracted_title)
            root.append(frag)
        else:
            root = document_fromstring(
                u'<html><head><title>%s</title></head><body/></html>' %
                extracted_title)
            root.xpath('//body')[0].append(frag)

        body = root.xpath('//body')[0]
        has_title = False
        for x in body.iterdescendants():
            if x.text == extracted_title:
                has_title = True
        inline_titles = body.xpath('//h1|//h2')
        if not has_title and not inline_titles:
            heading = body.makeelement('h2')
            heading.text = extracted_title
            body.insert(0, heading)

        raw_html = tostring(root, encoding=unicode)

        return raw_html

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
            'content'     : The full article (can be an empty string). Obsolete
                            do not use, instead save the content to a temporary
                            file and pass a file:///path/to/temp/file.html as
                            the URL.
            }

        For an example, see the recipe for downloading `The Atlantic`.
        In addition, you can add 'author' for the author of the article.
        '''
        raise NotImplementedError

    def get_obfuscated_article(self, url):
        '''
        If you set `articles_are_obfuscated` this method is called with
        every article URL. It should return the path to a file on the filesystem
        that contains the article HTML. That file is processed by the recursive
        HTML fetching engine, so it can contain links to pages/images on the web.

        This method is typically useful for sites that try to make it difficult to
        access article content automatically.
        '''
        raise NotImplementedError

    def add_toc_thumbnail(self, article, src):
        '''
        Call this from populate_article_metadata with the src attribute of an
        <img> tag from the article that is appropriate for use as the thumbnail
        representing the article in the Table of Contents. Whether the
        thumbnail is actually used is device dependent (currently only used by
        the Kindles). Note that the referenced image must be one that was
        successfully downloaded, otherwise it will be ignored.
        '''
        if not src or not hasattr(article, 'toc_thumbnail'):
            return

        src = src.replace('\\', '/')
        if re.search(r'feed_\d+/article_\d+/images/img', src, flags=re.I) is None:
            self.log.warn('Ignoring invalid TOC thumbnail image: %r'%src)
            return
        article.toc_thumbnail = re.sub(r'^.*?feed', 'feed',
                src, flags=re.IGNORECASE)

    def populate_article_metadata(self, article, soup, first):
        '''
        Called when each HTML page belonging to article is downloaded.
        Intended to be used to get article metadata like author/summary/etc.
        from the parsed HTML (soup).
        :param article: A object of class :class:`calibre.web.feeds.Article`.
        If you change the summary, remember to also change the
        text_summary
        :param soup: Parsed HTML belonging to this article
        :param first: True iff the parsed HTML is the first page of the article.
        '''
        pass

    def postprocess_book(self, oeb, opts, log):
        '''
        Run any needed post processing on the parsed downloaded e-book.

        :param oeb: An OEBBook object
        :param opts: Conversion options
        '''
        pass

    def __init__(self, options, log, progress_reporter):
        '''
        Initialize the recipe.
        :param options: Parsed commandline options
        :param parser:  Command line option parser. Used to intelligently merge options.
        :param progress_reporter: A Callable that takes two arguments: progress (a number between 0 and 1) and a string message. The message should be optional.
        '''
        self.log = log
        if not isinstance(self.title, unicode):
            self.title = unicode(self.title, 'utf-8', 'replace')

        self.debug = options.verbose > 1
        self.output_dir = os.path.abspath(os.getcwdu())
        self.verbose = options.verbose
        self.test = options.test
        self.username = options.username
        self.password = options.password
        self.lrf = options.lrf
        self.output_profile = options.output_profile
        self.touchscreen = getattr(self.output_profile, 'touchscreen', False)
        if self.touchscreen:
            self.template_css += self.output_profile.touchscreen_news_css

        if options.test:
            self.max_articles_per_feed = 2
            self.simultaneous_downloads = min(4, self.simultaneous_downloads)

        if self.debug:
            self.verbose = True
        self.report_progress = progress_reporter

        if isinstance(self.feeds, basestring):
            self.feeds = eval(self.feeds)
            if isinstance(self.feeds, basestring):
                self.feeds = [self.feeds]

        if self.needs_subscription and (\
                self.username is None or self.password is None or \
                (not self.username and not self.password)):
            if self.needs_subscription != 'optional':
                raise ValueError(_('The "%s" recipe needs a username and password.')%self.title)

        self.browser = self.get_browser()
        self.image_map, self.image_counter = {}, 1
        self.css_map = {}

        web2disk_cmdline = [ 'web2disk',
            '--timeout', str(self.timeout),
            '--max-recursions', str(self.recursions),
            '--delay', str(self.delay),
            ]

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
                      'skip_ad_pages', 'preprocess_html', 'remove_tags_after',
                      'remove_tags_before', 'is_link_wanted'):
            setattr(self.web2disk_options, extra, getattr(self, extra))
        self.web2disk_options.postprocess_html = self._postprocess_html
        self.web2disk_options.encoding = self.encoding
        self.web2disk_options.preprocess_raw_html = self.preprocess_raw_html_

        if self.delay > 0:
            self.simultaneous_downloads = 1

        self.navbar = templates.TouchscreenNavBarTemplate() if self.touchscreen else \
                      templates.NavBarTemplate()
        self.failed_downloads = []
        self.partial_failures = []


    def _postprocess_html(self, soup, first_fetch, job_info):
        if self.no_stylesheets:
            for link in list(soup.findAll('link', type=re.compile('css')))+list(soup.findAll('style')):
                link.extract()
        head = soup.find('head')
        if not head:
            head = soup.find('body')
        if not head:
            head = soup.find(True)
        style = BeautifulSoup(u'<style type="text/css" title="override_css">%s</style>'%(self.template_css +'\n\n'+(self.extra_css if self.extra_css else ''))).find('style')
        head.insert(len(head.contents), style)
        if first_fetch and job_info:
            url, f, a, feed_len = job_info
            body = soup.find('body')
            if body is not None:
                templ = self.navbar.generate(False, f, a, feed_len,
                                             not self.has_single_feed,
                                             url, __appname__,
                                             center=self.center_navbar,
                                             extra_css=self.extra_css)
                elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8')).find('div')
                body.insert(0, elem)
        if self.remove_javascript:
            for script in list(soup.findAll('script')):
                script.extract()
            for o in soup.findAll(onload=True):
                del o['onload']

        for script in list(soup.findAll('noscript')):
            script.extract()
        for attr in self.remove_attributes:
            for x in soup.findAll(attrs={attr:True}):
                del x[attr]
        for base in list(soup.findAll(['base', 'iframe', 'canvas', 'embed',
            'command', 'datalist', 'video', 'audio'])):
            base.extract()

        ans = self.postprocess_html(soup, first_fetch)

        # Nuke HTML5 tags
        for x in ans.findAll(['article', 'aside', 'header', 'footer', 'nav',
            'figcaption', 'figure', 'section']):
            x.name = 'div'

        if job_info:
            url, f, a, feed_len = job_info
            try:
                article = self.feed_objects[f].articles[a]
            except:
                self.log.exception('Failed to get article object for postprocessing')
                pass
            else:
                self.populate_article_metadata(article, ans, first_fetch)
        return ans


    def download(self):
        '''
        Download and pre-process all articles from the feeds in this recipe.
        This method should be called only once on a particular Recipe instance.
        Calling it more than once will lead to undefined behavior.
        :return: Path to index.html
        '''
        try:
            res = self.build_index()
            self.report_progress(1, _('Download finished'))
            if self.failed_downloads:
                self.log.warning(_('Failed to download the following articles:'))
                for feed, article, debug in self.failed_downloads:
                    self.log.warning(article.title, 'from', feed.title)
                    self.log.debug(article.url)
                    self.log.debug(debug)
            if self.partial_failures:
                self.log.warning(_('Failed to download parts of the following articles:'))
                for feed, atitle, aurl, debug in self.partial_failures:
                    self.log.warning(atitle + _(' from ') + feed)
                    self.log.debug(aurl)
                    self.log.warning(_('\tFailed links:'))
                    for l, tb in debug:
                        self.log.warning(l)
                        self.log.debug(tb)
            return res
        finally:
            self.cleanup()

    @property
    def lang_for_html(self):
        try:
            lang = self.language.replace('_', '-').partition('-')[0].lower()
            if lang == 'und':
                lang = None
        except:
            lang = None
        return lang

    def feeds2index(self, feeds):
        templ = (templates.TouchscreenIndexTemplate if self.touchscreen else
                templates.IndexTemplate)
        templ = templ(lang=self.lang_for_html)
        css = self.template_css + '\n\n' +(self.extra_css if self.extra_css else '')
        timefmt = self.timefmt
        return templ.generate(self.title, "mastheadImage.jpg", timefmt, feeds,
                              extra_css=css).render(doctype='xhtml')

    @classmethod
    def description_limiter(cls, src):
        if not src:
            return ''
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
        ans = src[:npos+1]
        if len(ans) < len(src):
            return ans+u'\u2026' if isinstance(ans, unicode) else ans + '...'
        return ans

    def feed2index(self, f, feeds):
        feed = feeds[f]
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


        templ = (templates.TouchscreenFeedTemplate if self.touchscreen else
                    templates.FeedTemplate)
        templ = templ(lang=self.lang_for_html)
        css = self.template_css + '\n\n' +(self.extra_css if self.extra_css else '')

        return templ.generate(f, feeds, self.description_limiter,
                              extra_css=css).render(doctype='xhtml')


    def _fetch_article(self, url, dir_, f, a, num_of_feeds):
        br = self.browser
        if self.get_browser.im_func is BasicNewsRecipe.get_browser.im_func:
            # We are using the default get_browser, which means no need to
            # clone
            br = BasicNewsRecipe.get_browser(self)
        else:
            br = self.clone_browser(self.browser)
        self.web2disk_options.browser = br
        fetcher = RecursiveFetcher(self.web2disk_options, self.log,
                self.image_map, self.css_map,
                (url, f, a, num_of_feeds))
        fetcher.browser = br
        fetcher.base_dir = dir_
        fetcher.current_dir = dir_
        fetcher.show_progress = False
        fetcher.image_url_processor = self.image_url_processor
        res, path, failures = fetcher.start_fetch(url), fetcher.downloaded_paths, fetcher.failed_links
        if not res or not os.path.exists(res):
            msg = _('Could not fetch article.') + ' '
            if self.debug:
                msg += _('The debug traceback is available earlier in this log')
            else:
                msg += _('Run with -vv to see the reason')
            raise Exception(msg)

        return res, path, failures

    def fetch_article(self, url, dir, f, a, num_of_feeds):
        return self._fetch_article(url, dir, f, a, num_of_feeds)

    def fetch_obfuscated_article(self, url, dir, f, a, num_of_feeds):
        path = os.path.abspath(self.get_obfuscated_article(url))
        url = ('file:'+path) if iswindows else ('file://'+path)
        return self._fetch_article(url, dir, f, a, num_of_feeds)

    def fetch_embedded_article(self, article, dir, f, a, num_of_feeds):
        templ = templates.EmbeddedContent()
        raw = templ.generate(article).render('html')
        with PersistentTemporaryFile('_feeds2disk.html') as pt:
            pt.write(raw)
            url = ('file:'+pt.name) if iswindows else ('file://'+pt.name)
        return self._fetch_article(url, dir,  f, a, num_of_feeds)


    def build_index(self):
        self.report_progress(0, _('Fetching feeds...'))
        try:
            feeds = feeds_from_index(self.parse_index(), oldest_article=self.oldest_article,
                                     max_articles_per_feed=self.max_articles_per_feed,
                                     log=self.log)
            self.report_progress(0, _('Got feeds from index page'))
        except NotImplementedError:
            feeds = self.parse_feeds()

        if not feeds:
            raise ValueError('No articles found, aborting')

        #feeds = FeedCollection(feeds)

        self.report_progress(0, _('Trying to download cover...'))
        self.download_cover()
        self.report_progress(0, _('Generating masthead...'))
        self.masthead_path = None

        try:
            murl = self.get_masthead_url()
        except:
            self.log.exception('Failed to get masthead url')
            murl = None

        if murl is not None:
            # Try downloading the user-supplied masthead_url
            # Failure sets self.masthead_path to None
            self.download_masthead(murl)
        if self.masthead_path is None:
            self.log.info("Synthesizing mastheadImage")
            self.masthead_path = os.path.join(self.output_dir, 'mastheadImage.jpg')
            try:
                self.default_masthead_image(self.masthead_path)
            except:
                self.log.exception('Failed to generate default masthead image')
                self.masthead_path = None

        if self.test:
            feeds = feeds[:2]
        self.has_single_feed = len(feeds) == 1

        index = os.path.join(self.output_dir, 'index.html')

        html = self.feeds2index(feeds)
        with open(index, 'wb') as fi:
            fi.write(html)

        self.jobs = []

        if self.reverse_article_order:
            for feed in feeds:
                if hasattr(feed, 'reverse'):
                    feed.reverse()

        self.feed_objects = feeds
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
                try:
                    url = self.print_version(article.url)
                except NotImplementedError:
                    url = article.url
                except:
                    self.log.exception('Failed to find print version for: '+article.url)
                    url = None
                if not url:
                    continue
                func, arg = (self.fetch_embedded_article, article) \
                            if self.use_embedded_content or (self.use_embedded_content == None and feed.has_embedded_content()) \
                            else \
                            ((self.fetch_obfuscated_article if self.articles_are_obfuscated \
                              else self.fetch_article), url)
                req = WorkRequest(func, (arg, art_dir, f, a, len(feed)),
                                      {}, (f, a), self.article_downloaded,
                                      self.error_in_article_download)
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
            html = self.feed2index(f,feeds)
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            with open(os.path.join(feed_dir, 'index.html'), 'wb') as fi:
                fi.write(html)
        self.create_opf(feeds)
        self.report_progress(1, _('Feeds downloaded to %s')%index)

        return index

    def _download_cover(self):
        self.cover_path = None
        try:
            cu = self.get_cover_url()
        except Exception as err:
            self.log.error(_('Could not download cover: %s')%as_unicode(err))
            self.log.debug(traceback.format_exc())
        else:
            if not cu:
                return
            cdata = None
            if os.access(cu, os.R_OK):
                cdata = open(cu, 'rb').read()
            else:
                self.report_progress(1, _('Downloading cover from %s')%cu)
                with closing(self.browser.open(cu)) as r:
                    cdata = r.read()
            if not cdata:
                return
            ext = cu.split('/')[-1].rpartition('.')[-1].lower().strip()
            if ext == 'pdf':
                from calibre.ebooks.metadata.pdf import get_metadata
                stream = cStringIO.StringIO(cdata)
                cdata = None
                mi = get_metadata(stream)
                if mi.cover_data and mi.cover_data[1]:
                    cdata = mi.cover_data[1]
            if not cdata:
                return
            if self.cover_margins[0] or self.cover_margins[1]:
                cdata = add_borders_to_image(cdata,
                            left=self.cover_margins[0],right=self.cover_margins[0],
                            top=self.cover_margins[1],bottom=self.cover_margins[1],
                            border_color=self.cover_margins[2])

            cpath = os.path.join(self.output_dir, 'cover.jpg')
            save_cover_data_to(cdata, cpath)
            self.cover_path = cpath

    def download_cover(self):
        self.cover_path = None
        try:
            self._download_cover()
        except:
            self.log.exception('Failed to download cover')
            self.cover_path = None

    def _download_masthead(self, mu):
        ext = mu.rpartition('.')[-1]
        if '?' in ext:
            ext = ''
        ext = ext.lower() if ext else 'jpg'
        mpath = os.path.join(self.output_dir, 'masthead_source.'+ext)
        outfile = os.path.join(self.output_dir, 'mastheadImage.jpg')
        if os.access(mu, os.R_OK):
            with open(mpath, 'wb') as mfile:
                mfile.write(open(mu, 'rb').read())
        else:
            with nested(open(mpath, 'wb'), closing(self.browser.open(mu))) as (mfile, r):
                mfile.write(r.read())
            self.report_progress(1, _('Masthead image downloaded'))
        self.prepare_masthead_image(mpath, outfile)
        self.masthead_path = outfile
        if os.path.exists(mpath):
            os.remove(mpath)


    def download_masthead(self, url):
        try:
            self._download_masthead(url)
        except:
            self.log.exception("Failed to download supplied masthead_url")

    def default_cover(self, cover_file):
        '''
        Create a generic cover for recipes that dont have a cover
        '''
        try:
            from calibre.ebooks import calibre_cover
            title = self.title if isinstance(self.title, unicode) else \
                    self.title.decode(preferred_encoding, 'replace')
            date = strftime(self.timefmt)
            img_data = calibre_cover(title, date)
            cover_file.write(img_data)
            cover_file.flush()
        except:
            self.log.exception('Failed to generate default cover')
            return False
        return True

    def get_masthead_title(self):
        'Override in subclass to use something other than the recipe title'
        return self.title

    MI_WIDTH = 600
    MI_HEIGHT = 60

    def default_masthead_image(self, out_path):
        from calibre.ebooks import generate_masthead
        generate_masthead(self.get_masthead_title(), output_path=out_path,
                width=self.MI_WIDTH, height=self.MI_HEIGHT)

    def prepare_masthead_image(self, path_to_image, out_path):
        from calibre import fit_image
        from calibre.utils.magick import Image, create_canvas

        img = Image()
        img.open(path_to_image)
        width, height = img.size
        scaled, nwidth, nheight = fit_image(width, height, self.MI_WIDTH, self.MI_HEIGHT)
        img2 = create_canvas(width, height)
        frame = create_canvas(self.MI_WIDTH, self.MI_HEIGHT)
        img2.compose(img)
        if scaled:
            img2.size = (nwidth, nheight, 'LanczosFilter', 0.5)
        left = int((self.MI_WIDTH - nwidth)/2.0)
        top = int((self.MI_HEIGHT - nheight)/2.0)
        frame.compose(img2, left, top)
        frame.save(out_path)

    def create_opf(self, feeds, dir=None):
        if dir is None:
            dir = self.output_dir
        title = self.short_title()
        if self.output_profile.periodical_date_in_title:
            title += strftime(self.timefmt)
        mi = MetaInformation(title, [__appname__])
        mi.publisher = __appname__
        mi.author_sort = __appname__
        mi.publication_type = 'periodical:'+self.publication_type+':'+self.short_title()
        mi.timestamp = nowf()
        article_titles, aseen = [], set()
        for f in feeds:
            for a in f:
                if a.title and a.title not in aseen:
                    aseen.add(a.title)
                    article_titles.append(force_unicode(a.title, 'utf-8'))

        mi.comments = self.description
        if not isinstance(mi.comments, unicode):
            mi.comments = mi.comments.decode('utf-8', 'replace')
        mi.comments += ('\n\n' + _('Articles in this issue: ') + '\n' +
                '\n\n'.join(article_titles))

        language = canonicalize_lang(self.language)
        if language is not None:
            mi.language = language
        mi.pubdate = nowf()
        opf_path = os.path.join(dir, 'index.opf')
        ncx_path = os.path.join(dir, 'index.ncx')

        opf = OPFCreator(dir, mi)
        # Add mastheadImage entry to <guide> section
        mp = getattr(self, 'masthead_path', None)
        if mp is not None and os.access(mp, os.R_OK):
            from calibre.ebooks.metadata.opf2 import Guide
            ref = Guide.Reference(os.path.basename(self.masthead_path), os.getcwdu())
            ref.type = 'masthead'
            ref.title = 'Masthead Image'
            opf.guide.append(ref)

        manifest = [os.path.join(dir, 'feed_%d'%i) for i in range(len(feeds))]
        manifest.append(os.path.join(dir, 'index.html'))
        manifest.append(os.path.join(dir, 'index.ncx'))

        # Get cover
        cpath = getattr(self, 'cover_path', None)
        if cpath is None:
            pf = open(os.path.join(dir, 'cover.jpg'), 'wb')
            if self.default_cover(pf):
                cpath =  pf.name
        if cpath is not None and os.access(cpath, os.R_OK):
            opf.cover = cpath
            manifest.append(cpath)

        # Get masthead
        mpath = getattr(self, 'masthead_path', None)
        if mpath is not None and os.access(mpath, os.R_OK):
            manifest.append(mpath)

        opf.create_manifest_from_files_in(manifest)
        for mani in opf.manifest:
            if mani.path.endswith('.ncx'):
                mani.id = 'ncx'
            if mani.path.endswith('mastheadImage.jpg'):
                mani.id = 'masthead-image'

        entries = ['index.html']
        toc = TOC(base_path=dir)
        self.play_order_counter = 0
        self.play_order_map = {}


        def feed_index(num, parent):
            f = feeds[num]
            for j, a in enumerate(f):
                if getattr(a, 'downloaded', False):
                    adir = 'feed_%d/article_%d/'%(num, j)
                    auth = a.author
                    if not auth:
                        auth = None
                    desc = a.text_summary
                    if not desc:
                        desc = None
                    else:
                        desc = self.description_limiter(desc)
                    tt = a.toc_thumbnail if a.toc_thumbnail else None
                    entries.append('%sindex.html'%adir)
                    po = self.play_order_map.get(entries[-1], None)
                    if po is None:
                        self.play_order_counter += 1
                        po = self.play_order_counter
                    parent.add_item('%sindex.html'%adir, None,
                            a.title if a.title else _('Untitled Article'),
                            play_order=po, author=auth,
                            description=desc, toc_thumbnail=tt)
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
        if len(feeds) == 0:
            raise Exception('All feeds are empty, aborting.')

        if len(feeds) > 1:
            for i, f in enumerate(feeds):
                entries.append('feed_%d/index.html'%i)
                po = self.play_order_map.get(entries[-1], None)
                if po is None:
                    self.play_order_counter += 1
                    po = self.play_order_counter
                auth = getattr(f, 'author', None)
                if not auth:
                    auth = None
                desc = getattr(f, 'description', None)
                if not desc:
                    desc = None
                feed_index(i, toc.add_item('feed_%d/index.html'%i, None,
                    f.title, play_order=po, description=desc, author=auth))

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
        self.log.debug('Downloaded article:', article.title, 'from', article.url)
        article.orig_url = article.url
        article.url = 'article_%d/index.html'%a
        article.downloaded = True
        article.sub_pages  = result[1][1:]
        self.jobs_done += 1
        self.report_progress(float(self.jobs_done)/len(self.jobs),
            _(u'Article downloaded: %s')%force_unicode(article.title))
        if result[2]:
            self.partial_failures.append((request.feed.title, article.title, article.url, result[2]))

    def error_in_article_download(self, request, traceback):
        self.jobs_done += 1
        self.log.error('Failed to download article:', request.article.title,
        'from', request.article.url)
        self.log.debug(traceback)
        self.log.debug('\n')
        self.report_progress(float(self.jobs_done)/len(self.jobs),
                _('Article download failed: %s')%force_unicode(request.article.title))
        self.failed_downloads.append((request.feed, request.article, traceback))

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
            if url.startswith('feed://'):
                url = 'http'+url[4:]
            self.report_progress(0, _('Fetching feed')+' %s...'%(title if title else url))
            try:
                with closing(self.browser.open(url)) as f:
                    parsed_feeds.append(feed_from_xml(f.read(),
                                          title=title,
                                          log=self.log,
                                          oldest_article=self.oldest_article,
                                          max_articles_per_feed=self.max_articles_per_feed,
                                          get_article_url=self.get_article_url))
                    if (self.delay > 0):
                        time.sleep(self.delay)
            except Exception as err:
                feed = Feed()
                msg = 'Failed feed: %s'%(title if title else url)
                feed.populate_from_preparsed_feed(msg, [])
                feed.description = as_unicode(err)
                parsed_feeds.append(feed)
                self.log.exception(msg)


        remove = [f for f in parsed_feeds if len(f) == 0 and
                self.remove_empty_feeds]
        for f in remove:
            parsed_feeds.remove(f)

        return parsed_feeds

    @classmethod
    def tag_to_string(self, tag, use_alt=True, normalize_whitespace=True):
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
        ans = u''.join(strings)
        if normalize_whitespace:
            ans = re.sub(r'\s+', ' ', ans)
        return ans

    @classmethod
    def soup(cls, raw):
        entity_replace = [(re.compile(ur'&(\S+?);'), partial(entity_to_unicode,
                                                           exceptions=[]))]
        nmassage = list(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(entity_replace)
        return BeautifulSoup(raw, markupMassage=nmassage)

    @classmethod
    def adeify_images(cls, soup):
         '''
         If your recipe when converted to EPUB has problems with images when
         viewed in Adobe Digital Editions, call this method from within
         :meth:`postprocess_html`.
         '''
         for item in soup.findAll('img'):
             for attrib in ['height','width','border','align','style']:
                 if item.has_key(attrib):
                    del item[attrib]
             oldParent = item.parent
             myIndex = oldParent.contents.index(item)
             item.extract()
             divtag = Tag(soup,'div')
             brtag  = Tag(soup,'br')
             oldParent.insert(myIndex,divtag)
             divtag.append(item)
             divtag.append(brtag)
         return soup


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
        self.web2disk_options.browser = self.clone_browser(self.browser)
        fetcher = RecursiveFetcher(self.web2disk_options, self.log)
        fetcher.base_dir = self.output_dir
        fetcher.current_dir = self.output_dir
        fetcher.show_progress = False
        res = fetcher.start_fetch(url)
        self.create_opf()
        return res

class AutomaticNewsRecipe(BasicNewsRecipe):

    auto_cleanup = True

class CalibrePeriodical(BasicNewsRecipe):

    #: Set this to the slug for the calibre periodical
    calibre_periodicals_slug = None

    LOG_IN = 'http://news.calibre-ebook.com/accounts/login'
    needs_subscription = True
    __author__ = 'calibre Periodicals'

    def get_browser(self):
        br = BasicNewsRecipe.get_browser(self)
        br.open(self.LOG_IN)
        br.select_form(name='login')
        br['username'] = self.username
        br['password'] = self.password
        raw = br.submit().read()
        if 'href="/my-account"' not in raw:
            raise LoginFailed(
                    _('Failed to log in, check your username and password for'
                    ' the calibre Periodicals service.'))

        return br

    def download(self):
        self.log('Fetching downloaded recipe')
        try:
            raw = self.browser.open_novisit(
                'http://news.calibre-ebook.com/subscribed_files/%s/0/temp.downloaded_recipe'
                % self.calibre_periodicals_slug
                    ).read()
        except Exception as e:
            if hasattr(e, 'getcode') and e.getcode() == 403:
                raise DownloadDenied(
                        _('You do not have permission to download this issue.'
                        ' Either your subscription has expired or you have'
                        ' exceeded the maximum allowed downloads for today.'))
            raise
        f = cStringIO.StringIO(raw)
        from calibre.utils.zipfile import ZipFile
        zf = ZipFile(f)
        zf.extractall()
        zf.close()
        from calibre.web.feeds.recipes import compile_recipe
        from glob import glob
        try:
            recipe = compile_recipe(open(glob('*.recipe')[0],
                'rb').read())
            self.conversion_options = recipe.conversion_options
        except:
            self.log.exception('Failed to compile downloaded recipe')
        return os.path.abspath('index.html')

