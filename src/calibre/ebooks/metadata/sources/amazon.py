#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import socket, time, re
from urllib import urlencode
from threading import Thread
from Queue import Queue, Empty

from lxml.html import soupparser, tostring

from calibre import as_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata.book.base import Metadata
from calibre.library.comments import sanitize_comments_html
from calibre.utils.date import parse_date

class Worker(Thread): # Get details {{{

    '''
    Get book details from amazons book page in a separate thread
    '''

    def __init__(self, url, result_queue, browser, log, relevance, plugin, timeout=20):
        Thread.__init__(self)
        self.daemon = True
        self.url, self.result_queue = url, result_queue
        self.log, self.timeout = log, timeout
        self.relevance, self.plugin = relevance, plugin
        self.browser = browser.clone_browser()
        self.cover_url = self.amazon_id = self.isbn = None

    def run(self):
        try:
            self.get_details()
        except:
            self.log.exception('get_details failed for url: %r'%self.url)

    def get_details(self):
        try:
            raw = self.browser.open_novisit(self.url, timeout=self.timeout).read().strip()
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                self.log.error('URL malformed: %r'%self.url)
                return
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                msg = 'Amazon timed out. Try again later.'
                self.log.error(msg)
            else:
                msg = 'Failed to make details query: %r'%self.url
                self.log.exception(msg)
            return

        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        #open('/t/t.html', 'wb').write(raw)

        if '<title>404 - ' in raw:
            self.log.error('URL malformed: %r'%self.url)
            return

        try:
            root = soupparser.fromstring(clean_ascii_chars(raw))
        except:
            msg = 'Failed to parse amazon details page: %r'%self.url
            self.log.exception(msg)
            return

        errmsg = root.xpath('//*[@id="errorMessage"]')
        if errmsg:
            msg = 'Failed to parse amazon details page: %r'%self.url
            msg += tostring(errmsg, method='text', encoding=unicode).strip()
            self.log.error(msg)
            return

        self.parse_details(root)

    def parse_details(self, root):
        try:
            asin = self.parse_asin(root)
        except:
            self.log.exception('Error parsing asin for url: %r'%self.url)
            asin = None

        try:
            title = self.parse_title(root)
        except:
            self.log.exception('Error parsing title for url: %r'%self.url)
            title = None

        try:
            authors = self.parse_authors(root)
        except:
            self.log.exception('Error parsing authors for url: %r'%self.url)
            authors = []


        if not title or not authors or not asin:
            self.log.error('Could not find title/authors/asin for %r'%self.url)
            self.log.error('ASIN: %r Title: %r Authors: %r'%(asin, title,
                authors))
            return

        mi = Metadata(title, authors)
        mi.set_identifier('amazon', asin)
        self.amazon_id = asin

        try:
            mi.rating = self.parse_rating(root)
        except:
            self.log.exception('Error parsing ratings for url: %r'%self.url)

        try:
            mi.comments = self.parse_comments(root)
        except:
            self.log.exception('Error parsing comments for url: %r'%self.url)

        try:
            self.cover_url = self.parse_cover(root)
        except:
            self.log.exception('Error parsing cover for url: %r'%self.url)
        mi.has_cover = bool(self.cover_url)

        pd = root.xpath('//h2[text()="Product Details"]/../div[@class="content"]')
        if pd:
            pd = pd[0]

            try:
                isbn = self.parse_isbn(pd)
                if isbn:
                    self.isbn = mi.isbn = isbn
            except:
                self.log.exception('Error parsing ISBN for url: %r'%self.url)

            try:
                mi.publisher = self.parse_publisher(pd)
            except:
                self.log.exception('Error parsing publisher for url: %r'%self.url)

            try:
                mi.pubdate = self.parse_pubdate(pd)
            except:
                self.log.exception('Error parsing publish date for url: %r'%self.url)

            try:
                lang = self.parse_language(pd)
                if lang:
                    mi.language = lang
            except:
                self.log.exception('Error parsing language for url: %r'%self.url)

        else:
            self.log.warning('Failed to find product description for url: %r'%self.url)

        mi.source_relevance = self.relevance

        if self.amazon_id:
            if self.isbn:
                self.plugin.cache_isbn_to_identifier(self.isbn, self.amazon_id)
            if self.cover_url:
                self.plugin.cache_identifier_to_cover_url(self.amazon_id,
                        self.cover_url)

        self.plugin.clean_downloaded_metadata(mi)

        self.result_queue.put(mi)

    def parse_asin(self, root):
        link = root.xpath('//link[@rel="canonical" and @href]')
        for l in link:
            return l.get('href').rpartition('/')[-1]

    def parse_title(self, root):
        tdiv = root.xpath('//h1[@class="parseasinTitle"]')[0]
        actual_title = tdiv.xpath('descendant::*[@id="btAsinTitle"]')
        if actual_title:
            title = tostring(actual_title[0], encoding=unicode,
                    method='text').strip()
        else:
            title = tostring(tdiv, encoding=unicode, method='text').strip()
        return re.sub(r'[(\[].*[)\]]', '', title).strip()

    def parse_authors(self, root):
        x = '//h1[@class="parseasinTitle"]/following-sibling::span/*[(name()="a" and @href) or (name()="span" and @class="contributorNameTrigger")]'
        aname = root.xpath(x)
        for x in aname:
            x.tail = ''
        authors = [tostring(x, encoding=unicode, method='text').strip() for x
                in aname]
        return authors

    def parse_rating(self, root):
        ratings = root.xpath('//div[@class="jumpBar"]/descendant::span[@class="asinReviewsSummary"]')
        pat = re.compile(r'([0-9.]+) out of (\d+) stars')
        if ratings:
            for elem in ratings[0].xpath('descendant::*[@title]'):
                t = elem.get('title').strip()
                m = pat.match(t)
                if m is not None:
                    return float(m.group(1))/float(m.group(2)) * 5

    def parse_comments(self, root):
        desc = root.xpath('//div[@id="productDescription"]/*[@class="content"]')
        if desc:
            desc = desc[0]
            for c in desc.xpath('descendant::*[@class="seeAll" or'
                    ' @class="emptyClear" or @href]'):
                c.getparent().remove(c)
            desc = tostring(desc, method='html', encoding=unicode).strip()
            # Encoding bug in Amazon data U+fffd (replacement char)
            # in some examples it is present in place of '
            desc = desc.replace('\ufffd', "'")
            # remove all attributes from tags
            desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
            # Collapse whitespace
            #desc = re.sub('\n+', '\n', desc)
            #desc = re.sub(' +', ' ', desc)
            # Remove the notice about text referring to out of print editions
            desc = re.sub(r'(?s)<em>--This text ref.*?</em>', '', desc)
            # Remove comments
            desc = re.sub(r'(?s)<!--.*?-->', '', desc)
            return sanitize_comments_html(desc)

    def parse_cover(self, root):
        imgs = root.xpath('//img[@id="prodImage" and @src]')
        if imgs:
            src = imgs[0].get('src')
            if '/no-image-avail' not in src:
                parts = src.split('/')
                if len(parts) > 3:
                    bn = parts[-1]
                    sparts = bn.split('_')
                    if len(sparts) > 2:
                        bn = sparts[0] + sparts[-1]
                        return ('/'.join(parts[:-1]))+'/'+bn

    def parse_isbn(self, pd):
        for x in reversed(pd.xpath(
            'descendant::*[starts-with(text(), "ISBN")]')):
            if x.tail:
                ans = check_isbn(x.tail.strip())
                if ans:
                    return ans

    def parse_publisher(self, pd):
        for x in reversed(pd.xpath(
            'descendant::*[starts-with(text(), "Publisher:")]')):
            if x.tail:
                ans = x.tail.partition(';')[0]
                return ans.partition('(')[0].strip()

    def parse_pubdate(self, pd):
        for x in reversed(pd.xpath(
            'descendant::*[starts-with(text(), "Publisher:")]')):
            if x.tail:
                ans = x.tail
                date = ans.partition('(')[-1].replace(')', '').strip()
                return parse_date(date, assume_utc=True)

    def parse_language(self, pd):
        for x in reversed(pd.xpath(
            'descendant::*[starts-with(text(), "Language:")]')):
            if x.tail:
                ans = x.tail.strip()
                if ans == 'English':
                    return 'en'
