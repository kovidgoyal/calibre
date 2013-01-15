# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2012, Tomasz Długosz <tomek3d@gmail.com>'
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

class EmpikStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        plain_url = 'http://www.empik.com/ebooki'
        url = 'https://ssl.afiliant.com/affskrypt,,2f9de2,,23c7f,,,?u=(' + plain_url + ')'
        detail_url = None

        if detail_item:
            detail_url = 'https://ssl.afiliant.com/affskrypt,,2f9de2,,23c7f,,,?u=(' + detail_item + ')'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.empik.com/szukaj/produkt?c=ebooki-ebooki&q=' + urllib.quote(query) + '&qtype=basicForm&start=1&catalogType=pl&searchCategory=3501&resultsPP=' + str(max_results)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="productsSet"]/div'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[@class="productBox-450Title"]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//div[@class="productBox-450Pic"]/a/img/@src'))
                title = ''.join(data.xpath('.//a[@class="productBox-450Title"]/text()'))
                title = re.sub(r' \(ebook\)', '', title)
                author = ''.join(data.xpath('.//div[@class="productBox-450Author"]/a/text()'))
                price = ''.join(data.xpath('.//div[@class="actPrice"]/text()'))
                formats = ''.join(data.xpath('.//div[@class="productBox-450Type"]/text()'))
                formats = re.sub(r'Ebook *,? *','', formats)
                formats = re.sub(r'\(.*\)','', formats)
                drm = data.xpath('boolean(.//div[@class="productBox-450Type" and contains(text(), "ADE")])')

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip() + ' ' + formats
                s.author = author.strip()
                s.price = price
                s.detail_item = 'http://empik.com' + id.strip()
                s.formats = formats.upper().strip()
                s.drm = SearchResult.DRM_LOCKED if drm else SearchResult.DRM_UNLOCKED

                yield s

