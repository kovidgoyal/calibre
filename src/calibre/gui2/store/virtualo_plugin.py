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

class VirtualoStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://virtualo.pl/ebook/c2/'
        detail_url = None

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://virtualo.pl/c2/?q=' + urllib.quote(query.encode('utf-8'))

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="product_list"]/div/div[@class="column"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//table/tr[2]/td[1]/a/@href'))
                if not id:
                    continue

                price = ''.join(data.xpath('.//span[@class="price"]/text() | .//span[@class="price abbr"]/text()'))
                cover_url = ''.join(data.xpath('.//table/tr[2]/td[1]/a/img/@src'))
                title = ''.join(data.xpath('.//div[@class="title"]/a/text()'))
                author = ', '.join(data.xpath('.//div[@class="authors"]/a/text()'))
                formats = ', '.join(data.xpath('.//span[@class="format"]/a/text()'))
                formats = re.sub(r'(, )?ONLINE(, )?', '', formats)

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip() + ' ' + formats
                s.author = author.strip()
                s.price = price + ' zł'
                s.detail_item = 'http://virtualo.pl' + id.strip()
                s.formats = formats.upper().strip()
                s.drm = SearchResult.DRM_UNKNOWN

                yield s
