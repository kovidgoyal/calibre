# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class WHSmithUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.whsmith.co.uk/'
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
        url = ('http://www.whsmith.co.uk/CatalogAndSearch/SearchWithinCategory.aspx'
               '?cat=\eb_eBooks&gq=' + urllib2.quote(query))

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="product-search"]/'
                                    'div[contains(@id, "whsSearchResultItem")]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[contains(@id, "labelProductTitle")]/@href'))
                if not id:
                    continue
                cover_url = ''.join(data.xpath('.//a[contains(@id, "hlinkProductImage")]/img/@src'))
                title = ''.join(data.xpath('.//a[contains(@id, "labelProductTitle")]/text()'))
                author = ', '.join(data.xpath('.//div[@class="author"]/h3/span/text()'))
                price = ''.join(data.xpath('.//span[contains(@id, "labelProductPrice")]/text()'))
                pdf = data.xpath('boolean(.//span[contains(@id, "labelFormatText") and '
                                                 'contains(., "PDF")])')
                epub = data.xpath('boolean(.//span[contains(@id, "labelFormatText") and '
                                                  'contains(., "ePub")])')
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.drm = SearchResult.DRM_LOCKED
                s.detail_item = id
                formats = []
                if epub:
                    formats.append('ePub')
                if pdf:
                    formats.append('PDF')
                s.formats = ', '.join(formats)

                yield s
