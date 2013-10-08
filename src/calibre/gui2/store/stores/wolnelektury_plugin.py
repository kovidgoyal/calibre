# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2012-2013, Tomasz Długosz <tomek3d@gmail.com>'
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

class WolneLekturyStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):

        url = 'http://wolnelektury.pl'
        detail_url = None

        if detail_item:
            detail_url = detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://wolnelektury.pl/szukaj?q=' + urllib.quote_plus(query.encode('utf-8'))

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//li[@class="Book-item"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="title"]/a/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//a[1]/img/@src'))
                title = ''.join(data.xpath('.//div[@class="title"]/a[1]/text()'))
                author = ', '.join(data.xpath('.//div[@class="mono author"]/a/text()'))
                price = '0,00 zł'

                counter -= 1

                s = SearchResult()
                for link in data.xpath('.//div[@class="book-box-formats mono"]/span/a'):
                    ext = ''.join(link.xpath('./text()'))
                    href = 'http://wolnelektury.pl' + link.get('href')
                    s.downloads[ext] = href
                s.cover_url = 'http://wolnelektury.pl' + cover_url.strip()
                s.title = title.strip()
                s.author = author
                s.price = price
                s.detail_item = 'http://wolnelektury.pl' + id
                s.formats = ', '.join(s.downloads.keys())
                s.drm = SearchResult.DRM_UNLOCKED

                yield s
