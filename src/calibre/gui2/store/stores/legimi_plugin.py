# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 9  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2017, Tomasz Długosz <tomek3d@gmail.com>'
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


class LegimiStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/9/58/'

        url = 'https://www.legimi.pl/ebooki/'

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
        url = 'https://www.legimi.pl/ebooki/?szukaj=' + urllib.quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="listBooks"]/div'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[1]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//span[@class="listImage imageDarkLoader"]/img/@src'))
                title = ''.join(data.xpath('.//span[@class="bookListTitle ellipsis"]/text()'))
                author = ''.join(data.xpath('.//span[@class="bookListAuthor ellipsis"]/text()'))
                price = ''.join(data.xpath('.//div[@class="bookListPrice"]/span/text()'))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.detail_item = 'https://www.legimi.pl/' + id.strip()

                yield s

    def get_details(self, search_result, timeout):
        drm_pattern = re.compile("zabezpieczona DRM")
        formats = []
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            formatlist = idata.xpath('.//div[@class="bookFormatsBox clearfix"]//span[@class="bookFormat"]/text()')
            for x in formatlist:
                if x.strip() not in formats:
                    formats.append(x.strip())
            drm = drm_pattern.search(''.join(idata.xpath('.//div[@id="fullBookFormats"]/p/text()')))
            search_result.formats = ', '.join(formats)
            search_result.drm = SearchResult.DRM_LOCKED if drm else SearchResult.DRM_UNLOCKED
        return True
