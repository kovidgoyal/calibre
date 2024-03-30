# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 4  # Needed for dynamic plugin loading

from contextlib import closing

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import html
from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def search_bn(query, max_results=10, timeout=60, write_html_to=''):
    url = 'https://www.barnesandnoble.com/s/%s?keyword=%s&store=ebook&view=list' % (query.replace(' ', '-'), quote_plus(query))

    br = browser()

    counter = max_results
    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
        if write_html_to:
            with open(write_html_to, 'wb') as f:
                f.write(raw)
        doc = html.fromstring(raw)
        for data in doc.xpath('//section[@id="gridView"]//div[contains(@class, "product-shelf-tile-book")]'):
            if counter <= 0:
                break
            counter -= 1

            cover_url = ''
            cover_div = data.xpath('.//div[contains(@class, "product-shelf-image")]')
            if cover_div:
                cover_url = 'https:' + ''.join(cover_div[0].xpath('descendant::img/@src'))

            title_div = data.xpath('.//div[contains(@class, "product-shelf-title")]')
            if not title_div:
                continue
            title = ''.join(title_div[0].xpath('descendant::a/text()')).strip()
            if not title:
                continue
            item_url = ''.join(title_div[0].xpath('descendant::a/@href')).strip()
            if not item_url:
                continue
            item_url = 'https://www.barnesandnoble.com' + item_url

            author = ''
            author_div = data.xpath('.//div[contains(@class, "product-shelf-author")]')
            if author_div:
                author = ''.join(author_div[0].xpath('descendant::a/text()')).strip()

            price = ''
            price_div = data.xpath('.//div[contains(@class, "product-shelf-pricing")]/div[contains(@class, "current")]')
            if price_div:
                spans = price_div[0].xpath('descendant::span')
                if spans:
                    price = ''.join(spans[-1].xpath('descendant::text()'))
                    if '\n' in price:
                        price = price.split('\n')[1].split(',')[0]

            s = SearchResult()
            s.cover_url = cover_url
            s.title = title.strip()
            s.author = author.strip()
            s.price = price.strip()
            s.detail_item = item_url.strip()
            s.drm = SearchResult.DRM_UNKNOWN
            s.formats = 'Nook'
            yield s


class BNStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = "https://bn.com"

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        yield from search_bn(query, max_results, timeout)


if __name__ == '__main__':
    import sys
    for result in search_bn(' '.join(sys.argv[1:]), write_html_to='/t/bn.html'):
        print(result)
