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
    try:
        from html5_parser import parse
    except ImportError:
        # Old versions of calibre
        import html5lib
        return html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)
    else:
        return parse(raw)


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
        from css_selectors import Select
        root = parse_html(raw)
        selector = Select(root)
        sku = next(selector('div.sku.attGroup'))
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
        bisac = tuple(selector('div.bisac.attGroup'))
        if bisac:
            bisac = astext(bisac[0])
            mi.tags = [x.strip() for x in bisac.split(',')]
            mi.tags = [t[1:].strip() if t.startswith('&') else t for t in mi.tags]

        # Publisher
        pub = tuple(selector('div.supplier.attGroup'))
        if pub:
            pub = astext(pub[0])
            mi.publisher = pub

        # Pubdate
        pub = tuple(selector('div.shipDate.attGroupItem'))
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
        general = tuple(selector('div#pd-general-overview-content'))
        if general:
            q = self.render_comments(general[0])
            if q != '<p>No title summary available. </p>':
                comm += q
        general = tuple(selector('div#pd-general-contributor-content'))
        if general:
            comm += self.render_comments(general[0])
        general = tuple(selector('div#pd-general-quotes-content'))
        if general:
            comm += self.render_comments(general[0])
        if comm:
            mi.comments = comm

        # Cover
        img = tuple(selector('img.title-image[src]'))
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
    version = (1, 0, 0)
    minimum_calibre_version = (2, 80, 0)
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
            return 'https://edelweiss.abovethetreeline.com/ProductDetailPage.aspx?sku=%s'%sku

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
        BASE_URL = 'https://edelweiss.abovethetreeline.com/Browse.aspx?source=catalog&rg=4187&group=browse&pg=0&'
        params = {
            'browseType':'title', 'startIndex':0, 'savecook':1, 'sord':20, 'secSord':20, 'tertSord':20,
        }
        keywords = []
        isbn = check_isbn(identifiers.get('isbn', None))
        if isbn is not None:
            keywords.append(isbn)
        elif title:
            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                keywords.extend(title_tokens)
            # Searching with author names does not work on edelweiss
            # author_tokens = self.get_author_tokens(authors,
            #         only_first_author=True)
            # if author_tokens:
            #     keywords.extend(author_tokens)
        if not keywords:
            return None
        params['bsk'] = (' '.join(keywords)).encode('utf-8')
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
            query = self.create_query(log, title=title, authors=authors,
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
            from css_selectors import Select
            select = Select(root)
            has_isbn = check_isbn(identifiers.get('isbn', None)) is not None
            if not has_isbn:
                author_tokens = set(x.lower() for x in self.get_author_tokens(authors, only_first_author=True))
            for entry in select('div.listRow div.listRowMain'):
                a = entry.xpath('descendant::a[contains(@href, "sku=") and contains(@href, "productDetailPage.aspx")]')
                if not a:
                    continue
                href = a[0].get('href')
                prefix, qs = href.partition('?')[0::2]
                sku = parse_qs(qs).get('sku', None)
                if sku and sku[0]:
                    sku = sku[0]
                    div = tuple(select('div.sku.attGroup'))
                    if div:
                        text = astext(div[0])
                        isbns = [check_isbn(x.strip()) for x in text.split(',')]
                        for isbn in isbns:
                            if isbn:
                                self.cache_isbn_to_identifier(isbn, sku)
                    for img in entry.xpath('descendant::img[contains(@src, "/jacket_covers/thumbnail/")]'):
                        self.cache_identifier_to_cover_url(sku, img.get('src').replace('/thumbnail/', '/flyout/'))

                    div = tuple(select('div.format.attGroup'))
                    text = astext(div[0]).lower()
                    if 'audio' in text or 'mp3' in text:  # Audio-book, ignore
                        continue
                    if not has_isbn:
                        # edelweiss returns matches based only on title, so we
                        # filter by author manually
                        div = tuple(select('div.contributor.attGroup'))
                        try:
                            entry_authors = set(self.get_author_tokens([x.strip() for x in astext(div[0]).lower().split(',')]))
                        except IndexError:
                            entry_authors = set()
                        if not entry_authors.issuperset(author_tokens):
                            continue
                    entries.append((self._get_book_url(sku), sku))

        if (not entries and identifiers and title and authors and
                not abort.is_set()):
            return self.identify(log, result_queue, abort, title=title,
                    authors=authors, timeout=timeout)

        if not entries:
            return

        workers = [Worker(skul, url, i, result_queue, br.clone_browser(), timeout, log, self)
                   for i, (url, skul) in enumerate(entries[:5])]

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
        "XQuery from the Experts: A Guide to the W3C XML Query Language"
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
