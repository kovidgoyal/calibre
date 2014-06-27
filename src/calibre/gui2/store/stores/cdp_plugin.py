# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 4 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2013-2014, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import urllib
from base64 import b64encode
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class CdpStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/47/58/'

        url = 'https://cdp.pl/ksiazki'

        aff_url = aff_root + str(b64encode(url))

        detail_url = None
        if detail_item:
            detail_url = aff_root + str(b64encode(detail_item))

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url if detail_url else aff_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):

        br = browser()
        page=1

        counter = max_results
        while counter:
            with closing(br.open(u'https://cdp.pl/products/search?utf8=✓&keywords=' + urllib.quote_plus(query) + '&page=' + str(page), timeout=timeout)) as f:
                doc = html.fromstring(f.read())
                for data in doc.xpath('//ul[@id="products"]/li'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//div[@class="product-image"]/a[1]/@href'))
                    if not id:
                        continue
                    if 'ksiazki' not in id:
                        continue

                    cover_url = ''.join(data.xpath('.//div[@class="product-image"]/a[1]/@data-background'))
                    cover_url = cover_url.split('\'')[1]
                    title = ''.join(data.xpath('.//div[@class="product-description"]/h2/a/text()'))
                    author = ''.join(data.xpath('.//div[@class="product-description"]//ul[@class="taxons"]/li[@class="author"]/a/text()'))
                    price = ''.join(data.xpath('.//span[@itemprop="price"]/text()'))

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = cover_url
                    s.title = title.strip()
                    s.author = author.strip()
                    s.price = price
                    s.detail_item = id.strip()
                    s.drm = SearchResult.DRM_UNLOCKED

                    yield s
                if not doc.xpath('//span[@class="next"]/a'):
                    break
            page+=1

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            formats = ', '.join(idata.xpath('//div[@id="product-bonus"]/div/ul/li/text()'))
            search_result.formats = formats.upper()
        return True
