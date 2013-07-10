#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, re
from threading import Thread
from Queue import Queue, Empty

from calibre import as_unicode, random_user_agent
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source

def parse_html(raw):
    import html5lib
    from calibre.ebooks.chardet import xml_to_unicode
    from calibre.utils.cleantext import clean_ascii_chars
    raw = clean_ascii_chars(xml_to_unicode(raw, strip_encoding_pats=True,
                                resolve_entities=True, assume_utf8=True)[0])
    return html5lib.parse(raw, treebuilder='lxml',
                              namespaceHTMLElements=False).getroot()

def CSSSelect(expr):
    from cssselect import HTMLTranslator
    from lxml.etree import XPath
    return XPath(HTMLTranslator().css_to_xpath(expr))

def astext(node):
    from lxml import etree
    return etree.tostring(node, method='text', encoding=unicode,
                          with_tail=False).strip()

class Worker(Thread):  # {{{

    def __init__(self, sku, url, relevance, result_queue, br, timeout, log, plugin):
        Thread.__init__(self)
        self.daemon = True
        self.url, self.br, self.log, self.timeout = url, br, log, timeout
        self.result_queue, self.plugin, self.sku = result_queue, plugin, sku
        self.relevance = relevance

    def run(self):
        try:
            raw = self.br.open_novisit(self.url, timeout=self.timeout).read()
        except:
            self.log.exception('Failed to load details page: %r'%self.url)
            return

        try:
            mi = self.parse(raw)
            mi.source_relevance = self.relevance
            self.plugin.clean_downloaded_metadata(mi)
            self.result_queue.put(mi)
        except:
            self.log.exception('Failed to parse details page: %r'%self.url)

    def parse(self, raw):
        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.utils.date import parse_only_date, UNDEFINED_DATE
        root = parse_html(raw)
        sku = CSSSelect('div.sku.attGroup')(root)[0]
        info = sku.getparent()
        top = info.getparent().getparent()
        banner = top.find('div')
        spans = banner.findall('span')
        title = ''
        for i, span in enumerate(spans):
            if i == 0 or '12pt' in span.get('style', ''):
                title += astext(span)
            else:
                break
        authors = [re.sub(r'\(.*\)', '', x).strip() for x in astext(spans[-1]).split(',')]
        mi = Metadata(title.strip(), authors)

        # Identifiers
        isbns = [check_isbn(x.strip()) for x in astext(sku).split(',')]
        for isbn in isbns:
            if isbn:
                self.plugin.cache_isbn_to_identifier(isbn, self.sku)
        isbns = sorted(isbns, key=lambda x:len(x) if x else 0, reverse=True)
        if isbns and isbns[0]:
            mi.isbn = isbns[0]
        mi.set_identifier('edelweiss', self.sku)

        # Tags
        bisac = CSSSelect('div.bisac.attGroup')(root)
        if bisac:
            bisac = astext(bisac[0])
            mi.tags = [x.strip() for x in bisac.split(',')]
            mi.tags = [t[1:].strip() if t.startswith('&') else t for t in mi.tags]

        # Publisher
        pub = CSSSelect('div.supplier.attGroup')(root)
        if pub:
            pub = astext(pub[0])
            mi.publisher = pub

        # Pubdate
        pub = CSSSelect('div.shipDate.attGroupItem')(root)
        if pub:
            pub = astext(pub[0])
            parts = pub.partition(':')[0::2]
            pub = parts[1] or parts[0]
            try:
                if ', Ship Date:' in pub:
                    pub = pub.partition(', Ship Date:')[0]
                q = parse_only_date(pub, assume_utc=True)
                if q.year != UNDEFINED_DATE:
                    mi.pubdate = q
            except:
                self.log.exception('Error parsing published date: %r'%pub)

        # Comments
        comm = ''
        general = CSSSelect('div#pd-general-overview-content')(root)
        if general:
            q = self.render_comments(general[0])
            if q != '<p>No title summary available. </p>':
                comm += q
        general = CSSSelect('div#pd-general-contributor-content')(root)
        if general:
            comm += self.render_comments(general[0])
        general = CSSSelect('div#pd-general-quotes-content')(root)
        if general:
            comm += self.render_comments(general[0])
        if comm:
            mi.comments = comm

        # Cover
        img = CSSSelect('img.title-image[src]')(root)
        if img:
            href = img[0].get('src').replace('jacket_covers/medium/',
                                             'jacket_covers/flyout/')
            self.plugin.cache_identifier_to_cover_url(self.sku, href)

        mi.has_cover = self.plugin.cached_identifier_to_cover_url(self.sku) is not None

        return mi

    def render_comments(self, desc):
        from lxml import etree
        from calibre.library.comments import sanitize_comments_html
        for c in desc.xpath('descendant::noscript'):
            c.getparent().remove(c)
        for a in desc.xpath('descendant::a[@href]'):
            del a.attrib['href']
            a.tag = 'span'
        desc = etree.tostring(desc, method='html', encoding=unicode).strip()

        # remove all attributes from tags
        desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
        # Collapse whitespace
        # desc = re.sub('\n+', '\n', desc)
        # desc = re.sub(' +', ' ', desc)
        # Remove comments
        desc = re.sub(r'(?s)<!--.*?-->', '', desc)
        return sanitize_comments_html(desc)
