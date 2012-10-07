# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

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

class WoblinkStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):

        url = 'http://woblink.com/publication'
        detail_url = None

        if detail_item:
            detail_url = 'http://woblink.com' + detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://woblink.com/katalog-e-book?query=' + urllib.quote_plus(query.encode('utf-8'))
        if max_results > 10:
            if max_results > 20:
                url += '&limit=30'
            else:
                url += '&limit=20'

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="book-item backgroundmix"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//td[@class="w10 va-t mYHaveItYes"]/a[1]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//td[@class="w10 va-t mYHaveItYes"]/a[1]/img/@src'))
                title = ''.join(data.xpath('.//h2[@class="title"]/a[1]/text()'))
                author = ', '.join(data.xpath('.//td[@class="va-t"]/h3/a/text()'))
                price = ''.join(data.xpath('.//div[@class="prices"]/span[1]/strong/span/text()'))
                price = re.sub('\.', ',', price)
                formats = [ form[8:-4].split('.')[0] for form in data.xpath('.//p[3]/img/@src')]

                s = SearchResult()
                s.cover_url = 'http://woblink.com' + cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price + ' zł'
                s.detail_item = id.strip()

                if 'epub_drm' in formats:
                    s.drm = SearchResult.DRM_LOCKED
                    s.formats = 'EPUB'

                    counter -= 1
                    yield s
                elif 'pdf' in formats:
                    s.drm = SearchResult.DRM_LOCKED
                    s.formats = 'PDF'

                    counter -= 1
                    yield s
                else:
                    s.drm = SearchResult.DRM_UNLOCKED
                    if 'MOBI_nieb' in formats:
                        formats.remove('MOBI_nieb')
                        formats.append('MOBI')
                    s.formats = ', '.join(formats).upper()

                    counter -= 1
                    yield s
