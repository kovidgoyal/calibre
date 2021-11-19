# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 4  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from lxml import html

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class MillsBoonUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'https://www.millsandboon.co.uk'

        if external or self.config.get('open_external', False):
            if detail_item:
                url = detail_item
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            if detail_item:
                detail_url = detail_item
            else:
                detail_url = None
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        base_url = 'https://www.millsandboon.co.uk'
        url = base_url + '/search.aspx??format=ebook&searchText=' + quote(query)
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//article[contains(@class, "group")]'):
                if counter <= 0:
                    break
                id_ = ''.join(data.xpath('.//div[@class="img-wrapper"]/a/@href')).strip()
                if not id_:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="img-wrapper"]/a/img/@src'))
                title =  ''.join(data.xpath('.//div[@class="img-wrapper"]/a/img/@alt')).strip()
                author = ''.join(data.xpath('.//a[@class="author"]/text()'))
                price = ''.join(data.xpath('.//div[@class="type-wrapper"]/ul/li[child::span[text()="eBook"]]/a/text()'))
                format_ = ''.join(data.xpath('.//p[@class="doc-meta-format"]/span[last()]/text()'))
                drm = SearchResult.DRM_LOCKED

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = id_
                s.drm = drm
                s.formats = format_

                yield s
