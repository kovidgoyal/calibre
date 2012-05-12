# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2, re
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class FoylesUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.awin1.com/awclick.php?mid=1414&id=120917'
        detail_url = 'http://www.awin1.com/cread.php?awinmid=1414&awinaffid=120917&clickref=&p='

        if external or self.config.get('open_external', False):
            if detail_item:
                url = detail_url + detail_item
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            detail_url = None
            if detail_item:
                detail_url = url + detail_item
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.foyles.co.uk/Public/Shop/Search.aspx?fFacetId=1015&searchBy=1&quick=true&term=' + urllib2.quote(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//table[contains(@id, "MainContent")]/tr/td/div[contains(@class, "Item")]'):
                if counter <= 0:
                    break
                id = ''.join(data.xpath('.//a[@class="Title"]/@href')).strip()
                if not id:
                    continue

                # filter out the audio books
                if not data.xpath('boolean(.//div[@class="Relative"]/ul/li[contains(text(), "ePub")])'):
                    continue

                cover_url = ''.join(data.xpath('.//a[@class="Jacket"]/img/@src'))
                title = ''.join(data.xpath('.//a[@class="Title"]/text()'))
                author = ', '.join(data.xpath('.//span[@class="Author"]/text()'))
                price = ''.join(data.xpath('./ul/li[@class="Strong"]/text()'))
                mo = re.search('£[\d\.]+', price)
                if mo is None:
                    continue
                price = mo.group(0)

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = id
                s.drm = SearchResult.DRM_LOCKED
                s.formats = 'ePub'

                yield s
