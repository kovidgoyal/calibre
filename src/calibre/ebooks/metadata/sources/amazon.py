#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import socket, time
from urllib import urlencode
from threading import Thread

from lxml.html import soupparser, tostring

from calibre import as_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.cleantext import clean_ascii_chars
from calibre.ebooks.chardet import xml_to_unicode

class Worker(Thread):

    def __init__(self, url, result_queue, browser, log, timeout=20):
        self.url, self.result_queue = url, result_queue
        self.log, self.timeout = log, timeout
        self.browser = browser.clone_browser()
        self.cover_url = self.amazon_id = None

    def run(self):
        try:
            self.get_details()
        except:
            self.log.error('get_details failed for url: %r'%self.url)

    def get_details(self):
        try:
            raw = self.browser.open_novisit(self.url, timeout=self.timeout).read().strip()
        except Exception, e:
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
        pass


class Amazon(Source):

    name = 'Amazon'
    description = _('Downloads metadata from Amazon')

    capabilities = frozenset(['identify'])
    touched_fields = frozenset(['title', 'authors', 'isbn', 'pubdate', 'comments'])

    AMAZON_DOMAINS = {
            'com': _('US'),
            'fr' : _('France'),
            'de' : _('Germany'),
    }

    def create_query(self, log, title=None, authors=None, identifiers={}):
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
                ('field-title' in q and 'field-author' in q)):
            # Insufficient metadata to make an identify query
            return None

        utf8q = dict([(x.encode('utf-8'), y.encode('utf-8')) for x, y in
            q.iteritems()])
        url = 'http://www.amazon.%s/s/?'%domain + urlencode(utf8q)
        return url


    def identify(self, log, result_queue, abort, title=None, authors=None,
            identifiers={}, timeout=20):
        query = self.create_query(log, title=title, authors=authors,
                identifiers=identifiers)
        if query is None:
            log.error('Insufficient metadata to construct query')
            return
        br = self.browser
        try:
            raw = br.open_novisit(query, timeout=timeout).read().strip()
        except Exception, e:
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

        if '<title>404 - ' in raw:
            log.error('No matches found for query: %r'%query)
            return

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
            return

        matches = []
        for div in root.xpath(r'//div[starts-with(@id, "result_")]'):
            for a in div.xpath(r'descendant::a[@class="title" and @href]'):
                title = tostring(a, method='text', encoding=unicode).lower()
                if 'bulk pack' not in title:
                    matches.append(a.get('href'))
                break

        # Keep only the top 5 matches as the matches are sorted by relevance by
        # Amazon so lower matches are not likely to be very relevant
        matches = matches[:5]

        if not matches:
            log.error('No matches found with query: %r'%query)
            return

        workers = [Worker(url, result_queue, br, log) for url in matches]

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


if __name__ == '__main__':
    # To run these test use: calibre-debug -e
    # src/calibre/ebooks/metadata/sources/amazon.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            title_test)
    test_identify_plugin(Amazon.name,
        [

            (
                {'identifiers':{'isbn': '0743273567'}},
                [title_test('The great gatsby', exact=True)]
            ),
        ])


