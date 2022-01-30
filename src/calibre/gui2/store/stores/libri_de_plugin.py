# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 8  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from lxml import html

from qt.core import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


class LibreDEStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'https://clk.tradedoubler.com/click?p=324630&a=3252627'
        url_details = ('https://clk.tradedoubler.com/click?p=324630&a=3252627'
                       '&url=https%3A%2F%2Fwww.ebook.de%2Fshop%2Faction%2FproductDetails%3FartiId%3D{0}')

        if external or self.config.get('open_external', False):
            if detail_item:
                url = url_details.format(detail_item)
            open_url(QUrl(url))
        else:
            detail_url = None
            if detail_item:
                detail_url = url_details.format(detail_item)
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        url = ('http://www.ebook.de/de/pathSearch?nav=52122&searchString=' + quote(query))
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@class="articlecontainer"]'):
                if counter <= 0:
                    break
                id_ = ''.join(data.xpath('.//div[@class="trackArtiId"]/text()'))
                if not id_:
                    continue
                details = data.xpath('./div[contains(@class, "articleinfobox")]')
                if not details:
                    continue
                details = details[0]
                title = ''.join(details.xpath('./div[@class="title"]/a/text()')).strip()
                author = ''.join(details.xpath('.//div[@class="author"]/text()')).strip()
                if author.startswith('von'):
                    author = author[4:]

                pdf = details.xpath(
                        'boolean(.//span[@class="bindername" and contains(text(), "pdf")]/text())')
                epub = details.xpath(
                        'boolean(.//span[@class="bindername" and contains(text(), "epub")]/text())')
                mobi = details.xpath(
                        'boolean(.//span[@class="bindername" and contains(text(), "mobipocket")]/text())')

                cover_url = ''.join(data.xpath('.//div[@class="coverimg"]/a/img/@src'))
                price = ''.join(data.xpath('.//div[@class="preis"]/text()')).replace('*', '').strip()

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.drm = SearchResult.DRM_UNKNOWN
                s.detail_item = id_
                formats = []
                if epub:
                    formats.append('ePub')
                if pdf:
                    formats.append('PDF')
                if mobi:
                    formats.append('MOBI')
                s.formats = ', '.join(formats)

                yield s
