#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals
import hashlib
import os
import re
import regex
import sys
import tempfile
import time

try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue

from calibre import as_unicode, replace_entities, prepare_string_for_xml
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata import authors_to_string, check_isbn
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


def pretty_google_books_comments(raw):
    raw = replace_entities(raw)
    # Paragraphs in the comments are removed but whatever software googl uses
    # to do this does not insert a space so we often find the pattern
    # word.Capital in the comments which can be used to find paragraph markers.
    parts = []
    for x in re.split(r'([a-z)"”])(\.)([A-Z("“])', raw):
        if x == '.':
            parts.append('.</p>\n\n<p>')
        else:
            parts.append(prepare_string_for_xml(x))
    raw = '<p>' + ''.join(parts) + '</p>'
    return raw


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

xpath_cache = {}


def XPath(x):
    ans = xpath_cache.get(x)
    if ans is None:
        from lxml import etree
        ans = xpath_cache[x] = etree.XPath(x, namespaces=NAMESPACES)
    return ans


def to_metadata(browser, log, entry_, timeout, running_a_test=False):  # {{{
    from lxml import etree

    # total_results  = XPath('//openSearch:totalResults')
    # start_index    = XPath('//openSearch:startIndex')
    # items_per_page = XPath('//openSearch:itemsPerPage')
    entry = XPath('//atom:entry')
    entry_id = XPath('descendant::atom:id')
    url = XPath('descendant::atom:link[@rel="self"]/@href')
    creator = XPath('descendant::dc:creator')
    identifier = XPath('descendant::dc:identifier')
    title = XPath('descendant::dc:title')
    date = XPath('descendant::dc:date')
    publisher = XPath('descendant::dc:publisher')
    subject = XPath('descendant::dc:subject')
    description = XPath('descendant::dc:description')
    language = XPath('descendant::dc:language')

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

    def get_extra_details():
        raw = get_details(browser, details_url, timeout)
        if running_a_test:
            with open(os.path.join(tempfile.gettempdir(), 'Google-' + details_url.split('/')[-1] + '.xml'), 'wb') as f:
                f.write(raw)
                print('Book details saved to:', f.name, file=sys.stderr)
        feed = etree.fromstring(
            xml_to_unicode(clean_ascii_chars(raw), strip_encoding_pats=True)[0],
            parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False)
        )
        return entry(feed)[0]

    if isinstance(entry_, str):
        google_id = entry_
        details_url = 'https://www.google.com/books/feeds/volumes/' + google_id
        extra = get_extra_details()
        title_ = ': '.join([x.text for x in title(extra)]).strip()
        authors = [x.text.strip() for x in creator(extra) if x.text]
    else:
        id_url = entry_id(entry_)[0].text
        google_id = id_url.split('/')[-1]
        details_url = url(entry_)[0]
        title_ = ': '.join([x.text for x in title(entry_)]).strip()
        authors = [x.text.strip() for x in creator(entry_) if x.text]
        if not id_url or not title:
            # Silently discard this entry
            return None
        extra = None

    if not authors:
        authors = [_('Unknown')]
    if not title:
        return None
    if extra is None:
        extra = get_extra_details()
    mi = Metadata(title_, authors)
    mi.identifiers = {'google': google_id}
    mi.comments = get_text(extra, description)
    lang = canonicalize_lang(get_text(extra, language))
    if lang:
        mi.language = lang
    mi.publisher = get_text(extra, publisher)

    # ISBN
    isbns = []
    for x in identifier(extra):
        t = type('')(x.text).strip()
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
    version = (1, 1, 1)
    minimum_calibre_version = (2, 80, 0)
    description = _('Downloads metadata and covers from Google Books')

    capabilities = frozenset({'identify'})
    touched_fields = frozenset({
        'title', 'authors', 'tags', 'pubdate', 'comments', 'publisher',
        'identifier:isbn', 'identifier:google', 'languages'
    })
    supports_gzip_transfer_encoding = True
    cached_cover_url_is_reliable = False

    GOOGLE_COVER = 'https://books.google.com/books?id=%s&printsec=frontcover&img=1'

    DUMMY_IMAGE_MD5 = frozenset(
        ('0de4383ebad0adad5eeb8975cd796657', 'a64fa89d7ebc97075c1d363fc5fea71f')
    )

    def get_book_url(self, identifiers):  # {{{
        goog = identifiers.get('google', None)
        if goog is not None:
            return ('google', goog, 'https://books.google.com/books?id=%s' % goog)
    # }}}

    def id_from_url(self, url):  # {{{
        from polyglot.urllib import parse_qs, urlparse
        purl = urlparse(url)
        if purl.netloc == 'books.google.com':
            q = parse_qs(purl.query)
            gid = q.get('id')
            if gid:
                return 'google', gid[0]
    # }}}

    def create_query(self, title=None, authors=None, identifiers={}, capitalize_isbn=False):  # {{{
        try:
            from urllib.parse import urlencode
        except ImportError:
            from urllib import urlencode
        BASE_URL = 'https://books.google.com/books/feeds/volumes?'
        isbn = check_isbn(identifiers.get('isbn', None))
        q = ''
        if isbn is not None:
            q += ('ISBN:' if capitalize_isbn else 'isbn:') + isbn
        elif title or authors:

            def build_term(prefix, parts):
                return ' '.join('in' + prefix + ':' + x for x in parts)

            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                q += build_term('title', title_tokens)
            author_tokens = list(self.get_author_tokens(authors, only_first_author=True))
            if author_tokens:
                q += ('+' if q else '') + build_term('author', author_tokens)

        if not q:
            return None
        if not isinstance(q, bytes):
            q = q.encode('utf-8')
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

    def postprocess_downloaded_google_metadata(self, ans, relevance=0):  # {{{
        if not isinstance(ans, Metadata):
            return ans
        ans.source_relevance = relevance
        goog = ans.identifiers['google']
        for isbn in getattr(ans, 'all_isbns', []):
            self.cache_isbn_to_identifier(isbn, goog)
        if getattr(ans, 'has_google_cover', False):
            self.cache_identifier_to_cover_url(goog, self.GOOGLE_COVER % goog)
        if ans.comments:
            ans.comments = pretty_google_books_comments(ans.comments)
        self.clean_downloaded_metadata(ans)
        return ans
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
                ans = self.postprocess_downloaded_google_metadata(to_metadata(br, log, i, timeout, self.running_a_test), relevance)
                if isinstance(ans, Metadata):
                    result_queue.put(ans)
            except Exception:
                log.exception(
                    'Failed to get metadata for identify entry:', etree.tostring(i)
                )
            if abort.is_set():
                break

    # }}}

    def identify_via_web_search(  # {{{
        self,
        log,
        result_queue,
        abort,
        title=None,
        authors=None,
        identifiers={},
        timeout=30
    ):
        from calibre.utils.filenames import ascii_text
        isbn = check_isbn(identifiers.get('isbn', None))
        q = []
        strip_punc_pat = regex.compile(r'[\p{C}|\p{M}|\p{P}|\p{S}|\p{Z}]+', regex.UNICODE)
        google_ids = []
        check_tokens = set()
        has_google_id = 'google' in identifiers

        def to_check_tokens(*tokens):
            for t in tokens:
                if len(t) < 3:
                    continue
                t = t.lower()
                if t in ('and', 'not', 'the'):
                    continue
                yield ascii_text(strip_punc_pat.sub('', t))

        if has_google_id:
            google_ids.append(identifiers['google'])
        elif isbn is not None:
            q.append(isbn)
        elif title or authors:
            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                q += title_tokens
                check_tokens |= set(to_check_tokens(*title_tokens))
            author_tokens = list(self.get_author_tokens(authors, only_first_author=True))
            if author_tokens:
                q += author_tokens
                check_tokens |= set(to_check_tokens(*author_tokens))
        if not q and not google_ids:
            return None
        from calibre.ebooks.metadata.sources.update import search_engines_module
        se = search_engines_module()
        br = se.google_specialize_browser(se.browser())
        if not has_google_id:
            url = se.google_format_query(q, tbm='bks')
            log('Making query:', url)
            r = []
            root = se.query(br, url, 'google', timeout=timeout, save_raw=r.append)
            pat = re.compile(r'id=([^&]+)')
            for q in se.google_parse_results(root, r[0], log=log, ignore_uncached=False):
                m = pat.search(q.url)
                if m is None or not q.url.startswith('https://books.google'):
                    continue
                google_ids.append(m.group(1))

        if not google_ids and isbn and (title or authors):
            return self.identify_via_web_search(log, result_queue, abort, title, authors, {}, timeout)
        found = False
        seen = set()
        for relevance, gid in enumerate(google_ids):
            if gid in seen:
                continue
            seen.add(gid)
            try:
                ans = to_metadata(br, log, gid, timeout, self.running_a_test)
                if isinstance(ans, Metadata):
                    if isbn:
                        if isbn not in ans.all_isbns:
                            log('Excluding', ans.title, 'by', authors_to_string(ans.authors), 'as it does not match the ISBN:', isbn,
                                'not in', ' '.join(ans.all_isbns))
                            continue
                    elif check_tokens:
                        candidate = set(to_check_tokens(*self.get_title_tokens(ans.title)))
                        candidate |= set(to_check_tokens(*self.get_author_tokens(ans.authors)))
                        if candidate.intersection(check_tokens) != check_tokens:
                            log('Excluding', ans.title, 'by', authors_to_string(ans.authors), 'as it does not match the query')
                            continue
                    ans = self.postprocess_downloaded_google_metadata(ans, relevance)
                    result_queue.put(ans)
                    found = True
            except:
                log.exception('Failed to get metadata for google books id:', gid)
            if abort.is_set():
                break
        if not found and isbn and (title or authors):
            return self.identify_via_web_search(log, result_queue, abort, title, authors, {}, timeout)
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
        entry = XPath('//atom:entry')
        identifiers = identifiers.copy()
        br = self.browser
        if 'google' in identifiers:
            try:
                ans = to_metadata(br, log, identifiers['google'], timeout, self.running_a_test)
                if isinstance(ans, Metadata):
                    self.postprocess_downloaded_google_metadata(ans)
                    result_queue.put(ans)
                    return
            except Exception:
                log.exception('Failed to get metadata for Google identifier:', identifiers['google'])
            del identifiers['google']

        query = self.create_query(
            title=title, authors=authors, identifiers=identifiers
        )
        if not query:
            log.error('Insufficient metadata to construct query')
            return

        def make_query(query):
            log('Making query:', query)
            try:
                raw = br.open_novisit(query, timeout=timeout).read()
            except Exception as e:
                log.exception('Failed to make identify query: %r' % query)
                return False, as_unicode(e)

            try:
                feed = etree.fromstring(
                    xml_to_unicode(clean_ascii_chars(raw), strip_encoding_pats=True)[0],
                    parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False)
                )
                return True, entry(feed)
            except Exception as e:
                log.exception('Failed to parse identify results')
                return False, as_unicode(e)
        ok, entries = make_query(query)
        if not ok:
            return entries
        if not entries and not abort.is_set():
            log('No results found, doing a web search instead')
            return self.identify_via_web_search(log, result_queue, abort, title, authors, identifiers, timeout)

        # There is no point running these queries in threads as google
        # throttles requests returning 403 Forbidden errors
        self.get_all_details(br, log, entries, abort, result_queue, timeout)

    # }}}


if __name__ == '__main__':  # tests {{{
    # To run these test use:
    # calibre-debug src/calibre/ebooks/metadata/sources/google.py
    from calibre.ebooks.metadata.sources.test import (
        authors_test, test_identify_plugin, title_test
    )
    tests = [
    ({
        'identifiers': {'google': 's7NIrgEACAAJ'},
    }, [title_test('Ride Every Stride', exact=False)]),

    ({
        'identifiers': {'isbn': '0743273567'},
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

    ({
        'title': 'The Blood Red Indian Summer: A Berger and Mitry Mystery',
        'authors': ['David Handler'],
    }, [title_test('The Blood Red Indian Summer: A Berger and Mitry Mystery')
    ]),

    ({
        # requires using web search to find the book
        'title': 'Dragon Done It',
        'authors': ['Eric Flint'],
    }, [
        title_test('The dragon done it', exact=True),
        authors_test(['Eric Flint', 'Mike Resnick'])
    ]),

    ]
    test_identify_plugin(GoogleBooks.name, tests[:])

# }}}
