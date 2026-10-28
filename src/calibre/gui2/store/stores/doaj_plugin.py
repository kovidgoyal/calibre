#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

store_version = 1  # Needed for dynamic plugin loading

import json
import re
from collections.abc import Iterator
from urllib.parse import quote, urlencode

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

BASE_URL = 'https://doaj.org'
# The maximum page size the API allows
MAX_PAGE_SIZE = 100
# The content types of full text links that can be downloaded as e-books
FORMATS = {'PDF': 'PDF', 'EPUB': 'EPUB'}
# Characters with special meaning in the Elasticsearch query string syntax
QUERY_SYNTAX_CHARS = re.compile(r'([+\-=&|!(){}\[\]^"~*?:\\/<>])')
QUERY_OPERATORS = re.compile(r'\b(AND|OR|NOT)\b')


def escape_query(query: str) -> str:
    # The API interprets the search as an Elasticsearch query string, so
    # escape its syntax to search for the text the user typed literally
    query = QUERY_OPERATORS.sub(lambda m: m.group().lower(), query)
    return QUERY_SYNTAX_CHARS.sub(r'\\\1', query)


def search(query: str, max_results: int = 10, timeout: int = 60, write_raw_to: str | None = None) -> Iterator[SearchResult]:
    # See https://doaj.org/api/v4/docs
    url = f'{BASE_URL}/api/v4/search/articles/{quote(escape_query(query), safe="")}?' + urlencode({'pageSize': max(1, min(max_results, MAX_PAGE_SIZE))})
    br = browser()
    raw = br.open(url, timeout=timeout).read()
    if write_raw_to is not None:
        with open(write_raw_to, 'wb') as f:
            f.write(raw)

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError(f'Unexpected response from DOAJ: {raw[:200]!r}')
    counter = max_results
    for article in data.get('results') or ():
        if counter <= 0:
            break
        bibjson = article.get('bibjson') or {}
        title = (bibjson.get('title') or '').strip()
        if not title or not article.get('id'):
            continue
        counter -= 1
        s = SearchResult()
        s.title = title
        s.author = ' & '.join(filter(None, ((a.get('name') or '').strip() for a in bibjson.get('author') or ())))
        s.detail_item = f'{BASE_URL}/article/{article["id"]}'
        for link in bibjson.get('link') or ():
            fmt = FORMATS.get((link.get('content_type') or '').upper())
            if link.get('type') == 'fulltext' and fmt and link.get('url') and fmt not in s.downloads:
                s.downloads[fmt] = link['url']
        s.formats = ', '.join(s.downloads)
        s.drm = SearchResult.DRM_UNLOCKED
        yield s


class DOAJStore(StorePlugin):
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
