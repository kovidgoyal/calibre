# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
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

class ZixoStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):

        url = 'http://zixo.pl/e_ksiazki/start/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://zixo.pl/wyszukiwarka/?search=' + urllib.quote(query.encode('utf-8')) + '&product_type=0'

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="productInline"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[@class="productThumb"]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//a[@class="productThumb"]/img/@src'))
                title = ''.join(data.xpath('.//a[@class="title"]/text()'))
                author = ','.join(data.xpath('.//div[@class="productDescription"]/span[1]/a/text()'))
                price = ''.join(data.xpath('.//div[@class="priceList"]/span/text()'))
                price = re.sub('\.', ',', price)

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = 'http://zixo.pl' + id.strip()
                s.drm = SearchResult.DRM_LOCKED

                yield s

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            formats = ''.join(idata.xpath('//ul[@class="prop"]/li[3]/text()'))
            formats = re.sub(r'\(.*\)', '', formats)
            formats = re.sub('Zixo Reader', 'ZIXO', formats)
            search_result.formats = formats
        return True
