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

class BNStore(BasicStoreConfig, StorePlugin):
    
    def open(self, parent=None, detail_item=None, external=False):
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

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        query = query.replace(' ', '-')
        url = 'http://www.barnesandnoble.com/s/%s?store=ebook&sze=%s' % (query, max_results)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[contains(@class, "result-set")]/li[contains(@class, "result")]'):
                if counter <= 0:
                    break
                
                id = ''.join(data.xpath('.//div[contains(@class, "image")]/a/@href'))
                if not id:
                    continue
                cover_url = ''.join(data.xpath('.//div[contains(@class, "image")]//img/@src'))
                
                title = ''.join(data.xpath('.//p[@class="title"]//span[@class="name"]/text()'))
                author = ', '.join(data.xpath('.//ul[@class="contributors"]//li[position()>1]//a/text()'))
                price = ''.join(data.xpath('.//table[@class="displayed-formats"]//a[@class="subtle"]/text()'))
                
                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Nook'

                yield s
