# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
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
        pub_id = 'sHa5EXvYOwA'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            pub_id = '0dsO3kDu/AU'

        base_url = 'http://click.linksynergy.com/fs-bin/click?id=%s&subid=&offerid=229293.1&type=10&tmpid=8433&RD_PARM1=' % pub_id
        url = base_url + 'http%253A%252F%252Fwww.barnesandnoble.com%252F'

        if detail_item:
            detail_item = base_url + detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        query = query.replace(' ', '-')
        url = 'http://www.barnesandnoble.com/s/%s?store=nookstore' % query

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[contains(@class, "result-set")]/li[contains(@class, "result")]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[contains(@class, "thumb")]/@href'))
                if not id:
                    continue
                cover_url = ''.join(data.xpath('.//img[contains(@class, "product-image")]/@src'))

                title = ''.join(data.xpath('.//a[@class="title"]//text()'))
                author = ', '.join(data.xpath('.//a[@class="contributor"]//text()'))
                price = ''.join(data.xpath('.//div[@class="price-format"]//span[contains(@class, "price")]/text()'))

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
