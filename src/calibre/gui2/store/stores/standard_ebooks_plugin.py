#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

store_version = 1  # Needed for dynamic plugin loading

from collections.abc import Iterator
from urllib.parse import urlencode

from lxml import etree

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

BASE_URL = 'https://standardebooks.org'
# The maximum number of results per page the site allows
MAX_PER_PAGE = 60


def absurl(href: str) -> str:
    if href.startswith('/'):
        href = BASE_URL + href
    return href


def text_of(elems: list[etree._Element]) -> str:
    return ' '.join(' '.join(''.join(e.itertext()) for e in elems).split())


def search(query: str, max_results: int = 10, timeout: int = 60, write_raw_to: str | None = None) -> Iterator[SearchResult]:
    from html5_parser import parse

    url = BASE_URL + '/ebooks?' + urlencode({'query': query, 'per-page': MAX_PER_PAGE})
    br = browser()
    raw = br.open(url, timeout=timeout).read()
    if write_raw_to is not None:
        with open(write_raw_to, 'wb') as f:
            f.write(raw)

    root = parse(raw)
    counter = max_results
    for li in root.xpath('//ol[contains(@class, "ebooks-list")]/li[@typeof="schema:Book"]'):
        if counter <= 0:
            break
        covers = li.xpath('./div[@class="thumbnail-container"]//img/@src')
        links = li.xpath('./p[not(@class)]/a[@href]')
        # Books that are wanted or in progress have no cover and cannot be
        # downloaded, so a full page is requested to have enough left over
        if not covers or not links:
            continue
        counter -= 1

        s = SearchResult()
        s.title = text_of(links[0].xpath('./span[@property="schema:name"]'))
        s.author = ' & '.join(filter(None, (text_of([x]) for x in li.xpath('./p[contains(@class, "author")]//span[@property="schema:name"]'))))
        s.cover_url = absurl(covers[0])
        s.detail_item = absurl(links[0].get('href'))
        # The books are downloaded from their page on the site, which shows a
        # request for donations first, so no direct download links are used
        s.formats = 'EPUB, AZW3, KEPUB'
        s.drm = SearchResult.DRM_UNLOCKED
        yield s


class StandardEbooksStore(StorePlugin):
    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        # The Get books search dialog passes the query as UTF-8 encoded bytes
        if isinstance(query, bytes):
            query = query.decode('utf-8', 'replace')
        yield from search(query, max_results, timeout)

    def open(self, gui=None, parent=None, detail_item=None, external=False):
        url = detail_item or BASE_URL
        if external:
            open_url(url)
            return
        d = WebStoreDialog(self.gui, BASE_URL, parent, detail_item)
        d.setWindowTitle(self.name)
        d.exec()


if __name__ == '__main__':
    import sys

    for result in search(' '.join(sys.argv[1:])):
        print(result)
