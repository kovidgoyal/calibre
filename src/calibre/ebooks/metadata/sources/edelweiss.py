#!/usr/bin/env python2
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


def clean_html(raw):
    from calibre.ebooks.chardet import xml_to_unicode
    from calibre.utils.cleantext import clean_ascii_chars
    return clean_ascii_chars(xml_to_unicode(raw, strip_encoding_pats=True,
                                resolve_entities=True, assume_utf8=True)[0])


def parse_html(raw):
    raw = clean_html(raw)
    from html5_parser import parse
    return parse(raw)


def astext(node):
    from lxml import etree
    return etree.tostring(node, method='text', encoding=unicode,
                          with_tail=False).strip()


class Worker(Thread):  # {{{

    def __init__(self, basic_data, relevance, result_queue, br, timeout, log, plugin):
        Thread.__init__(self)
        self.daemon = True
        self.basic_data = basic_data
        self.br, self.log, self.timeout = br, log, timeout
        self.result_queue, self.plugin, self.sku = result_queue, plugin, self.basic_data['sku']
        self.relevance = relevance

    def run(self):
        url = ('https://www.edelweiss.plus/GetTreelineControl.aspx?controlName=/uc/product/two_Enhanced.ascx&'
        'sku={0}&idPrefix=content_1_{0}&mode=0'.format(self.sku))
        try:
            raw = self.br.open_novisit(url, timeout=self.timeout).read()
        except:
            self.log.exception('Failed to load comments page: %r'%url)
            return

        try:
            mi = self.parse(raw)
            mi.source_relevance = self.relevance
            self.plugin.clean_downloaded_metadata(mi)
            self.result_queue.put(mi)
        except:
            self.log.exception('Failed to parse details for sku: %s'%self.sku)

    def parse(self, raw):
        from calibre.ebooks.metadata.book.base import Metadata
        from calibre.utils.date import UNDEFINED_DATE
        root = parse_html(raw)
        mi = Metadata(self.basic_data['title'], self.basic_data['authors'])

        # Identifiers
        if self.basic_data['isbns']:
            mi.isbn = self.basic_data['isbns'][0]
        mi.set_identifier('edelweiss', self.sku)

        # Tags
        if self.basic_data['tags']:
            mi.tags = self.basic_data['tags']
            mi.tags = [t[1:].strip() if t.startswith('&') else t for t in mi.tags]

        # Publisher
        mi.publisher = self.basic_data['publisher']

        # Pubdate
        if self.basic_data['pubdate'] and self.basic_data['pubdate'].year != UNDEFINED_DATE:
            mi.pubdate = self.basic_data['pubdate']

        # Rating
        if self.basic_data['rating']:
            mi.rating = self.basic_data['rating']

        # Comments
        comments = ''
        for cid in ('summary', 'contributorbio', 'quotes_reviews'):
            cid = 'desc_{}{}-content'.format(cid, self.sku)
            div = root.xpath('//*[@id="{}"]'.format(cid))
            if div:
                comments += self.render_comments(div[0])
        if comments:
            mi.comments = comments

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


def get_basic_data(browser, log, *skus):
    from calibre.utils.date import parse_only_date
    from mechanize import Request
    zeroes = ','.join('0' for sku in skus)
    data = {
            'skus': ','.join(skus),
            'drc': zeroes,
            'startPosition': '0',
            'sequence': '1',
            'selected': zeroes,
            'itemID': '0',
            'orderID': '0',
            'mailingID': '',
            'tContentWidth': '926',
            'originalOrder': ','.join(str(i) for i in range(len(skus))),
            'selectedOrderID': '0',
            'selectedSortColumn': '0',
            'listType': '1',
            'resultType': '32',
            'blockView': '1',
    }
    items_data_url = 'https://www.edelweiss.plus/GetTreelineControl.aspx?controlName=/uc/listviews/ListView_Title_Multi.ascx'
    req = Request(items_data_url, data)
    response = browser.open_novisit(req)
    raw = response.read()
    root = parse_html(raw)
    for item in root.xpath('//div[@data-priority]'):
        row = item.getparent().getparent()
        sku = item.get('id').split('-')[-1]
        isbns = [x.strip() for x in row.xpath('descendant::*[contains(@class, "pev_sku")]/text()')[0].split(',') if check_isbn(x.strip())]
        isbns.sort(key=len, reverse=True)
        try:
            tags = [x.strip() for x in astext(row.xpath('descendant::*[contains(@class, "pev_categories")]')[0]).split('/')]
        except IndexError:
            tags = []
        rating = 0
        for bar in row.xpath('descendant::*[contains(@class, "bgdColorCommunity")]/@style'):
            m = re.search('width: (\d+)px;.*max-width: (\d+)px', bar)
            if m is not None:
                rating = float(m.group(1)) / float(m.group(2))
                break
        try:
            pubdate = parse_only_date(astext(row.xpath('descendant::*[contains(@class, "pev_shipDate")]')[0]
                ).split(':')[-1].split(u'\xa0')[-1].strip(), assume_utc=True)
        except Exception:
            log.exception('Error parsing published date')
            pubdate = None
        authors = []
        for x in [x.strip() for x in row.xpath('descendant::*[contains(@class, "pev_contributor")]/@title')]:
            authors.extend(a.strip() for a in x.split(','))
        entry = {
                'sku': sku,
                'cover': row.xpath('descendant::img/@src')[0].split('?')[0],
                'publisher': astext(row.xpath('descendant::*[contains(@class, "headerPublisher")]')[0]),
                'title': astext(row.xpath('descendant::*[@id="title_{}"]'.format(sku))[0]),
                'authors': authors,
                'isbns': isbns,
                'tags': tags,
                'pubdate': pubdate,
                'format': ' '.join(row.xpath('descendant::*[contains(@class, "pev_format")]/text()')).strip(),
                'rating': rating,
        }
        if entry['cover'].startswith('/'):
            entry['cover'] = None
        yield entry


