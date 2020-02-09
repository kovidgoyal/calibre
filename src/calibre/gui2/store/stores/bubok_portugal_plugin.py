# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2014, Rafael Vega <rafavega@gmail.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class BubokPortugalStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'https://www.bubok.pt/tienda'
        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.bubok.pt/resellers/calibre_search/' + quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[contains(@class, "libro")]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="url"]/text()'))

                title = ''.join(data.xpath('.//div[@class="titulo"]/text()'))

                author = ''.join(data.xpath('.//div[@class="autor"]/text()'))

                price = ''.join(data.xpath('.//div[@class="precio"]/text()'))

                formats = ''.join(data.xpath('.//div[@class="formatos"]/text()'))

                cover = ''.join(data.xpath('.//div[@class="portada"]/text()'))

                counter -= 1

                s = SearchResult()
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = id.strip()
                s.price = price.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats.strip()
                s.cover_url = cover.strip()
                yield s

    def get_details(self, search_result, timeout):
        return True
