# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 8  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2013-2016, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import urllib
from base64 import b64encode
from contextlib import closing

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class CdpStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/47/58/'

        url = 'https://cdp.pl/ksiazki/e-book.html'

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
            with closing(br.open(u'https://cdp.pl/ksiazki/e-book.html?q=' + urllib.quote_plus(query) + '&p=' + str(page), timeout=timeout)) as f:
                doc = html.fromstring(f.read())
                for data in doc.xpath('//ul[@class="products"]/li'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//a[@class="product-image"]/@href'))
                    if not id:
                        continue

                    cover_url = ''.join(data.xpath('.//a[@class="product-image"]/img/@data-src'))
                    title = ''.join(data.xpath('.//h3[1]/a/@title'))
                    price = ''.join(data.xpath('.//span[@class="custom_price"]/text()'))+','+''.join(data.xpath('.//span[@class="custom_price"]/sup/text()'))
                    author = ''.join(data.xpath('.//div[@class="authors"]/@title'))
                    formats = ''
                    with closing(br.open(id.strip(), timeout=timeout/4)) as nf:
                        idata = html.fromstring(nf.read())
                        formats = idata.xpath('//div[@class="second-part-holder"]//div[@class="product-attributes-container"]/ul/li/span/text()')[-1]

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = cover_url
                    s.title = title.replace(' (ebook)','').strip()
                    s.author = author
                    s.price = price + ' zł'
                    s.detail_item = id.strip()
                    s.drm = SearchResult.DRM_UNLOCKED
                    s.formats = formats.upper().strip()

                    yield s
                if not doc.xpath('//a[@class="next-page"]'):
                    break
            page+=1
