#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from urllib import urlencode
from functools import partial

from lxml import etree

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.date import parse_date, utcnow
from calibre.utils.cleantext import clean_ascii_chars
from calibre import as_unicode

NAMESPACES = {
              'openSearch':'http://a9.com/-/spec/opensearchrss/1.0/',
              'atom' : 'http://www.w3.org/2005/Atom',
              'dc': 'http://purl.org/dc/terms'
            }
XPath = partial(etree.XPath, namespaces=NAMESPACES)

total_results  = XPath('//openSearch:totalResults')
start_index    = XPath('//openSearch:startIndex')
items_per_page = XPath('//openSearch:itemsPerPage')
entry          = XPath('//atom:entry')
entry_id       = XPath('descendant::atom:id')
creator        = XPath('descendant::dc:creator')
identifier     = XPath('descendant::dc:identifier')
title          = XPath('descendant::dc:title')
date           = XPath('descendant::dc:date')
publisher      = XPath('descendant::dc:publisher')
subject        = XPath('descendant::dc:subject')
description    = XPath('descendant::dc:description')
language       = XPath('descendant::dc:language')

def get_details(browser, url, timeout):
    try:
        raw = browser.open_novisit(url, timeout=timeout).read()
    except Exception as e:
        gc = getattr(e, 'getcode', lambda : -1)
        if gc() != 403:
            raise
        # Google is throttling us, wait a little
        time.sleep(1)
        raw = browser.open_novisit(url, timeout=timeout).read()

    return raw

def to_metadata(browser, log, entry_, timeout):

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
    mi.identifiers = {'google':google_id}
    try:
        raw = get_details(browser, id_url, timeout)
        feed = etree.fromstring(xml_to_unicode(clean_ascii_chars(raw),
            strip_encoding_pats=True)[0])
        extra = entry(feed)[0]
    except:
        log.exception('Failed to get additional details for', mi.title)
        return mi

    mi.comments = get_text(extra, description)
    #mi.language = get_text(extra, language)
    mi.publisher = get_text(extra, publisher)

    # Author sort
    for x in creator(extra):
        for key, val in x.attrib.items():
            if key.endswith('file-as') and val and val.strip():
                mi.author_sort = val
                break
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
            tags.extend([y.strip() for y in t.split('/')])
        tags = list(sorted(list(set(tags))))
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
            log.exception('Failed to parse pubdate')


    return mi


class GoogleBooks(Source):

    name = 'Google Books'
    description = _('Downloads metadata from Google Books')

    capabilities = frozenset(['identify'])
    touched_fields = frozenset(['title', 'authors', 'isbn', 'tags', 'pubdate',
        'comments', 'publisher', 'author_sort']) # language currently disabled

    def create_query(self, log, title=None, authors=None, identifiers={}):
        BASE_URL = 'http://books.google.com/books/feeds/volumes?'
        isbn = check_isbn(identifiers.get('isbn', None))
        q = ''
        if isbn is not None:
            q += 'isbn:'+isbn
        elif title or authors:
            def build_term(prefix, parts):
                return ' '.join('in'+prefix + ':' + x for x in parts)
            title_tokens = list(self.get_title_tokens(title))
            if title_tokens:
                q += build_term('title', title_tokens)
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            if author_tokens:
                q += ('+' if q else '') + build_term('author',
                        author_tokens)

        if isinstance(q, unicode):
            q = q.encode('utf-8')
        if not q:
            return None
        return BASE_URL+urlencode({
            'q':q,
            'max-results':20,
            'start-index':1,
            'min-viewability':'none',
            })

    def cover_url_from_identifiers(self, identifiers):
        goog = identifiers.get('google', None)
        if goog is None:
            isbn = identifiers.get('isbn', None)
            goog = self.cached_isbn_to_identifier(isbn)
        if goog is not None:
            return ('http://books.google.com/books?id=%s&printsec=frontcover&img=1' %
                goog)

    def is_cover_image_valid(self, raw):
        # When no cover is present, returns a PNG saying image not available
        # Try for example google identifier llNqPwAACAAJ
        # I have yet to see an actual cover in PNG format
        return raw and len(raw) > 17000 and raw[1:4] != 'PNG'

    def get_all_details(self, br, log, entries, abort, result_queue, timeout):
        for i in entries:
            try:
                ans = to_metadata(br, log, i, timeout)
                if isinstance(ans, Metadata):
                    result_queue.put(ans)
                    for isbn in ans.all_isbns:
                        self.cache_isbn_to_identifier(isbn,
                                ans.identifiers['google'])
            except:
                log.exception(
                    'Failed to get metadata for identify entry:',
                    etree.tostring(i))
            if abort.is_set():
                break

    def identify(self, log, result_queue, abort, title=None, authors=None,
            identifiers={}, timeout=5):
        query = self.create_query(log, title=title, authors=authors,
                identifiers=identifiers)
        br = self.browser()
        try:
            raw = br.open_novisit(query, timeout=timeout).read()
        except Exception, e:
            log.exception('Failed to make identify query: %r'%query)
            return as_unicode(e)

        try:
            parser = etree.XMLParser(recover=True, no_network=True)
            feed = etree.fromstring(xml_to_unicode(clean_ascii_chars(raw),
                strip_encoding_pats=True)[0], parser=parser)
            entries = entry(feed)
        except Exception, e:
            log.exception('Failed to parse identify results')
            return as_unicode(e)

        # There is no point running these queries in threads as google
        # throttles requests returning 403 Forbidden errors
        self.get_all_details(br, log, entries, abort, result_queue, timeout)

        return None

if __name__ == '__main__':
    # To run these test use: calibre-debug -e src/calibre/ebooks/metadata/sources/google.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            title_test)
    test_identify_plugin(GoogleBooks.name,
        [

            (
                {'identifiers':{'isbn': '0743273567'}},
                [title_test('The great gatsby', exact=True)]
            ),

            #(
            #    {'title': 'Great Expectations', 'authors':['Charles Dickens']},
            #    [title_test('Great Expectations', exact=True)]
            #),
    ])
