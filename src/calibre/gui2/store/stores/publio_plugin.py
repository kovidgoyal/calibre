# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 9  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2012-2017, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote
from base64 import b64encode
from contextlib import closing

from lxml import html

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def as_base64(data):
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    ans = b64encode(data)
    if isinstance(ans, bytes):
        ans = ans.decode('ascii')
    return ans


class PublioStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/29/58/'
        url = 'http://www.publio.pl/'

        aff_url = aff_root + as_base64(url)

        detail_url = None
        if detail_item:
            detail_url = aff_root + as_base64(detail_item)

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url if detail_url else aff_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=20, timeout=60):

        br = browser()

        counter = max_results
        page = 1
        while counter:
            with closing(br.open('http://www.publio.pl/e-booki,strona{}.html?q={}'.format(page, quote(query)), timeout=timeout)) as f:  # noqa
                doc = html.fromstring(f.read())
                for data in doc.xpath('//div[@class="products-list"]//div[@class="product-tile"]'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//a[@class="product-tile-cover"]/@href'))
                    if not id:
                        continue

                    cover_url = ''.join(data.xpath('.//img[@class="product-tile-cover-photo"]/@src'))
                    title = ''.join(data.xpath('.//span[@class="product-tile-title-long"]/text()'))
                    author = ', '.join(data.xpath('.//span[@class="product-tile-author"]/a/text()'))
                    price = ''.join(data.xpath('.//div[@class="product-tile-price-wrapper "]/a/ins/text()'))
                    formats = ''.join(data.xpath('.//a[@class="product-tile-cover"]/img/@alt')).split(' - ebook ')[1]

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = 'http://www.publio.pl' + cover_url
                    s.title = title.strip()
                    s.author = author
                    s.price = price
                    s.detail_item = 'http://www.publio.pl' + id.strip()
                    s.formats = formats.upper().strip()

                    yield s
                if not doc.xpath('boolean(//a[@class="next"])'):
                    break
                page+=1
