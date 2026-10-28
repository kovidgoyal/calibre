#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

store_version = 1  # Needed for dynamic plugin loading

import json
import posixpath
import re
from collections.abc import Iterator
from urllib.parse import urlencode, urlparse

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

BASE_URL = 'https://directory.doabooks.org'
# The extensions of full text links that can be downloaded as e-books, most
# links are to the page for the book on the publisher's site
FORMATS = {'.pdf': 'PDF', '.epub': 'EPUB'}
# Editors are sometimes listed as authors, with (Ed.), (Eds.) or (Hrsg.) after their name
EDITOR_SUFFIX = re.compile(r'\s*\((?:eds?|hrsg)\.?\)\s*$', re.IGNORECASE)


def metadata_values(item: dict[str, list[dict[str, str]]], key: str) -> list[str]:
    return [v for m in item.get('metadata') or () if m.get('key') == key and (v := (m.get('value') or '').strip())]


def search(query: str, max_results: int = 10, timeout: int = 60, write_raw_to: str | None = None) -> Iterator[SearchResult]:
    # See https://www.doabooks.org/en/resources/metadata-harvesting-and-content-dissemination
    # The query is quoted as otherwise the results are mostly not relevant to it
    url = f'{BASE_URL}/rest/search?' + urlencode({
        'query': '"{}"'.format(' '.join(query.replace('"', ' ').split())),
        'expand': 'metadata',
        'limit': max(1, max_results),
    })
    br = browser()
    raw = br.open(url, timeout=timeout).read()
    if write_raw_to is not None:
        with open(write_raw_to, 'wb') as f:
            f.write(raw)

    items = json.loads(raw)
    if not isinstance(items, list):
        raise TypeError(f'Unexpected response from DOAB: {raw[:200]!r}')
    counter = max_results
    for item in items:
        if counter <= 0:
            break
        titles, uris = metadata_values(item, 'dc.title'), metadata_values(item, 'dc.identifier.uri')
        if not titles or not uris:
            continue
        counter -= 1
        s = SearchResult()
        s.title = titles[0]
        authors = [a for a in (EDITOR_SUFFIX.sub('', x) for x in metadata_values(item, 'dc.contributor.author')) if a]
        s.author = ' & '.join(authors or metadata_values(item, 'dc.contributor.editor'))
        s.detail_item = uris[0]
        for link in metadata_values(item, 'dc.identifier'):
            parsed = urlparse(link)
            fmt = FORMATS.get(posixpath.splitext(parsed.path)[1].lower())
            if parsed.scheme in ('http', 'https') and fmt and fmt not in s.downloads:
                s.downloads[fmt] = link
        s.formats = ', '.join(s.downloads)
        s.drm = SearchResult.DRM_UNLOCKED
        yield s


class DOABStore(StorePlugin):
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
