#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>; 2011, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

import time
from urllib import urlencode
from functools import partial
from Queue import Queue, Empty


from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre import as_unicode

NAMESPACES = {
              'openSearch':'http://a9.com/-/spec/opensearchrss/1.0/',
              'atom' : 'http://www.w3.org/2005/Atom',
              'db': 'http://www.douban.com/xmlns/',
              'gd': 'http://schemas.google.com/g/2005'
            }
def get_details(browser, url, timeout): # {{{
    try:
        if Douban.DOUBAN_API_KEY and Douban.DOUBAN_API_KEY != '':
            url = url + "?apikey=" + Douban.DOUBAN_API_KEY
        raw = browser.open_novisit(url, timeout=timeout).read()
    except Exception as e:
        gc = getattr(e, 'getcode', lambda : -1)
        if gc() != 403:
            raise
        # Douban is throttling us, wait a little
        time.sleep(2)
        raw = browser.open_novisit(url, timeout=timeout).read()

    return raw
# }}}

def to_metadata(browser, log, entry_, timeout): # {{{
    from lxml import etree
    from calibre.ebooks.chardet import xml_to_unicode
    from calibre.utils.date import parse_date, utcnow
    from calibre.utils.cleantext import clean_ascii_chars

    XPath = partial(etree.XPath, namespaces=NAMESPACES)
    entry          = XPath('//atom:entry')
    entry_id       = XPath('descendant::atom:id')
    title          = XPath('descendant::atom:title')
    description    = XPath('descendant::atom:summary')
    publisher      = XPath("descendant::db:attribute[@name='publisher']")
    isbn           = XPath("descendant::db:attribute[@name='isbn13']")
    date           = XPath("descendant::db:attribute[@name='pubdate']")
    creator        = XPath("descendant::db:attribute[@name='author']")
    booktag        = XPath("descendant::db:tag/attribute::name")
    rating         = XPath("descendant::gd:rating/attribute::average")
    cover_url      = XPath("descendant::atom:link[@rel='image']/attribute::href")


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
    douban_id = id_url.split('/')[-1]
    title_ = ': '.join([x.text for x in title(entry_)]).strip()
    authors = [x.text.strip() for x in creator(entry_) if x.text]
    if not authors:
        authors = [_('Unknown')]
    if not id_url or not title:
        # Silently discard this entry
        return None

    mi = Metadata(title_, authors)
    mi.identifiers = {'douban':douban_id}
    try:
        raw = get_details(browser, id_url, timeout)
        feed = etree.fromstring(xml_to_unicode(clean_ascii_chars(raw),
            strip_encoding_pats=True)[0])
        extra = entry(feed)[0]
    except:
        log.exception('Failed to get additional details for', mi.title)
        return mi
    mi.comments = get_text(extra, description)
    mi.publisher = get_text(extra, publisher)

    # ISBN
    isbns = []
    for x in [t.text for t in isbn(extra)]:
        if check_isbn(x):
            isbns.append(x)
    if isbns:
        mi.isbn = sorted(isbns, key=len)[-1]
    mi.all_isbns = isbns

    # Tags
    try:
        btags = [x for x in booktag(extra) if x]
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
        try:
            default = utcnow().replace(day=15)
            mi.pubdate = parse_date(pubdate, assume_utc=True, default=default)
        except:
            log.error('Failed to parse pubdate %r'%pubdate)

    # Ratings
    if rating(extra):
        try:
            mi.rating = float(rating(extra)[0]) / 2.0
        except:
            log.exception('Failed to parse rating')
            mi.rating = 0

    # Cover
    mi.has_douban_cover = None
    u = cover_url(extra)
    if u:
        u = u[0].replace('/spic/', '/lpic/');
        # If URL contains "book-default", the book doesn't have a cover
        if u.find('book-default') == -1:
            mi.has_douban_cover = u
    return mi
# }}}

