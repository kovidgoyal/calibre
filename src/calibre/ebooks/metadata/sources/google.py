#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
import time
from functools import partial
from Queue import Empty, Queue

from calibre import as_unicode
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars
from calibre.utils.localization import canonicalize_lang

NAMESPACES = {
    'openSearch': 'http://a9.com/-/spec/opensearchrss/1.0/',
    'atom': 'http://www.w3.org/2005/Atom',
    'dc': 'http://purl.org/dc/terms',
    'gd': 'http://schemas.google.com/g/2005'
}


def get_details(browser, url, timeout):  # {{{
    try:
        raw = browser.open_novisit(url, timeout=timeout).read()
    except Exception as e:
        gc = getattr(e, 'getcode', lambda: -1)
        if gc() != 403:
            raise
        # Google is throttling us, wait a little
        time.sleep(2)
        raw = browser.open_novisit(url, timeout=timeout).read()

    return raw


# }}}


def to_metadata(browser, log, entry_, timeout):  # {{{
    from lxml import etree
    XPath = partial(etree.XPath, namespaces=NAMESPACES)

    # total_results  = XPath('//openSearch:totalResults')
    # start_index    = XPath('//openSearch:startIndex')
    # items_per_page = XPath('//openSearch:itemsPerPage')
    entry = XPath('//atom:entry')
    entry_id = XPath('descendant::atom:id')
    creator = XPath('descendant::dc:creator')
    identifier = XPath('descendant::dc:identifier')
    title = XPath('descendant::dc:title')
    date = XPath('descendant::dc:date')
    publisher = XPath('descendant::dc:publisher')
    subject = XPath('descendant::dc:subject')
    description = XPath('descendant::dc:description')
    language = XPath('descendant::dc:language')
    rating = XPath('descendant::gd:rating[@average]')
    # print(etree.tostring(entry_, pretty_print=True))

    def get_text(extra, x):
        try:
            ans = x(extra)
            if ans:
                ans = ans[0].text
                if ans and ans.strip():
                    return ans.strip()
        except:
            log.exception('Programming error:')
        return None

    id_url = entry_id(entry_)[0].text
    google_id = id_url.split('/')[-1]
    title_ = ': '.join([x.text for x in title(entry_)]).strip()
    authors = [x.text.strip() for x in creator(entry_) if x.text]
    if not authors:
        authors = [_('Unknown')]
    if not id_url or not title:
        # Silently discard this entry
        return None

    mi = Metadata(title_, authors)
    mi.identifiers = {'google': google_id}
    try:
        raw = get_details(browser, id_url, timeout)
        feed = etree.fromstring(
            xml_to_unicode(clean_ascii_chars(raw), strip_encoding_pats=True)[0]
        )
        extra = entry(feed)[0]
    except:
        log.exception('Failed to get additional details for', mi.title)
        return mi

    mi.comments = get_text(extra, description)
    lang = canonicalize_lang(get_text(extra, language))
    if lang:
        mi.language = lang
    mi.publisher = get_text(extra, publisher)

    # ISBN
    isbns = []
    for x in identifier(extra):
        t = str(x.text).strip()
        if t[:5].upper() in ('ISBN:', 'LCCN:', 'OCLC:'):
            if t[:5].upper() == 'ISBN:':
                t = check_isbn(t[5:])
                if t:
                    isbns.append(t)
    if isbns:
        mi.isbn = sorted(isbns, key=len)[-1]
    mi.all_isbns = isbns

    # Tags
    try:
        btags = [x.text for x in subject(extra) if x.text]
        tags = []
        for t in btags:
            atags = [y.strip() for y in t.split('/')]
            for tag in atags:
                if tag not in tags:
                    tags.append(tag)
    except:
        log.exception('Failed to parse tags:')
        tags = []
    if tags:
        mi.tags = [x.replace(',', ';') for x in tags]

    # pubdate
    pubdate = get_text(extra, date)
    if pubdate:
        from calibre.utils.date import parse_date, utcnow
        try:
            default = utcnow().replace(day=15)
            mi.pubdate = parse_date(pubdate, assume_utc=True, default=default)
        except:
            log.error('Failed to parse pubdate %r' % pubdate)

    # Ratings
    for x in rating(extra):
        try:
            mi.rating = float(x.get('average'))
            if mi.rating > 5:
                mi.rating /= 2
        except:
            log.exception('Failed to parse rating')

    # Cover
    mi.has_google_cover = None
    for x in extra.xpath(
        '//*[@href and @rel="http://schemas.google.com/books/2008/thumbnail"]'
    ):
        mi.has_google_cover = x.get('href')
        break

    return mi


# }}}


