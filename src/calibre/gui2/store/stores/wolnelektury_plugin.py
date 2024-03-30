# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 4  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2012-2023, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing

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


class WolneLekturyStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):

        url = 'https://wolnelektury.pl'
        detail_url = None

        if detail_item:
            detail_url = detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        url = 'https://wolnelektury.pl/szukaj?q=' + quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="l-books__grid"]/article'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//figure/a/@href'))
                if not id:
                    continue

                title = ''.join(data.xpath('.//h2/a/text()'))
                author = ', '.join(data.xpath('.//h3/a/text()'))
                cover_url = ''.join(data.xpath('.//figure/a/img/@src'))
                price = '0,00 zł'

                counter -= 1

                s = SearchResult()
                s.cover_url = 'https://wolnelektury.pl' + cover_url.strip()
                s.title = title.strip()
                s.author = author
                s.price = price
                s.detail_item = 'https://wolnelektury.pl' + id
                s.formats = ', '.join(s.downloads.keys())
                s.drm = SearchResult.DRM_UNLOCKED

                yield s
