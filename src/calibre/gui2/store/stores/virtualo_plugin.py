# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 9  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2017, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
import urllib
from base64 import b64encode
from contextlib import closing

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class VirtualoStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/12/58/'

        url = 'http://virtualo.pl/ebook/c2/'

        aff_url = aff_root + str(b64encode(url))

        detail_url = None
        if detail_item:
            detail_url = aff_root + str(b64encode(detail_item))

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=12, timeout=60):
        url = 'http://virtualo.pl/?q=' + urllib.quote(query)

        br = browser()
        no_drm_pattern = re.compile(r'Watermark|Brak')

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="products-list-wrapper"]//li[@class="product "]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="cover-wrapper"]//a/@href')).split(r'?q=')[0]
                if not id:
                    continue

                price = ''.join(data.xpath('.//div[@class="information"]//div[@class="price"]/text()'))
                cover_url = ''.join(data.xpath('.//img[@class="cover"]/@src'))
                title = ''.join(data.xpath('.//div[@class="title"]/a//text()'))
                author = ', '.join(data.xpath('.//div[@class="information"]//div[@class="authors"]/a//text()'))
                formats = [form.strip() for form in data.xpath('.//div[@class="information"]//div[@class="format"]/a//text()')]
                nodrm = no_drm_pattern.search(''.join(data.xpath('.//div[@class="protection"]/text()')))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = re.sub('\.',',',price.strip())
                s.detail_item = id
                s.formats = ', '.join(formats).upper()
                s.drm = SearchResult.DRM_UNLOCKED if nodrm else SearchResult.DRM_LOCKED

                yield s