class GoogleBooks(Source):

    name = 'Google'
    version = (1, 0, 0)
    minimum_calibre_version = (2, 80, 0)
    description = _('Downloads metadata and covers from Google Books')

    capabilities = frozenset({'identify', 'cover'})
    touched_fields = frozenset({
        'title', 'authors', 'tags', 'pubdate', 'comments', 'publisher',
        'identifier:isbn', 'identifier:google', 'languages'
    })
    supports_gzip_transfer_encoding = True
    cached_cover_url_is_reliable = False

    GOOGLE_COVER = 'https://books.google.com/books?id=%s&printsec=frontcover&img=1'

    DUMMY_IMAGE_MD5 = frozenset({'0de4383ebad0adad5eeb8975cd796657', 'a64fa89d7ebc97075c1d363fc5fea71f'})

    def get_book_url(self, identifiers):  # {{{
        goog = identifiers.get('google', None)
        if goog is not None:
            return ('google', goog, 'https://books.google.com/books?id=%s' % goog)

    # }}}

    def create_query(self, log, title=None, authors=None, identifiers={}):  # {{{
        from urllib import urlencode
        BASE_URL = 'https://books.google.com/books/feeds/volumes?'
        isbn = check_isbn(identifiers.get('isbn', None))
        q = ''
        if isbn is not None:
            q += 'isbn:' + isbn
        elif title or authors:

            def build_term(prefix, parts):
                return ' '.join('in' + prefix + ':' + x for x in parts)

            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                q += build_term('title', title_tokens)
            author_tokens = self.get_author_tokens(authors, only_first_author=True)
            if author_tokens:
                q += ('+' if q else '') + build_term('author', author_tokens)

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        if not q:
            return None
        return BASE_URL + urlencode({
            'q': q,
            'max-results': 20,
            'start-index': 1,
            'min-viewability': 'none',
        })

    # }}}

    def download_cover(  # {{{
        self,
        log,
        result_queue,
        abort,
        title=None,
        authors=None,
        identifiers={},
        timeout=30,
        get_best_cover=False
    ):
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(
                log,
                rq,
                abort,
                title=title,
                authors=authors,
                identifiers=identifiers
            )
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(
                key=self.identify_results_keygen(
                    title=title, authors=authors, identifiers=identifiers
                )
            )
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break
        if cached_url is None:
            log.info('No cover found')
            return

        br = self.browser
        for candidate in (0, 1):
            if abort.is_set():
                return
            url = cached_url + '&zoom={}'.format(candidate)
            log('Downloading cover from:', cached_url)
            try:
                cdata = br.open_novisit(url, timeout=timeout).read()
                if cdata:
                    if hashlib.md5(cdata).hexdigest() in self.DUMMY_IMAGE_MD5:
                        log.warning('Google returned a dummy image, ignoring')
                    else:
                        result_queue.put((self, cdata))
                        break
            except Exception:
                log.exception('Failed to download cover from:', cached_url)

    # }}}

    def get_cached_cover_url(self, identifiers):  # {{{
        url = None
        goog = identifiers.get('google', None)
        if goog is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                goog = self.cached_isbn_to_identifier(isbn)
        if goog is not None:
            url = self.cached_identifier_to_cover_url(goog)

        return url

    # }}}

    def get_all_details(  # {{{
        self,
        br,
        log,
        entries,
        abort,
        result_queue,
        timeout
    ):
        from lxml import etree
        for relevance, i in enumerate(entries):
            try:
                ans = to_metadata(br, log, i, timeout)
                if isinstance(ans, Metadata):
                    ans.source_relevance = relevance
                    goog = ans.identifiers['google']
                    for isbn in getattr(ans, 'all_isbns', []):
                        self.cache_isbn_to_identifier(isbn, goog)
                    if getattr(ans, 'has_google_cover', False):
                        self.cache_identifier_to_cover_url(
                            goog, self.GOOGLE_COVER % goog
                        )
                    self.clean_downloaded_metadata(ans)
                    result_queue.put(ans)
            except:
                log.exception(
                    'Failed to get metadata for identify entry:', etree.tostring(i)
                )
            if abort.is_set():
                break

    # }}}

    def identify(  # {{{
        self,
        log,
        result_queue,
        abort,
        title=None,
        authors=None,
        identifiers={},
        timeout=30
    ):
        from lxml import etree
        XPath = partial(etree.XPath, namespaces=NAMESPACES)
        entry = XPath('//atom:entry')

        query = self.create_query(
            log, title=title, authors=authors, identifiers=identifiers
        )
        if not query:
            log.error('Insufficient metadata to construct query')
            return
        br = self.browser
        try:
            raw = br.open_novisit(query, timeout=timeout).read()
        except Exception as e:
            log.exception('Failed to make identify query: %r' % query)
            return as_unicode(e)

        try:
            parser = etree.XMLParser(recover=True, no_network=True)
            feed = etree.fromstring(
                xml_to_unicode(clean_ascii_chars(raw), strip_encoding_pats=True)[0],
                parser=parser
            )
            entries = entry(feed)
        except Exception as e:
            log.exception('Failed to parse identify results')
            return as_unicode(e)

        if not entries and identifiers and title and authors and \
                not abort.is_set():
            return self.identify(
                log,
                result_queue,
                abort,
                title=title,
                authors=authors,
                timeout=timeout
            )

        # There is no point running these queries in threads as google
        # throttles requests returning 403 Forbidden errors
        self.get_all_details(br, log, entries, abort, result_queue, timeout)

        return None

    # }}}


if __name__ == '__main__':  # tests {{{
    # To run these test use: calibre-debug -e src/calibre/ebooks/metadata/sources/google.py
    from calibre.ebooks.metadata.sources.test import (
        test_identify_plugin, title_test, authors_test
    )
    test_identify_plugin(
        GoogleBooks.name, [
            ({
                'identifiers': {
                    'isbn': '0743273567'
                },
                'title': 'Great Gatsby',
                'authors': ['Fitzgerald']
            }, [
                title_test('The great gatsby', exact=True),
                authors_test(['F. Scott Fitzgerald'])
            ]),
            ({
                'title': 'Flatland',
                'authors': ['Abbott']
            }, [title_test('Flatland', exact=False)]),
        ]
    )

# }}}
