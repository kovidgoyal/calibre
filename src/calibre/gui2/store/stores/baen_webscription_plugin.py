# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from lxml import html

from qt.core import QUrl

from calibre import browser
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def search(query, max_results=10, timeout=60):
    url = 'http://www.baen.com/catalogsearch/result/?' + urlencode(
        {'q':query.lower(), 'dir':'desc', 'order':'relevance'})

    br = browser()

    counter = max_results
    with closing(br.open_novisit(url, timeout=timeout)) as f:
        raw = f.read()
        root = html.fromstring(raw)
        for data in root.xpath('//div[@id="productMatches"]//table[@id="authorTable"]//tr[contains(@class, "IDCell")]'):
            if counter <= 0:
                break

            try:
                book_url = data.xpath('./td[1]/a/@href[1]')[0]
            except IndexError:
                continue

            try:
                title = data.xpath('./td[2]/a[1]/text()')[0].strip()
            except IndexError:
                continue
            try:
                cover_url = data.xpath('./td[1]//img[1]/@src')[0]
            except IndexError:
                cover_url = ''

            tails = [(b.tail or '').strip() for b in data.xpath('./td[2]/br')]
            authors = [x[2:].strip() for x in tails if x.startswith('by ')]
            author = authors_to_string(authors)
            price = ''.join(data.xpath('.//span[@class="variantprice"]/text()'))
            a, b, price = price.partition('$')
            price = b + price

            counter -= 1

            s = SearchResult()
            s.cover_url = cover_url
            s.title = title.strip()
            s.author = author.strip()
            s.price = price
            s.detail_item = book_url.strip()
            s.drm = SearchResult.DRM_UNLOCKED
            s.formats = 'RB, MOBI, EPUB, LIT, LRF, RTF, HTML'

            yield s


class BaenWebScriptionStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.baenebooks.com/'
        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item or url))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item or url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        for result in search(query, max_results, timeout):
            yield result


if __name__ == '__main__':
    import sys
    for result in search(' '.join(sys.argv[1:])):
        print(result)
