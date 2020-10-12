# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 3  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
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


class EbookscomStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        m_url = 'http://www.dpbolvw.net/'
        h_click = 'click-4913808-10364500'
        d_click = 'click-4913808-10281551'

        url = m_url + h_click
        detail_url = None
        if detail_item:
            detail_url = m_url + d_click + detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.ebooks.com/SearchApp/SearchResults.net?term=' + quote_plus(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="results"]//li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[1]/@href'))
                mo = re.search(r'\d+', id)
                if not mo:
                    continue
                id = mo.group()

                cover_url = ''.join(data.xpath('.//div[contains(@class, "img")]//img/@src'))

                title = ''.join(data.xpath(
                    'descendant::span[@class="book-title"]/a/text()')).strip()
                author = ', '.join(data.xpath(
                    'descendant::span[@class="author"]/a/text()')).strip()
                if not title or not author:
                    continue

                price = ''.join(data.xpath(
                    './/span[starts-with(text(), "US$") or'
                    ' starts-with(text(), "€") or starts-with(text(), "CA$") or'
                    ' starts-with(text(), "AU$") or starts-with(text(), "£")]/text()')).strip()

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '?url=http://www.ebooks.com/cj.asp?IID=' + id.strip() + '&cjsku=' + id.strip()

                yield s

    def get_details(self, search_result, timeout):
        url = 'http://www.ebooks.com/ebooks/book_display.asp?IID='

        mo = re.search(r'\?IID=(?P<id>\d+)', search_result.detail_item)
        if mo:
            id = mo.group('id')
        if not id:
            return

        br = browser()
        with closing(br.open(url + id, timeout=timeout)) as nf:
            pdoc = html.fromstring(nf.read())

            search_result.drm = SearchResult.DRM_UNLOCKED
            permissions = ' '.join(pdoc.xpath('//div[@class="permissions-items"]//text()'))
            if 'off' in permissions:
                search_result.drm = SearchResult.DRM_LOCKED

            fdata = pdoc.xpath('//div[contains(@class, "more-links") and contains(@class, "more-links-info")]/div//span/text()')
            if len(fdata) > 1:
                search_result.formats = ', '.join(fdata[1:])

        return True
