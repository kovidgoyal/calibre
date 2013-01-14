# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import urllib
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class BookotekaStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):

        url = 'http://bookoteka.pl/ebooki'
        detail_url = None

        if detail_item:
            detail_url = detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://bookoteka.pl/list?search=' + urllib.quote_plus(query) + '&cat=1&hp=1&type=1'

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//li[@class="EBOOK"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[@class="item_link"]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//a[@class="item_link"]/img/@src'))
                title = ''.join(data.xpath('.//div[@class="shelf_title"]/a/text()'))
                author = ''.join(data.xpath('.//div[@class="shelf_authors"][1]/text()'))
                price = ''.join(data.xpath('.//span[@class="EBOOK"]/text()'))
                price = price.replace('.', ',')
                formats = ', '.join(data.xpath('.//a[@class="fancybox protected"]/text()'))

                counter -= 1

                s = SearchResult()
                s.cover_url = 'http://bookoteka.pl' + cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = 'http://bookoteka.pl' + id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats.strip()

                yield s
