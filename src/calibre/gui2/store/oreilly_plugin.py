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

class OReillyStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://oreilly.com/ebooks/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://search.oreilly.com/?t1=Books&t2=Format&t3=Ebook&q=' + urllib.quote_plus(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="results"]/div[@class="result"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="title"]/a/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="bigCover"]//img/@src'))

                title = ''.join(data.xpath('.//div[@class="title"]/a/text()'))
                author = ''.join(data.xpath('.//div[@class="author"]/text()'))
                author = author.split('By ')[-1].strip()

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                
                yield s
                
    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            doc = html.fromstring(nf.read())

            search_result.price = ''.join(doc.xpath('(//span[@class="price"])[1]/span//text()')).strip()
            search_result.formats = ', '.join(doc.xpath('//div[@class="ebook_formats"]//a/text()')).upper()
            
        return True

