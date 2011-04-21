# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
import re
import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class BNStore(BasicStoreConfig, StorePlugin):
    
    def open(self, parent=None, detail_item=None, external=False):
        settings = self.get_settings()

        pub_id = '21000000000352219'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            pub_id = '21000000000352583'
        
        url = 'http://gan.doubleclick.net/gan_click?lid=41000000028437369&pubid=' + pub_id

        if detail_item:
            mo = re.search(r'(?<=/)(?P<isbn>\d+)(?=/|$)', detail_item)
            if mo:
                isbn = mo.group('isbn')
                detail_item = 'http://gan.doubleclick.net/gan_click?lid=41000000012871747&pid=' + isbn + '&adurl=' + detail_item + '&pubid=' + pub_id

        if external or settings.get(self.name + '_open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(settings.get(self.name + '_tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://productsearch.barnesandnoble.com/search/results.aspx?STORE=EBOOK&SZE=%s&WRD=' % max_results
        url += urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[contains(@class, "wgt-search-results-display")]/li[contains(@class, "search-result-item") and contains(@class, "nook-result-item")]'):
                if counter <= 0:
                    break
                
                id = ''.join(data.xpath('.//div[contains(@class, "wgt-product-image-module")]/a/@href'))
                if not id:
                    continue
                cover_url = ''.join(data.xpath('.//div[contains(@class, "wgt-product-image-module")]/a/img/@src'))
                
                title = ''.join(data.xpath('.//span[@class="product-title"]/a/text()'))
                author = ', '.join(data.xpath('.//span[@class="contributers-line"]/a/text()'))
                price = ''.join(data.xpath('.//span[contains(@class, "onlinePriceValue2")]/text()'))
                
                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Nook'
                
                yield s
