# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 8  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2016, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
from base64 import b64encode
from contextlib import closing
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def as_base64(data):
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    ans = b64encode(data)
    if isinstance(ans, bytes):
        ans = ans.decode('ascii')
    return ans


class EbookpointStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/32/58/'

        url = 'http://ebookpoint.pl/'

        aff_url = aff_root + as_base64(url)

        detail_url = None
        if detail_item:
            detail_url = aff_root + as_base64(detail_item)

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url if detail_url else aff_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=25, timeout=60):
        url = 'http://ebookpoint.pl/search?qa=&szukaj=' + quote_plus(
            query.decode('utf-8').encode('iso-8859-2')) + '&serwisyall=0&wprzyg=0&wsprzed=1&wyczerp=0&formaty=em-p'

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[@class="list"]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('./a/@href'))
                if not id:
                    continue

                formats = ', '.join(data.xpath('.//ul[@class="book-type book-type-points"]//span[@class="popup"]/span/text()'))
                cover_url = ''.join(data.xpath('.//p[@class="cover"]/img/@data-src'))
                title = ''.join(data.xpath('.//div[@class="book-info"]/h3/a/text()'))
                author = ''.join(data.xpath('.//p[@class="author"]//text()'))
                price = ''.join(data.xpath('.//p[@class="price price-incart"]/a/ins/text()|.//p[@class="price price-add"]/a/text()'))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = re.sub(r'\.',',',price)
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = formats.upper()

                yield s
