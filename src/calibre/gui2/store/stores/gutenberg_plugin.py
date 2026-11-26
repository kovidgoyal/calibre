# License: GPLv3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

store_version = 10  # Needed for dynamic plugin loading

import mimetypes
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from css_selectors import Select
from html5_parser import parse
from lxml import etree

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

if TYPE_CHECKING:
    from collections.abc import Iterator

    from qt.core import QWidget

    from calibre.gui2.ui import Main


def absurl(href: str) -> str:
    if href.startswith('//'):
        href = 'https:' + href
    elif href.startswith('/'):
        href = 'https://www.gutenberg.org' + href
    return href


def search(query: bytes | str, max_results: int = 10, timeout: int = 60, write_raw_to: str | None = None) -> Iterator[SearchResult]:
    url = f'https://www.gutenberg.org/ebooks/search/?query={quote_plus(query)}&submit_search=Search'

    counter = max_results
    br = browser()
    raw = br.open(url).read()

    if write_raw_to is not None:
        with open(write_raw_to, 'wb') as f:
            f.write(raw)

    root = parse(raw)
    CSSSelect = Select(root)
    for li in CSSSelect('li.booklink'):
        if counter <= 0:
            break
        counter -= 1

        s = SearchResult()
        href = next(CSSSelect('a.link', li)).get('href')
        if not href:
            continue
        s.detail_item = absurl(href)
        s.title = etree.tostring(next(CSSSelect('span.title', li)), method='text', encoding='unicode').strip()
        try:
            s.author = etree.tostring(next(CSSSelect('span.subtitle', li)), method='text', encoding='unicode').strip()
        except StopIteration:
            s.author = ''
        for img in CSSSelect('img.cover-thumb', li):
            if src := img.get('src'):
                s.cover_url = absurl(src)
            break

        # Get the formats and direct download links.
        details_doc = parse(br.open_novisit(s.detail_item).read())
        doc_select = Select(details_doc)
        for a in doc_select('a.featured-format-link'):
            href = a.get('href')
            if not href:
                continue
            for span in doc_select('span.featured-format-name', a):
                fname = etree.tostring(span, method='text', encoding='unicode').strip()
                if fname == 'EPUB3':
                    s.downloads['EPUB'] = absurl(href.split('?')[0])
        for a in doc_select('a.other-format-link'):
            href = a.get('href')
            type = a.get('type')
            ext = mimetypes.guess_extension(type.split(';')[0]) if type else None
            if href and ext:
                url = absurl(href.split('?')[0])
                ext = ext[1:].upper().strip()
                if ext not in s.downloads:
                    s.downloads[ext] = url

        s.formats = ', '.join(s.downloads.keys())
        if not s.formats:
            continue

        s.drm = SearchResult.DRM_UNLOCKED
        yield s


class GutenbergStore(StorePlugin):
    def search(self, query: bytes | str, max_results: int = 10, timeout: int = 60) -> Iterator[SearchResult]:
        yield from search(query, max_results, timeout)

    def open(self, gui: Main | None = None, parent: QWidget | None = None, detail_item: str | None = None, external: bool = False) -> None:
        url = detail_item or absurl('/')
        if external:
            open_url(url)
            return
        d = WebStoreDialog(self.gui, url, parent, detail_item)
        d.setWindowTitle(self.name)
        d.exec()


if __name__ == '__main__':
    import sys

    for result in search(' '.join(sys.argv[1:]), write_raw_to='/t/gutenberg.html'):
        print(result)
