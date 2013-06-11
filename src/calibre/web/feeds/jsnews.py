#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re
from io import BytesIO
from functools import partial

from calibre import force_unicode, walk
from calibre.constants import __appname__
from calibre.web.feeds import feeds_from_index
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.web.fetch.javascript import fetch_page,  AbortFetch, links_from_selectors
from calibre.ebooks.chardet import xml_to_unicode, strip_encoding_declarations

def image_data_to_url(data, base='cover'):
    from calibre.utils.imghdr import what
    ans = BytesIO(data)
    ext = what(None, data)
    if not ext:
        if data.startswith(b'%PDF-'):
            ext = 'pdf'
        else:
            ext = 'jpg'
    ans.name = 'cover.' + ext
    return ans

class JavascriptRecipe(BasicNewsRecipe):

    '''

    This recipe class is used to download content from javascript heavy
    sites. It uses a full WebKit browser to do the downloading, therefore it
    can support sites that use javascript to dynamically fetch content.

    Most of the parameters from :class:`BasicNewsRecipe` still apply, apart
    from those noted specifically below. The biggest difference is that you use
    CSS selectors to specify tags to keep and remove as well as links to
    follow, instead of the BeautifulSoup selectors used in
    :class:`BasicNewsRecipe`. Indeed, BeautifulSoup has been completely removed
    and replaced by lxml, whereever you previously expected BeautifulSoup to
    represent parsed HTML, you will now get lxml trees. See
    http://lxml.de/tutorial.html for a tutorial on using lxml.

    The various article pre-processing callbacks such as ``preprocess_html()``
    and ``skip_ad_pages()`` have all been replaced by just two callbacks,
    :meth:`preprocess_stage1` and :meth:`preprocess_stage2`. These methods are
    a passed the browser instance, and can thus do anything they like.

    An important method that you will often have to implement is
    :meth:`load_complete` to tell the download system when a page has finished
    loading and is ready to be scraped.

    '''

    #: Minimum calibre version needed to use this recipe
    requires_version = (0, 9, 34)

    #: List of tags to be removed. Specified tags are removed from downloaded HTML.
    #: A tag is specified using CSS selectors.
    #: A common example::
    #:
    #:   remove_tags = ['div.advert', 'div.tools']
    #:
    #: This will remove all `<div class="advert">` and `<div class="tools">` tags and all
    #: their children from the downloaded :term:`HTML`.
    remove_tags           = ()

    #: Remove all tags that occur after the specified tag.
    #: A tag is specified using CSS selectors.
    #: For example::
    #:
    # :     remove_tags_after = '#content'
    #:
    #: will remove all tags after the first element with `id="content"`.
    remove_tags_after     = None

    #: Remove all tags that occur before the specified tag.
    #: A tag is specified using CSS selectors.
    #: For example::
    #:
    # :     remove_tags_before = '#content'
    #:
    #: will remove all tags before the first element with `id="content"`.
    remove_tags_before    = None

    #: Keep only the specified tags and their children.
    #: Uses the CSS selector syntax.
    #: If this list is not empty, then the `<body>` tag will be emptied and re-filled with
    #: the tags that match the entries in this list. For example::
    #:
    # :     keep_only_tags = ['#content', '#heading']
    #:
    #: will keep only tags that have an `id` attribute of `"content"` or `"heading"`.
    keep_only_tags        = ()

    #: A list of selectors that match <a href> elements that you want followed.
    #: For this to work you must also set recursions to at least 1.
    #: You can get more control by re-implemnting :met:`select_links` in your sub-class.
    links_from_selectors = ()

    def select_links(self, browser, url, recursion_level):
        '''
        Override this method in your recipe to implement arbitrary link following logic. It must return a
        list of URLs, each of which will be downloaded in turn.
        '''
        return links_from_selectors(self.links_from_selectors, self.recursions, browser, url, recursion_level)

    def get_jsbrowser(self, *args, **kwargs):
        '''
        Override this method in your recipe if you want to use a non-standard Browser object.
        '''
        from calibre.web.jsbrowser.browser import Browser
        return Browser(default_timeout=kwargs.get('default_timeout', 120))

    def do_login(self, browser, username, password):
        '''
        This method is used to login to a website that uses a paywall. Implement it in
        your recipe if the site uses a paywall. An example implementation::

            def do_login(self, browser, username, password):
                browser.visit('http://some-page-that-has-a-login')
                form = browser.select_form(nr=0) # Select the first form on the page
                form['username'] = username
                form['password'] = password
                browser.submit(timeout=120) # Submit the form and wait at most two minutes for loading to complete

        Note that you can also select forms with CSS2 selectors, like this::

            browser.select_form('form#login_form')
            browser.select_from('form[name="someform"]')
        '''

        pass

    def get_publication_data(self, browser):
        '''
        Download the cover, the masthead image and the list of sections/articles.
        Should return a dictionary with keys 'index', 'cover' and 'masthead'.
        'cover' and 'masthead' are optional, if not present, they will be auto-generated.
        The index must be in the same format as described in :meth:`parse_index`.
        '''
        raise NotImplementedError('You must implement this method in your recipe')

    def load_complete(self, browser, url, recursion_level):
        '''
        This method is called after every page on the website is loaded. To be
        precise, it is called when the DOM is ready. If further checks need to
        be made, they should be made here. For example, if you want to check
        that some element in the DOM is present, you would use::

            def load_complete(self, browser, url, rl):
                browser.wait_for_element('#article-footer')
                return True

        where article-footer is the id of the element you want to wait for.
        '''
        return True

    def abort_article(self, msg=None):
        '''
        Call this method in any article processing callback to abort the download of the article.
        For example::
            def postprocess_html(self, article, root, url, recursion_level):
                if '/video/' in url:
                    self.abort_article()
                return root

        This will cause this article to be ignored.
        '''
        raise AbortFetch(msg or 'Article fetch aborted')

    def preprocess_stage1(self, article, browser, url, recursion_level):
        '''
        This method is a callback called for every downloaded page, before any cleanup is done.
        '''
        pass

    def preprocess_stage2(self, article, browser, url, recursion_level):
        '''
        This method is a callback called for every downloaded page, after the cleanup is done.
        '''
        pass

    def postprocess_html(self, article, root, url, recursion_level):
        '''
        This method is called with the downloaded html for every page as an lxml
        tree. It is called after all cleanup and related processing is completed.
        You can use it to perform any extra cleanup,or to abort the article
        download (see :meth:`abort_article`).

        :param article: The Article object, which represents the article being currently downloaded
        :param root: The parsed downloaded HTML, as an lxml tree, see http://lxml.de/tutorial.html
        for help with using lxml to manipulate HTML.
        :param url: The URL from which this HTML was downloaded
        :param recursion_level: This is zero for the first page in an article and > 0 for subsequent pages.
        '''
        return root

    def index_to_soup(self, url_or_raw, raw=False):
        '''
        Convenience method that takes an URL to the index page and returns
        a parsed lxml tree representation of it. See http://lxml.de/tutorial.html

        `url_or_raw`: Either a URL or the downloaded index page as a string
        '''
        if re.match(r'\w+://', url_or_raw):
            self.jsbrowser.start_load(url_or_raw)
            html = self.jsbrowser.html
        else:
            html = url_or_raw
        if isinstance(html, bytes):
            html = xml_to_unicode(html)[0]
        html = strip_encoding_declarations(html)
        if raw:
            return html
        import html5lib
        root = html5lib.parse(html, treebuilder='lxml', namespaceHTMLElements=False).getroot()
        return root

