# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 7  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2015, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
import urllib
from base64 import b64encode
from contextlib import closing

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class EmpikStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/78/58/'

        url = 'http://www.empik.com/ebooki'

        aff_url = aff_root + str(b64encode(url))

        detail_url = None
        if detail_item:
            detail_url = aff_root + str(b64encode(detail_item))

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url if detail_url else aff_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.empik.com/szukaj/produkt?c=ebooki-ebooki&q=' + \
            urllib.quote(query) + '&qtype=basicForm&start=1&catalogType=pl&searchCategory=3501&format=epub&format=mobi&format=pdf&resultsPP=' + str(max_results)

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

                cover_url = ''.join(data.xpath('.//div[@class="productBox-450Pic"]/a/img/@data-original'))
                title = ''.join(data.xpath('.//a[@class="productBox-450Title"]/text()'))
                title = re.sub(r' \(ebook\)', '', title)
                author = ', '.join(data.xpath('.//div[@class="productBox-450Author"]/a/text()'))
                price = ''.join(data.xpath('.//span[@class="currentPrice"]/text()'))
                formats = ''.join(data.xpath('.//div[@class="productBox-450Type"]/text()'))
                formats = re.sub(r'Ebook *,? *','', formats)
                formats = re.sub(r'\(.*\)','', formats)
                with closing(br.open('http://empik.com' + id.strip(), timeout=timeout/4)) as nf:
                    idata = html.fromstring(nf.read())
                    crawled = idata.xpath('.//td[(@class="connectedInfo") or (@class="connectedInfo connectedBordered")]/a/text()')
                    formats_more = ','.join([re.sub('ebook, ','', x) for x in crawled if 'ebook' in x])
                    if formats_more:
                        formats += ', ' + formats_more
                drm = data.xpath('boolean(.//div[@class="productBox-450Type" and contains(text(), "ADE")])')

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = 'http://empik.com' + id.strip()
                s.formats = formats.upper().strip()
                s.drm = SearchResult.DRM_LOCKED if drm else SearchResult.DRM_UNLOCKED

                yield s

