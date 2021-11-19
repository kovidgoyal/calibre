# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2012, Alex Stanev <alex@stanev.org>'
__docformat__ = 'restructuredtext en'

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from contextlib import closing
from lxml import html


class BiblioStore(BasicStoreConfig, StorePlugin):

    web_url = 'https://biblio.bg'

    def open(self, parent=None, detail_item=None, external=False):
        if external or self.config.get('open_external', False):
            open_url(detail_item)
        else:
            d = WebStoreDialog(self.gui, self.web_url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        if isinstance(query, bytes):
            query = query.decode('utf-8')

        if len(query) < 3:
            return

        # do keyword search
        url = '{}/книги?query={}&search_by=0'.format(self.web_url, quote_plus(query))
        yield from self._do_search(url, max_results, timeout)

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            search_result.formats = ''
            search_result.drm = SearchResult.DRM_LOCKED

            for option in idata.xpath('//ul[@class="order_product_options"]/li'):
                option_type = option.text.strip() if option.text else ''
                if option_type.startswith('Формат:'):
                    search_result.formats = ''.join(option.xpath('.//b/text()')).strip()
                if option_type.startswith('Защита:'):
                    if ''.join(option.xpath('.//b/text()')).strip() == 'няма':
                        search_result.drm = SearchResult.DRM_UNLOCKED

            if not search_result.author:
                search_result.author = ', '.join(idata.xpath('//div[@class="row product_info"]/div/div/div[@class="item-author"]/a/text()')).strip(', ')

        return True

    def _do_search(self, url, max_results, timeout):
        br = browser()
        with closing(br.open(url, timeout=timeout)) as f:
            page = f.read().decode('utf-8')
            doc = html.fromstring(page)

            for data in doc.xpath('//ul[contains(@class,"book_list")]/li'):
                if max_results <= 0:
                    break

                s = SearchResult()
                s.detail_item = ''.join(data.xpath('.//a[@class="th"]/@href')).strip()
                if not id:
                    continue

                s.cover_url = ''.join(data.xpath('.//a[@class="th"]/img/@data-original')).strip()
                s.title = ''.join(data.xpath('.//div[@class="item-title"]/a/text()')).strip()
                s.author = ', '.join(data.xpath('.//div[@class="item-author"]/a/text()')).strip(', ')

                price_list = data.xpath('.//div[@class="item-price"]')
                for price_item in price_list:
                    if price_item.text.startswith('е-книга:'):
                        s.price = ''.join(price_item.xpath('.//span/text()'))
                        break

                s.price = '0.00 лв.' if not s.price and not price_list else s.price
                if not s.price:
                    # no e-book available
                    continue

                max_results -= 1
                yield s
