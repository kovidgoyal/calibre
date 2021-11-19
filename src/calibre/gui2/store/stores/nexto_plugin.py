# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 6  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2020, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
from contextlib import closing
from base64 import standard_b64encode
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import html

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def as_base64(data):
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    ans = standard_b64encode(data)
    if isinstance(ans, bytes):
        ans = ans.decode('ascii')
    return ans


class NextoStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/35/58/'

        url = 'http://www.nexto.pl/'

        aff_url = aff_root + as_base64(url)

        detail_url = None
        if detail_item:
            book_id = re.search(r'p[0-9]*\.xml\Z', detail_item)
            book_id = book_id.group(0).replace('.xml','').replace('p','')
            if book_id:
                detail_url = aff_root + as_base64('http://www.nexto.pl/rf/pr?p=' + book_id)

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url if detail_url else aff_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.nexto.pl/szukaj.xml?search-clause=' + quote_plus(query) + '&scid=1015'

        br = browser()
        offset=0

        counter = max_results

        while counter:
            with closing(br.open(url + '&_offset={}'.format(offset), timeout=timeout)) as f:
                doc = html.fromstring(f.read())
                for data in doc.xpath('//ul[@class="productslist"]/li'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//div[@class="col-2"]/a/@href'))
                    if not id:
                        continue

                    price = ''.join(data.xpath('.//strong[@class="nprice"]/text()'))

                    cover_url = ''.join(data.xpath('.//img[@class="cover"]/@src'))
                    cover_url = re.sub(r'%2F', '/', cover_url)
                    cover_url = re.sub(r'widthMax=120&heightMax=200', 'widthMax=64&heightMax=64', cover_url)
                    title = ''.join(data.xpath('.//a[@class="title"]/text()'))
                    title = re.sub(r' – ebook', '', title)
                    author = ', '.join(data.xpath('.//div[@class="col-7"]//h4//a/text()'))
                    formats = ', '.join(data.xpath('.//ul[@class="formats"]/li//b/text()'))
                    DrmFree = data.xpath('.//ul[@class="formats"]/li//b[contains(@title, "znak")]')

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = cover_url if cover_url[:4] == 'http' else 'http://www.nexto.pl' + cover_url
                    s.title = title.strip()
                    s.author = author.strip()
                    s.price = price.strip()
                    s.detail_item = id.strip()
                    s.drm = SearchResult.DRM_UNLOCKED if DrmFree else SearchResult.DRM_LOCKED
                    s.formats = formats.upper().strip()

                    yield s
                if not doc.xpath('//div[@class="listnavigator"]//a[@class="next"]'):
                    break
            offset+=10