class Douban(Source):

    name = 'Douban Books'
    author = 'Li Fanxi'
    version = (2, 0, 0)

    description = _('Downloads metadata and covers from Douban.com. '
            'Useful only for chinese language books.')

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'tags',
        'pubdate', 'comments', 'publisher', 'identifier:isbn', 'rating',
        'identifier:douban']) # language currently disabled
    supports_gzip_transfer_encoding = True
    cached_cover_url_is_reliable = True

    DOUBAN_API_KEY = '0bd1672394eb1ebf2374356abec15c3d'
    DOUBAN_BOOK_URL = 'http://book.douban.com/subject/%s/'

    def get_book_url(self, identifiers): # {{{
        db = identifiers.get('douban', None)
        if db is not None:
            return ('douban', db, self.DOUBAN_BOOK_URL%db)
    # }}}

    def create_query(self, log, title=None, authors=None, identifiers={}): # {{{
        SEARCH_URL = 'http://api.douban.com/book/subjects?'
        ISBN_URL = 'http://api.douban.com/book/subject/isbn/'
        SUBJECT_URL = 'http://api.douban.com/book/subject/'

        q = ''
        t = None
        isbn = check_isbn(identifiers.get('isbn', None))
        subject = identifiers.get('douban', None)
        if isbn is not None:
            q = isbn
            t = 'isbn'
        elif subject is not None:
            q = subject
            t = 'subject'
        elif title or authors:
            def build_term(prefix, parts):
                return ' '.join(x for x in parts)
            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                q += build_term('title', title_tokens)
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            if author_tokens:
                q += ((' ' if q != '' else '') +
                    build_term('author', author_tokens))
            t = 'search'
        q = q.strip()
        if isinstance(q, unicode):
            q = q.encode('utf-8')
        if not q:
            return None
        url = None
        if t == "isbn":
            url = ISBN_URL + q
        elif t == 'subject':
            url = SUBJECT_URL + q
        else:
            url = SEARCH_URL + urlencode({
                    'q': q,
                    })
        if self.DOUBAN_API_KEY and self.DOUBAN_API_KEY != '':
            if t == "isbn" or t == "subject":
                url = url + "?apikey=" + self.DOUBAN_API_KEY
            else:
                url = url + "&apikey=" + self.DOUBAN_API_KEY
        return url
    # }}}

    def download_cover(self, log, result_queue, abort, # {{{
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
            if cdata:
                result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)

    # }}}

    def get_cached_cover_url(self, identifiers): # {{{
        url = None
        db = identifiers.get('douban', None)
        if db is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                db = self.cached_isbn_to_identifier(isbn)
        if db is not None:
            url = self.cached_identifier_to_cover_url(db)

        return url
    # }}}

    def get_all_details(self, br, log, entries, abort, # {{{
            result_queue, timeout):
        from lxml import etree
        for relevance, i in enumerate(entries):
            try:
                ans = to_metadata(br, log, i, timeout)
                if isinstance(ans, Metadata):
                    ans.source_relevance = relevance
                    db = ans.identifiers['douban']
                    for isbn in getattr(ans, 'all_isbns', []):
                        self.cache_isbn_to_identifier(isbn, db)
                    if ans.has_douban_cover:
                        self.cache_identifier_to_cover_url(db,
                                ans.has_douban_cover)
                    self.clean_downloaded_metadata(ans)
                    result_queue.put(ans)
            except:
                log.exception(
                    'Failed to get metadata for identify entry:',
                    etree.tostring(i))
            if abort.is_set():
                break
    # }}}

    def identify(self, log, result_queue, abort, title=None, authors=None, # {{{
            identifiers={}, timeout=30):
        from lxml import etree
        from calibre.ebooks.chardet import xml_to_unicode
        from calibre.utils.cleantext import clean_ascii_chars

        XPath = partial(etree.XPath, namespaces=NAMESPACES)
        entry          = XPath('//atom:entry')

        query = self.create_query(log, title=title, authors=authors,
                identifiers=identifiers)
        if not query:
            log.error('Insufficient metadata to construct query')
            return
        br = self.browser
        try:
            raw = br.open_novisit(query, timeout=timeout).read()
        except Exception as e:
            log.exception('Failed to make identify query: %r'%query)
            return as_unicode(e)
        try:
            parser = etree.XMLParser(recover=True, no_network=True)
            feed = etree.fromstring(xml_to_unicode(clean_ascii_chars(raw),
                strip_encoding_pats=True)[0], parser=parser)
            entries = entry(feed)
        except Exception as e:
            log.exception('Failed to parse identify results')
            return as_unicode(e)
        if not entries and identifiers and title and authors and \
                not abort.is_set():
            return self.identify(log, result_queue, abort, title=title,
                    authors=authors, timeout=timeout)

        # There is no point running these queries in threads as douban
        # throttles requests returning 403 Forbidden errors
        self.get_all_details(br, log, entries, abort, result_queue, timeout)

        return None
    # }}}

if __name__ == '__main__': # tests {{{
    # To run these test use: calibre-debug -e src/calibre/ebooks/metadata/sources/douban.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            title_test, authors_test)
    test_identify_plugin(Douban.name,
        [


            (
                {'identifiers':{'isbn': '9787536692930'}, 'title':'三体',
                    'authors':['刘慈欣']},
                [title_test('三体', exact=True),
                    authors_test(['刘慈欣'])]
            ),

            (
                {'title': 'Linux内核修炼之道', 'authors':['任桥伟']},
                [title_test('Linux内核修炼之道', exact=False)]
            ),
    ])
# }}}

