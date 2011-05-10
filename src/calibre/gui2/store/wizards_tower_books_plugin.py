# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
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

class WizardsTowerBooksStore(BasicStoreConfig, StorePlugin):

    url = 'http://www.wizardstowerbooks.com/'

    def open(self, parent=None, detail_item=None, external=False):
        if detail_item:
            detail_item = self.url + detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, self.url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.wizardstowerbooks.com/search.html?for=' + urllib.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//table[@class="gridp"]//td'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//span[@class="prti"]/a/@href'))
                id = id.strip()
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="prim"]/a/img/@src'))
                cover_url = url_slash_cleaner(self.url + cover_url.strip())

                price = ''.join(data.xpath('.//font[@class="selling_price"]//text()'))
                price = price.strip()
                if not price:
                    continue
                
                title = ''.join(data.xpath('.//span[@class="prti"]/a/b/text()'))
                author = ''.join(data.xpath('.//p[@class="last"]/text()'))
                a, b, author = author.partition(' by ')
                
                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                
                yield s

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(url_slash_cleaner(self.url + search_result.detail_item), timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
        
            formats = ', '.join(idata.xpath('//select[@id="N1_"]//option//text()'))
            search_result.formats = formats.upper()
            
        return True
