# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
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

class DieselEbooksStore(BasicStoreConfig, StorePlugin):
        
    def open(self, parent=None, detail_item=None, external=False):
        settings = self.get_settings()
        url = 'http://www.diesel-ebooks.com/'

        aff_id = '?aid=2049'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            aff_id = '?aid=2053'

        detail_url = None
        if detail_item:
            detail_url = url + detail_item + aff_id
        url = url + aff_id

        if external or settings.get(self.name + '_open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(settings.get(self.name + '_tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.diesel-ebooks.com/index.php?page=seek&id[m]=&id[c]=scope%253Dinventory&id[q]=' + urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="item clearfix"]'):
                data = html.fromstring(html.tostring(data))
                if counter <= 0:
                    break

                id = ''.join(data.xpath('div[@class="cover"]/a/@href'))
                if not id or '/item/' not in id:
                    continue
                a, b, id = id.partition('/item/')

                cover_url = ''.join(data.xpath('div[@class="cover"]//img/@src'))
                if cover_url.startswith('/'):
                    cover_url = cover_url[1:]
                cover_url = 'http://www.diesel-ebooks.com/' + cover_url

                title = ''.join(data.xpath('.//div[@class="content"]//h2/text()'))
                author = ''.join(data.xpath('//div[@class="content"]//div[@class="author"]/a/text()'))
                price = ''
                price_elem = data.xpath('//td[@class="price"]/text()')
                if price_elem:
                    price = price_elem[0]

                formats = ', '.join(data.xpath('.//td[@class="format"]/text()'))

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '/item/' + id.strip()
                s.formats = formats
                
                yield s

    def get_details(self, search_result, timeout):
        url = 'http://www.diesel-ebooks.com/item/'
        
        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if idata.xpath('boolean(//table[@class="format-info"]//tr[contains(th, "DRM") and contains(td, "No")])'):
                search_result.drm = SearchResult.DRM_UNLOCKED
            else:
                search_result.drm = SearchResult.DRM_LOCKED
