# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2012, John Schember <john@nachtimwald.com>'
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

class NookUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = "http://uk.nook.com"

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = u'http://uk.nook.com/s/%s?s%%5Bdref%%5D=1&s%%5Bkeyword%%5D=%s' % (query.replace(' ', '-'), urllib.quote(query))

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            raw = f.read()
            doc = html.fromstring(raw)
            for data in doc.xpath('//ul[contains(@class, "product_list")]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//span[contains(@class, "image")]/a/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//span[contains(@class, "image")]//img/@data-src'))

                title = ''.join(data.xpath('.//div[contains(@class, "title")]//text()')).strip()
                if not title:
                    continue

                author = ', '.join(data.xpath('.//div[contains(@class, "contributor")]//a/text()')).strip()
                price = ''.join(data.xpath('.//div[contains(@class, "action")]//a//text()')).strip()
                price = re.sub(r'[^\d.,£]', '', price);

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = 'http://uk.nook.com/' + id.strip()
                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Nook'

                yield s
