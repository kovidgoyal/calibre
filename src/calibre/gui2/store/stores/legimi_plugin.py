# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

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

class LegimiStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        
        plain_url = 'http://www.legimi.com/pl/ebooks/?price=any'
        url = 'https://ssl.afiliant.com/affskrypt,,2f9de2,,11483,,,?u=(' + plain_url + ')'
        detail_url = None

        if detail_item:
            detail_url = 'https://ssl.afiliant.com/affskrypt,,2f9de2,,11483,,,?u=(' + detail_item + ')'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.legimi.com/pl/ebooks/?price=any&lang=pl&search=' + urllib.quote_plus(query) + '&sort=relevance'
        
        br = browser()
        drm_pattern = re.compile("(DRM)")
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="list"]/ul/li'):
                if counter <= 0:
                    break
                
                id = ''.join(data.xpath('.//div[@class="item_cover_container"]/a[1]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="item_cover_container"]/a/img/@src'))
                title = ''.join(data.xpath('.//div[@class="item_entries"]/h2/a/text()'))
                author = ''.join(data.xpath('.//div[@class="item_entries"]/span[1]/a/text()'))
                author = re.sub(',','',author)
                author = re.sub(';',',',author)
                price = ''.join(data.xpath('.//span[@class="ebook_price"]/text()'))
                formats = ''.join(data.xpath('.//div[@class="item_entries"]/span[3]/text()'))
                formats = re.sub('Format:','',formats)
                drm = drm_pattern.search(formats)
                formats = re.sub('\(DRM\)','',formats)

                counter -= 1
                
                s = SearchResult()
                s.cover_url = 'http://www.legimi.com/' + cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = 'http://www.legimi.com/' + id.strip()
                s.drm = SearchResult.DRM_LOCKED if drm else SearchResult.DRM_UNLOCKED
                s.formats = formats.strip()
                
                yield s
