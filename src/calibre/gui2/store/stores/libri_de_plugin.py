# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class LibreDEStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://ad.zanox.com/ppc/?18817073C15644254T'
        url_details = ('http://ad.zanox.com/ppc/?18817073C15644254T&ULP=[['
                       'http://www.libri.de/shop/action/productDetails?artiId={0}]]')

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
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = ('http://www.libri.de/shop/action/quickSearch?facetNodeId=6'
               '&mainsearchSubmit=Los!&searchString=' + urllib2.quote(query))
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[contains(@class, "item")]'):
                if counter <= 0:
                    break

                details = data.xpath('./div[@class="beschreibungContainer"]')
                if not details:
                    continue
                details = details[0]
                id = ''.join(details.xpath('./div[@class="text"]/a/@name')).strip()
                if not id:
                    continue
                cover_url = ''.join(details.xpath('.//div[@class="coverImg"]/a/img/@src'))
                title = ''.join(details.xpath('./div[@class="text"]/span[@class="titel"]/a/text()')).strip()
                author = ''.join(details.xpath('./div[@class="text"]/span[@class="author"]/text()')).strip()
                pdf = details.xpath(
                        'boolean(.//span[@class="format" and contains(text(), "pdf")]/text())')
                epub = details.xpath(
                        'boolean(.//span[@class="format" and contains(text(), "epub")]/text())')
                mobi = details.xpath(
                        'boolean(.//span[@class="format" and contains(text(), "mobipocket")]/text())')
                price = ''.join(data.xpath('.//span[@class="preis"]/text()')).replace('*', '').strip()

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price
                s.drm = SearchResult.DRM_UNKNOWN
                s.detail_item = id
                formats = []
                if epub:
                    formats.append('ePub')
                if pdf:
                    formats.append('PDF')
                if mobi:
                    formats.append('MOBI')
                s.formats = ', '.join(formats)

                yield s
