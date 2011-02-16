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
from threading import Thread

from lxml import etree

from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.date import parse_date, utcnow
from calibre import browser, as_unicode

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

def get_details(browser, url):
    try:
        raw = browser.open_novisit(url).read()
    except Exception as e:
        gc = getattr(e, 'getcode', lambda : -1)
        if gc() != 403:
            raise
        # Google is throttling us, wait a little
        time.sleep(2)
        raw = browser.open_novisit(url).read()

    return raw

def to_metadata(browser, log, entry_):

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
    title_ = ': '.join([x.text for x in title(entry_)]).strip()
    authors = [x.text.strip() for x in creator(entry_) if x.text]
    if not authors:
        authors = [_('Unknown')]
    if not id_url or not title:
        # Silently discard this entry
        return None

    mi = Metadata(title_, authors)
    try:
        raw = get_details(browser, id_url)
        feed = etree.fromstring(xml_to_unicode(raw, strip_encoding_pats=True)[0])
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
                isbns.append(t[5:])
    if isbns:
        mi.isbn = sorted(isbns, key=len)[-1]

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

class Worker(Thread):

    def __init__(self, log, entries, abort, result_queue):
        self.browser, self.log, self.entries = browser(), log, entries
        self.abort, self.result_queue = abort, result_queue
        Thread.__init__(self)
        self.daemon = True

    def run(self):
        for i in self.entries:
            try:
                ans = to_metadata(self.browser, self.log, i)
                if isinstance(ans, Metadata):
                    self.result_queue.put(ans)
            except:
                self.log.exception(
                    'Failed to get metadata for identify entry:',
                    etree.tostring(i))
            if self.abort.is_set():
                break


class GoogleBooks(Source):

    name = 'Google Books'
    description = _('Downloads metadata from Google Books')

    capabilities = frozenset(['identify'])
    touched_fields = frozenset(['title', 'authors', 'isbn', 'tags', 'pubdate',
        'comments', 'publisher', 'author_sort']) # language currently disabled

    def create_query(self, log, title=None, authors=None, identifiers={},
            start_index=1):
        BASE_URL = 'http://books.google.com/books/feeds/volumes?'
        isbn = identifiers.get('isbn', None)
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
            'start-index':start_index,
            'min-viewability':'none',
            })


    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}):
        query = self.create_query(log, title=title, authors=authors,
                identifiers=identifiers)
        try:
            raw = browser().open_novisit(query).read()
        except Exception, e:
            log.exception('Failed to make identify query: %r'%query)
            return as_unicode(e)

        try:
            parser = etree.XMLParser(recover=True, no_network=True)
            feed = etree.fromstring(xml_to_unicode(raw,
                strip_encoding_pats=True)[0], parser=parser)
            entries = entry(feed)
        except Exception, e:
            log.exception('Failed to parse identify results')
            return as_unicode(e)


        groups = self.split_jobs(entries, 5) # At most 5 threads
        if not groups:
            return None
        workers = [Worker(log, entries, abort, result_queue) for entries in
                groups]

        if abort.is_set():
            return None

        for worker in workers: worker.start()

        has_alive_worker = True
        while has_alive_worker and not abort.is_set():
            time.sleep(0.1)
            has_alive_worker = False
            for worker in workers:
                if worker.is_alive():
                    has_alive_worker = True

        return None

if __name__ == '__main__':
    # To run these test use: calibre-debug -e src/calibre/ebooks/metadata/sources/google.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            isbn_test)
    test_identify_plugin(GoogleBooks.name,
        [
            (
                {'title': 'Great Expectations', 'authors':['Charles Dickens']},
                [isbn_test('9781607541592')]
            ),
    ])
