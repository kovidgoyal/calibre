# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

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


class EBookNLStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.ebook.nl/'
        url_details = ('http://www.ebook.nl/store/{0}')

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
        url = ('http://www.ebook.nl/store/advanced_search_result.php?keywords=' + quote(query))
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="books"]/div[@itemtype="http://schema.org/Book"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('./meta[@itemprop="url"]/@content')).strip()
                if not id:
                    continue
                cover_url = 'http://www.ebook.nl/store/' + ''.join(data.xpath('.//img[@itemprop="image"]/@src'))
                title = ''.join(data.xpath('./span[@itemprop="name"]/a/text()')).strip()
                author = ''.join(data.xpath('./span[@itemprop="author"]/a/text()')).strip()
                if author == '&nbsp':
                    author = ''
                price = ''.join(data.xpath('.//span[@itemprop="price"]//text()'))
                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.drm = SearchResult.DRM_UNKNOWN
                s.detail_item = id

                yield s

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            formats = []
            if idata.xpath('.//div[@id="book_detail_body"]/ul/li[strong[contains(., "Type")]]/span[contains(., "ePub")]'):
                if idata.xpath('.//div[@id="book_detail_body"]/ul/li[strong[contains(., "Type")]]/span[contains(., "EPUB3")]'):
                    formats.append('EPUB3')
                else:
                    formats.append('EPUB')
            if idata.xpath('.//div[@id="book_detail_body"]/ul/li[strong[contains(., "Type")]]/span[contains(., "Pdf")]'):
                formats.append('PDF')
            search_result.formats = ', '.join(formats)

            if idata.xpath('.//div[@id="book_detail_body"]/ul/li[strong[contains(., "Type")]]'
                           '//span[@class="ePubAdobeDRM" or @class="ePubwatermerk" or'
                           ' @class="Pdfwatermark" or @class="PdfAdobeDRM"]'):
                search_result.drm = SearchResult.DRM_LOCKED
            if idata.xpath('.//div[@id="book_detail_body"]/ul/li[strong[contains(., "Type")]]//span[@class="ePubzonderDRM"]'):
                search_result.drm = SearchResult.DRM_UNLOCKED
        return True
