# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 6  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2012-2023, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

try:
    from calibre.utils.xml_parse import safe_html_fromstring
except ImportError:
    from lxml.html import fromstring as safe_html_fromstring

import json


class WolneLekturyStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):

        url = 'https://wolnelektury.pl'
        detail_url = None

        if detail_item:
            detail_url = detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url or url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        url = 'https://wolnelektury.pl/szukaj?q=' + quote_plus(query)

        br = browser()
        price = '0,00 zł'

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = safe_html_fromstring(f.read())
            for data in doc.xpath('//div[@class="l-books__grid"]/article'):
                if counter <= 0:
                    break

                try:
                    id = ''.join(data.xpath('.//figure/a/@href')).split('/')[3]
                except IndexError:
                    continue

                title = ''.join(data.xpath('.//h2/a/text()'))
                author = ', '.join(data.xpath('.//h3/a/text()'))
                cover_url = ''.join(data.xpath('.//figure/a/img/@src'))

                s = SearchResult()
                s.cover_url = 'https://wolnelektury.pl' + cover_url.strip()
                s.title = title.strip()
                s.author = author
                s.price = price
                s.detail_item = 'https://wolnelektury.pl/katalog/lektura/' + id

                s.downloads.update(self._search_formats(id, timeout=timeout))

                s.formats = ', '.join(s.downloads.keys())
                s.drm = SearchResult.DRM_UNLOCKED

                counter -= 1

                yield s

    def _search_formats(self, id: str, timeout: int = 60) -> dict[str, str]:
        # formats used by the site and calibre (as of 01.05.2026)
        ALLOWED_FORMATS: tuple[str,...] = ('pdf', 'epub', 'mobi', 'txt', 'html', 'fb2')
        result: dict[str, str] = {}
        br=browser()
        url = f'https://wolnelektury.pl/api/books/{id}/?format=json'
        with closing(br.open(url, timeout=timeout)) as page:
            parsed_data = json.load(page)
            for ext in ALLOWED_FORMATS:
                if (book_url := parsed_data.get(ext)) is None:
                    continue
                if book_url != '':
                    result[ext] = book_url

        return result
