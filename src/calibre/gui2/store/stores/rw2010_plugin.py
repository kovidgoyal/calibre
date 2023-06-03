# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 1  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from calibre import url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import browser_get_url, StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class RW2010Store(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.rw2010.pl/'

        if external or self.config.get('open_external', False):
            open_url(url_slash_cleaner(detail_item if detail_item else url))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.rw2010.pl/go.live.php/?launch_macro=catalogue-search-rd'
        values = {
            'fkeyword': query,
            'file_type': ''
        }
        doc = browser_get_url(url, timeout, data=urlencode(values))

        counter = max_results
        for data in doc.xpath('//div[@class="ProductDetail"]'):
            if counter <= 0:
                break

            id = ''.join(data.xpath('.//div[@class="img"]/a/@href'))
            if not id:
                continue

            iadata = browser_get_url(id.strip(), timeout/4)
            cover_url = ''.join(idata.xpath('//div[@class="boxa"]//div[@class="img"]/img/@src'))
            author = ''.join(idata.xpath('//div[@class="boxb"]//h3[text()="Autor: "]/span/text()'))
            title = ''.join(idata.xpath('//div[@class="boxb"]/h2[1]/text()'))
            title = re.sub(r'\(#.+\)', '', title)
            formats = ''.join(idata.xpath('//div[@class="boxb"]//h3[text()="Format pliku: "]/span/text()'))
            price = ''.join(idata.xpath('//div[@class="price-box"]/span/text()')) + ',00 zł'

            counter -= 1

            s = SearchResult()
            s.cover_url = 'http://www.rw2010.pl/' + cover_url
            s.title = title.strip()
            s.author = author.strip()
            s.price = price
            s.detail_item = re.sub(r'%3D', '=', id)
            s.drm = SearchResult.DRM_UNLOCKED
            s.formats = formats[0:-2].upper()

            yield s