class Edelweiss(Source):

    name = 'Edelweiss'
    version = (2, 0, 0)
    minimum_calibre_version = (3, 6, 0)
    description = _('Downloads metadata and covers from Edelweiss - A catalog updated by book publishers')

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset([
        'title', 'authors', 'tags', 'pubdate', 'comments', 'publisher',
        'identifier:isbn', 'identifier:edelweiss', 'rating'])
    supports_gzip_transfer_encoding = True
    has_html_comments = True

    @property
    def user_agent(self):
        # Pass in an index to random_user_agent() to test with a particular
        # user agent
        return random_user_agent(allow_ie=False)

    def _get_book_url(self, sku):
        if sku:
            return 'https://www.edelweiss.plus/#sku={}&page=1'.format(sku)

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

    def create_query(self, log, title=None, authors=None, identifiers={}):
        from urllib import urlencode
        import time
        BASE_URL = ('https://www.edelweiss.plus/GetTreelineControl.aspx?'
        'controlName=/uc/listviews/controls/ListView_data.ascx&itemID=0&resultType=32&dashboardType=8&itemType=1&dataType=products&keywordSearch&')
        keywords = []
        isbn = check_isbn(identifiers.get('isbn', None))
        if isbn is not None:
            keywords.append(isbn)
        elif title:
            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                keywords.extend(title_tokens)
            author_tokens = self.get_author_tokens(authors, only_first_author=True)
            if author_tokens:
                keywords.extend(author_tokens)
        if not keywords:
            return None
        params = {
            'q': (' '.join(keywords)).encode('utf-8'),
            '_': str(int(time.time()))
        }
        return BASE_URL+urlencode(params)

    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None,  # {{{
            identifiers={}, timeout=30):
        import json

        br = self.browser
        br.addheaders = [
            ('Referer', 'https://www.edelweiss.plus/'),
            ('X-Requested-With', 'XMLHttpRequest'),
            ('Cache-Control', 'no-cache'),
            ('Pragma', 'no-cache'),
        ]
        if 'edelweiss' in identifiers:
            items = [identifiers['edelweiss']]
        else:
            query = self.create_query(log, title=title, authors=authors,
                    identifiers=identifiers)
            if not query:
                log.error('Insufficient metadata to construct query')
                return
            log('Using query URL:', query)
            try:
                raw = br.open(query, timeout=timeout).read().decode('utf-8')
            except Exception as e:
                log.exception('Failed to make identify query: %r'%query)
                return as_unicode(e)
            items = re.search('window[.]items\s*=\s*(.+?);', raw)
            if items is None:
                log.error('Failed to get list of matching items')
                log.debug('Response text:')
                log.debug(raw)
                return
            items = json.loads(items.group(1))

        if (not items and identifiers and title and authors and
                not abort.is_set()):
            return self.identify(log, result_queue, abort, title=title,
                    authors=authors, timeout=timeout)

        if not items:
            return

        workers = []
        items = items[:5]
        for i, item in enumerate(get_basic_data(self.browser, log, *items)):
            sku = item['sku']
            for isbn in item['isbns']:
                self.cache_isbn_to_identifier(isbn, sku)
            if item['cover']:
                self.cache_identifier_to_cover_url(sku, item['cover'])
            fmt = item['format'].lower()
            if 'audio' in fmt or 'mp3' in fmt:
                continue  # Audio-book, ignore
            workers.append(Worker(item, i, result_queue, br.clone_browser(), timeout, log, self))

        if not workers:
            return

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
        (  # A title and author search
         {'title': 'The Husband\'s Secret', 'authors':['Liane Moriarty']},
         [title_test('The Husband\'s Secret', exact=True),
                authors_test(['Liane Moriarty'])]
        ),

        (  # An isbn present in edelweiss
         {'identifiers':{'isbn': '9780312621360'}, },
         [title_test('Flame: A Sky Chasers Novel', exact=True),
                authors_test(['Amy Kathleen Ryan'])]
        ),

        # Multiple authors and two part title and no general description
        ({'identifiers':{'edelweiss':'0321180607'}},
        [title_test(
        "XQuery From the Experts: A Guide to the W3C XML Query Language"
        , exact=True), authors_test([
            'Howard Katz', 'Don Chamberlin', 'Denise Draper', 'Mary Fernandez',
            'Michael Kay', 'Jonathan Robie', 'Michael Rys', 'Jerome Simeon',
            'Jim Tivy', 'Philip Wadler']), pubdate_test(2003, 8, 22),
            comments_test('Jérôme Siméon'), lambda mi: bool(mi.comments and 'No title summary' not in mi.comments)
        ]),
    ]
    start, stop = 0, len(tests)

    tests = tests[start:stop]
    test_identify_plugin(Edelweiss.name, tests)
