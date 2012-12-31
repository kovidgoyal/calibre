# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
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

class BNStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = "http://bn.com"

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.barnesandnoble.com/s/%s?keyword=%s&store=ebook&view=list' % (query.replace(' ', '-'), urllib.quote_plus(query))

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            raw = f.read()
            doc = html.fromstring(raw)
            for data in doc.xpath('//ul[contains(@class, "result-set")]/li[contains(@class, "result")]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[contains(@class, "image-block")]/a/@href'))
                if not id:
                    continue

                cover_url = ''
                cover_id = ''.join(data.xpath('.//img[contains(@class, "product-image")]/@id'))
                m = re.search(r"%s'.*?srcUrl: '(?P<iurl>.*?)'.*?}" % cover_id, raw)
                if m:
                    cover_url = m.group('iurl')

                title = ''.join(data.xpath('descendant::p[@class="title"]//span[@class="name"]//text()')).strip()
                if not title:
                    continue

                author = ', '.join(data.xpath('.//ul[contains(@class, "contributors")]//a[contains(@class, "subtle")]//text()')).strip()
                price = ''.join(data.xpath('.//a[contains(@class, "bn-price")]//text()'))

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
