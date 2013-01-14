# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

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

class EBookShoppeUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url_details = 'http://www.awin1.com/cread.php?awinmid=1414&awinaffid=120917&clickref=&p={0}'
        url = 'http://www.awin1.com/awclick.php?mid=2666&id=120917'

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
        url = 'http://www.ebookshoppe.com/search.php?search_query=' + urllib2.quote(query)
        br = browser()
        br.addheaders = [("Referer", "http://www.ebookshoppe.com/")]

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[@class="ProductList"]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('./div[@class="ProductDetails"]/'
                                        'strong/a/@href')).strip()
                if not id:
                    continue
                cover_url = ''.join(data.xpath('./div[@class="ProductImage"]/a/img/@src'))
                title = ''.join(data.xpath('./div[@class="ProductDetails"]/strong/a/text()'))
                price = ''.join(data.xpath('./div[@class="ProductPriceRating"]/em/text()'))
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.price = price
                s.drm = SearchResult.DRM_UNLOCKED
                s.detail_item = id

                self.get_author_and_formats(s, timeout)
                if not s.author:
                    continue

                yield s

    def get_author_and_formats(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            author = ''.join(idata.xpath('//div[@id="ProductOtherDetails"]/dl/dd[1]/text()'))
            if author:
                search_result.author = author
            formats = idata.xpath('//dl[@class="ProductAddToCart"]/dd/'
                                  'ul[@class="ProductOptionList"]/li/label/text()')
            if formats:
                search_result.formats = ', '.join(formats)
            search_result.drm = SearchResult.DRM_UNKNOWN
        return True
