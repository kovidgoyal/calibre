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

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class MillsBoonUKStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.awin1.com/awclick.php?mid=1150&id=120917'
        detail_url = 'http://www.awin1.com/cread.php?awinmid=1150&awinaffid=120917&clickref=&p='

        if external or self.config.get('open_external', False):
            if detail_item:
                url = detail_url + detail_item
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            detail_url = None
            if detail_item:
                detail_url = url + detail_item
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        base_url = 'http://millsandboon.co.uk'
        url = base_url + '/pages/searchres.htm?search=true&booktypesearch=ebook&first=yes&inputsearch=' + urllib2.quote(query)
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="catProdDiv"]'):
                if counter <= 0:
                    break
                id_ = ''.join(data.xpath('.//div[@class="catProdImage"]/div/a/@href')).strip()
                id_ = base_url + id_[2:]
                if not id_:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="catProdImage"]/div/a/img/@src'))
                cover_url = base_url + cover_url[2:]
                title =  ''.join(data.xpath('.//div[@class="catProdImage"]/div/a/img/@alt')).strip()
                title = title[23:]
                author = ''.join(data.xpath('.//div[@class="catProdDetails"]/div[@class="catProdDetails-top"]/p[1]/a/text()'))
                price = ''.join(data.xpath('.//span[@class="priceBold"]/text()'))
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
