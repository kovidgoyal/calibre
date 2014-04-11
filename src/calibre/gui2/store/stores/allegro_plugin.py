# -*- coding: utf-8 -*-

from __future__ import (division, absolute_import, print_function, unicode_literals)
store_version = 1  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2013, Tomasz Długosz <tomek3d@gmail.com>'
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

class AllegroStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/34/58/'

        url = 'http://ebooki.allegro.pl/'

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
            with closing(br.open('http://ebooki.allegro.pl/szukaj?fraza=' + urllib.quote(query) + '&strona=' + str(page), timeout=timeout)) as f:
                doc = html.fromstring(f.read().decode('utf-8'))
                for data in doc.xpath('//div[@class="listing-list"]/div[@class="listing-list-item"]'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//div[@class="listing-cover-wrapper"]/a/@href'))
                    if not id:
                        continue

                    cover_url = ''.join(data.xpath('.//div[@class="listing-cover-wrapper"]/a/img/@src'))
                    title = ''.join(data.xpath('.//div[@class="listing-info"]/div[1]/a/text()'))
                    author = ', '.join(data.xpath('.//div[@class="listing-info"]/div[2]/a/text()'))
                    price = ''.join(data.xpath('.//div[@class="book-price"]/text()'))
                    formats = ', '.join(data.xpath('.//div[@class="listing-buy-formats"]//div[@class="devices-wrapper"]/span[@class="device-label"]/span/text()'))

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = 'http://ebooki.allegro.pl/' + cover_url
                    s.title = title.strip()
                    s.author = author.strip()
                    s.price = price
                    s.detail_item = 'http://ebooki.allegro.pl/' + id[1:]
                    s.formats = formats.upper()
                    s.drm = SearchResult.DRM_UNLOCKED

                    yield s
                if not doc.xpath('//a[@class="paging-arrow right-paging-arrow"]'):
                    break
            page+=1
