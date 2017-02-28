#!/usr/bin/env python2
# vim:fileencoding=UTF-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.metadata.sources.base import Source, Option


def get_urls(br, tokens):
    from urllib import quote_plus
    from mechanize import Request
    from lxml import html
    escaped = [quote_plus(x.encode('utf-8')) for x in tokens if x and x.strip()]
    q = b'+'.join(escaped)
    url = 'http://bigbooksearch.com/books/'+q
    br.open(url).read()
    req = Request('http://bigbooksearch.com/query.php?SearchIndex=books&Keywords=%s&ItemPage=1'%q)
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    req.add_header('Referer', url)
    raw = br.open(req).read()
    root = html.fromstring(raw.decode('utf-8'))
    urls = [i.get('src') for i in root.xpath('//img[@src]')]
    return urls


class BigBookSearch(Source):

    name = 'Big Book Search'
    version = (1, 0, 0)
    minimum_calibre_version = (2, 80, 0)
    description = _('Downloads multiple book covers from Amazon. Useful to find alternate covers.')
    capabilities = frozenset(['cover'])
    config_help_message = _('Configure the Big Book Search plugin')
    can_get_multiple_covers = True
    options = (Option('max_covers', 'number', 5, _('Maximum number of covers to get'),
                      _('The maximum number of covers to process from the search result')),
    )
    supports_gzip_transfer_encoding = True

    def download_cover(self, log, result_queue, abort,
            title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
        if not title:
            return
        br = self.browser
        tokens = tuple(self.get_title_tokens(title)) + tuple(self.get_author_tokens(authors))
        urls = get_urls(br, tokens)
        self.download_multiple_covers(title, authors, urls, get_best_cover, timeout, result_queue, abort, log)


def test():
    from calibre import browser
    import pprint
    br = browser()
    urls = get_urls(br, ['consider', 'phlebas', 'banks'])
    pprint.pprint(urls)

if __name__ == '__main__':
    test()
