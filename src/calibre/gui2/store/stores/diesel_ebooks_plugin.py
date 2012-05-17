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

class DieselEbooksStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.diesel-ebooks.com/'

        aff_id = '?aid=2049'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            aff_id = '?aid=2053'

        detail_url = None
        if detail_item:
            detail_url = detail_item + aff_id
        url = url + aff_id

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.diesel-ebooks.com/index.php?page=seek&id[m]=&id[c]=scope%253Dinventory&id[q]=' + urllib.quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())

            if doc.xpath('not(boolean(//select[contains(@id, "selection")]))'):
                id = ''.join(doc.xpath('//div[@class="price_fat"]//a/@href'))
                mo = re.search('(?<=id=).+?(?=&)', id)
                if not mo:
                    yield None
                id = mo.group()

                cover_url = ''.join(doc.xpath('//div[@class="cover"]/a/@href'))

                title = ''.join(doc.xpath('//div[@class="desc_fat"]//h1/text()'))
                author = ''.join(doc.xpath('//div[@class="desc_fat"]//span[@itemprop="author"]/text()'))
                price = ''.join(doc.xpath('//div[@class="price_fat"]//h1/text()'))

                formats = ', '.join(doc.xpath('//div[@class="desc_fat"]//p[contains(text(), "Format")]/text()'))
                a, b, formats = formats.partition('Format:')

                drm = SearchResult.DRM_LOCKED
                if 'drm free' in formats.lower():
                    drm = SearchResult.DRM_UNLOCKED

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id.strip()
                s.formats = formats
                s.drm = drm

                yield s
            else:
                for data in doc.xpath('//div[contains(@class, "item")]'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('div[@class="cover"]/a/@href'))
                    if not id or '/item/' not in id:
                        continue

                    cover_url = ''.join(data.xpath('div[@class="cover"]//img/@src'))

                    title = ''.join(data.xpath('.//div[@class="content"]//h2/a/text()'))
                    author = ''.join(data.xpath('.//div[@class="content"]/span//a/text()'))
                    price = ''
                    price_elem = data.xpath('.//div[@class="price_fat"]//h1/text()')
                    if price_elem:
                        price = price_elem[0]

                    formats = ', '.join(data.xpath('.//div[@class="book-info"]//text()')).strip()
                    a, b, formats = formats.partition('Format:')
                    drm = SearchResult.DRM_LOCKED
                    if 'drm free' in formats.lower():
                        drm = SearchResult.DRM_UNLOCKED

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = cover_url
                    s.title = title.strip()
                    s.author = author.strip()
                    s.price = price.strip()
                    s.detail_item = id.strip()
                    s.formats = formats
                    s.drm = drm

                    yield s