# }}}

class Edelweiss(Source):

    name = 'Edelweiss'
    description = _('Downloads metadata and covers from Edelweiss - A catalog updated by book publishers')

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset([
        'title', 'authors', 'tags', 'pubdate', 'comments', 'publisher',
        'identifier:isbn', 'identifier:edelweiss'])
    supports_gzip_transfer_encoding = True
    has_html_comments = True

    @property
    def user_agent(self):
        # Pass in an index to random_user_agent() to test with a particular
        # user agent
        return random_user_agent()

    def _get_book_url(self, sku):
        if sku:
            return 'http://edelweiss.abovethetreeline.com/ProductDetailPage.aspx?sku=%s'%sku

    def get_book_url(self, identifiers):  # {{{
        sku = identifiers.get('edelweiss', None)
        if sku:
            return 'edelweiss', sku, self._get_book_url(sku)

    # }}}

    def get_cached_cover_url(self, identifiers):  # {{{
        sku = identifiers.get('edelweiss', None)
        if not sku:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                sku = self.cached_isbn_to_identifier(isbn)
        return self.cached_identifier_to_cover_url(sku)
    # }}}

    def create_query(self, log, title=None, authors=None, identifiers={}):  # {{{
        from urllib import urlencode
        BASE_URL = 'http://edelweiss.abovethetreeline.com/CatalogOverview.aspx?'
        params = {
            'group':'search',
            'searchType':999,
            'searchOrgID':'',
            'dateRange':0,
            'isbn':'',
        }
        for num in (0, 1, 2, 3, 4, 5, 6, 200, 201, 202, 204):
            params['condition%d'%num] = 1
            params['keywords%d'%num] = ''
        title_key, author_key = 'keywords200', 'keywords201'

        isbn = check_isbn(identifiers.get('isbn', None))
        found = False
        if isbn is not None:
            params['isbn'] = isbn
            found = True
        elif title or authors:
            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                params[title_key] = ' '.join(title_tokens)
                found = True
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            if author_tokens:
                params[author_key] = ' '.join(author_tokens)
                found = True

        if not found:
            return None

        for k in (title_key, author_key, 'isbn'):
            v = params[k]
            if isinstance(v, unicode):
                params[k] = v.encode('utf-8')

        return BASE_URL+urlencode(params)

    def create_query2(self, log, title=None, authors=None, identifiers={}):
        ''' The edelweiss advanced search appears to be broken, use the keyword search instead, until it is fixed. '''
        from urllib import urlencode
        BASE_URL = 'http://edelweiss.abovethetreeline.com/CatalogOverview.aspx?'
        params = {
            'group':'search',
            'section':'CatalogOverview',
            'searchType':1,
            'searchOrgID':'',
            'searchCatalogID': '',
            'searchMailingID': '',
            'searchSelect':1,
        }
        keywords = []
        isbn = check_isbn(identifiers.get('isbn', None))
        if isbn is not None:
            keywords.append(isbn)
        elif title or authors:
            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                keywords.extend(title_tokens)
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            if author_tokens:
                keywords.extend(author_tokens)
        if not keywords:
            return None
        params['keywords'] = (' '.join(keywords)).encode('utf-8')
        return BASE_URL+urlencode(params)

    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None,  # {{{
            identifiers={}, timeout=30):
        from urlparse import parse_qs

        book_url = self._get_book_url(identifiers.get('edelweiss', None))
        br = self.browser
        if book_url:
            entries = [(book_url, identifiers['edelweiss'])]
        else:
            entries = []
            query = self.create_query2(log, title=title, authors=authors,
                    identifiers=identifiers)
            if not query:
                log.error('Insufficient metadata to construct query')
                return
            log('Using query URL:', query)
            try:
                raw = br.open_novisit(query, timeout=timeout).read()
            except Exception as e:
                log.exception('Failed to make identify query: %r'%query)
                return as_unicode(e)

            try:
                root = parse_html(raw)
            except Exception as e:
                log.exception('Failed to parse identify results')
                return as_unicode(e)

            for entry in CSSSelect('div.listRow div.listRowMain')(root):
                a = entry.xpath('descendant::a[contains(@href, "sku=") and contains(@href, "ProductDetailPage.aspx")]')
                if not a:
                    continue
                href = a[0].get('href')
                prefix, qs = href.partition('?')[0::2]
                sku = parse_qs(qs).get('sku', None)
                if sku and sku[0]:
                    sku = sku[0]
                    div = CSSSelect('div.sku.attGroup')(entry)
                    if div:
                        text = astext(div[0])
                        isbns = [check_isbn(x.strip()) for x in text.split(',')]
                        for isbn in isbns:
                            if isbn:
                                self.cache_isbn_to_identifier(isbn, sku)
                    for img in entry.xpath('descendant::img[contains(@src, "/jacket_covers/thumbnail/")]'):
                        self.cache_identifier_to_cover_url(sku, img.get('src').replace('/thumbnail/', '/flyout/'))

                    div = CSSSelect('div.format.attGroup')(entry)
                    text = astext(div[0]).lower()
                    if 'audio' in text or 'mp3' in text:  # Audio-book, ignore
                        continue
                    entries.append((self._get_book_url(sku), sku))

        if (not entries and identifiers and title and authors and
                not abort.is_set()):
            return self.identify(log, result_queue, abort, title=title,
                    authors=authors, timeout=timeout)

        if not entries:
            return

        workers = [Worker(sku, url, i, result_queue, br.clone_browser(), timeout, log, self)
                   for i, (url, sku) in enumerate(entries[:5])]

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

    # }}}

    def download_cover(self, log, result_queue, abort,  # {{{
            title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
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

if __name__ == '__main__':
    from calibre.ebooks.metadata.sources.test import (
        test_identify_plugin, title_test, authors_test, comments_test, pubdate_test)
    tests = [
        # Multiple authors and two part title and no general description
        ({'identifiers':{'edelweiss':'0321180607'}},
        [title_test(
        "XQuery from the Experts: A Guide to the W3C XML Query Language"
        , exact=True), authors_test([
            'Howard Katz', 'Don Chamberlin', 'Denise Draper', 'Mary Fernandez',
            'Michael Kay', 'Jonathan Robie', 'Michael Rys', 'Jerome Simeon',
            'Jim Tivy', 'Philip Wadler']), pubdate_test(2003, 8, 22),
            comments_test('Jérôme Siméon'), lambda mi: bool(mi.comments and 'No title summary' not in mi.comments)
        ]),

        (  # An isbn not present in edelweiss
         {'identifiers':{'isbn': '9780316044981'}, 'title':'The Heroes',
          'authors':['Joe Abercrombie']},
            [title_test('The Heroes', exact=True),
                authors_test(['Joe Abercrombie'])]

        ),

        (  # Pubdate
         {'title':'The Great Gatsby', 'authors':['F. Scott Fitzgerald']},
            [title_test('The great gatsby', exact=True),
                authors_test(['F. Scott Fitzgerald']), pubdate_test(2004, 9, 29)]
        ),


    ]
    start, stop = 0, len(tests)

    tests = tests[start:stop]
    test_identify_plugin(Edelweiss.name, tests)