# }}}

class Amazon(Source):

    name = 'Amazon.com'
    description = _('Downloads metadata and covers from Amazon')

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'identifier:amazon',
        'identifier:isbn', 'rating', 'comments', 'publisher', 'pubdate',
        'language'])
    has_html_comments = True
    supports_gzip_transfer_encoding = True

    AMAZON_DOMAINS = {
            'com': _('US'),
            'fr' : _('France'),
            'de' : _('Germany'),
            'uk' : _('UK'),
    }

    def get_book_url(self, identifiers): # {{{
        asin = identifiers.get('amazon', None)
        if asin is None:
            asin = identifiers.get('asin', None)
        if asin:
            return ('amazon', asin, 'http://amzn.com/%s'%asin)
    # }}}

    def create_query(self, log, title=None, authors=None, identifiers={}): # {{{
        domain = self.prefs.get('domain', 'com')

        # See the amazon detailed search page to get all options
        q = {   'search-alias' : 'aps',
                'unfiltered' : '1',
            }

        if domain == 'com':
            q['sort'] = 'relevanceexprank'
        else:
            q['sort'] = 'relevancerank'

        asin = identifiers.get('amazon', None)
        isbn = check_isbn(identifiers.get('isbn', None))

        if asin is not None:
            q['field-keywords'] = asin
        elif isbn is not None:
            q['field-isbn'] = isbn
        else:
            # Only return book results
            q['search-alias'] = 'stripbooks'
            if title:
                title_tokens = list(self.get_title_tokens(title))
                if title_tokens:
                    q['field-title'] = ' '.join(title_tokens)
            if authors:
                author_tokens = self.get_author_tokens(authors,
                        only_first_author=True)
                if author_tokens:
                    q['field-author'] = ' '.join(author_tokens)

        if not ('field-keywords' in q or 'field-isbn' in q or
                ('field-title' in q)):
            # Insufficient metadata to make an identify query
            return None

        latin1q = dict([(x.encode('latin1', 'ignore'), y.encode('latin1',
            'ignore')) for x, y in
            q.iteritems()])
        url = 'http://www.amazon.%s/s/?'%domain + urlencode(latin1q)
        return url

    # }}}

    def get_cached_cover_url(self, identifiers): # {{{
        url = None
        asin = identifiers.get('amazon', None)
        if asin is None:
            asin = identifiers.get('asin', None)
        if asin is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                asin = self.cached_isbn_to_identifier(isbn)
        if asin is not None:
            url = self.cached_identifier_to_cover_url(asin)

        return url
    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None, # {{{
            identifiers={}, timeout=30):
        '''
        Note this method will retry without identifiers automatically if no
        match is found with identifiers.
        '''
        query = self.create_query(log, title=title, authors=authors,
                identifiers=identifiers)
        if query is None:
            log.error('Insufficient metadata to construct query')
            return
        br = self.browser
        try:
            raw = br.open_novisit(query, timeout=timeout).read().strip()
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                log.error('Query malformed: %r'%query)
                return
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                msg = _('Amazon timed out. Try again later.')
                log.error(msg)
            else:
                msg = 'Failed to make identify query: %r'%query
                log.exception(msg)
            return as_unicode(msg)


        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]

        matches = []
        found = '<title>404 - ' not in raw

        if found:
            try:
                root = soupparser.fromstring(clean_ascii_chars(raw))
            except:
                msg = 'Failed to parse amazon page for query: %r'%query
                log.exception(msg)
                return msg

                errmsg = root.xpath('//*[@id="errorMessage"]')
                if errmsg:
                    msg = tostring(errmsg, method='text', encoding=unicode).strip()
                    log.error(msg)
                    # The error is almost always a not found error
                    found = False

        if found:
            for div in root.xpath(r'//div[starts-with(@id, "result_")]'):
                for a in div.xpath(r'descendant::a[@class="title" and @href]'):
                    title = tostring(a, method='text', encoding=unicode).lower()
                    if 'bulk pack' not in title:
                        matches.append(a.get('href'))
                    break
            if not matches:
                # This can happen for some user agents that Amazon thinks are
                # mobile/less capable
                log('Trying alternate results page markup')
                for td in root.xpath(
                    r'//div[@id="Results"]/descendant::td[starts-with(@id, "search:Td:")]'):
                    for a in td.xpath(r'descendant::td[@class="dataColumn"]/descendant::a[@href]/span[@class="srTitle"]/..'):
                        title = tostring(a, method='text', encoding=unicode).lower()
                        if 'bulk pack' not in title:
                            matches.append(a.get('href'))
                        break


        # Keep only the top 5 matches as the matches are sorted by relevance by
        # Amazon so lower matches are not likely to be very relevant
        matches = matches[:5]

        if abort.is_set():
            return

        if not matches:
            if identifiers and title and authors:
                log('No matches found with identifiers, retrying using only'
                        ' title and authors')
                return self.identify(log, result_queue, abort, title=title,
                        authors=authors, timeout=timeout)
            log.error('No matches found with query: %r'%query)
            return

        workers = [Worker(url, result_queue, br, log, i, self) for i, url in
                enumerate(matches)]

        for w in workers:
            w.start()
            # Don't send all requests at the same time
            time.sleep(0.1)

        while not abort.is_set():
            a_worker_is_alive = False
            for w in workers:
                w.join(0.2)
                if abort.is_set():
                    break
                if w.is_alive():
                    a_worker_is_alive = True
            if not a_worker_is_alive:
                break

        return None
    # }}}

    def download_cover(self, log, result_queue, abort, # {{{
            title=None, authors=None, identifiers={}, timeout=30):
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title, authors=authors,
                    identifiers=identifiers)
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(key=self.identify_results_keygen(
                title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break
        if cached_url is None:
            log.info('No cover found')
            return

        if abort.is_set():
            return
        br = self.browser
        log('Downloading cover from:', cached_url)
        try:
            cdata = br.open_novisit(cached_url, timeout=timeout).read()
            result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)
    # }}}

if __name__ == '__main__': # tests {{{
    # To run these test use: calibre-debug -e
    # src/calibre/ebooks/metadata/sources/amazon.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            title_test, authors_test)
    test_identify_plugin(Amazon.name,
        [

            ( # An e-book ISBN not on Amazon, one of the authors is
              # unknown to Amazon, so no popup wrapper
                {'identifiers':{'isbn': '9780307459671'},
                    'title':'Invisible Gorilla', 'authors':['Christopher Chabris']},
                [title_test('The Invisible Gorilla: And Other Ways Our Intuitions Deceive Us',
                    exact=True), authors_test(['Christopher Chabris', 'Daniel Simons'])]

            ),

            (  # This isbn not on amazon
                {'identifiers':{'isbn': '8324616489'}, 'title':'Learning Python',
                    'authors':['Lutz']},
                [title_test('Learning Python, 3rd Edition',
                    exact=True), authors_test(['Mark Lutz'])
                 ]

            ),

            ( # Sophisticated comment formatting
                {'identifiers':{'isbn': '9781416580829'}},
                [title_test('Angels & Demons - Movie Tie-In: A Novel',
                    exact=True), authors_test(['Dan Brown'])]
            ),

            ( # No specific problems
                {'identifiers':{'isbn': '0743273567'}},
                [title_test('The great gatsby', exact=True),
                    authors_test(['F. Scott Fitzgerald'])]
            ),

            (  # A newer book
                {'identifiers':{'isbn': '9780316044981'}},
                [title_test('The Heroes', exact=True),
                    authors_test(['Joe Abercrombie'])]

            ),

        ])
# }}}

