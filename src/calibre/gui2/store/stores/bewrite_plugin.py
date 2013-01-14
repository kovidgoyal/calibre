# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class BeWriteStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.bewrite.net/mm5/merchant.mvc?Screen=SFNT'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.bewrite.net/mm5/merchant.mvc?Search_Code=B&Screen=SRCH&Search=' + urllib2.quote(query)

        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//div[@id="content"]//table/tr[position() > 1]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a/@href'))
                if not id:
                    continue

                heading = ''.join(data.xpath('./td[2]//text()'))
                title, q, author = heading.partition('by ')
                cover_url = ''
                price = ''

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED

                yield s

    def get_details(self, search_result, timeout):
        br = browser()

        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())

            price = ''.join(idata.xpath('//div[@id="content"]//td[contains(text(), "ePub")]/text()'))
            if not price:
                price = ''.join(idata.xpath('//div[@id="content"]//td[contains(text(), "MOBI")]/text()'))
            if not price:
                price = ''.join(idata.xpath('//div[@id="content"]//td[contains(text(), "PDF")]/text()'))
            price = '$' + price.split('$')[-1]
            search_result.price = price.strip()

            cover_img = idata.xpath('//div[@id="content"]//img/@src')
            if cover_img:
                for i in cover_img:
                    if '00001' in i:
                        cover_url = 'http://www.bewrite.net/mm5/' + i
                        search_result.cover_url = cover_url.strip()
                        break

            formats = set([])
            if idata.xpath('boolean(//div[@id="content"]//td[contains(text(), "ePub")])'):
                formats.add('EPUB')
            if idata.xpath('boolean(//div[@id="content"]//td[contains(text(), "PDF")])'):
                formats.add('PDF')
            if idata.xpath('boolean(//div[@id="content"]//td[contains(text(), "MOBI")])'):
                formats.add('MOBI')
            search_result.formats = ', '.join(list(formats))

        return True
