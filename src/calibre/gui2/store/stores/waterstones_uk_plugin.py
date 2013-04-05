# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 2 # Needed for dynamic plugin loading

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

class WaterstonesUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.awin1.com/awclick.php?mid=3787&id=120917'
        url_details = 'http://www.awin1.com/cread.php?awinmid=3787&awinaffid=120917&clickref=&p={0}'

        if external or self.config.get('open_external', False):
            if detail_item:
                url = url_details.format(detail_item)
            open_url(QUrl(url))
        else:
            detail_url = None
            if detail_item:
                detail_url = url_details.format(detail_item)
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.waterstones.com/waterstonesweb/simpleSearch.do?simpleSearchString=ebook+' + urllib2.quote(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[contains(@class, "results-pane")]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('./div/div/h2/a/@href')).strip()
                if not id:
                    continue
                cover_url = ''.join(data.xpath('.//div[@class="image"]/a/img/@src'))
                if not cover_url.startswith("http"):
                    cover_url = 'http://www.waterstones.com' + cover_url
                title = ''.join(data.xpath('./div/div/h2/a/text()'))
                author = ', '.join(data.xpath('.//p[@class="byAuthor"]/a/text()'))
                price = ''.join(data.xpath('.//p[@class="price"]/span[@class="priceRed2"]/text()'))
                drm = data.xpath('boolean(.//td[@headers="productFormat" and contains(., "DRM")])')
                pdf = data.xpath('boolean(.//td[@headers="productFormat" and contains(., "PDF")])')
                epub = data.xpath('boolean(.//td[@headers="productFormat" and contains(., "EPUB")])')

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                if drm:
                    s.drm = SearchResult.DRM_LOCKED
                else:
                    s.drm = SearchResult.DRM_UNKNOWN
                s.detail_item = id
                formats = []
                if epub:
                    formats.append('ePub')
                if pdf:
                    formats.append('PDF')
                s.formats = ', '.join(formats)

                yield s
