# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class WHSmithUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'https://www.whsmith.co.uk/'
        url_details = ''

        if external or self.config.get('open_external', False):
            if detail_item:
                url = url_details + detail_item
            open_url(QUrl(url))
        else:
            detail_url = None
            if detail_item:
                detail_url = url_details + detail_item
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = ('https://www.whsmith.co.uk/search?keywordCategoryId=wc_dept_ebooks&results=60'
               '&page=1&keywords=' + quote(query))

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//li[@class="product"]'):
                if counter <= 0:
                    break
                id_ = ''.join(data.xpath('./a[@class="product_image_wrap"]/@href'))
                if not id_:
                    continue
                id_ = 'https://www.whsmith.co.uk' + id_
                cover_url = ''.join(data.xpath('.//img[@class="product_image"]/@src'))
                title = ''.join(data.xpath('.//h4[@class="product_title"]/text()'))
                author = ', '.join(data.xpath('.//span[@class="product_second"]/text()'))
                price = ''.join(data.xpath('.//span[@class="price"]/text()'))
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.drm = SearchResult.DRM_LOCKED
                s.detail_item = id_
                s.formats = 'ePub'

                yield s
