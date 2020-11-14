# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 7  # Needed for dynamic plugin loading

import mimetypes

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from html5_parser import parse
from lxml import etree

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from css_selectors import Select


def absurl(href):
    if href.startswith('//'):
        href = 'https:' + href
    elif href.startswith('/'):
        href = 'https://www.gutenberg.org' + href
    return href


def search(query, max_results=10, timeout=60, write_raw_to=None):
    url = 'https://www.gutenberg.org/ebooks/search/?query={}&submit_search=Search'.format(quote_plus(query))

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
        a = next(CSSSelect('a.link', li))
        s.detail_item = absurl(a.get('href'))
        s.title = etree.tostring(next(CSSSelect('span.title', li)), method='text', encoding='unicode').strip()
        s.author = etree.tostring(next(CSSSelect('span.subtitle', li)), method='text', encoding='unicode').strip()
        for img in CSSSelect('img.cover-thumb', li):
            s.cover_url = absurl(img.get('src'))
            break

        # Get the formats and direct download links.
        details_doc = parse(br.open_novisit(s.detail_item).read())
        doc_select = Select(details_doc)
        for tr in doc_select('table.files tr[typeof="pgterms:file"]'):
            for a in doc_select('a.link', tr):
                href = a.get('href')
                type = a.get('type')
                ext = mimetypes.guess_extension(type.split(';')[0]) if type else None
                if href and ext:
                    url = absurl(href.split('?')[0])
                    ext = ext[1:].upper().strip()
                    if ext not in s.downloads:
                        s.downloads[ext] = url
                    break

        s.formats = ', '.join(s.downloads.keys())
        if not s.formats:
            continue

        yield s


class GutenbergStore(StorePlugin):

    def search(self, query, max_results=10, timeout=60):
        for result in search(query, max_results, timeout):
            yield result

    def open(self, parent=None, detail_item=None, external=False):
        url = detail_item or absurl('/')
        if external:
            open_url(url)
            return
        d = WebStoreDialog(self.gui, url, parent, detail_item)
        d.setWindowTitle(self.name)
        d.exec_()


if __name__ == '__main__':
    import sys

    for result in search(' '.join(sys.argv[1:]), write_raw_to='/t/gutenberg.html'):
        print(result)