# ***************************** Internal API *****************************

    def _preprocess_browser(self, article, browser, url, stage, recursion_level):
        func = getattr(self, 'preprocess_stage%d' % stage)
        return func(article, browser, url, recursion_level)

    def _postprocess_html(self, article, feed_num, art_num, feed_len, root, url, recursion_level):
        from lxml.html.builder import STYLE
        if self.no_stylesheets:
            for link in root.xpath('//link[@href]'):
                if (link.get('type', '') or 'text/css'):
                    link.getparent().remove(link)
            for style in root.xpath('//style'):
                style.getparent().remove(style)

        # Add recipe specific styling
        head = root.xpath('//head|//body')
        head = head[0] if head else next(root.iterdescendants())
        head.append(STYLE(self.template_css + '\n\n' + (self.extra_css or '') + '\n'))

        # Add the top navbar
        if recursion_level == 0:
            body = root.xpath('//body')
            if body:
                templ = self.navbar.generate(
                    False, feed_num, art_num, feed_len, not self.has_single_feed, url,
                    __appname__, center=self.center_navbar,
                    extra_css=self.extra_css)
                body[0].insert(0, templ.root.xpath('//div')[0])

        # Remove javascript
        remove_attrs = set(self.remove_attributes)
        if self.remove_javascript:
            remove_attrs.add('onload')
            for script in root.xpath('//*[name()="script" or name()="noscript"]'):
                script.getparent().remove(script)

        # Remove specified attributes
        for attr in remove_attrs:
            for tag in root.xpath('//*[@%s]' % attr):
                tag.attrib.pop(attr, None)

        # Remove tags that cause problems on ebook devices
        nuke = ['base', 'iframe', 'canvas', 'embed', 'command', 'datalist', 'video', 'audio', 'form']
        for tag in root.xpath('|'.join('//%s' % tag for tag in nuke)):
            tag.getparent().remove(tag)

        root = self.postprocess_html(article, root, url, recursion_level)

        if root is not None:
            # Nuke HTML5 tags
            tags = ['article', 'aside', 'header', 'footer', 'nav', 'figcaption', 'figure', 'section']
            for tag in root.xpath('|'.join('//%s' % tag for tag in tags)):
                tag.tag = 'div'

            self.populate_article_metadata(article, root, recursion_level == 0)

        return root

    def download(self):
        browser = self.jsbrowser = self.get_jsbrowser()
        with browser:
            try:
                if self.needs_subscription and self.username and self.password:
                    self.do_login(browser, self.username, self.password)
                data = self.get_publication_data(browser)

                # Process cover, if any
                cdata = data.get('cover', None)
                if cdata:
                    self.cover_url = image_data_to_url(cdata)
                self.download_cover()

                # Process masthead, if any
                mdata = data.get('masthead', None)
                if mdata:
                    self.masthead_url = image_data_to_url(mdata)
                self.resolve_masthead()

                # Process the list of sections/articles
                return self.build_index(data, browser)
            finally:
                self.cleanup()

    def build_index(self, data, browser):
        sections = data.get('index', None)
        if not sections:
            raise ValueError('No articles found, aborting')

        feeds = feeds_from_index(sections, oldest_article=self.oldest_article,
                                    max_articles_per_feed=self.max_articles_per_feed,
                                    log=self.log)
        if not feeds:
            raise ValueError('No articles found, aborting')
        if self.ignore_duplicate_articles is not None:
            feeds = self.remove_duplicate_articles(feeds)
        if self.test:
            feeds = feeds[:2]
        self.has_single_feed = len(feeds) == 1
        index = os.path.join(self.output_dir, 'index.html')

        html = self.feeds2index(feeds)
        with open(index, 'wb') as fi:
            fi.write(html)

        if self.reverse_article_order:
            for feed in feeds:
                if hasattr(feed, 'reverse'):
                    feed.reverse()

        self.report_progress(0, _('Got feeds from index page'))
        resource_cache = {}

        total = 0
        for feed in feeds:
            total += min(self.max_articles_per_feed, len(feed))
        num = 0

        for f, feed in enumerate(feeds):
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            if not os.path.isdir(feed_dir):
                os.makedirs(feed_dir)

            for a, article in enumerate(feed):
                if a >= self.max_articles_per_feed:
                    break
                num += 1
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

                self.log.debug('Downloading article:', article.title, 'from', url)
                try:
                    pages = fetch_page(
                        url,
                        load_complete=self.load_complete,
                        links=self.select_links,
                        remove=self.remove_tags,
                        keep_only=self.keep_only_tags,
                        preprocess_browser=partial(self._preprocess_browser, article),
                        postprocess_html=partial(self._postprocess_html, article, f, a, len(feed)),
                        remove_before=self.remove_tags_before,
                        remove_after=self.remove_tags_after,
                        remove_javascript=self.remove_javascript,
                        resource_cache=resource_cache, output_dir=art_dir, browser=browser)
                except AbortFetch:
                    self.log.exception('Fetching of article: %r aborted' % article.title)
                    continue
                except Exception:
                    self.log.exception('Fetching of article: %r failed' % article.title)
                    continue
                self.log.debug('Downloaded article:', article.title, 'from', article.url)
                article.orig_url = article.url
                article.url = 'article_%d/index.html'%a
                article.downloaded = True
                article.sub_pages  = pages[1:]
                self.report_progress(float(num)/total,
                    _(u'Article downloaded: %s')%force_unicode(article.title))

        for f, feed in enumerate(feeds):
            html = self.feed2index(f, feeds)
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            with open(os.path.join(feed_dir, 'index.html'), 'wb') as fi:
                fi.write(html)
        if self.no_stylesheets:
            for f in walk(self.output_dir):
                if f.endswith('.css'):
                    os.remove(f)
        self.create_opf(feeds)
        self.report_progress(1, _('Download finished'))
        return index

