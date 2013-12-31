# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 4  # Needed for dynamic plugin loading

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
        url = 'http://www.nook.com/gb/store'
        detail_url = ''

        if external or self.config.get('open_external', False):
            if detail_item:
                url = detail_url + detail_item

            open_url(QUrl(url_slash_cleaner(url)))
        else:
            if detail_item:
                detail_url = detail_url + detail_item
            else:
                detail_url = None
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

                id_ = ''.join(data.xpath('.//span[contains(@class, "image")]/a/@href'))
                if not id_:
                    continue
                if id_.startswith('/gb'):
                    id_ = id_[3:]
                id_ = 'http://uk.nook.com' + id_.strip()

                cover_url = ''.join(data.xpath('.//span[contains(@class, "image")]//img/@data-src'))

                title = ''.join(data.xpath('.//div[contains(@class, "title")]//text()')).strip()
                if not title:
                    continue

                author = ', '.join(data.xpath('.//div[contains(@class, "contributor")]//a/text()')).strip()
                price = ''.join(data.xpath('.//div[contains(@class, "action")]//a//text()')).strip()
                price = re.sub(r'[^\d.,£]', '', price)

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id_
                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Nook'

                yield s
