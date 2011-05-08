# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
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

class BordersStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        #m_url = 'http://www.dpbolvw.net/'
        #h_click = 'click-4879827-10762497'
        #d_click = 'click-4879827-10772898'
        # Use Kovid's affiliate id 30% of the time.
        #if random.randint(1, 10) in (1, 2, 3):
        #    h_click = 'click-4913808-10762497'
        #    d_click = 'click-4913808-10772898'
        
        #url = m_url + h_click
        url = 'http://www.borders.com/online/store/Landing?nav=5185+700152'
        detail_url = None
        if detail_item:
            detail_url = 'http://www.borders.com/online/store/TitleDetail?sku=%s' % detail_item
            #detail_url = m_url + d_click + detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.borders.com/online/store/SearchResults?type=44&simple=1&keyword=' + urllib.quote_plus(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//table[@class="browseResultsTable"]//tr'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//td[1]/a[1]/@href'))
                if not id:
                    continue
                id = re.search('(?<=sku=)\d+', id)
                if not id:
                    continue
                id = id.group()

                cover_url = ''.join(data.xpath('.//img[@class="jtip prod-item"]/@src'))

                title = ''.join(data.xpath('.//td[@align="left"][1]//a[1]//text()'))
                author = ''.join(data.xpath('.//td[@align="left"][1]//a[2]/text()'))

                price = ''.join(data.xpath('.//div[@class="sale_price"]//text()'))
                price = re.search('\$[\d.]+', price)
                if not price:
                    continue
                price = price.group()

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id.strip()
                #s.detail_item = '?url=http://www.kobobooks.com/' + id.strip()
                s.drm = SearchResult.DRM_LOCKED
                s.formats = 'EPUB'

                yield s
