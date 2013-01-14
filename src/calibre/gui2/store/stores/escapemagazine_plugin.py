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

class EscapeMagazineStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        pid = '44010'

        url = 'http://www.escapemagazine.pl/s/' + pid

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item + '/s/' + pid if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=20, timeout=60):
        url = 'http://www.escapemagazine.pl/wyszukiwarka?query=' + urllib.quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="item item_short"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//h2[@class="title"]/a[1]/@href'))
                if not id:
                    continue

                title = ''.join(data.xpath('.//h2[@class="title"]/a[1]/text()'))
                author = ''.join(data.xpath('.//div[@class="author"]/text()'))
                price = ''.join(data.xpath('.//span[@class="price_now"]/strong/text()')) + ' zł'
                cover_url = ''.join(data.xpath('.//img[@class="cover"]/@src'))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = 'http://www.escapemagazine.pl' + id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = 'PDF'

                yield s
